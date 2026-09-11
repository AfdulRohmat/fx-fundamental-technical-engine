"""Read-only current-period real-tick availability probe for MT5 parity work."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.evidence import canonical_sha256, write_json_atomic
from fx_fundamental_technical.mt5_history import HistoryError


def run_tick_probe(
    terminal_executable: Path,
    symbols: list[str],
    start: datetime,
    end: datetime,
    output_path: Path,
) -> dict[str, object]:
    """Record whether recent bid/ask ticks can support later execution parity."""

    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("tick-probe interval must be ordered and timezone-aware")
    mt5: Any = importlib.import_module("MetaTrader5")
    executable = terminal_executable.resolve()
    if not mt5.initialize(str(executable), timeout=60_000):
        raise HistoryError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        probes: list[dict[str, object]] = []
        for symbol in symbols:
            raw = mt5.copy_ticks_range(
                symbol,
                start.astimezone(UTC),
                end.astimezone(UTC),
                mt5.COPY_TICKS_ALL,
            )
            frame = pd.DataFrame(raw)
            usable = not frame.empty and {"time_msc", "bid", "ask"}.issubset(
                frame.columns
            )
            probes.append(
                {
                    "symbol": symbol,
                    "ticks": len(frame),
                    "usable_bid_ask": usable,
                    "first_time_msc": (
                        int(frame["time_msc"].iloc[0]) if usable else None
                    ),
                    "last_time_msc": (
                        int(frame["time_msc"].iloc[-1]) if usable else None
                    ),
                }
            )
        payload: dict[str, object] = {
            "schema_version": "1.0",
            "status": (
                "PASS_CURRENT_OVERLAP_ONLY"
                if all(bool(item["usable_bid_ask"]) for item in probes)
                else "FAIL"
            ),
            "start_utc": start.astimezone(UTC).isoformat(),
            "end_utc": end.astimezone(UTC).isoformat(),
            "read_only": True,
            "historical_coverage_claimed": False,
            "probes": probes,
        }
        payload["summary_sha256"] = canonical_sha256(payload)
        write_json_atomic(output_path, payload)
        return payload
    finally:
        mt5.shutdown()
