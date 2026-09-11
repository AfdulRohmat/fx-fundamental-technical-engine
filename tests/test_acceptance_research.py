from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.acceptance_research import (
    evaluate_acceptance_promotion,
    generate_acceptance_signals,
)


def _origin(direction: int = 1) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "strategy": ["T3"],
            "pair": ["EURUSD"],
            "direction": [direction],
            "signal_time": [pd.Timestamp("2024-01-02T09:00:00Z")],
            "entry_time": [pd.Timestamp("2024-01-02T09:00:00Z")],
            "atr": [1.0],
        }
    )


def _bars(confirmation_close: float) -> dict[str, pd.DataFrame]:
    return {
        "EURUSD": pd.DataFrame(
            {
                "time": pd.date_range("2024-01-02T09:00:00Z", periods=3, freq="15min"),
                "close": [confirmation_close, 101.0, 102.0],
                "session_vwap": [100.0, 100.5, 101.0],
                "atr": [1.1, 1.2, 1.3],
            }
        )
    }


def test_acceptance_enters_after_one_completed_confirmation_bar() -> None:
    accepted, rejected = generate_acceptance_signals(_origin(), _bars(101.0))

    assert rejected.empty
    assert len(accepted) == 1
    assert accepted.iloc[0]["signal_time"] == pd.Timestamp("2024-01-02T09:15:00Z")
    assert accepted.iloc[0]["entry_time"] == pd.Timestamp("2024-01-02T09:15:00Z")
    assert accepted.iloc[0]["atr"] == 1.1


def test_acceptance_rejects_immediate_false_reclaim() -> None:
    accepted, rejected = generate_acceptance_signals(_origin(), _bars(99.0))

    assert accepted.empty
    assert rejected.iloc[0]["reason"] == "ACCEPTANCE_FAILED"


def test_latency_stress_delays_entry_without_changing_confirmation() -> None:
    accepted, rejected = generate_acceptance_signals(
        _origin(), _bars(101.0), extra_entry_delay_bars=1
    )

    assert rejected.empty
    assert accepted.iloc[0]["signal_time"] == pd.Timestamp("2024-01-02T09:15:00Z")
    assert accepted.iloc[0]["entry_time"] == pd.Timestamp("2024-01-02T09:30:00Z")
    assert accepted.iloc[0]["atr"] == 1.2


def _ledger(value: float) -> pd.DataFrame:
    size = 12
    return pd.DataFrame(
        {
            "entry_time": pd.date_range(
                "2022-01-01", periods=size, freq="31D", tz="UTC"
            ),
            "exit_time": pd.date_range(
                "2022-01-01T01:00:00Z", periods=size, freq="31D"
            ),
            "pair": ["EURUSD", "GBPUSD", "USDCAD", "AUDUSD"] * 3,
            "net_r": [value] * size,
            "commission_r": [0.05] * size,
            "spread_cost_r_estimate": [0.01] * size,
            "exit_reason": ["VWAP_INVALIDATION"] * size,
        }
    )


def test_acceptance_gate_requires_fundamental_attribution() -> None:
    candidate = _ledger(0.2)
    gate: dict[str, object] = {
        "minimum_development_trades": 10,
        "maximum_drawdown_r": 25.0,
        "minimum_positive_pairs": 3,
        "minimum_positive_calendar_years": 1,
        "maximum_single_pair_positive_profit_share": 0.5,
        "bootstrap_block_months": 1,
        "bootstrap_resamples": 100,
        "five_point_slippage_floor_r": -0.05,
    }
    result = evaluate_acceptance_promotion(
        candidate,
        _ledger(-0.1),
        _ledger(0.3),
        {"REVERSED": _ledger(-0.1)},
        candidate,
        {2: candidate, 5: candidate},
        gate,
    )

    assert result["promotion_checks"]["improves_technical_only_acceptance"] is False
    assert result["eligible_for_locked_test"] is False
