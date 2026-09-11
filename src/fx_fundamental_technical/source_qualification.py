"""Deterministic Phase 01 source qualification and common-window selection."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.calendar_export import (
    file_sha256,
    inventory_calendar,
    load_calendar_rows,
)
from fx_fundamental_technical.evidence import canonical_sha256, write_json_atomic


class SourceQualificationError(ValueError):
    """Raised when a mandatory source family cannot meet its contract."""


def _load_object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise SourceQualificationError(f"expected JSON object: {path}")
    return cast(dict[str, object], decoded)


def macro_series_inventory(
    calendar_path: Path, registry_path: Path
) -> list[dict[str, object]]:
    """Inventory each frozen macro mapping without calculating FX outcomes."""

    registry = _load_object(registry_path)
    mappings = registry.get("macro_series")
    if not isinstance(mappings, dict):
        raise SourceQualificationError("macro_series registry is invalid")
    rows = load_calendar_rows(calendar_path)
    inventory: list[dict[str, object]] = []
    for currency, untyped_mapping in sorted(mappings.items()):
        if not isinstance(currency, str) or not isinstance(untyped_mapping, dict):
            raise SourceQualificationError("invalid macro series mapping")
        for family in ("inflation", "labour", "policy"):
            event_code = untyped_mapping.get(family)
            country_code = untyped_mapping.get("country_code")
            if not isinstance(event_code, str) or not isinstance(country_code, str):
                raise SourceQualificationError(
                    f"invalid mapping for {currency} {family}"
                )
            matches = [
                row
                for row in rows
                if row["currency"] == currency
                and row["country_code"] == country_code
                and row["event_code"] == event_code
            ]
            if not matches:
                raise SourceQualificationError(
                    f"calendar has no rows for {currency} {family} {event_code}"
                )
            inventory.append(
                {
                    "currency": currency,
                    "family": family,
                    "country_code": country_code,
                    "event_code": event_code,
                    "event_name": matches[0]["event_name"],
                    "rows": len(matches),
                    "first_release_server": min(
                        row["release_time_server"] for row in matches
                    ),
                    "last_release_server": max(
                        row["release_time_server"] for row in matches
                    ),
                    "with_actual": sum(bool(row["actual"]) for row in matches),
                    "with_forecast": sum(bool(row["forecast"]) for row in matches),
                    "with_previous": sum(
                        bool(row["previous_as_reported"]) for row in matches
                    ),
                    "with_revised_previous": sum(
                        bool(row["revised_previous"]) for row in matches
                    ),
                }
            )
    return inventory


def m15_coverage_inventory(
    raw_price_root: Path, pairs: list[str], *, threshold: float = 80.0
) -> tuple[list[dict[str, object]], str]:
    """Find the first month with actual intraday M15 density for every pair."""

    records: list[dict[str, object]] = []
    starts: list[pd.Period] = []
    for pair in pairs:
        path = raw_price_root / f"{pair.lower()}_m15.parquet"
        frame = pd.read_parquet(path, columns=["time"])
        if frame.empty:
            raise SourceQualificationError(f"price source is empty: {pair}")
        timestamps = pd.to_datetime(frame["time"], utc=True)
        density = (
            pd.DataFrame(
                {
                    "month": timestamps.dt.tz_localize(None).dt.to_period("M"),
                    "date": timestamps.dt.date,
                }
            )
            .groupby(["month", "date"])
            .size()
            .groupby("month")
            .median()
        )
        qualified = density[density >= threshold]
        if qualified.empty:
            raise SourceQualificationError(f"no true M15 month found for {pair}")
        first = cast(pd.Period, qualified.index[0])
        starts.append(first)
        records.append(
            {
                "pair": pair,
                "rows": len(frame),
                "raw_sha256": file_sha256(path),
                "first_timestamp_utc": timestamps.iloc[0].isoformat(),
                "last_timestamp_utc": timestamps.iloc[-1].isoformat(),
                "first_qualified_m15_month": str(first),
                "median_bars_per_active_day_before": float(
                    density.loc[first - 1] if first - 1 in density.index else 0.0
                ),
                "median_bars_per_active_day_at_start": float(density.loc[first]),
                "density_threshold": threshold,
            }
        )
    common = max(starts)
    return records, common.start_time.date().isoformat()


def run_source_qualification(
    calendar_path: Path,
    registry_path: Path,
    price_root: Path,
    yield_evidence_path: Path,
    tick_evidence_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Freeze Phase 01 source evidence and the pre-PnL common sample start."""

    registry = _load_object(registry_path)
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
    calendar = inventory_calendar(calendar_path)
    macro = macro_series_inventory(calendar_path, registry_path)
    price, common_start = m15_coverage_inventory(price_root, pairs)
    yield_evidence = _load_object(yield_evidence_path)
    tick_evidence = _load_object(tick_evidence_path)
    yield_currencies = yield_evidence.get("currencies")
    if not isinstance(yield_currencies, list) or len(yield_currencies) != 6:
        raise SourceQualificationError("six qualified yield series are required")
    required_macro = 6 * 3
    complete_macro = sum(
        isinstance(record["with_actual"], int)
        and record["with_actual"] > 0
        and str(record["first_release_server"])[:4] <= "2017"
        for record in macro
    )
    if complete_macro != required_macro:
        raise SourceQualificationError("mandatory macro history is incomplete")

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "status": "PASS_WITH_SOURCE_DRIVEN_WINDOW_AMENDMENT",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "outcome_firewall": {
            "fx_returns_calculated": False,
            "strategy_pnl_calculated": False,
            "sample_selected_from_source_density_only": True,
        },
        "calendar": {
            "status": "PASS",
            "provider": cast(dict[str, object], registry["calendar"])["provider"],
            "path": str(calendar_path),
            "sha256": calendar.sha256,
            "rows": calendar.row_count,
            "first_release_server": calendar.first_release_server,
            "last_release_server": calendar.last_release_server,
            "duplicate_value_ids": calendar.duplicate_value_ids,
            "with_actual": calendar.with_actual,
            "with_forecast": calendar.with_forecast,
            "with_previous": calendar.with_previous,
            "with_revised_previous": calendar.with_revised_previous,
            "mapped_series": macro,
        },
        "two_year_yields": {
            "status": "PASS_AS_CONFIRMATION_PROXY_WITH_REVISION_RISK",
            "reason": (
                "Six official daily series cover the target history. Files are "
                "current archive snapshots rather than vintage market databases; "
                "a one-business-day 12:00 UTC lag is imposed."
            ),
            "audit_path": str(yield_evidence_path),
            "audit_sha256": file_sha256(yield_evidence_path),
            "currencies": yield_currencies,
        },
        "fx_prices": {
            "status": "PASS_FROM_COMMON_M15_START",
            "provider": "Exness MT5 account history",
            "pairs": price,
            "target_start": "2017-01-01",
            "qualified_common_start": common_start,
            "excluded_history_reason": (
                "Broker returned D1 bars through November 2020, H1 bars through "
                "May 2021, and a partial transition in June 2021 under an M15 request."
            ),
        },
        "execution_inputs": {
            "status": "PASS_WITH_INTRADAY_ROLLOVER_EXCLUSION",
            "recorded_bar_spread": True,
            "raw_commission_usd_per_lot_per_side": 3.5,
            "historical_swap_available": False,
            "resolution": "force flat at 20:45 UTC before the earliest rollover",
            "real_tick_overlap": tick_evidence.get("status"),
            "real_tick_audit_path": str(tick_evidence_path),
            "real_tick_audit_sha256": file_sha256(tick_evidence_path),
        },
        "frozen_common_window": {
            "start_utc": f"{common_start}T00:00:00Z",
            "cutoff_utc": "2026-09-11T13:00:00Z",
            "selection_basis": (
                "common broker-native M15 density and mandatory features"
            ),
        },
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(output_path, payload)
    return payload
