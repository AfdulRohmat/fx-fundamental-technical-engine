"""Pre-registered Phase 08 exit-asymmetry research for F2_T3."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from statistics import mean
from typing import cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.clocks import fx_day_id
from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)
from fx_fundamental_technical.fundamental_bias import verify_bias_freeze
from fx_fundamental_technical.hybrid import align_signals_to_bias
from fx_fundamental_technical.technical import (
    PAIRS,
    _in_news_blackout,
    _usd_value,
    metrics,
    prepare_bars,
)

EXIT_RESEARCH_ENGINE_VERSION = "f2-t3-vwap-exit-v0.1"


class ExitResearchError(ValueError):
    """Raised when an exit experiment violates its frozen contract."""


def _object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise ExitResearchError(f"expected JSON object: {path}")
    return cast(dict[str, object], decoded)


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExitResearchError(f"expected numeric value, got {value!r}")
    return float(value)


def add_london_vwap(bars: pd.DataFrame) -> pd.DataFrame:
    """Add the causal London-session VWAP and freeze it after 17:00 London."""

    result = bars.copy()
    result["session_vwap"] = np.nan
    session_mask = (result["london_minute"] >= 480) & (result["london_minute"] < 1020)
    session = result.loc[session_mask]
    positive = session["tick_volume"].astype(float) > 0
    valid_dates = set(
        session.loc[positive]
        .groupby("london_date")["tick_volume"]
        .count()
        .loc[
            lambda counts: (
                counts == session.groupby("london_date")["tick_volume"].count()
            )
        ]
        .index
    )
    valid_mask = session["london_date"].isin(valid_dates)
    valid = session.loc[valid_mask]
    if not valid.empty:
        typical = (valid["high"] + valid["low"] + valid["close"]) / 3.0
        volume = valid["tick_volume"].astype(float)
        numerator = (typical * volume).groupby(valid["london_date"]).cumsum()
        denominator = volume.groupby(valid["london_date"]).cumsum()
        result.loc[valid.index, "session_vwap"] = numerator / denominator
    result["session_vwap"] = result.groupby("london_date")["session_vwap"].ffill()
    return result


def _deadline(signal: pd.Series) -> tuple[pd.Timestamp, str]:
    entry_time = cast(pd.Timestamp, signal["entry_time"])
    rollover = pd.Timestamp(f"{entry_time.date().isoformat()}T20:45:00Z")
    maximum = entry_time + pd.Timedelta(hours=24)
    bias_exit = signal.get("bias_exit_time")
    bias_deadline = (
        cast(pd.Timestamp, bias_exit)
        if bias_exit is not None and pd.notna(bias_exit)
        else maximum
    )
    deadline = min(rollover, maximum, bias_deadline)
    reason = (
        "BIAS_FLIP"
        if deadline == bias_deadline and bias_deadline < min(rollover, maximum)
        else "ROLLOVER_FLAT"
        if deadline == rollover
        else "MAX_HOLD"
    )
    return deadline, reason


def _open_exit_price(
    bar: pd.Series,
    direction: int,
    point: float,
    slip: float,
) -> tuple[float, float]:
    spread = float(bar["spread"]) * point
    price = (
        float(bar["open"]) - slip
        if direction > 0
        else float(bar["open"]) + spread + slip
    )
    return price, spread


def _simulate_vwap_position(
    signal: pd.Series,
    bars: pd.DataFrame,
    point: float,
    contract_size: float,
    commission_side: float,
    slippage_points: int,
    *,
    invalidation_delay_bars: int = 0,
) -> dict[str, object] | None:
    """Execute one no-target position with a completed-close VWAP exit."""

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
    deadline, deadline_reason = _deadline(signal)
    pending_exit_index: int | None = None
    exit_price: float | None = None
    exit_time: pd.Timestamp | None = None
    exit_reason = "NO_EXIT"
    spread_exit = 0.0
    maximum_favorable_r = 0.0
    maximum_adverse_r = 0.0
    threshold_times: dict[int, pd.Timestamp] = {}

    for index in range(entry_index, len(bars)):
        bar = bars.loc[index]
        time = cast(pd.Timestamp, bar["time"])
        if time >= deadline:
            exit_price, spread_exit = _open_exit_price(bar, direction, point, slip)
            exit_time = time
            exit_reason = deadline_reason
            break
        if pending_exit_index is not None and index >= pending_exit_index:
            exit_price, spread_exit = _open_exit_price(bar, direction, point, slip)
            exit_time = time
            exit_reason = (
                "VWAP_INVALIDATION"
                if invalidation_delay_bars == 0
                else "VWAP_INVALIDATION_DELAY_1"
            )
            break

        spread_exit = float(bar["spread"]) * point
        if direction > 0:
            hit_stop = float(bar["low"]) <= stop
        else:
            hit_stop = float(bar["high"]) + spread_exit >= stop
        if hit_stop:
            if direction > 0:
                exit_price = min(stop, float(bar["open"])) - slip
            else:
                ask_open = float(bar["open"]) + spread_exit
                exit_price = max(stop, ask_open) + slip
            exit_time = time + pd.Timedelta(minutes=15)
            exit_reason = "STOP"
            maximum_adverse_r = max(
                maximum_adverse_r,
                direction * (entry_price - exit_price) / atr,
            )
            break

        if direction > 0:
            favorable_r = (float(bar["high"]) - entry_price) / atr
            adverse_r = (entry_price - float(bar["low"])) / atr
        else:
            ask_high = float(bar["high"]) + spread_exit
            ask_low = float(bar["low"]) + spread_exit
            favorable_r = (entry_price - ask_low) / atr
            adverse_r = (ask_high - entry_price) / atr
        maximum_favorable_r = max(maximum_favorable_r, favorable_r)
        maximum_adverse_r = max(maximum_adverse_r, adverse_r)
        for threshold in range(1, 6):
            if maximum_favorable_r >= threshold and threshold not in threshold_times:
                threshold_times[threshold] = time + pd.Timedelta(minutes=15)

        vwap = float(bar["session_vwap"])
        if math.isfinite(vwap):
            invalidated = (
                float(bar["close"]) < vwap
                if direction > 0
                else float(bar["close"]) > vwap
            )
            if invalidated:
                pending_exit_index = index + 1 + invalidation_delay_bars

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
        "strategy": "F2_T3_E1",
        "pair": str(signal["pair"]),
        "direction": "LONG" if direction > 0 else "SHORT",
        "signal_time": signal["signal_time"],
        "entry_time": signal["entry_time"],
        "exit_time": exit_time,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "stop_price": stop,
        "target_price": None,
        "atr": atr,
        "exit_reason": exit_reason,
        "price_r_before_commission": price_r,
        "commission_r": commission_r,
        "spread_cost_r_estimate": spread_cost_r,
        "slippage_cost_r_estimate": slippage_cost_r,
        "net_r": price_r - commission_r,
        "maximum_favorable_excursion_r": maximum_favorable_r,
        "maximum_adverse_excursion_r": maximum_adverse_r,
        "giveback_from_mfe_r": maximum_favorable_r - price_r,
        **{
            f"reached_{threshold}r": threshold in threshold_times
            for threshold in range(1, 6)
        },
        **{
            f"reached_{threshold}r_time": threshold_times.get(threshold, pd.NaT)
            for threshold in range(1, 6)
        },
        "fx_day": fx_day_id(cast(pd.Timestamp, signal["entry_time"])).isoformat(),
    }


def simulate_vwap_portfolio(
    signals: pd.DataFrame,
    prepared: dict[str, pd.DataFrame],
    events: pd.DataFrame,
    config: dict[str, object],
    *,
    slippage_points: int = 0,
    invalidation_delay_bars: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Execute E1 chronologically under the frozen portfolio constraints."""

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
                    "strategy": "F2_T3_E1",
                    "pair": pair,
                    "entry_time": entry_time,
                    "reason": reason,
                }
            )
            continue
        trade = _simulate_vwap_position(
            signal,
            prepared[pair],
            float(point_map[pair]),
            float(cast(float, config["contract_size"])),
            float(cast(float, config["commission_usd_per_lot_per_side"])),
            slippage_points,
            invalidation_delay_bars=invalidation_delay_bars,
        )
        if trade is None:
            rejections.append(
                {
                    "strategy": "F2_T3_E1",
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


def extended_metrics(ledger: pd.DataFrame) -> dict[str, object]:
    """Add tail and path measurements to the standard costed metrics."""

    result = metrics(ledger)
    if ledger.empty:
        return result
    net = ledger["net_r"].astype(float)
    wins = net[net > 0]
    holding_hours = (
        ledger["exit_time"] - ledger["entry_time"]
    ).dt.total_seconds() / 3600
    result.update(
        {
            "maximum_winner_r": float(net.max()),
            "return_skew": float(net.skew()),
            "net_r_percentiles": {
                str(level): float(net.quantile(level / 100))
                for level in (50, 90, 95, 99)
            },
            "top_5pct_positive_profit_share": (
                float(net.nlargest(max(1, math.ceil(len(net) * 0.05))).sum())
                / float(wins.sum())
                if not wins.empty
                else None
            ),
            "median_winner_holding_hours": (
                float(holding_hours[net > 0].median()) if not wins.empty else None
            ),
            "median_loss_holding_hours": float(holding_hours[net <= 0].median()),
        }
    )
    if "price_r_before_commission" in ledger:
        result["price_r_before_commission"] = float(
            ledger["price_r_before_commission"].astype(float).sum()
        )
    if "maximum_favorable_excursion_r" in ledger:
        mfe = ledger["maximum_favorable_excursion_r"].astype(float)
        hit_two = mfe >= 2.0
        continuation: dict[str, float | None] = {}
        for threshold in (3, 4, 5):
            continuation[f"hit_{threshold}r_given_2r"] = (
                float((mfe[hit_two] >= threshold).mean()) if hit_two.any() else None
            )
        result["path"] = {
            "median_mfe_r": float(mfe.median()),
            "median_mae_r": float(
                ledger["maximum_adverse_excursion_r"].astype(float).median()
            ),
            "hit_2r_count": int(hit_two.sum()),
            "hit_2r_fraction": float(hit_two.mean()),
            "continuation_after_2r": continuation,
            "median_giveback_r": float(
                ledger["giveback_from_mfe_r"].astype(float).median()
            ),
        }
    return result


def _group_metrics(ledger: pd.DataFrame, column: str) -> dict[str, dict[str, object]]:
    return {
        str(key): extended_metrics(group)
        for key, group in ledger.groupby(column, sort=True)
    }


def _bootstrap_expectancy(
    ledger: pd.DataFrame, block_months: int, resamples: int
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
    estimates: list[float] = []
    for _ in range(resamples):
        sample: list[float] = []
        while len(sample) < len(monthly):
            start = generator.randrange(len(monthly))
            sample.extend(
                monthly[(start + offset) % len(monthly)]
                for offset in range(block_months)
            )
        estimates.append(mean(sample[: len(monthly)]))
    estimates.sort()
    return [
        estimates[int(0.025 * (len(estimates) - 1))],
        estimates[int(0.975 * (len(estimates) - 1))],
    ]


def evaluate_promotion(
    candidate: pd.DataFrame,
    control: pd.DataFrame,
    delay: pd.DataFrame,
    stresses: dict[int, pd.DataFrame],
    gate: dict[str, object],
) -> dict[str, object]:
    """Evaluate only the checks registered before new outcomes were opened."""

    candidate_metrics = extended_metrics(candidate)
    control_metrics = extended_metrics(control)
    pair_metrics = _group_metrics(candidate, "pair")
    year_frame = candidate.assign(year=candidate["entry_time"].dt.year)
    year_metrics = _group_metrics(year_frame, "year")
    positive_pair_net = [
        _as_float(item["net_r"])
        for item in pair_metrics.values()
        if _as_float(item["net_r"]) > 0
    ]
    total_positive_pair_net = sum(positive_pair_net)
    concentration = (
        max(positive_pair_net) / total_positive_pair_net if positive_pair_net else None
    )
    interval = _bootstrap_expectancy(
        candidate,
        int(cast(int, gate["bootstrap_block_months"])),
        int(cast(int, gate["bootstrap_resamples"])),
    )
    candidate_expectancy = _as_float(candidate_metrics["expectancy_r"])
    control_expectancy = _as_float(control_metrics["expectancy_r"])
    delay_expectancy = _as_float(extended_metrics(delay)["expectancy_r"])
    stress_metrics = {
        str(points): extended_metrics(ledger) for points, ledger in stresses.items()
    }
    control_entries = set(zip(control["pair"], control["entry_time"], strict=True))
    candidate_entries = set(
        zip(candidate["pair"], candidate["entry_time"], strict=True)
    )
    overlap = len(control_entries & candidate_entries)
    checks = {
        "minimum_development_trades": len(candidate)
        >= int(cast(int, gate["minimum_development_trades"])),
        "positive_expectancy": candidate_expectancy > 0,
        "improves_control": candidate_expectancy > control_expectancy,
        "drawdown": _as_float(candidate_metrics["maximum_drawdown_r"])
        <= float(cast(float, gate["maximum_drawdown_r"])),
        "positive_pairs": len(positive_pair_net)
        >= int(cast(int, gate["minimum_positive_pairs"])),
        "positive_calendar_years": sum(
            _as_float(item["net_r"]) > 0 for item in year_metrics.values()
        )
        >= int(cast(int, gate["minimum_positive_calendar_years"])),
        "pair_concentration": concentration is not None
        and concentration
        <= float(cast(float, gate["maximum_single_pair_positive_profit_share"])),
        "positive_bootstrap_lower_bound": interval is not None and interval[0] > 0,
        "two_point_slippage": _as_float(stress_metrics["2"]["expectancy_r"]) > 0,
        "five_point_slippage": _as_float(stress_metrics["5"]["expectancy_r"])
        >= float(cast(float, gate["five_point_slippage_floor_r"])),
        "one_bar_exit_delay": delay_expectancy > 0,
    }
    return {
        "candidate_metrics": candidate_metrics,
        "control_metrics": control_metrics,
        "incremental_expectancy_r": candidate_expectancy - control_expectancy,
        "pair_metrics": pair_metrics,
        "calendar_year_metrics": year_metrics,
        "positive_pair_count": len(positive_pair_net),
        "positive_calendar_year_count": sum(
            _as_float(item["net_r"]) > 0 for item in year_metrics.values()
        ),
        "single_pair_positive_profit_share_max": concentration,
        "expectancy_block_bootstrap_95_ci_r": interval,
        "one_bar_exit_delay_metrics": extended_metrics(delay),
        "slippage_stress_metrics": stress_metrics,
        "entry_set_comparison": {
            "overlap": overlap,
            "control_only": len(control_entries - candidate_entries),
            "candidate_only": len(candidate_entries - control_entries),
            "control_overlap_fraction": overlap / len(control_entries),
        },
        "promotion_checks": checks,
        "eligible_for_locked_test": all(checks.values()),
    }


def _read_before(path: Path, time_column: str, end: pd.Timestamp) -> pd.DataFrame:
    frame = pd.read_parquet(
        path,
        filters=[(time_column, "<", end.to_pydatetime())],
    )
    if not frame.empty and (frame[time_column] >= end).any():
        raise ExitResearchError(f"locked observation leaked from {path}")
    return frame


def _write_report(path: Path, payload: dict[str, object]) -> None:
    assessment = cast(dict[str, object], payload["assessment"])
    candidate = cast(dict[str, object], assessment["candidate_metrics"])
    control = cast(dict[str, object], assessment["control_metrics"])
    checks = cast(dict[str, bool], assessment["promotion_checks"])
    path_metrics = cast(dict[str, object], candidate["path"])
    continuation = cast(dict[str, object], path_metrics["continuation_after_2r"])
    interval = cast(list[float], assessment["expectancy_block_bootstrap_95_ci_r"])
    stress = cast(dict[str, dict[str, object]], assessment["slippage_stress_metrics"])
    delay = cast(dict[str, object], assessment["one_bar_exit_delay_metrics"])
    entries = cast(dict[str, object], assessment["entry_set_comparison"])
    lines = [
        "# Phase 08 - Exit Asymmetry Development Result",
        "",
        f"Status: `{payload['status']}`. Locked outcomes accessed: `false`.",
        "",
        "## Economic comparison",
        "",
        "| Exit | Trades | Win rate | Expectancy | Net R | Max DD | PF |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| E0 fixed 2R | {control['trades']} | "
            f"{100 * _as_float(control['win_rate']):.2f}% | "
            f"{_as_float(control['expectancy_r']):+.4f}R | "
            f"{_as_float(control['net_r']):+.2f}R | "
            f"{_as_float(control['maximum_drawdown_r']):.2f}R | "
            f"{_as_float(control['profit_factor']):.3f} |"
        ),
        (
            f"| E1 VWAP invalidation | {candidate['trades']} | "
            f"{100 * _as_float(candidate['win_rate']):.2f}% | "
            f"{_as_float(candidate['expectancy_r']):+.4f}R | "
            f"{_as_float(candidate['net_r']):+.2f}R | "
            f"{_as_float(candidate['maximum_drawdown_r']):.2f}R | "
            f"{_as_float(candidate['profit_factor']):.3f} |"
        ),
        "",
        "## Winner continuation",
        "",
        f"- Reached +2R: {path_metrics['hit_2r_count']} trades "
        f"({100 * _as_float(path_metrics['hit_2r_fraction']):.2f}%).",
        (
            "- Conditional continuation after +2R: "
            f"+3R {100 * _as_float(continuation['hit_3r_given_2r'] or 0):.2f}%, "
            f"+4R {100 * _as_float(continuation['hit_4r_given_2r'] or 0):.2f}%, "
            f"+5R {100 * _as_float(continuation['hit_5r_given_2r'] or 0):.2f}%."
        ),
        f"- Maximum realized winner: {_as_float(candidate['maximum_winner_r']):+.2f}R.",
        f"- Return skew: {_as_float(candidate['return_skew']):+.3f}.",
        f"- Median MFE giveback: {_as_float(path_metrics['median_giveback_r']):.2f}R.",
        f"- Top 5% of trades supplied "
        f"{100 * _as_float(candidate['top_5pct_positive_profit_share']):.2f}% "
        "of positive profit.",
        "",
        "## Cost and stability",
        "",
        f"- Price PnL after spread but before commission: "
        f"{_as_float(candidate['price_r_before_commission']):+.2f}R; commission: "
        f"-{_as_float(candidate['commission_r']):.2f}R; net: "
        f"{_as_float(candidate['net_r']):+.2f}R.",
        f"- Positive pairs: {assessment['positive_pair_count']}/5; positive calendar "
        f"years: {assessment['positive_calendar_year_count']}/5.",
        f"- Three-month-block bootstrap 95% interval: [{interval[0]:+.4f}R, "
        f"{interval[1]:+.4f}R].",
        f"- Added slippage expectancy: +2 points "
        f"{_as_float(stress['2']['expectancy_r']):+.4f}R; +5 points "
        f"{_as_float(stress['5']['expectancy_r']):+.4f}R.",
        f"- One-bar delayed invalidation expectancy: "
        f"{_as_float(delay['expectancy_r']):+.4f}R.",
        f"- Entry overlap with E0: {entries['overlap']}/{control['trades']} "
        f"({100 * _as_float(entries['control_overlap_fraction']):.2f}%).",
        "",
        "## Frozen promotion checks",
        "",
        *[
            f"- {'PASS' if passed else 'FAIL'} - `{name}`"
            for name, passed in checks.items()
        ],
        "",
        "## Interpretation",
        "",
        (
            "E1 is frozen for one locked test. No tuning is permitted."
            if payload["status"] == "CANDIDATE_FROZEN"
            else "E1 is not promoted and the locked slice remains unopened."
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase08(
    contract_path: Path,
    execution_path: Path,
    bias_freeze_path: Path,
    bias_path: Path,
    price_path: Path,
    event_path: Path,
    signal_path: Path,
    control_ledger_path: Path,
    output_root: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Run development-only E1 research and keep locked outcomes closed."""

    contract = _object(contract_path)
    execution = _object(execution_path)
    if not bool(contract.get("registered_before_new_path_outcomes")):
        raise ExitResearchError("exit contract was not pre-registered")
    if bool(contract.get("locked_outcomes_allowed")):
        raise ExitResearchError("Phase 08 may not access locked outcomes")
    if bool(contract.get("parameter_grid_allowed")):
        raise ExitResearchError("Phase 08 forbids parameter grids")
    if contract.get("base_candidate") != "F2_T3":
        raise ExitResearchError("Phase 08 is restricted to frozen F2_T3 entries")
    verify_bias_freeze(bias_freeze_path)
    start = pd.Timestamp(str(contract["development_start_utc"]))
    end = pd.Timestamp(str(contract["development_end_exclusive_utc"]))

    prices = _read_before(price_path, "time", end)
    prices = prices[prices["time"] >= start]
    events = _read_before(event_path, "released_at_utc", end)
    bias = _read_before(bias_path, "effective_from_utc", end)
    signals = _read_before(signal_path, "entry_time", end)
    signals = signals[signals["entry_time"] >= start]
    control = _read_before(control_ledger_path, "entry_time", end)
    control = control[control["entry_time"] >= start]
    if signals.empty or control.empty:
        raise ExitResearchError("development signal or control ledger is empty")

    aligned, bias_rejections = align_signals_to_bias(signals, bias, "F2")
    prepared = {
        pair: add_london_vwap(
            prepare_bars(
                prices[prices["pair"] == pair],
                int(cast(int, execution["atr_period"])),
            )
        )
        for pair in PAIRS
    }
    primary, primary_rejections = simulate_vwap_portfolio(
        aligned, prepared, events, execution
    )
    delayed, delayed_rejections = simulate_vwap_portfolio(
        aligned,
        prepared,
        events,
        execution,
        invalidation_delay_bars=1,
    )
    gate = cast(dict[str, object], contract["promotion_gate"])
    stresses: dict[int, pd.DataFrame] = {}
    stress_rejections: dict[int, pd.DataFrame] = {}
    for points in cast(list[int], gate["stress_slippage_points"]):
        ledger, rejections = simulate_vwap_portfolio(
            aligned,
            prepared,
            events,
            execution,
            slippage_points=int(points),
        )
        stresses[int(points)] = ledger
        stress_rejections[int(points)] = rejections

    assessment = evaluate_promotion(primary, control, delayed, stresses, gate)
    eligible = bool(assessment["eligible_for_locked_test"])
    output_root.mkdir(parents=True, exist_ok=True)
    ledgers = {
        "primary": primary,
        "delay_1": delayed,
        **{f"slippage_{points}": ledger for points, ledger in stresses.items()},
    }
    files: list[dict[str, object]] = []
    for name, ledger in ledgers.items():
        output = output_root / f"e1_{name}_ledger.parquet"
        ledger.to_parquet(output, index=False)
        files.append({"name": name, "path": str(output), "sha256": file_sha256(output)})

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "engine_version": EXIT_RESEARCH_ENGINE_VERSION,
        "experiment_id": contract["experiment_id"],
        "status": "CANDIDATE_FROZEN" if eligible else "NO_PROMOTION",
        "locked_outcomes_accessed": False,
        "locked_runs_consumed": 0,
        "development_start_utc": str(start),
        "development_end_exclusive_utc": str(end),
        "signals": len(signals),
        "bias_aligned_signals": len(aligned),
        "bias_rejections": len(bias_rejections),
        "execution_rejections": {
            "primary": len(primary_rejections),
            "delay_1": len(delayed_rejections),
            **{
                f"slippage_{points}": len(rejections)
                for points, rejections in stress_rejections.items()
            },
        },
        "assessment": assessment,
        "files": files,
        "input_hashes": {
            "contract": file_sha256(contract_path),
            "execution": file_sha256(execution_path),
            "bias_freeze": file_sha256(bias_freeze_path),
            "bias": file_sha256(bias_path),
            "prices": file_sha256(price_path),
            "events": file_sha256(event_path),
            "signals": file_sha256(signal_path),
            "control_ledger": file_sha256(control_ledger_path),
        },
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(evidence_path, payload)
    _write_report(evidence_path.parent / "REPORT.md", payload)
    if eligible:
        primary_file = next(item for item in files if item["name"] == "primary")
        freeze: dict[str, object] = {
            "schema_version": "1.0",
            "experiment_id": contract["experiment_id"],
            "candidate": "E1_VWAP_INVALIDATION",
            "engine_version": EXIT_RESEARCH_ENGINE_VERSION,
            "contract_sha256": file_sha256(contract_path),
            "development_ledger_sha256": primary_file["sha256"],
            "locked_start_utc": contract["locked_start_utc"],
            "locked_end_exclusive_utc": contract["locked_end_exclusive_utc"],
            "locked_runs_remaining": 1,
        }
        freeze["summary_sha256"] = canonical_sha256(freeze)
        write_json_atomic(evidence_path.parent / "candidate_freeze.json", freeze)
    return payload
