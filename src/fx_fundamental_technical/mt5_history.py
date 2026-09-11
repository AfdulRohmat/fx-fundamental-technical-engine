"""Broker-native MT5 history extraction without any trading interface."""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)

EXTRACTOR_VERSION = "fx-hybrid-mt5-history-v0.1"
BAR_COLUMNS = (
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)


class HistoryError(RuntimeError):
    """Raised when MT5 history violates the source qualification contract."""


class HistoryApi(Protocol):
    TIMEFRAME_M15: int

    def initialize(self, path: str, *, timeout: int) -> bool: ...

    def shutdown(self) -> None: ...

    def last_error(self) -> tuple[int, str]: ...

    def terminal_info(self) -> object | None: ...

    def account_info(self) -> object | None: ...

    def symbols_get(self) -> Iterable[object] | None: ...

    def symbol_select(self, name: str, enable: bool) -> bool: ...

    def symbol_info(self, name: str) -> object | None: ...

    def copy_rates_range(
        self, symbol: str, timeframe: int, start: datetime, end: datetime
    ) -> object | None: ...


def vendor_api() -> HistoryApi:
    try:
        module = importlib.import_module("MetaTrader5")
    except ImportError as exc:
        raise HistoryError("MetaTrader5 package is unavailable") from exc
    return cast(HistoryApi, module)


def _text(record: object, field: str) -> str:
    return str(getattr(record, field, ""))


def _integer(record: object, field: str) -> int:
    return int(cast(int | str, getattr(record, field, 0)))


def resolve_symbols(
    requested: Sequence[str], available: Iterable[str]
) -> dict[str, str]:
    names = tuple(dict.fromkeys(name for name in available if name))
    resolved: dict[str, str] = {}
    for symbol in requested:
        target = symbol.upper()
        exact = [name for name in names if name.upper() == target]
        candidates = exact or [
            name for name in names if name.upper().startswith(target)
        ]
        if len(candidates) != 1:
            raise HistoryError(
                f"expected exactly one broker symbol for {symbol}, got {candidates}"
            )
        resolved[symbol] = candidates[0]
    return resolved


def rates_frame(raw: object, symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(raw)
    missing = set(BAR_COLUMNS) - set(frame.columns)
    if frame.empty or missing:
        raise HistoryError(
            f"{symbol} returned no usable M15 bars; missing={sorted(missing)}"
        )
    frame = frame.loc[:, BAR_COLUMNS].copy()
    frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    if not frame["time"].is_monotonic_increasing:
        raise HistoryError(f"{symbol} M15 timestamps are not sorted")
    return frame


def summarize_bars(frame: pd.DataFrame, symbol: str) -> dict[str, object]:
    duplicate_times = int(frame["time"].duplicated().sum())
    inconsistent_ohlc = int(
        (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
        ).sum()
    )
    nonpositive_ohlc = int(
        (frame[["open", "high", "low", "close"]] <= 0).any(axis=1).sum()
    )
    spread = pd.to_numeric(frame["spread"], errors="coerce")
    tick_volume = pd.to_numeric(frame["tick_volume"], errors="coerce")
    return {
        "symbol": symbol,
        "rows": len(frame),
        "first_bar_utc": frame["time"].iloc[0].isoformat(),
        "last_bar_utc": frame["time"].iloc[-1].isoformat(),
        "duplicate_timestamps": duplicate_times,
        "inconsistent_ohlc_rows": inconsistent_ohlc,
        "nonpositive_ohlc_rows": nonpositive_ohlc,
        "positive_tick_volume_fraction": float((tick_volume > 0).mean()),
        "positive_spread_fraction": float((spread > 0).mean()),
        "spread_points_median": float(spread.median()),
        "spread_points_p95": float(spread.quantile(0.95)),
    }


def run_price_source_audit(
    terminal_executable: Path,
    requested_symbols: Sequence[str],
    start: datetime,
    end: datetime,
    raw_root: Path,
    evidence_path: Path,
    *,
    timeout_seconds: int = 60,
    api: HistoryApi | None = None,
) -> dict[str, object]:
    """Extract M15 source data and record coverage without calculating returns."""

    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if start >= end:
        raise ValueError("start must precede end")
    executable = terminal_executable.resolve()
    if not executable.is_file():
        raise HistoryError(f"terminal not found: {executable}")
    mt5 = api or vendor_api()
    if not mt5.initialize(str(executable), timeout=timeout_seconds * 1000):
        raise HistoryError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        if terminal is None or not bool(getattr(terminal, "connected", False)):
            raise HistoryError("terminal is not connected")
        if account is None:
            raise HistoryError("terminal has no authorized account")
        symbols = mt5.symbols_get()
        if symbols is None:
            raise HistoryError(f"symbols_get failed: {mt5.last_error()}")
        resolved = resolve_symbols(
            requested_symbols, (_text(item, "name") for item in symbols)
        )

        raw_root.mkdir(parents=True, exist_ok=True)
        summaries: list[dict[str, object]] = []
        files: list[dict[str, object]] = []
        for requested, broker_symbol in resolved.items():
            if not mt5.symbol_select(broker_symbol, True):
                raise HistoryError(f"symbol_select failed for {broker_symbol}")
            raw = mt5.copy_rates_range(
                broker_symbol,
                mt5.TIMEFRAME_M15,
                start.astimezone(UTC),
                end.astimezone(UTC),
            )
            if raw is None:
                raise HistoryError(
                    f"copy_rates_range failed for {broker_symbol}: {mt5.last_error()}"
                )
            frame = rates_frame(raw, broker_symbol)
            output = raw_root / f"{requested.lower()}_m15.parquet"
            frame.to_parquet(output, index=False)
            summaries.append(summarize_bars(frame, requested))
            files.append(
                {
                    "requested_symbol": requested,
                    "broker_symbol": broker_symbol,
                    "path": str(output),
                    "sha256": file_sha256(output),
                    "bytes": output.stat().st_size,
                }
            )

        payload: dict[str, object] = {
            "schema_version": "1.0",
            "extractor_version": EXTRACTOR_VERSION,
            "status": "EXTRACTED_FOR_SOURCE_QUALIFICATION",
            "observed_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "requested_start_utc": start.astimezone(UTC).isoformat(),
            "requested_end_utc": end.astimezone(UTC).isoformat(),
            "safety": {
                "read_only": True,
                "returns_calculated": False,
                "pnl_calculated": False,
                "credentials_persisted": False,
            },
            "terminal": {
                "build": _integer(terminal, "build"),
                "max_bars": _integer(terminal, "maxbars"),
            },
            "broker": {
                "company": _text(account, "company"),
                "server": _text(account, "server"),
                "currency": _text(account, "currency"),
            },
            "symbols": summaries,
            "raw_files": files,
        }
        payload["summary_sha256"] = canonical_sha256(payload)
        write_json_atomic(evidence_path, payload)
        return payload
    finally:
        mt5.shutdown()
