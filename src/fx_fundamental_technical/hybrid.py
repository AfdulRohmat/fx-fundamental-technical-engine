"""Frozen-bias hybrid matrix, validation selection, and placebo controls."""

from __future__ import annotations

import json
import random
from pathlib import Path
from statistics import mean
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)
from fx_fundamental_technical.fundamental_bias import verify_bias_freeze
from fx_fundamental_technical.technical import (
    PAIRS,
    metrics,
    prepare_bars,
    simulate_portfolio,
)

HYBRID_ENGINE_VERSION = "frozen-bias-permission-v0.1"


class HybridError(ValueError):
    """Raised when a frozen-bias comparison violates its information boundary."""


def _object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HybridError(f"expected JSON object: {path}")
    return cast(dict[str, object], value)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HybridError(f"expected numeric value, got {value!r}")
    return float(value)


def transform_bias(bias: pd.DataFrame, variant: str, seed: int) -> pd.DataFrame:
    """Apply a registered placebo while preserving timestamps and frequency."""

    result = bias.copy()
    columns = ("direction_f1", "direction_f2")
    if variant == "PRIMARY":
        return result
    if variant == "REVERSED":
        for column in columns:
            result[column] = result[column].map(
                {"LONG_BASE": "SHORT_BASE", "SHORT_BASE": "LONG_BASE", "FLAT": "FLAT"}
            )
        return result
    if variant == "ONE_SNAPSHOT_LAG":
        for column in columns:
            result[column] = result.groupby("pair")[column].shift(1).fillna("FLAT")
        return result
    if variant == "FREQUENCY_MATCHED_SHUFFLE":
        generator = random.Random(seed)
        for _pair, indices in result.groupby("pair").groups.items():
            ordered = list(indices)
            for column in columns:
                values = result.loc[ordered, column].tolist()
                generator.shuffle(values)
                result.loc[ordered, column] = values
        return result
    raise HybridError(f"unknown bias transform: {variant}")


def align_signals_to_bias(
    signals: pd.DataFrame, bias: pd.DataFrame, fundamental: str
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Permit only same-direction signals and attach the next bias-flip exit."""

    column = f"direction_{fundamental.lower()}"
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    grouped = {
        pair: group.sort_values("effective_from_utc").reset_index(drop=True)
        for pair, group in bias.groupby("pair")
    }
    for _, signal in signals.sort_values(["entry_time", "pair"]).iterrows():
        pair = str(signal["pair"])
        entry = cast(pd.Timestamp, signal["entry_time"])
        group = grouped[pair]
        times = pd.DatetimeIndex(group["effective_from_utc"])
        position = int(times.searchsorted(entry, side="right")) - 1
        expected = "LONG_BASE" if int(signal["direction"]) > 0 else "SHORT_BASE"
        reason: str | None = None
        selected: pd.Series | None = None
        if position < 0:
            reason = "NO_BIAS_SNAPSHOT"
        else:
            selected = group.iloc[position]
            if entry >= cast(pd.Timestamp, selected["expiry_utc"]):
                reason = "BIAS_EXPIRED"
            elif selected[column] != expected:
                reason = "BIAS_NOT_ALIGNED"
        if reason is not None or selected is None:
            rejected.append(
                {"pair": pair, "entry_time": entry, "reason": reason or "NO_BIAS"}
            )
            continue
        future = group.iloc[position + 1 :]
        changes = future[future[column] != expected]
        record = cast(dict[str, object], signal.to_dict())
        record["bias_snapshot_id"] = str(selected["snapshot_id"])
        record["bias_direction"] = expected
        record["bias_exit_time"] = (
            pd.NaT
            if changes.empty
            else cast(pd.Timestamp, changes.iloc[0]["effective_from_utc"])
        )
        accepted.append(record)
    return pd.DataFrame.from_records(accepted), pd.DataFrame.from_records(rejected)


def _with_split(ledger: pd.DataFrame, development_end: pd.Timestamp) -> pd.DataFrame:
    result = ledger.copy()
    if not result.empty:
        result["split"] = result["entry_time"].apply(
            lambda value: "DEVELOPMENT" if value < development_end else "VALIDATION"
        )
    return result


def _pair_metrics(ledger: pd.DataFrame) -> dict[str, dict[str, object]]:
    return {
        str(pair): metrics(group) for pair, group in ledger.groupby("pair", sort=True)
    }


def _bootstrap_expectancy(
    ledger: pd.DataFrame, config: dict[str, object]
) -> list[float] | None:
    if ledger.empty:
        return None
    monthly = (
        ledger.assign(month=ledger["entry_time"].dt.tz_localize(None).dt.to_period("M"))
        .groupby("month")["net_r"]
        .mean()
        .astype(float)
        .tolist()
    )
    generator = random.Random(20260911)
    block = int(cast(int, config["bootstrap_block_months"]))
    resamples = int(cast(int, config["bootstrap_resamples"]))
    estimates: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < len(monthly):
            start = generator.randrange(len(monthly))
            sample.extend(
                monthly[(start + offset) % len(monthly)] for offset in range(block)
            )
        estimates.append(mean(sample[: len(monthly)]))
    estimates.sort()
    return [
        estimates[int(0.025 * (len(estimates) - 1))],
        estimates[int(0.975 * (len(estimates) - 1))],
    ]


def _candidate_assessment(
    validation: pd.DataFrame,
    baseline_expectancy: float,
    config: dict[str, object],
) -> dict[str, object]:
    result = metrics(validation)
    pair_results = _pair_metrics(validation)
    positive = {
        pair: _as_float(item["net_r"])
        for pair, item in pair_results.items()
        if _as_float(item["net_r"]) > 0
    }
    total_positive = sum(positive.values())
    concentration = (
        max(positive.values()) / total_positive if total_positive > 0 else None
    )
    expectancy = result.get("expectancy_r")
    drawdown = _as_float(result.get("maximum_drawdown_r", 0.0))
    checks = {
        "minimum_trades": len(validation)
        >= int(cast(int, config["minimum_validation_trades"])),
        "positive_expectancy": expectancy is not None and _as_float(expectancy) > 0,
        "improves_baseline": expectancy is not None
        and _as_float(expectancy) > baseline_expectancy,
        "positive_pairs": len(positive)
        >= int(cast(int, config["minimum_positive_validation_pairs"])),
        "drawdown": drawdown
        <= float(cast(float, config["maximum_validation_drawdown_r"])),
        "concentration": concentration is not None
        and concentration
        <= float(cast(float, config["maximum_single_pair_positive_profit_share"])),
    }
    return {
        "metrics": result,
        "baseline_expectancy_r": baseline_expectancy,
        "incremental_expectancy_r": (
            None if expectancy is None else _as_float(expectancy) - baseline_expectancy
        ),
        "positive_pair_count": len(positive),
        "positive_pair_profit_share_max": concentration,
        "pair_metrics": pair_results,
        "expectancy_block_bootstrap_95_ci_r": _bootstrap_expectancy(validation, config),
        "promotion_checks": checks,
        "eligible_for_promotion": all(checks.values()),
    }


def _run_candidate(
    candidate_id: str,
    signals: pd.DataFrame,
    bias: pd.DataFrame,
    prepared: dict[str, pd.DataFrame],
    events: pd.DataFrame,
    execution: dict[str, object],
    development_end: pd.Timestamp,
    validation_end: pd.Timestamp,
    config: dict[str, object],
    *,
    slippage_points: int = 0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    fundamental, _ = candidate_id.split("_")
    aligned, bias_rejections = align_signals_to_bias(signals, bias, fundamental)
    if aligned.empty:
        ledger = pd.DataFrame()
        execution_rejections = pd.DataFrame()
    else:
        ledger, execution_rejections = simulate_portfolio(
            aligned,
            prepared,
            events,
            execution,
            slippage_points=slippage_points,
        )
    ledger = _with_split(ledger, development_end)
    if not ledger.empty and (ledger["entry_time"] >= validation_end).any():
        raise HybridError("locked outcome leaked into hybrid validation")
    development = (
        ledger[ledger.get("split") == "DEVELOPMENT"] if not ledger.empty else ledger
    )
    validation = (
        ledger[ledger.get("split") == "VALIDATION"] if not ledger.empty else ledger
    )
    summary: dict[str, object] = {
        "technical_signals": len(signals),
        "bias_aligned_signals": len(aligned),
        "bias_rejections": len(bias_rejections),
        "execution_rejections": len(execution_rejections),
        "development": metrics(development),
        "validation": metrics(validation),
    }
    return ledger, summary


def run_phase05(
    validation_config_path: Path,
    execution_config_path: Path,
    baseline_evidence_path: Path,
    bias_freeze_path: Path,
    bias_path: Path,
    price_path: Path,
    event_path: Path,
    signal_root: Path,
    output_root: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Run all registered hybrids through validation and select at most one."""

    config = _object(validation_config_path)
    execution = _object(execution_config_path)
    if bool(config.get("locked_outcomes_allowed")):
        raise HybridError("Phase 05 must keep locked outcomes closed")
    verify_bias_freeze(bias_freeze_path)
    baseline = _object(baseline_evidence_path)
    bias = pd.read_parquet(bias_path)
    validation_end = pd.Timestamp(str(execution["validation_end_exclusive_utc"]))
    development_end = pd.Timestamp(str(execution["development_end_exclusive_utc"]))
    prices = pd.read_parquet(price_path)
    prices = prices[prices["time"] < validation_end]
    events = pd.read_parquet(event_path)
    events = events[events["released_at_utc"] < validation_end]
    prepared = {
        pair: prepare_bars(
            prices[prices["pair"] == pair], int(cast(int, execution["atr_period"]))
        )
        for pair in PAIRS
    }
    output_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {}
    ledgers: dict[str, pd.DataFrame] = {}
    for candidate_id in cast(list[str], config["matrix"]):
        _, technical = candidate_id.split("_")
        signals = pd.read_parquet(signal_root / f"{technical.lower()}_signals.parquet")
        ledger, summary = _run_candidate(
            candidate_id,
            signals,
            bias,
            prepared,
            events,
            execution,
            development_end,
            validation_end,
            config,
        )
        baseline_strategy = cast(dict[str, object], baseline["strategies"])[technical]
        baseline_splits = cast(dict[str, object], baseline_strategy)["by_split"]
        baseline_validation = cast(dict[str, object], baseline_splits)["validation"]
        baseline_expectancy = _as_float(
            cast(dict[str, object], baseline_validation)["expectancy_r"]
        )
        validation = (
            ledger[ledger["split"] == "VALIDATION"] if not ledger.empty else ledger
        )
        summary["assessment"] = _candidate_assessment(
            validation, baseline_expectancy, config
        )
        results[candidate_id] = summary
        ledgers[candidate_id] = ledger
        ledger.to_parquet(
            output_root / f"{candidate_id.lower()}_ledger.parquet", index=False
        )

    eligible = [
        candidate
        for candidate, result in results.items()
        if bool(
            cast(dict[str, object], cast(dict[str, object], result)["assessment"])[
                "eligible_for_promotion"
            ]
        )
    ]
    promoted: str | None = None
    if eligible:
        promoted = max(
            eligible,
            key=lambda candidate: float(
                cast(
                    dict[str, object],
                    cast(dict[str, object], results[candidate])["assessment"],
                )["metrics"]["expectancy_r"]  # type: ignore[index]
            ),
        )
    diagnostic_candidate = promoted or max(
        results,
        key=lambda candidate: float(
            cast(
                dict[str, object],
                cast(dict[str, object], results[candidate])["assessment"],
            )["metrics"]["expectancy_r"]  # type: ignore[index]
        ),
    )
    _fundamental, technical = diagnostic_candidate.split("_")
    diagnostic_signals = pd.read_parquet(
        signal_root / f"{technical.lower()}_signals.parquet"
    )
    controls: dict[str, object] = {}
    for placebo in cast(list[str], config["placebos"]):
        transformed = transform_bias(
            bias, placebo, int(cast(int, config["placebo_seed"]))
        )
        _, placebo_summary = _run_candidate(
            diagnostic_candidate,
            diagnostic_signals,
            transformed,
            prepared,
            events,
            execution,
            development_end,
            validation_end,
            config,
        )
        controls[placebo] = placebo_summary["validation"]
    stress: dict[str, object] = {}
    for points in cast(list[int], config["stress_slippage_points"]):
        _, stress_summary = _run_candidate(
            diagnostic_candidate,
            diagnostic_signals,
            bias,
            prepared,
            events,
            execution,
            development_end,
            validation_end,
            config,
            slippage_points=int(points),
        )
        stress[str(points)] = stress_summary["validation"]

    frozen_files = [
        {
            "candidate": candidate,
            "path": str(path := output_root / f"{candidate.lower()}_ledger.parquet"),
            "sha256": file_sha256(path),
        }
        for candidate in results
    ]
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "engine_version": HYBRID_ENGINE_VERSION,
        "status": "CANDIDATE_PROMOTED" if promoted else "NO_CANDIDATE_PROMOTED",
        "promoted_candidate": promoted,
        "diagnostic_candidate": diagnostic_candidate,
        "locked_outcomes_accessed": False,
        "bias_freeze_verified": True,
        "results": results,
        "diagnostic_candidate_placebos": controls,
        "diagnostic_candidate_slippage_stress": stress,
        "files": frozen_files,
        "validation_config_sha256": file_sha256(validation_config_path),
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(evidence_path, payload)
    if promoted:
        freeze: dict[str, object] = {
            "candidate": promoted,
            "ledger_sha256": next(
                item["sha256"] for item in frozen_files if item["candidate"] == promoted
            ),
            "settings_sha256": file_sha256(validation_config_path),
            "locked_start_utc": "2025-08-28T00:00:00Z",
            "locked_end_exclusive_utc": "2026-09-11T00:00:00Z",
            "locked_runs_remaining": 1,
        }
        freeze["summary_sha256"] = canonical_sha256(freeze)
        write_json_atomic(evidence_path.parent / "candidate_freeze.json", freeze)
    return payload
