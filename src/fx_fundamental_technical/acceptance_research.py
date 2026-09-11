"""Pre-registered Phase 09 one-bar VWAP acceptance research."""

from __future__ import annotations

import math
from pathlib import Path
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)
from fx_fundamental_technical.exit_research import (
    EXIT_RESEARCH_ENGINE_VERSION,
    _as_float,
    _bootstrap_expectancy,
    _group_metrics,
    _object,
    _read_before,
    add_london_vwap,
    extended_metrics,
    simulate_vwap_portfolio,
)
from fx_fundamental_technical.fundamental_bias import verify_bias_freeze
from fx_fundamental_technical.hybrid import align_signals_to_bias, transform_bias
from fx_fundamental_technical.technical import PAIRS, prepare_bars

ACCEPTANCE_ENGINE_VERSION = "f2-t3-one-bar-acceptance-v0.1"


class AcceptanceResearchError(ValueError):
    """Raised when Phase 09 violates the frozen acceptance contract."""


def generate_acceptance_signals(
    signals: pd.DataFrame,
    prepared: dict[str, pd.DataFrame],
    *,
    extra_entry_delay_bars: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Confirm one completed bar after reclaim and enter on a later open."""

    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for _, signal in signals.sort_values(["entry_time", "pair"]).iterrows():
        pair = str(signal["pair"])
        bars = prepared[pair]
        origin_entry = cast(pd.Timestamp, signal["entry_time"])
        matches = bars.index[bars["time"] == origin_entry]
        reason: str | None = None
        if len(matches) != 1:
            reason = "MISSING_CONFIRMATION_BAR"
        else:
            confirmation_index = int(matches[0])
            confirmation = bars.loc[confirmation_index]
            vwap = float(confirmation["session_vwap"])
            if not math.isfinite(vwap):
                reason = "VWAP_UNAVAILABLE"
            else:
                direction = int(signal["direction"])
                accepted_close = (
                    float(confirmation["close"]) > vwap
                    if direction > 0
                    else float(confirmation["close"]) < vwap
                )
                if not accepted_close:
                    reason = "ACCEPTANCE_FAILED"
                else:
                    entry_index = confirmation_index + 1 + extra_entry_delay_bars
                    if entry_index >= len(bars):
                        reason = "MISSING_ENTRY_BAR"
                    else:
                        entry = bars.loc[entry_index]
                        expected = origin_entry + pd.Timedelta(
                            minutes=15 * (1 + extra_entry_delay_bars)
                        )
                        entry_time = cast(pd.Timestamp, entry["time"])
                        london = entry_time.tz_convert("Europe/London")
                        london_minute = london.hour * 60 + london.minute
                        atr = float(bars.loc[entry_index - 1, "atr"])
                        if entry_time != expected:
                            reason = "NONCONTIGUOUS_ENTRY_BAR"
                        elif not 480 <= london_minute < 1020:
                            reason = "ENTRY_OUTSIDE_LONDON_WINDOW"
                        elif not math.isfinite(atr) or atr <= 0:
                            reason = "ATR_UNAVAILABLE"
                        else:
                            accepted.append(
                                {
                                    "strategy": "T3_A1",
                                    "pair": pair,
                                    "direction": direction,
                                    "signal_time": origin_entry
                                    + pd.Timedelta(minutes=15),
                                    "entry_time": entry_time,
                                    "atr": atr,
                                    "origin_entry_time": origin_entry,
                                    "confirmation_close": float(confirmation["close"]),
                                    "confirmation_vwap": vwap,
                                    "extra_entry_delay_bars": extra_entry_delay_bars,
                                }
                            )
        if reason is not None:
            rejected.append(
                {
                    "pair": pair,
                    "origin_entry_time": origin_entry,
                    "reason": reason,
                    "extra_entry_delay_bars": extra_entry_delay_bars,
                }
            )
    return pd.DataFrame.from_records(accepted), pd.DataFrame.from_records(rejected)


def _expectancy(result: dict[str, object]) -> float | None:
    value = result.get("expectancy_r")
    return None if value is None else _as_float(value)


def evaluate_acceptance_promotion(
    candidate: pd.DataFrame,
    immediate_control: pd.DataFrame,
    technical_only: pd.DataFrame,
    placebos: dict[str, pd.DataFrame],
    delay: pd.DataFrame,
    stresses: dict[int, pd.DataFrame],
    gate: dict[str, object],
) -> dict[str, object]:
    """Apply the frozen economic, attribution, and robustness checks."""

    candidate_metrics = extended_metrics(candidate)
    immediate_metrics = extended_metrics(immediate_control)
    technical_metrics = extended_metrics(technical_only)
    placebo_metrics = {
        name: extended_metrics(ledger) for name, ledger in placebos.items()
    }
    delay_metrics = extended_metrics(delay)
    stress_metrics = {
        str(points): extended_metrics(ledger) for points, ledger in stresses.items()
    }
    candidate_expectancy = _expectancy(candidate_metrics)
    immediate_expectancy = _expectancy(immediate_metrics)
    technical_expectancy = _expectancy(technical_metrics)
    delay_expectancy = _expectancy(delay_metrics)
    placebo_expectancies = {
        name: _expectancy(result) for name, result in placebo_metrics.items()
    }
    if candidate_expectancy is None:
        raise AcceptanceResearchError("candidate ledger has no expectancy")

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
    all_placebos_observed = all(
        value is not None for value in placebo_expectancies.values()
    )
    beats_placebos = all_placebos_observed and all(
        candidate_expectancy > cast(float, value)
        for value in placebo_expectancies.values()
    )
    two_point_expectancy = _expectancy(stress_metrics["2"])
    five_point_expectancy = _expectancy(stress_metrics["5"])
    checks = {
        "minimum_development_trades": len(candidate)
        >= int(cast(int, gate["minimum_development_trades"])),
        "positive_expectancy": candidate_expectancy > 0,
        "improves_immediate_entry_control": immediate_expectancy is not None
        and candidate_expectancy > immediate_expectancy,
        "improves_technical_only_acceptance": technical_expectancy is not None
        and candidate_expectancy > technical_expectancy,
        "beats_every_bias_placebo": beats_placebos,
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
        "two_point_slippage": two_point_expectancy is not None
        and two_point_expectancy > 0,
        "five_point_slippage": five_point_expectancy is not None
        and five_point_expectancy
        >= float(cast(float, gate["five_point_slippage_floor_r"])),
        "additional_entry_delay": delay_expectancy is not None and delay_expectancy > 0,
    }
    return {
        "candidate_metrics": candidate_metrics,
        "immediate_entry_control_metrics": immediate_metrics,
        "technical_only_acceptance_metrics": technical_metrics,
        "incremental_expectancy_vs_immediate_r": (
            None
            if immediate_expectancy is None
            else candidate_expectancy - immediate_expectancy
        ),
        "incremental_expectancy_vs_technical_only_r": (
            None
            if technical_expectancy is None
            else candidate_expectancy - technical_expectancy
        ),
        "bias_placebo_metrics": placebo_metrics,
        "bias_placebo_expectancies_r": placebo_expectancies,
        "pair_metrics": pair_metrics,
        "calendar_year_metrics": year_metrics,
        "positive_pair_count": len(positive_pair_net),
        "positive_calendar_year_count": sum(
            _as_float(item["net_r"]) > 0 for item in year_metrics.values()
        ),
        "single_pair_positive_profit_share_max": concentration,
        "expectancy_block_bootstrap_95_ci_r": interval,
        "additional_entry_delay_metrics": delay_metrics,
        "slippage_stress_metrics": stress_metrics,
        "promotion_checks": checks,
        "eligible_for_locked_test": all(checks.values()),
    }


def _write_report(path: Path, payload: dict[str, object]) -> None:
    assessment = cast(dict[str, object], payload["assessment"])
    candidate = cast(dict[str, object], assessment["candidate_metrics"])
    immediate = cast(dict[str, object], assessment["immediate_entry_control_metrics"])
    technical = cast(dict[str, object], assessment["technical_only_acceptance_metrics"])
    placebos = cast(dict[str, object], assessment["bias_placebo_expectancies_r"])
    interval = cast(list[float], assessment["expectancy_block_bootstrap_95_ci_r"])
    stress = cast(dict[str, dict[str, object]], assessment["slippage_stress_metrics"])
    delay = cast(dict[str, object], assessment["additional_entry_delay_metrics"])
    checks = cast(dict[str, bool], assessment["promotion_checks"])
    path_metrics = cast(dict[str, object], candidate["path"])
    weeks = _as_float(payload["development_days"]) / 7
    months = _as_float(payload["development_days"]) / (365.2425 / 12)
    candidate_trades = _as_float(candidate["trades"])
    lines = [
        "# Phase 09 - One-Bar VWAP Acceptance Development Result",
        "",
        f"Status: `{payload['status']}`. Locked outcomes accessed: `false`.",
        "",
        "## Economic comparison",
        "",
        "| Strategy | Trades | Win rate | Expectancy | Net R | Max DD | PF |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| F2 immediate entry | {immediate['trades']} | "
            f"{100 * _as_float(immediate['win_rate']):.2f}% | "
            f"{_as_float(immediate['expectancy_r']):+.4f}R | "
            f"{_as_float(immediate['net_r']):+.2f}R | "
            f"{_as_float(immediate['maximum_drawdown_r']):.2f}R | "
            f"{_as_float(immediate['profit_factor']):.3f} |"
        ),
        (
            f"| Technical-only acceptance | {technical['trades']} | "
            f"{100 * _as_float(technical['win_rate']):.2f}% | "
            f"{_as_float(technical['expectancy_r']):+.4f}R | "
            f"{_as_float(technical['net_r']):+.2f}R | "
            f"{_as_float(technical['maximum_drawdown_r']):.2f}R | "
            f"{_as_float(technical['profit_factor']):.3f} |"
        ),
        (
            f"| F2 one-bar acceptance | {candidate['trades']} | "
            f"{100 * _as_float(candidate['win_rate']):.2f}% | "
            f"{_as_float(candidate['expectancy_r']):+.4f}R | "
            f"{_as_float(candidate['net_r']):+.2f}R | "
            f"{_as_float(candidate['maximum_drawdown_r']):.2f}R | "
            f"{_as_float(candidate['profit_factor']):.3f} |"
        ),
        "",
        f"Observed frequency: {candidate_trades / weeks:.2f} trades/week and "
        f"{candidate_trades / months:.2f} trades/month.",
        "",
        "## Attribution and robustness",
        "",
        f"- Incremental expectancy versus immediate entry: "
        f"{_as_float(assessment['incremental_expectancy_vs_immediate_r']):+.4f}R.",
        f"- Incremental expectancy versus technical-only acceptance: "
        f"{_as_float(assessment['incremental_expectancy_vs_technical_only_r']):+.4f}R.",
        "- Bias-placebo expectancy: "
        + ", ".join(
            f"{name} {_as_float(value):+.4f}R" for name, value in placebos.items()
        )
        + ".",
        f"- Positive pairs: {assessment['positive_pair_count']}/5; positive years: "
        f"{assessment['positive_calendar_year_count']}/5.",
        f"- Bootstrap 95% interval: [{interval[0]:+.4f}R, {interval[1]:+.4f}R].",
        f"- Added slippage: +2 points "
        f"{_as_float(stress['2']['expectancy_r']):+.4f}R; +5 points "
        f"{_as_float(stress['5']['expectancy_r']):+.4f}R.",
        f"- One additional entry-delay bar: {_as_float(delay['expectancy_r']):+.4f}R.",
        f"- Maximum winner: {_as_float(candidate['maximum_winner_r']):+.2f}R; "
        f"reached +2R: {path_metrics['hit_2r_count']} trades.",
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
            "The candidate is frozen for one separate locked run; no tuning is "
            "permitted."
            if payload["status"] == "CANDIDATE_FROZEN"
            else "The candidate is not promoted and the locked slice remains unopened."
        ),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_phase09(
    contract_path: Path,
    execution_path: Path,
    bias_freeze_path: Path,
    bias_path: Path,
    price_path: Path,
    event_path: Path,
    t3_signal_path: Path,
    immediate_control_path: Path,
    output_root: Path,
    evidence_path: Path,
) -> dict[str, object]:
    """Run Phase 09 development checks without loading the locked interval."""

    contract = _object(contract_path)
    execution = _object(execution_path)
    if not bool(contract.get("registered_before_new_acceptance_outcomes")):
        raise AcceptanceResearchError("acceptance contract was not pre-registered")
    if bool(contract.get("locked_outcomes_allowed")):
        raise AcceptanceResearchError("Phase 09 may not access locked outcomes")
    if bool(contract.get("parameter_grid_allowed")):
        raise AcceptanceResearchError("Phase 09 forbids parameter grids")
    verify_bias_freeze(bias_freeze_path)
    start = pd.Timestamp(str(contract["development_start_utc"]))
    end = pd.Timestamp(str(contract["development_end_exclusive_utc"]))
    prices = _read_before(price_path, "time", end)
    prices = prices[prices["time"] >= start]
    events = _read_before(event_path, "released_at_utc", end)
    bias = _read_before(bias_path, "effective_from_utc", end)
    t3_signals = _read_before(t3_signal_path, "entry_time", end)
    t3_signals = t3_signals[t3_signals["entry_time"] >= start]
    immediate_control = _read_before(immediate_control_path, "entry_time", end)
    immediate_control = immediate_control[immediate_control["entry_time"] >= start]
    if t3_signals.empty or immediate_control.empty:
        raise AcceptanceResearchError("development signals or control are empty")

    prepared = {
        pair: add_london_vwap(
            prepare_bars(
                prices[prices["pair"] == pair],
                int(cast(int, execution["atr_period"])),
            )
        )
        for pair in PAIRS
    }
    acceptance_signals, acceptance_rejections = generate_acceptance_signals(
        t3_signals, prepared
    )
    primary_signals, primary_bias_rejections = align_signals_to_bias(
        acceptance_signals, bias, "F2"
    )
    primary, primary_execution_rejections = simulate_vwap_portfolio(
        primary_signals, prepared, events, execution
    )
    technical_only, technical_execution_rejections = simulate_vwap_portfolio(
        acceptance_signals, prepared, events, execution
    )

    controls = cast(dict[str, object], contract["controls"])
    placebo_ledgers: dict[str, pd.DataFrame] = {}
    placebo_counts: dict[str, dict[str, int]] = {}
    for placebo in cast(list[str], controls["bias_placebos"]):
        transformed = transform_bias(
            bias, placebo, int(cast(int, controls["placebo_seed"]))
        )
        placebo_signals, rejected = align_signals_to_bias(
            acceptance_signals, transformed, "F2"
        )
        ledger, execution_rejections = simulate_vwap_portfolio(
            placebo_signals, prepared, events, execution
        )
        placebo_ledgers[placebo] = ledger
        placebo_counts[placebo] = {
            "bias_rejections": len(rejected),
            "execution_rejections": len(execution_rejections),
        }

    delayed_signals, delayed_signal_rejections = generate_acceptance_signals(
        t3_signals, prepared, extra_entry_delay_bars=1
    )
    delayed_f2, delayed_bias_rejections = align_signals_to_bias(
        delayed_signals, bias, "F2"
    )
    delayed, delayed_execution_rejections = simulate_vwap_portfolio(
        delayed_f2, prepared, events, execution
    )

    gate = cast(dict[str, object], contract["promotion_gate"])
    stresses: dict[int, pd.DataFrame] = {}
    stress_rejections: dict[int, pd.DataFrame] = {}
    for points in cast(list[int], gate["stress_slippage_points"]):
        ledger, rejections = simulate_vwap_portfolio(
            primary_signals,
            prepared,
            events,
            execution,
            slippage_points=int(points),
        )
        stresses[int(points)] = ledger
        stress_rejections[int(points)] = rejections

    assessment = evaluate_acceptance_promotion(
        primary,
        immediate_control,
        technical_only,
        placebo_ledgers,
        delayed,
        stresses,
        gate,
    )
    eligible = bool(assessment["eligible_for_locked_test"])
    output_root.mkdir(parents=True, exist_ok=True)
    ledgers = {
        "primary": primary,
        "technical_only": technical_only,
        "entry_delay_1": delayed,
        **{f"placebo_{name.lower()}": value for name, value in placebo_ledgers.items()},
        **{f"slippage_{points}": value for points, value in stresses.items()},
    }
    files: list[dict[str, object]] = []
    for name, ledger in ledgers.items():
        output = output_root / f"{name}_ledger.parquet"
        ledger.to_parquet(output, index=False)
        files.append({"name": name, "path": str(output), "sha256": file_sha256(output)})

    development_days = (end - start).total_seconds() / 86400
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "engine_version": ACCEPTANCE_ENGINE_VERSION,
        "exit_engine_version": EXIT_RESEARCH_ENGINE_VERSION,
        "experiment_id": contract["experiment_id"],
        "status": "CANDIDATE_FROZEN" if eligible else "NO_PROMOTION",
        "locked_outcomes_accessed": False,
        "locked_runs_consumed": 0,
        "development_start_utc": str(start),
        "development_end_exclusive_utc": str(end),
        "development_days": development_days,
        "origin_t3_signals": len(t3_signals),
        "acceptance_signals": len(acceptance_signals),
        "acceptance_rejections": len(acceptance_rejections),
        "primary_f2_signals": len(primary_signals),
        "primary_bias_rejections": len(primary_bias_rejections),
        "execution_rejections": {
            "primary": len(primary_execution_rejections),
            "technical_only": len(technical_execution_rejections),
            "entry_delay_1_signal": len(delayed_signal_rejections),
            "entry_delay_1_bias": len(delayed_bias_rejections),
            "entry_delay_1_execution": len(delayed_execution_rejections),
            **{
                f"slippage_{points}": len(rejections)
                for points, rejections in stress_rejections.items()
            },
        },
        "placebo_counts": placebo_counts,
        "assessment": assessment,
        "files": files,
        "input_hashes": {
            "contract": file_sha256(contract_path),
            "execution": file_sha256(execution_path),
            "bias_freeze": file_sha256(bias_freeze_path),
            "bias": file_sha256(bias_path),
            "prices": file_sha256(price_path),
            "events": file_sha256(event_path),
            "t3_signals": file_sha256(t3_signal_path),
            "immediate_control": file_sha256(immediate_control_path),
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
            "candidate": "F2_T3_A1_E1",
            "engine_version": ACCEPTANCE_ENGINE_VERSION,
            "contract_sha256": file_sha256(contract_path),
            "development_ledger_sha256": primary_file["sha256"],
            "locked_start_utc": contract["locked_start_utc"],
            "locked_end_exclusive_utc": contract["locked_end_exclusive_utc"],
            "locked_runs_remaining": 1,
        }
        freeze["summary_sha256"] = canonical_sha256(freeze)
        write_json_atomic(evidence_path.parent / "candidate_freeze.json", freeze)
    return payload
