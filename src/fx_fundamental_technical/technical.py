"""Mechanical M15 entries and bid/ask-aware Exness Raw backtest engine."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.clocks import fx_day_id
from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)

TECHNICAL_ENGINE_VERSION = "mechanical-m15-v0.1"
PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD")


class TechnicalEngineError(ValueError):
    """Raised when technical data or execution invariants fail."""


@dataclass(frozen=True)
class CandidateSignal:
    strategy: str
    pair: str
    direction: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    atr: float


def _object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise TechnicalEngineError(f"expected JSON object: {path}")
    return cast(dict[str, object], decoded)


def prepare_bars(frame: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    """Add completed-bar ATR and both registered DST-aware session clocks."""

    bars = frame.sort_values("time").copy()
    bars["time"] = pd.to_datetime(bars["time"], utc=True)
    prior_close = bars["close"].shift(1)
    true_range = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - prior_close).abs(),
            (bars["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    # ATR attached to a signal bar is based on that completed bar and all prior
    # bars. Entry remains the following M15 open.
    bars["atr"] = true_range.rolling(atr_period, min_periods=atr_period).mean()
    london = bars["time"].dt.tz_convert("Europe/London")
    new_york = bars["time"].dt.tz_convert("America/New_York")
    bars["london_date"] = london.dt.date
    bars["london_minute"] = london.dt.hour * 60 + london.dt.minute
    bars["fx_day"] = (new_york - pd.Timedelta(hours=17)).dt.date
    return bars.reset_index(drop=True)


def _next_entry(bars: pd.DataFrame, index: int) -> tuple[pd.Timestamp, float] | None:
    if index + 1 >= len(bars) or pd.isna(bars.iloc[index]["atr"]):
        return None
    signal_time = cast(pd.Timestamp, bars.iloc[index]["time"]) + pd.Timedelta(
        minutes=15
    )
    next_time = cast(pd.Timestamp, bars.iloc[index + 1]["time"])
    if next_time != signal_time:
        return None
    london = next_time.tz_convert("Europe/London")
    minute = london.hour * 60 + london.minute
    if not 480 <= minute < 1020:
        return None
    return next_time, float(bars.iloc[index]["atr"])


def signals_t2(bars: pd.DataFrame, pair: str) -> list[CandidateSignal]:
    """First close outside each completed 08:00-09:00 London range."""

    signals: list[CandidateSignal] = []
    for _, day in bars.groupby("london_date", sort=True):
        opening = day[(day["london_minute"] >= 480) & (day["london_minute"] < 540)]
        eligible = day[(day["london_minute"] >= 540) & (day["london_minute"] < 1020)]
        if len(opening) != 4 or eligible.empty:
            continue
        high, low = float(opening["high"].max()), float(opening["low"].min())
        breakouts = eligible[(eligible["close"] > high) | (eligible["close"] < low)]
        if breakouts.empty:
            continue
        index = int(breakouts.index[0])
        direction = 1 if float(bars.loc[index, "close"]) > high else -1
        entry = _next_entry(bars, index)
        if entry is not None:
            signals.append(CandidateSignal("T2", pair, direction, entry[0], *entry))
    return signals


def signals_t3(bars: pd.DataFrame, pair: str) -> list[CandidateSignal]:
    """First London-session completed close that crosses anchored tick VWAP."""

    signals: list[CandidateSignal] = []
    for _, day in bars.groupby("london_date", sort=True):
        session = day[
            (day["london_minute"] >= 480) & (day["london_minute"] < 1020)
        ].copy()
        if len(session) < 2 or (session["tick_volume"] <= 0).any():
            continue
        typical = (session["high"] + session["low"] + session["close"]) / 3.0
        volume = session["tick_volume"].astype(float)
        session["vwap"] = (typical * volume).cumsum() / volume.cumsum()
        prior_side = session["close"].shift(1) - session["vwap"].shift(1)
        current_side = session["close"] - session["vwap"]
        crosses = session[
            ((prior_side < 0) & (current_side > 0))
            | ((prior_side > 0) & (current_side < 0))
        ]
        if crosses.empty:
            continue
        index = int(crosses.index[0])
        direction = 1 if float(current_side.loc[index]) > 0 else -1
        entry = _next_entry(bars, index)
        if entry is not None:
            signals.append(CandidateSignal("T3", pair, direction, entry[0], *entry))
    return signals


def signals_t1(
    bars: pd.DataFrame, pair: str, retest_bars: int
) -> list[CandidateSignal]:
    """First valid H1 prior-FX-day breakout and M15 retest each FX day."""

    day_ranges = bars.groupby("fx_day").agg(
        day_high=("high", "max"), day_low=("low", "min")
    )
    day_ranges["prior_high"] = day_ranges["day_high"].shift(1)
    day_ranges["prior_low"] = day_ranges["day_low"].shift(1)
    work = bars.join(day_ranges[["prior_high", "prior_low"]], on="fx_day")
    work["hour"] = work["time"].dt.floor("h")
    hourly = (
        work.groupby(["fx_day", "hour"], as_index=False)
        .agg(
            close=("close", "last"),
            prior_high=("prior_high", "last"),
            prior_low=("prior_low", "last"),
        )
        .dropna()
        .sort_values("hour")
    )
    signals: list[CandidateSignal] = []
    for fx_day, hours in hourly.groupby("fx_day", sort=True):
        day_work = work[work["fx_day"] == fx_day]
        valid: list[CandidateSignal] = []
        for hour in hours.itertuples(index=False):
            direction = (
                1
                if float(hour.close) > float(hour.prior_high)
                else -1
                if float(hour.close) < float(hour.prior_low)
                else 0
            )
            if direction == 0:
                continue
            completion = cast(pd.Timestamp, hour.hour) + pd.Timedelta(hours=1)
            future = day_work[day_work["time"] >= completion].head(retest_bars)
            boundary = float(hour.prior_high if direction > 0 else hour.prior_low)
            retests = future[
                ((future["low"] <= boundary) & (future["close"] > boundary))
                if direction > 0
                else ((future["high"] >= boundary) & (future["close"] < boundary))
            ]
            if retests.empty:
                continue
            index = int(retests.index[0])
            if not 480 <= int(work.loc[index, "london_minute"]) < 1020:
                continue
            entry = _next_entry(work, index)
            if entry is not None:
                valid.append(CandidateSignal("T1", pair, direction, entry[0], *entry))
                break
        if valid:
            signals.append(min(valid, key=lambda item: item.entry_time))
    return signals


def generate_signals(
    prices: pd.DataFrame, atr_period: int, retest_bars: int
) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """Generate all three technical candidates without looking at bias."""

    prepared: dict[str, pd.DataFrame] = {}
    by_strategy: dict[str, list[CandidateSignal]] = {"T1": [], "T2": [], "T3": []}
    for pair in PAIRS:
        bars = prepare_bars(prices[prices["pair"] == pair], atr_period)
        prepared[pair] = bars
        by_strategy["T1"].extend(signals_t1(bars, pair, retest_bars))
        by_strategy["T2"].extend(signals_t2(bars, pair))
        by_strategy["T3"].extend(signals_t3(bars, pair))
    frames = {
        name: pd.DataFrame([signal.__dict__ for signal in signals]).sort_values(
            ["entry_time", "pair"]
        )
        for name, signals in by_strategy.items()
    }
    return frames, prepared


def _in_news_blackout(
    pair: str, entry_time: pd.Timestamp, events: pd.DataFrame, minutes: int
) -> bool:
    currencies = {pair[:3], pair[3:]}
    window = pd.Timedelta(minutes=minutes)
    nearby = events[
        events["currency"].isin(currencies)
        & (events["released_at_utc"] >= entry_time - window)
        & (events["released_at_utc"] <= entry_time + window)
    ]
    return not nearby.empty


def _usd_value(
    price_delta: float, pair: str, conversion_price: float, size: float
) -> float:
    quote_value = price_delta * size
    return quote_value if pair[3:] == "USD" else quote_value / conversion_price


def _simulate_position(
    signal: pd.Series,
    bars: pd.DataFrame,
    point: float,
    contract_size: float,
    commission_side: float,
    slippage_points: int,
    target_r: float,
) -> dict[str, object] | None:
    matches = bars.index[bars["time"] == signal["entry_time"]]
    if len(matches) != 1:
        return None
    entry_index = int(matches[0])
    entry_bar = bars.loc[entry_index]
    direction = int(signal["direction"])
    spread_entry = float(entry_bar["spread"]) * point
    slip = slippage_points * point
    bid_open = float(entry_bar["open"])
    entry_price = bid_open + spread_entry + slip if direction > 0 else bid_open - slip
    atr = float(signal["atr"])
    if not math.isfinite(atr) or atr <= 0:
        return None
    stop = entry_price - direction * atr
    target = entry_price + direction * target_r * atr
    entry_date = cast(pd.Timestamp, signal["entry_time"]).date()
    rollover = pd.Timestamp(f"{entry_date.isoformat()}T20:45:00Z")
    maximum = cast(pd.Timestamp, signal["entry_time"]) + pd.Timedelta(hours=24)
    deadline = min(rollover, maximum)
    exit_price: float | None = None
    exit_time: pd.Timestamp | None = None
    exit_reason = "NO_EXIT"
    spread_exit = 0.0
    for index in range(entry_index, len(bars)):
        bar = bars.loc[index]
        time = cast(pd.Timestamp, bar["time"])
        if time >= deadline:
            spread_exit = float(bar["spread"]) * point
            exit_price = (
                float(bar["open"]) - slip
                if direction > 0
                else float(bar["open"]) + spread_exit + slip
            )
            exit_time = time
            exit_reason = "ROLLOVER_FLAT" if deadline == rollover else "MAX_HOLD"
            break
        spread_exit = float(bar["spread"]) * point
        if direction > 0:
            hit_stop = float(bar["low"]) <= stop
            hit_target = float(bar["high"]) >= target
        else:
            ask_high = float(bar["high"]) + spread_exit
            ask_low = float(bar["low"]) + spread_exit
            hit_stop = ask_high >= stop
            hit_target = ask_low <= target
        if hit_stop:
            if direction > 0:
                exit_price = min(stop, float(bar["open"])) - slip
            else:
                ask_open = float(bar["open"]) + spread_exit
                exit_price = max(stop, ask_open) + slip
            exit_time = time + pd.Timedelta(minutes=15)
            exit_reason = "STOP"
            break
        if hit_target:
            exit_price = target - direction * slip
            exit_time = time + pd.Timedelta(minutes=15)
            exit_reason = "TARGET"
            break
    if exit_price is None or exit_time is None:
        return None
    risk_usd_per_lot = abs(
        _usd_value(atr, str(signal["pair"]), entry_price, contract_size)
    )
    pnl_usd_per_lot = _usd_value(
        direction * (exit_price - entry_price),
        str(signal["pair"]),
        exit_price,
        contract_size,
    )
    commission_r = (2.0 * commission_side) / risk_usd_per_lot
    price_r = pnl_usd_per_lot / risk_usd_per_lot
    spread_cost_r = (
        abs(
            _usd_value(
                spread_entry if direction > 0 else spread_exit,
                str(signal["pair"]),
                entry_price,
                contract_size,
            )
        )
        / risk_usd_per_lot
    )
    slippage_cost_r = (
        abs(_usd_value(2 * slip, str(signal["pair"]), entry_price, contract_size))
        / risk_usd_per_lot
    )
    return {
        "strategy": str(signal["strategy"]),
        "pair": str(signal["pair"]),
        "direction": "LONG" if direction > 0 else "SHORT",
        "signal_time": signal["signal_time"],
        "entry_time": signal["entry_time"],
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "stop_price": stop,
        "target_price": target,
        "atr": atr,
        "exit_reason": exit_reason,
        "price_r_before_commission": price_r,
        "commission_r": commission_r,
        "spread_cost_r_estimate": spread_cost_r,
        "slippage_cost_r_estimate": slippage_cost_r,
        "net_r": price_r - commission_r,
        "fx_day": fx_day_id(cast(pd.Timestamp, signal["entry_time"])).isoformat(),
    }


def simulate_portfolio(
    signals: pd.DataFrame,
    prepared: dict[str, pd.DataFrame],
    events: pd.DataFrame,
    config: dict[str, object],
    *,
    slippage_points: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute signals chronologically with blackout and portfolio constraints."""

    point_map = cast(dict[str, float], config["point_by_pair"])
    active: list[dict[str, object]] = []
    used_days: set[tuple[str, str]] = set()
    trades: list[dict[str, object]] = []
    rejections: list[dict[str, object]] = []
    for _, signal in signals.sort_values(["entry_time", "pair"]).iterrows():
        entry_time = cast(pd.Timestamp, signal["entry_time"])
        active = [
            trade
            for trade in active
            if cast(pd.Timestamp, trade["exit_time"]) > entry_time
        ]
        pair = str(signal["pair"])
        day = fx_day_id(entry_time).isoformat()
        reason: str | None = None
        if _in_news_blackout(
            pair, entry_time, events, int(cast(int, config["news_blackout_minutes"]))
        ):
            reason = "NEWS_BLACKOUT"
        elif (pair, day) in used_days:
            reason = "PAIR_DAY_LIMIT"
        elif any(str(trade["pair"]) == pair for trade in active):
            reason = "PAIR_ALREADY_OPEN"
        elif len(active) >= int(cast(int, config["maximum_open_positions"])):
            reason = "PORTFOLIO_LIMIT"
        if reason is not None:
            rejections.append(
                {
                    "strategy": signal["strategy"],
                    "pair": pair,
                    "entry_time": entry_time,
                    "reason": reason,
                }
            )
            continue
        trade = _simulate_position(
            signal,
            prepared[pair],
            float(point_map[pair]),
            float(cast(float, config["contract_size"])),
            float(cast(float, config["commission_usd_per_lot_per_side"])),
            slippage_points,
            float(cast(float, config["target_r_multiple"])),
        )
        if trade is None:
            rejections.append(
                {
                    "strategy": signal["strategy"],
                    "pair": pair,
                    "entry_time": entry_time,
                    "reason": "UNEXECUTABLE",
                }
            )
            continue
        trades.append(trade)
        active.append(trade)
        used_days.add((pair, day))
    return pd.DataFrame(trades), pd.DataFrame(rejections)


def _maximum_drawdown(values: pd.Series) -> float:
    cumulative = values.cumsum()
    peaks = cumulative.cummax().clip(lower=0.0)
    return float((peaks - cumulative).max()) if not cumulative.empty else 0.0


def metrics(ledger: pd.DataFrame) -> dict[str, object]:
    if ledger.empty:
        return {"trades": 0, "expectancy_r": None, "net_r": 0.0}
    net = ledger["net_r"].astype(float)
    wins, losses = net[net > 0], net[net <= 0]
    gross_profit, gross_loss = float(wins.sum()), abs(float(losses.sum()))
    return {
        "trades": len(ledger),
        "win_rate": float((net > 0).mean()),
        "expectancy_r": float(net.mean()),
        "net_r": float(net.sum()),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
        "average_win_r": float(wins.mean()) if not wins.empty else None,
        "average_loss_r": float(losses.mean()) if not losses.empty else None,
        "maximum_drawdown_r": _maximum_drawdown(net),
        "median_holding_hours": float(
            (
                (ledger["exit_time"] - ledger["entry_time"]).dt.total_seconds() / 3600
            ).median()
        ),
        "commission_r": float(ledger["commission_r"].sum()),
        "estimated_spread_r": float(ledger["spread_cost_r_estimate"].sum()),
        "exit_reasons": {
            str(key): int(value)
            for key, value in ledger["exit_reason"].value_counts().items()
        },
    }


def run_phase04(
    execution_config_path: Path,
    price_path: Path,
    event_path: Path,
    output_root: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Run technical-only development/validation baselines; locked data is closed."""

    config = _object(execution_config_path)
    if bool(config.get("locked_outcomes_allowed")):
        raise TechnicalEngineError("Phase 04 must keep locked outcomes closed")
    prices = pd.read_parquet(price_path)
    events = pd.read_parquet(event_path)
    end = pd.Timestamp(str(config["validation_end_exclusive_utc"]))
    prices = prices[prices["time"] < end].copy()
    events = events[events["released_at_utc"] < end].copy()
    signals, prepared = generate_signals(
        prices,
        int(cast(int, config["atr_period"])),
        int(cast(int, config["t1_retest_bars"])),
    )
    development_end = pd.Timestamp(str(config["development_end_exclusive_utc"]))
    output_root.mkdir(parents=True, exist_ok=True)
    strategies: dict[str, object] = {}
    frozen_files: list[dict[str, object]] = []
    for name in ("T1", "T2", "T3"):
        signal_path = output_root / f"{name.lower()}_signals.parquet"
        signals[name].to_parquet(signal_path, index=False)
        ledger, rejections = simulate_portfolio(signals[name], prepared, events, config)
        if not ledger.empty:
            ledger["split"] = ledger["entry_time"].apply(
                lambda value: "DEVELOPMENT" if value < development_end else "VALIDATION"
            )
            if (ledger["entry_time"] >= end).any():
                raise TechnicalEngineError("locked outcome leaked into Phase 04")
        ledger_path = output_root / f"{name.lower()}_ledger.parquet"
        rejection_path = output_root / f"{name.lower()}_rejections.parquet"
        ledger.to_parquet(ledger_path, index=False)
        rejections.to_parquet(rejection_path, index=False)
        split_metrics = {
            split.lower(): metrics(group) for split, group in ledger.groupby("split")
        }
        strategies[name] = {
            "signals": len(signals[name]),
            "executed": len(ledger),
            "rejections": len(rejections),
            "all_open_slices": metrics(ledger),
            "by_split": split_metrics,
            "by_pair": {
                str(pair): metrics(group) for pair, group in ledger.groupby("pair")
            },
        }
        for artifact_name, path in (
            (f"{name}_signals", signal_path),
            (f"{name}_ledger", ledger_path),
            (f"{name}_rejections", rejection_path),
        ):
            frozen_files.append(
                {
                    "name": artifact_name,
                    "path": str(path),
                    "sha256": file_sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "engine_version": TECHNICAL_ENGINE_VERSION,
        "status": "PASS_BASELINES_COMPLETE",
        "execution_config": str(execution_config_path),
        "execution_config_sha256": file_sha256(execution_config_path),
        "sample_end_exclusive_utc": end.isoformat(),
        "locked_outcomes_accessed": False,
        "strategies": strategies,
        "files": frozen_files,
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(evidence_path, payload)
    return payload
