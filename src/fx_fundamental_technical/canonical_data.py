"""Point-in-time canonical macro, event, yield, and M15 dataset builder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.calendar_export import file_sha256, load_calendar_rows
from fx_fundamental_technical.clocks import require_utc
from fx_fundamental_technical.evidence import canonical_sha256, write_json_atomic

CANONICAL_BUILDER_VERSION = "point-in-time-canonical-v0.1"
FAMILIES = ("inflation", "labour", "policy")


class CanonicalDataError(ValueError):
    """Raised when source rows cannot meet the canonical data contract."""


def _json_object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise CanonicalDataError(f"expected JSON object: {path}")
    return cast(dict[str, object], decoded)


def _number(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise CanonicalDataError(f"invalid numeric calendar value: {value!r}") from exc


def build_macro_releases(calendar_path: Path, registry_path: Path) -> pd.DataFrame:
    """Normalize only the 18 source-gated macro series."""

    registry = _json_object(registry_path)
    mappings = registry.get("macro_series")
    if not isinstance(mappings, dict):
        raise CanonicalDataError("macro_series registry is invalid")
    lookup: dict[tuple[str, str, str], tuple[str, float]] = {}
    for currency, mapping in mappings.items():
        if not isinstance(currency, str) or not isinstance(mapping, dict):
            raise CanonicalDataError("invalid macro mapping")
        country = mapping.get("country_code")
        target = mapping.get("inflation_target_percent")
        if not isinstance(country, str) or not isinstance(target, (int, float)):
            raise CanonicalDataError(f"invalid metadata for {currency}")
        for family in FAMILIES:
            code = mapping.get(family)
            if not isinstance(code, str):
                raise CanonicalDataError(f"missing {currency} {family} code")
            lookup[(currency, country, code)] = (family, float(target))

    raw_hash = file_sha256(calendar_path)
    records: list[dict[str, object]] = []
    for row in load_calendar_rows(calendar_path):
        key = (row["currency"], row["country_code"], row["event_code"])
        mapped = lookup.get(key)
        if mapped is None or row["actual"] == "":
            continue
        family, target = mapped
        released = pd.to_datetime(int(row["release_epoch_raw"]), unit="s", utc=True)
        reference = pd.to_datetime(int(row["reference_epoch_raw"]), unit="s", utc=True)
        # MT5 policy-decision rows publish a zero reference epoch. A policy
        # rate becomes effective at the decision release, so use that release
        # date as its canonical observation reference.
        if family == "policy" and int(row["reference_epoch_raw"]) == 0:
            reference = released.normalize()
        if int(row["server_utc_offset_seconds_at_export"]) != 0:
            raise CanonicalDataError("calendar server offset drifted from frozen UTC+0")
        records.append(
            {
                "value_id": int(row["value_id"]),
                "event_id": int(row["event_id"]),
                "currency": row["currency"],
                "country_code": row["country_code"],
                "family": family,
                "event_code": row["event_code"],
                "event_name": row["event_name"],
                "reference_period_utc": reference,
                "released_at_utc": released,
                "available_at_utc": released,
                "actual": _number(row["actual"]),
                "forecast": _number(row["forecast"]),
                "previous_as_reported": _number(row["previous_as_reported"]),
                "revised_previous": _number(row["revised_previous"]),
                "revision_sequence": int(row["revision"]),
                "importance": int(row["importance"]),
                "unit": int(row["unit"]),
                "multiplier": int(row["multiplier"]),
                "digits": int(row["digits"]),
                "inflation_target_percent": target,
                "source_url": row["source_url"],
                "provider": "MetaTrader 5 Economic Calendar",
                "raw_sha256": raw_hash,
                "quality_status": "SOURCE_GATED",
            }
        )
    frame = pd.DataFrame.from_records(records).sort_values(
        ["available_at_utc", "currency", "family", "value_id"]
    )
    if frame.empty or frame["value_id"].duplicated().any():
        raise CanonicalDataError("canonical macro releases are empty or duplicated")
    require_utc(frame["available_at_utc"])
    return frame.reset_index(drop=True)


def build_vintage_values(releases: pd.DataFrame) -> pd.DataFrame:
    """Append actual and later previous-period revision knowledge as versions."""

    records: list[dict[str, object]] = []
    for (currency, family), group in releases.groupby(
        ["currency", "family"], sort=True
    ):
        ordered = group.sort_values(["available_at_utc", "value_id"])
        known_references: list[pd.Timestamp] = []
        for row in ordered.itertuples(index=False):
            reference = cast(pd.Timestamp, row.reference_period_utc)
            records.append(
                {
                    "currency": currency,
                    "family": family,
                    "reference_period_utc": reference,
                    "value": float(row.actual),
                    "available_at_utc": row.available_at_utc,
                    "source_value_id": int(row.value_id),
                    "version_kind": "ACTUAL_RELEASE",
                }
            )
            prior = [item for item in known_references if item < reference]
            if pd.notna(row.revised_previous) and prior:
                records.append(
                    {
                        "currency": currency,
                        "family": family,
                        "reference_period_utc": max(prior),
                        "value": float(row.revised_previous),
                        "available_at_utc": row.available_at_utc,
                        "source_value_id": int(row.value_id),
                        "version_kind": "REVISED_PREVIOUS",
                    }
                )
            if reference not in known_references:
                known_references.append(reference)
    frame = pd.DataFrame.from_records(records).sort_values(
        ["available_at_utc", "currency", "family", "reference_period_utc"]
    )
    require_utc(frame["available_at_utc"])
    return frame.reset_index(drop=True)


def _latest_release(group: pd.DataFrame, asof: pd.Timestamp) -> pd.Series | None:
    known = group[group["available_at_utc"] <= asof]
    return None if known.empty else known.iloc[-1]


def _latest_vintage_at_or_before(
    group: pd.DataFrame, asof: pd.Timestamp, reference_cutoff: pd.Timestamp
) -> pd.Series | None:
    known = group[
        (group["available_at_utc"] <= asof)
        & (group["reference_period_utc"] <= reference_cutoff)
    ]
    if known.empty:
        return None
    latest_reference = known["reference_period_utc"].max()
    return known[known["reference_period_utc"] == latest_reference].iloc[-1]


@dataclass
class _StateCursor:
    """Incremental as-of cursor; avoids repeated whole-frame scans."""

    releases: list[dict[str, object]]
    vintages: list[dict[str, object]]
    release_index: int = 0
    vintage_index: int = 0
    current: dict[str, object] | None = None
    known_vintages: dict[pd.Timestamp, dict[str, object]] = field(default_factory=dict)

    def advance(self, asof: pd.Timestamp) -> None:
        while self.release_index < len(self.releases):
            row = self.releases[self.release_index]
            if cast(pd.Timestamp, row["available_at_utc"]) > asof:
                break
            self.current = row
            self.release_index += 1
        while self.vintage_index < len(self.vintages):
            row = self.vintages[self.vintage_index]
            if cast(pd.Timestamp, row["available_at_utc"]) > asof:
                break
            reference = cast(pd.Timestamp, row["reference_period_utc"])
            self.known_vintages[reference] = row
            self.vintage_index += 1

    def lag(self, reference_cutoff: pd.Timestamp) -> dict[str, object] | None:
        eligible = [
            reference
            for reference in self.known_vintages
            if reference <= reference_cutoff
        ]
        if not eligible:
            return None
        return self.known_vintages[max(eligible)]


def build_daily_macro_states(
    releases: pd.DataFrame,
    vintages: pd.DataFrame,
    registry_path: Path,
    start: str,
    end_exclusive: str,
) -> pd.DataFrame:
    """Build 06:00 UTC latest-known states with revision-aware 3m lags."""

    dates = pd.date_range(start, end_exclusive, freq="B", inclusive="left", tz="UTC")
    snapshots = dates.normalize() + pd.Timedelta(hours=6)
    return build_macro_states_at_snapshots(releases, vintages, registry_path, snapshots)


def build_macro_states_at_snapshots(
    releases: pd.DataFrame,
    vintages: pd.DataFrame,
    registry_path: Path,
    snapshots: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Build latest-known states at an arbitrary sorted UTC snapshot schedule."""

    if snapshots.tz is None or str(snapshots.tz) != "UTC":
        raise CanonicalDataError("macro snapshot schedule must be UTC-aware")
    snapshots = snapshots.sort_values().unique()
    registry = _json_object(registry_path)
    freshness = registry.get("freshness_days")
    mappings = registry.get("macro_series")
    if not isinstance(freshness, dict) or not isinstance(mappings, dict):
        raise CanonicalDataError("registry freshness or macro mapping invalid")
    records: list[dict[str, object]] = []
    for currency in sorted(mappings):
        state: dict[str, _StateCursor] = {}
        for family in FAMILIES:
            releases_group = releases[
                (releases["currency"] == currency) & (releases["family"] == family)
            ].sort_values(["available_at_utc", "value_id"])
            vintage_group = vintages[
                (vintages["currency"] == currency) & (vintages["family"] == family)
            ].sort_values(["available_at_utc", "source_value_id"])
            state[family] = _StateCursor(
                releases=cast(
                    list[dict[str, object]], releases_group.to_dict("records")
                ),
                vintages=cast(
                    list[dict[str, object]], vintage_group.to_dict("records")
                ),
            )
        for asof in snapshots:
            record: dict[str, object] = {"asof_utc": asof, "currency": currency}
            available = True
            for family in FAMILIES:
                cursor = state[family]
                cursor.advance(asof)
                current = cursor.current
                if current is None:
                    available = False
                    record[f"{family}_value"] = None
                    continue
                release_time = cast(pd.Timestamp, current["available_at_utc"])
                age_days = (asof - release_time).total_seconds() / 86_400
                limit = freshness.get(family)
                if not isinstance(limit, int):
                    raise CanonicalDataError(f"invalid freshness limit for {family}")
                is_fresh = age_days <= limit
                available = available and is_fresh
                reference = cast(pd.Timestamp, current["reference_period_utc"])
                lag = cursor.lag(reference - pd.DateOffset(months=3))
                record.update(
                    {
                        f"{family}_value": cast(float, current["actual"]),
                        f"{family}_reference_utc": reference,
                        f"{family}_available_at_utc": release_time,
                        f"{family}_age_days": age_days,
                        f"{family}_fresh": is_fresh,
                        f"{family}_lag3_value": (
                            None if lag is None else cast(float, lag["value"])
                        ),
                        f"{family}_lag3_reference_utc": (
                            pd.NaT if lag is None else lag["reference_period_utc"]
                        ),
                    }
                )
                if lag is None:
                    available = False
            record["mandatory_inputs_available"] = available
            records.append(record)
    frame = pd.DataFrame.from_records(records).sort_values(["asof_utc", "currency"])
    require_utc(frame["asof_utc"])
    return frame.reset_index(drop=True)


def build_blackout_events(calendar_path: Path, start: str, end: str) -> pd.DataFrame:
    """Preserve high-impact event times for the registered news blackout."""

    raw_hash = file_sha256(calendar_path)
    records: list[dict[str, object]] = []
    currencies = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD"}
    lower = pd.Timestamp(start)
    upper = pd.Timestamp(end)
    for row in load_calendar_rows(calendar_path):
        if row["currency"] not in currencies or int(row["importance"]) != 3:
            continue
        released = pd.to_datetime(int(row["release_epoch_raw"]), unit="s", utc=True)
        if not lower <= released < upper:
            continue
        records.append(
            {
                "value_id": int(row["value_id"]),
                "currency": row["currency"],
                "event_code": row["event_code"],
                "event_name": row["event_name"],
                "released_at_utc": released,
                "available_at_utc": released,
                "importance": 3,
                "raw_sha256": raw_hash,
            }
        )
    frame = pd.DataFrame.from_records(records).sort_values("released_at_utc")
    if frame.empty:
        raise CanonicalDataError("high-impact event table is empty")
    return frame.reset_index(drop=True)


def build_m15_prices(
    raw_root: Path, pairs: list[str], start: str, end_exclusive: str
) -> pd.DataFrame:
    """Combine only the source-qualified continuous M15 interval."""

    lower = pd.Timestamp(start)
    upper = pd.Timestamp(end_exclusive)
    frames: list[pd.DataFrame] = []
    for pair in pairs:
        raw = pd.read_parquet(raw_root / f"{pair.lower()}_m15.parquet")
        raw["time"] = pd.to_datetime(raw["time"], utc=True)
        selected = raw[(raw["time"] >= lower) & (raw["time"] < upper)].copy()
        if selected.empty or selected["time"].duplicated().any():
            raise CanonicalDataError(f"invalid M15 interval for {pair}")
        selected["pair"] = pair
        frames.append(selected)
    combined = pd.concat(frames, ignore_index=True).sort_values(["time", "pair"])
    require_utc(combined["time"])
    return combined.reset_index(drop=True)


def run_phase02_build(
    dataset_contract_path: Path,
    registry_path: Path,
    output_root: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Build and hash every Phase 02 canonical artifact without opening PnL."""

    contract = _json_object(dataset_contract_path)
    calendar_path = Path(str(contract["raw_calendar_snapshot"]))
    price_root = Path(str(contract["raw_price_root"]))
    yield_path = Path(str(contract["source_yield_canonical"]))
    macro_start = str(contract["macro_training_start_utc"])
    price_start = str(contract["price_start_inclusive_utc"])
    price_end = str(contract["price_end_exclusive_utc"])
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]

    releases = build_macro_releases(calendar_path, registry_path)
    vintages = build_vintage_values(releases)
    states = build_daily_macro_states(
        releases, vintages, registry_path, macro_start, price_end
    )
    blackout = build_blackout_events(calendar_path, price_start, price_end)
    prices = build_m15_prices(price_root, pairs, price_start, price_end)
    yields = pd.read_parquet(yield_path)
    yields["available_at_utc"] = pd.to_datetime(yields["available_at_utc"], utc=True)
    yields = yields[
        (yields["available_at_utc"] >= pd.Timestamp(macro_start))
        & (yields["available_at_utc"] < pd.Timestamp(price_end))
    ].sort_values(["available_at_utc", "currency"])
    if set(yields["currency"]) != {"USD", "EUR", "GBP", "JPY", "AUD", "CAD"}:
        raise CanonicalDataError("canonical yields do not contain all currencies")

    output_root.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "macro_releases": (output_root / "macro_releases.parquet", releases),
        "macro_vintages": (output_root / "macro_vintages.parquet", vintages),
        "daily_macro_states": (output_root / "daily_macro_states.parquet", states),
        "high_impact_events": (output_root / "high_impact_events.parquet", blackout),
        "m15_prices": (output_root / "m15_prices.parquet", prices),
        "two_year_yields": (output_root / "two_year_yields.parquet", yields),
    }
    files: list[dict[str, object]] = []
    for name, (path, frame) in artifacts.items():
        frame.to_parquet(path, index=False)
        files.append(
            {
                "name": name,
                "path": str(path),
                "rows": len(frame),
                "sha256": file_sha256(path),
                "first_timestamp": _first_time(frame),
                "last_timestamp": _last_time(frame),
            }
        )
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "builder_version": CANONICAL_BUILDER_VERSION,
        "status": "PASS",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "dataset_contract": str(dataset_contract_path),
        "dataset_contract_sha256": file_sha256(dataset_contract_path),
        "outcome_firewall": {
            "fx_returns_calculated": False,
            "strategy_pnl_calculated": False,
        },
        "artifacts": files,
        "quality": {
            "macro_value_ids_unique": not releases["value_id"].duplicated().any(),
            "vintage_revisions": int(
                vintages["version_kind"].eq("REVISED_PREVIOUS").sum()
            ),
            "state_rows_available": int(states["mandatory_inputs_available"].sum()),
            "state_rows_total": len(states),
            "price_duplicate_pair_times": int(
                prices.duplicated(["pair", "time"]).sum()
            ),
            "price_pairs": sorted(prices["pair"].unique().tolist()),
            "state_release_times_not_after_snapshot": all(
                bool(
                    (
                        states[f"{family}_available_at_utc"].isna()
                        | (states[f"{family}_available_at_utc"] <= states["asof_utc"])
                    ).all()
                )
                for family in FAMILIES
            ),
            "lag_references_precede_current_references": all(
                bool(
                    (
                        states[f"{family}_lag3_reference_utc"].isna()
                        | (
                            states[f"{family}_lag3_reference_utc"]
                            < states[f"{family}_reference_utc"]
                        )
                    ).all()
                )
                for family in FAMILIES
            ),
        },
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(evidence_path, payload)
    return payload


def _first_time(frame: pd.DataFrame) -> str | None:
    for column in ("available_at_utc", "asof_utc", "released_at_utc", "time"):
        if column in frame and not frame.empty:
            return cast(str, cast(pd.Timestamp, frame[column].min()).isoformat())
    return None


def _last_time(frame: pd.DataFrame) -> str | None:
    for column in ("available_at_utc", "asof_utc", "released_at_utc", "time"):
        if column in frame and not frame.empty:
            return cast(str, cast(pd.Timestamp, frame[column].max()).isoformat())
    return None
