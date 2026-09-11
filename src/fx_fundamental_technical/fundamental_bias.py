"""Walk-forward structural-policy model and immutable F1/F2 bias snapshots."""

from __future__ import annotations

import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.canonical_data import (
    build_macro_states_at_snapshots,
)
from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)
from fx_fundamental_technical.ridge import predict, ridge_fit

FEATURES = (
    "inflation_gap",
    "inflation_momentum_3m",
    "labour_tightness",
    "labour_momentum_3m",
    "policy_rate",
    "policy_change_3m_bp",
)
MACRO_FEATURES = FEATURES[:4]
BIAS_BUILDER_VERSION = "structural-policy-bias-v0.1"


class FundamentalModelError(ValueError):
    """Raised when the walk-forward bias contract cannot be satisfied."""


@dataclass(frozen=True)
class FittedPolicyModel:
    currencies: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    penalty: float
    training_rows: int


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FundamentalModelError(f"expected JSON object: {path}")
    return cast(dict[str, object], value)


def feature_frame(states: pd.DataFrame) -> pd.DataFrame:
    """Orient every macro feature so positive means more hawkish pressure."""

    result = states.copy()
    targets = {
        "AUD": 2.5,
        "CAD": 2.0,
        "EUR": 2.0,
        "GBP": 2.0,
        "JPY": 2.0,
        "USD": 2.0,
    }
    result["inflation_gap"] = result["inflation_value"] - result["currency"].map(
        targets
    )
    result["inflation_momentum_3m"] = (
        result["inflation_value"] - result["inflation_lag3_value"]
    )
    result["labour_tightness"] = -result["labour_value"]
    result["labour_momentum_3m"] = result["labour_lag3_value"] - result["labour_value"]
    result["policy_rate"] = result["policy_value"]
    result["policy_change_3m_bp"] = (
        result["policy_value"] - result["policy_lag3_value"]
    ) * 100.0
    result["feature_complete"] = result["mandatory_inputs_available"] & result[
        list(FEATURES)
    ].notna().all(axis=1)
    return result


def build_monthly_policy_panel(states: pd.DataFrame) -> pd.DataFrame:
    """Create one currency observation per month and a six-month policy label."""

    featured = feature_frame(states)
    featured["month"] = featured["asof_utc"].dt.tz_localize(None).dt.to_period("M")
    monthly = (
        featured.sort_values("asof_utc")
        .groupby(["currency", "month"], as_index=False)
        .tail(1)
        .sort_values(["currency", "asof_utc"])
        .reset_index(drop=True)
    )
    monthly["future_policy_rate"] = monthly.groupby("currency")["policy_rate"].shift(-6)
    monthly["label_available_at_utc"] = monthly.groupby("currency")["asof_utc"].shift(
        -6
    )
    monthly["policy_change_6m_bp"] = (
        monthly["future_policy_rate"] - monthly["policy_rate"]
    ) * 100.0
    monthly["panel_complete"] = (
        monthly["feature_complete"] & monthly["policy_change_6m_bp"].notna()
    )
    return monthly


def eligible_training_rows(panel: pd.DataFrame, origin: pd.Timestamp) -> pd.DataFrame:
    """Return rows whose entire six-month policy outcome was known at origin."""

    return panel[
        panel["panel_complete"] & (panel["label_available_at_utc"] <= origin)
    ].copy()


def _scaler(rows: pd.DataFrame) -> tuple[tuple[float, ...], tuple[float, ...]]:
    means = tuple(float(rows[name].mean()) for name in FEATURES)
    scales = tuple(
        value if (value := float(rows[name].std(ddof=1))) > 0 else 1.0
        for name in FEATURES
    )
    return means, scales


def _design_row(
    row: pd.Series,
    currencies: tuple[str, ...],
    means: tuple[float, ...],
    scales: tuple[float, ...],
) -> list[float]:
    return [float(row["currency"] == currency) for currency in currencies] + [
        (float(row[name]) - location) / scale
        for name, location, scale in zip(FEATURES, means, scales, strict=True)
    ]


def fit_policy_model(
    rows: pd.DataFrame, currencies: tuple[str, ...], penalty: float
) -> FittedPolicyModel:
    """Fit pooled currency fixed effects plus constrained structural slopes."""

    means, scales = _scaler(rows)
    design = [_design_row(row, currencies, means, scales) for _, row in rows.iterrows()]
    target = rows["policy_change_6m_bp"].astype(float).tolist()
    offset = len(currencies)
    coefficients = ridge_fit(
        design,
        target,
        penalty=penalty,
        unpenalized=frozenset(range(offset)),
        nonnegative=frozenset(range(offset, offset + len(MACRO_FEATURES))),
    )
    return FittedPolicyModel(
        currencies, means, scales, coefficients, penalty, len(rows)
    )


def predict_policy(model: FittedPolicyModel, row: pd.Series) -> float:
    return predict(
        _design_row(row, model.currencies, model.means, model.scales),
        model.coefficients,
    )


def _minimums_met(
    rows: pd.DataFrame,
    currencies: tuple[str, ...],
    per_currency: int,
    pooled: int,
) -> bool:
    counts = rows["currency"].value_counts()
    return len(rows) >= pooled and all(
        int(counts.get(item, 0)) >= per_currency for item in currencies
    )


def select_penalty(
    panel: pd.DataFrame,
    origin: pd.Timestamp,
    currencies: tuple[str, ...],
    penalties: tuple[float, ...],
    fold_count: int,
) -> tuple[float, list[dict[str, object]]]:
    """Select ridge strength using only policy labels available by outer origin."""

    outer_known = eligible_training_rows(panel, origin)
    validation_dates = sorted(outer_known["asof_utc"].unique())[-fold_count:]
    scores: list[tuple[float, float]] = []
    audit: list[dict[str, object]] = []
    for penalty in penalties:
        errors: list[float] = []
        for validation_date in validation_dates:
            validation_at = pd.Timestamp(validation_date)
            inner_train = eligible_training_rows(panel, validation_at)
            validation = panel[
                panel["panel_complete"] & (panel["asof_utc"] == validation_at)
            ]
            if validation.empty or not _minimums_met(inner_train, currencies, 18, 108):
                continue
            fitted = fit_policy_model(inner_train, currencies, penalty)
            fold_errors = [
                abs(float(row["policy_change_6m_bp"]) - predict_policy(fitted, row))
                for _, row in validation.iterrows()
            ]
            errors.extend(fold_errors)
            audit.append(
                {
                    "outer_origin_utc": origin.isoformat(),
                    "validation_origin_utc": validation_at.isoformat(),
                    "penalty": penalty,
                    "training_rows": len(inner_train),
                    "validation_rows": len(validation),
                    "mae_bp": mean(fold_errors),
                }
            )
        scores.append((mean(errors) if errors else math.inf, penalty))
    selected = min(scores)[1]
    if not math.isfinite(min(scores)[0]):
        raise FundamentalModelError(f"no valid inner policy folds at {origin}")
    return selected, audit


def _snapshot_schedule(
    states: pd.DataFrame, releases: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[pd.DatetimeIndex, set[pd.Timestamp]]:
    daily = pd.DatetimeIndex(
        states.loc[
            (states["asof_utc"] >= start) & (states["asof_utc"] < end), "asof_utc"
        ].unique()
    )
    event_times = (
        releases.loc[
            (releases["available_at_utc"] >= start)
            & (releases["available_at_utc"] < end),
            "available_at_utc",
        ]
        + pd.Timedelta(minutes=30)
    ).dt.ceil("15min")
    events = set(pd.Timestamp(item) for item in event_times)
    schedule = daily.union(pd.DatetimeIndex(sorted(events))).sort_values()
    return schedule, events


def _models_by_month(
    panel: pd.DataFrame,
    schedule: pd.DatetimeIndex,
    config: dict[str, object],
) -> tuple[dict[str, FittedPolicyModel], list[dict[str, object]]]:
    currencies = tuple(cast(list[str], config["currencies"]))
    penalties = tuple(
        float(item) for item in cast(list[float], config["ridge_penalties"])
    )
    fold_count = int(cast(int, config["inner_validation_origins"]))
    per_currency = int(cast(int, config["minimum_training_months_per_currency"]))
    pooled = int(cast(int, config["minimum_pooled_training_rows"]))
    origins = (
        pd.Series(schedule)
        .groupby(pd.Series(schedule).dt.tz_localize(None).dt.to_period("M"))
        .min()
    )
    models: dict[str, FittedPolicyModel] = {}
    audit: list[dict[str, object]] = []
    for month, origin_value in origins.items():
        origin = pd.Timestamp(origin_value)
        training = eligible_training_rows(panel, origin)
        if not _minimums_met(training, currencies, per_currency, pooled):
            continue
        penalty, folds = select_penalty(
            panel, origin, currencies, penalties, fold_count
        )
        model = fit_policy_model(training, currencies, penalty)
        models[str(month)] = model
        audit.extend(folds)
        audit.append(
            {
                "outer_origin_utc": origin.isoformat(),
                "record_kind": "OUTER_FIT",
                "month": str(month),
                "selected_penalty": penalty,
                "training_rows": len(training),
                "coefficients": list(model.coefficients),
                "means": list(model.means),
                "scales": list(model.scales),
            }
        )
    if not models:
        raise FundamentalModelError("no monthly policy model met training minimums")
    return models, audit


def _currency_predictions(
    states: pd.DataFrame,
    models: dict[str, FittedPolicyModel],
    event_times: set[pd.Timestamp],
) -> pd.DataFrame:
    featured = feature_frame(states)
    records: list[dict[str, object]] = []
    for _, row in featured.iterrows():
        asof = cast(pd.Timestamp, row["asof_utc"])
        month = str(asof.tz_localize(None).to_period("M"))
        model = models.get(month)
        prediction_value: float | None = None
        if model is not None and bool(row["feature_complete"]):
            prediction_value = predict_policy(model, row)
        records.append(
            {
                "asof_utc": asof,
                "currency": str(row["currency"]),
                "snapshot_type": "POST_EVENT" if asof in event_times else "DAILY_06",
                "prediction_6m_policy_change_bp": prediction_value,
                "feature_complete": bool(row["feature_complete"]),
                "model_available": model is not None,
                "model_penalty": None if model is None else model.penalty,
                "model_training_rows": None if model is None else model.training_rows,
            }
        )
    predictions = pd.DataFrame.from_records(records).sort_values(
        ["currency", "asof_utc"]
    )
    predictions["prediction_one_month_prior_bp"] = float("nan")
    for _, indices in predictions.groupby("currency").groups.items():
        ordered_indices = list(indices)
        times = predictions.loc[ordered_indices, "asof_utc"].tolist()
        values = predictions.loc[
            ordered_indices, "prediction_6m_policy_change_bp"
        ].tolist()
        for position, index in enumerate(ordered_indices):
            cutoff = cast(pd.Timestamp, times[position]) - pd.DateOffset(months=1)
            candidates = [
                offset
                for offset in range(position)
                if cast(pd.Timestamp, times[offset]) <= cutoff
                and pd.notna(values[offset])
            ]
            if candidates:
                predictions.loc[index, "prediction_one_month_prior_bp"] = values[
                    candidates[-1]
                ]
    predictions["prediction_revision_1m_bp"] = (
        predictions["prediction_6m_policy_change_bp"]
        - predictions["prediction_one_month_prior_bp"]
    )
    return predictions.sort_values(["asof_utc", "currency"]).reset_index(drop=True)


def _yield_states(
    yields: pd.DataFrame, schedule: pd.DatetimeIndex, lookback: int
) -> dict[tuple[pd.Timestamp, str], tuple[float | None, bool]]:
    result: dict[tuple[pd.Timestamp, str], tuple[float | None, bool]] = {}
    for currency, group in yields.groupby("currency"):
        ordered = group.sort_values("available_at_utc").reset_index(drop=True)
        times = ordered["available_at_utc"].tolist()
        values = ordered["yield_percent"].astype(float).tolist()
        pointer = 0
        for asof in schedule:
            while pointer < len(times) and cast(pd.Timestamp, times[pointer]) <= asof:
                pointer += 1
            index = pointer - 1
            fresh = (
                index >= 0
                and (asof - cast(pd.Timestamp, times[index])).total_seconds()
                <= 7 * 86_400
            )
            change = (
                values[index] - values[index - lookback]
                if fresh and index >= lookback
                else None
            )
            result[(asof, str(currency))] = (change, fresh)
    return result


def _direction(sign: float) -> str:
    return "LONG_BASE" if sign > 0 else "SHORT_BASE"


def build_pair_bias(
    predictions: pd.DataFrame,
    yields: pd.DataFrame,
    pairs: tuple[str, ...],
    yield_lookback: int,
) -> pd.DataFrame:
    """Create the frozen pair-level F1 and F2 daily/post-event state machine."""

    schedule = pd.DatetimeIndex(predictions["asof_utc"].unique()).sort_values()
    yield_state = _yield_states(yields, schedule, yield_lookback)
    lookup = {
        (cast(pd.Timestamp, row.asof_utc), str(row.currency)): row
        for row in predictions.itertuples(index=False)
    }
    records: list[dict[str, object]] = []
    for asof in schedule:
        for pair in pairs:
            base, quote = pair[:3], pair[3:]
            base_row = lookup[(asof, base)]
            quote_row = lookup[(asof, quote)]
            base_prediction = base_row.prediction_6m_policy_change_bp
            quote_prediction = quote_row.prediction_6m_policy_change_bp
            base_revision = base_row.prediction_revision_1m_bp
            quote_revision = quote_row.prediction_revision_1m_bp
            complete = all(
                pd.notna(value)
                for value in (
                    base_prediction,
                    quote_prediction,
                    base_revision,
                    quote_revision,
                )
            )
            level = (
                float(base_prediction) - float(quote_prediction) if complete else None
            )
            revision = (
                float(base_revision) - float(quote_revision) if complete else None
            )
            agreement = (
                level is not None
                and revision is not None
                and level != 0
                and revision != 0
                and level * revision > 0
            )
            f1 = _direction(level) if agreement and level is not None else "FLAT"
            base_yield, base_yield_fresh = yield_state[(asof, base)]
            quote_yield, quote_yield_fresh = yield_state[(asof, quote)]
            yield_change = (
                base_yield - quote_yield
                if base_yield is not None and quote_yield is not None
                else None
            )
            yield_agrees = (
                agreement
                and yield_change is not None
                and level is not None
                and yield_change != 0
                and yield_change * level > 0
            )
            f2 = f1 if yield_agrees else "FLAT"
            reason = (
                "MISSING_OR_STALE_MACRO"
                if not complete
                else "LEVEL_REVISION_CONFLICT"
                if not agreement
                else "YIELD_CONFIRMED"
                if yield_agrees
                else "YIELD_NOT_CONFIRMED"
            )
            identifier = canonical_sha256(
                {
                    "version": BIAS_BUILDER_VERSION,
                    "pair": pair,
                    "asof": asof.isoformat(),
                }
            )[:24]
            records.append(
                {
                    "snapshot_id": identifier,
                    "version": BIAS_BUILDER_VERSION,
                    "asof_utc": asof,
                    "effective_from_utc": asof,
                    "expiry_utc": asof + pd.Timedelta(hours=24),
                    "source_cutoff_utc": asof,
                    "snapshot_type": base_row.snapshot_type,
                    "pair": pair,
                    "base": base,
                    "quote": quote,
                    "direction_f1": f1,
                    "direction_f2": f2,
                    "level_divergence_bp": level,
                    "revision_divergence_bp": revision,
                    "yield_spread_change_20obs_bp": (
                        None if yield_change is None else yield_change * 100.0
                    ),
                    "yield_inputs_fresh": base_yield_fresh and quote_yield_fresh,
                    "data_quality": "COMPLETE" if complete else "UNAVAILABLE",
                    "reason_code": reason,
                }
            )
    result = pd.DataFrame.from_records(records).sort_values(["pair", "asof_utc"])
    for _, indices in result.groupby("pair").groups.items():
        ordered = list(indices)
        next_times = result.loc[ordered, "asof_utc"].shift(-1)
        result.loc[ordered, "expiry_utc"] = next_times.fillna(
            result.loc[ordered, "expiry_utc"]
        )
    return result.sort_values(["asof_utc", "pair"]).reset_index(drop=True)


def _policy_diagnostic(
    panel: pd.DataFrame,
    predictions: pd.DataFrame,
    end: pd.Timestamp,
    bootstrap: dict[str, object],
) -> dict[str, object]:
    monthly_predictions = predictions[predictions["snapshot_type"] == "DAILY_06"]
    merged = panel.merge(
        monthly_predictions[["asof_utc", "currency", "prediction_6m_policy_change_bp"]],
        on=["asof_utc", "currency"],
        how="inner",
    )
    eligible = merged[
        merged["panel_complete"]
        & (merged["label_available_at_utc"] < end)
        & merged["prediction_6m_policy_change_bp"].notna()
    ].copy()
    if eligible.empty:
        return {"status": "NOT_ESTIMABLE", "rows": 0}
    actual = eligible["policy_change_6m_bp"].astype(float)
    primary = eligible["prediction_6m_policy_change_bp"].astype(float)
    no_change = pd.Series(0.0, index=eligible.index)
    momentum = eligible["policy_change_3m_bp"].astype(float) * 2.0
    mae = {
        "structural_model": float((actual - primary).abs().mean()),
        "no_change": float((actual - no_change).abs().mean()),
        "three_month_momentum": float((actual - momentum).abs().mean()),
    }
    nonzero = actual != 0
    directional = float(((primary[nonzero] > 0) == (actual[nonzero] > 0)).mean())
    intervals: dict[str, list[float]] = {}
    for offset, (name, baseline) in enumerate(
        (("no_change", no_change), ("three_month_momentum", momentum))
    ):
        improvements = (actual - baseline).abs() - (actual - primary).abs()
        monthly = (
            pd.DataFrame(
                {
                    "month": eligible["month"].astype(str),
                    "improvement": improvements,
                }
            )
            .groupby("month")["improvement"]
            .mean()
            .tolist()
        )
        intervals[name] = list(
            _block_bootstrap_mean_ci(
                [float(value) for value in monthly],
                int(cast(int, bootstrap["block_length_months"])),
                int(cast(int, bootstrap["resamples"])),
                int(cast(int, bootstrap["seed"])) + offset,
            )
        )
    supported = mae["structural_model"] < min(
        mae["no_change"], mae["three_month_momentum"]
    ) and all(interval[0] > 0 for interval in intervals.values())
    return {
        "status": "SUPPORTED" if supported else "NOT_SUPPORTED",
        "rows": len(eligible),
        "months": int(eligible["month"].nunique()),
        "currencies": sorted(eligible["currency"].unique().tolist()),
        "mae_bp": mae,
        "paired_mae_improvement_95_ci_bp": intervals,
        "directional_accuracy_nonzero": directional,
    }


def _block_bootstrap_mean_ci(
    monthly_values: list[float], block_length: int, resamples: int, seed: int
) -> tuple[float, float]:
    if not monthly_values or block_length < 1 or resamples < 1:
        raise FundamentalModelError("invalid policy diagnostic bootstrap inputs")
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < len(monthly_values):
            start = generator.randrange(len(monthly_values))
            sample.extend(
                monthly_values[(start + offset) % len(monthly_values)]
                for offset in range(block_length)
            )
        estimates.append(mean(sample[: len(monthly_values)]))
    estimates.sort()
    lower = estimates[int(0.025 * (len(estimates) - 1))]
    upper = estimates[int(0.975 * (len(estimates) - 1))]
    return lower, upper


def verify_bias_freeze(freeze_path: Path) -> dict[str, bool]:
    freeze = _object(freeze_path)
    files = freeze.get("files")
    if not isinstance(files, list):
        raise FundamentalModelError("bias freeze file list is invalid")
    checks: dict[str, bool] = {}
    for item in files:
        if not isinstance(item, dict):
            raise FundamentalModelError("invalid bias freeze item")
        name, path, expected = item.get("name"), item.get("path"), item.get("sha256")
        if not all(isinstance(value, str) for value in (name, path, expected)):
            raise FundamentalModelError("invalid bias freeze fields")
        checks[cast(str, name)] = file_sha256(Path(cast(str, path))) == expected
    if not checks or not all(checks.values()):
        raise FundamentalModelError(f"bias freeze mismatch: {checks}")
    return checks


def run_phase03(
    model_config_path: Path,
    registry_path: Path,
    canonical_root: Path,
    output_root: Path,
    evidence_root: Path,
) -> dict[str, object]:
    """Fit policy labels only, freeze pair bias, and never accept an FX path."""

    config = _object(model_config_path)
    states = pd.read_parquet(canonical_root / "daily_macro_states.parquet")
    releases = pd.read_parquet(canonical_root / "macro_releases.parquet")
    vintages = pd.read_parquet(canonical_root / "macro_vintages.parquet")
    yields = pd.read_parquet(canonical_root / "two_year_yields.parquet")
    start = pd.Timestamp("2021-07-01T00:00:00Z")
    end = pd.Timestamp("2026-09-11T00:00:00Z")
    panel = build_monthly_policy_panel(states)
    history_start = start - pd.DateOffset(months=1)
    schedule, event_times = _snapshot_schedule(states, releases, history_start, end)
    all_states = build_macro_states_at_snapshots(
        releases, vintages, registry_path, schedule
    )
    models, model_audit = _models_by_month(panel, schedule, config)
    predictions = _currency_predictions(all_states, models, event_times)
    pairs = tuple(cast(list[str], config["pairs"]))
    pair_bias = build_pair_bias(
        predictions,
        yields,
        pairs,
        int(cast(int, config["f2_yield_change_observations"])),
    )
    pair_bias = pair_bias[pair_bias["asof_utc"] >= start].reset_index(drop=True)
    bootstrap = config.get("policy_diagnostic_bootstrap")
    if not isinstance(bootstrap, dict):
        raise FundamentalModelError("policy diagnostic bootstrap config is invalid")
    diagnostic = _policy_diagnostic(panel, predictions, end, bootstrap)

    output_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    paths = {
        "monthly_policy_panel": output_root / "monthly_policy_panel.parquet",
        "currency_predictions": output_root / "currency_predictions.parquet",
        "pair_bias": output_root / "pair_bias.parquet",
        "model_audit": output_root / "model_audit.json",
    }
    panel.to_parquet(paths["monthly_policy_panel"], index=False)
    predictions.to_parquet(paths["currency_predictions"], index=False)
    pair_bias.to_parquet(paths["pair_bias"], index=False)
    write_json_atomic(paths["model_audit"], {"fits_and_folds": model_audit})
    files = [
        {
            "name": name,
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for name, path in paths.items()
    ]
    freeze: dict[str, object] = {
        "schema_version": "1.0",
        "builder_version": BIAS_BUILDER_VERSION,
        "model_config": str(model_config_path),
        "model_config_sha256": file_sha256(model_config_path),
        "fx_inputs_accepted": False,
        "files": files,
    }
    freeze["summary_sha256"] = canonical_sha256(freeze)
    freeze_path = evidence_root / "bias_freeze.json"
    write_json_atomic(freeze_path, freeze)
    verify_bias_freeze(freeze_path)

    direction_counts: dict[str, dict[str, int]] = {}
    for variant in ("f1", "f2"):
        column = f"direction_{variant}"
        direction_counts[variant.upper()] = {
            str(key): int(value)
            for key, value in pair_bias[column].value_counts().sort_index().items()
        }
    penalties = Counter(
        str(row["selected_penalty"])
        for row in model_audit
        if row.get("record_kind") == "OUTER_FIT"
    )
    summary: dict[str, object] = {
        "schema_version": "1.0",
        "status": "PASS_BIAS_FROZEN",
        "policy_diagnostic": diagnostic,
        "monthly_panel_rows": len(panel),
        "currency_prediction_rows": len(predictions),
        "pair_bias_rows": len(pair_bias),
        "bias_direction_counts": direction_counts,
        "monthly_models": len(models),
        "selected_penalty_counts": dict(sorted(penalties.items())),
        "post_event_snapshot_times": len(event_times),
        "fx_returns_accessed": False,
        "strategy_pnl_accessed": False,
        "freeze_path": str(freeze_path),
        "freeze_sha256": file_sha256(freeze_path),
    }
    summary["summary_sha256"] = canonical_sha256(summary)
    write_json_atomic(evidence_root / "summary.json", summary)
    return summary
