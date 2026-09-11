"""Command-line entry points for reproducible research operations."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from fx_fundamental_technical.calendar_export import inventory_calendar
from fx_fundamental_technical.exit_research import run_phase08
from fx_fundamental_technical.mt5_history import run_price_source_audit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fx-hybrid")
    commands = parser.add_subparsers(dest="command", required=True)

    calendar = commands.add_parser("calendar-inventory")
    calendar.add_argument("path", type=Path)

    prices = commands.add_parser("price-source-audit")
    prices.add_argument("--terminal", type=Path, required=True)
    prices.add_argument("--start", required=True)
    prices.add_argument("--end", required=True)
    prices.add_argument("--raw-root", type=Path, default=Path("data/raw/mt5_m15"))
    prices.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/phase01/price_source_audit.json"),
    )
    prices.add_argument(
        "symbols",
        nargs="+",
        default=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"],
    )

    exit_research = commands.add_parser("phase08-exit-research")
    exit_research.add_argument(
        "--contract",
        type=Path,
        default=Path("config/exit_research_v0_1.json"),
    )
    exit_research.add_argument(
        "--execution",
        type=Path,
        default=Path("config/execution_model_v0_1.json"),
    )
    exit_research.add_argument(
        "--bias-freeze",
        type=Path,
        default=Path("evidence/phase03/bias_freeze.json"),
    )
    exit_research.add_argument(
        "--bias",
        type=Path,
        default=Path("data/canonical/phase03/pair_bias.parquet"),
    )
    exit_research.add_argument(
        "--prices",
        type=Path,
        default=Path("data/canonical/phase02/m15_prices.parquet"),
    )
    exit_research.add_argument(
        "--events",
        type=Path,
        default=Path("data/canonical/phase02/high_impact_events.parquet"),
    )
    exit_research.add_argument(
        "--signals",
        type=Path,
        default=Path("data/canonical/phase04/t3_signals.parquet"),
    )
    exit_research.add_argument(
        "--control-ledger",
        type=Path,
        default=Path("data/canonical/phase05/f2_t3_ledger.parquet"),
    )
    exit_research.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/canonical/phase08"),
    )
    exit_research.add_argument(
        "--evidence",
        type=Path,
        default=Path("evidence/phase08/summary.json"),
    )
    return parser


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    command = cast(str, arguments.command)
    if command == "calendar-inventory":
        print(json.dumps(asdict(inventory_calendar(arguments.path)), indent=2))
        return 0
    if command == "price-source-audit":
        result = run_price_source_audit(
            arguments.terminal,
            arguments.symbols,
            _utc(arguments.start),
            _utc(arguments.end),
            arguments.raw_root,
            arguments.evidence,
        )
        print(json.dumps(result, indent=2))
        return 0
    if command == "phase08-exit-research":
        result = run_phase08(
            arguments.contract,
            arguments.execution,
            arguments.bias_freeze,
            arguments.bias,
            arguments.prices,
            arguments.events,
            arguments.signals,
            arguments.control_ledger,
            arguments.output_root,
            arguments.evidence,
        )
        print(json.dumps(result, indent=2, default=str))
        return 0
    raise AssertionError(f"unhandled command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
