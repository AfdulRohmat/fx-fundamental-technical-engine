from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.technical import (
    _simulate_position,
    prepare_bars,
    signals_t2,
)


def test_london_opening_range_enters_next_bar() -> None:
    times = pd.date_range("2024-01-02T08:00:00Z", periods=6, freq="15min")
    frame = pd.DataFrame(
        {
            "time": times,
            "open": [1.0] * 6,
            "high": [1.01, 1.02, 1.015, 1.01, 1.03, 1.031],
            "low": [0.99, 0.995, 1.0, 1.0, 1.01, 1.02],
            "close": [1.0, 1.01, 1.005, 1.0, 1.025, 1.03],
            "tick_volume": [10] * 6,
            "spread": [1] * 6,
        }
    )
    bars = prepare_bars(frame, atr_period=2)

    signals = signals_t2(bars, "EURUSD")

    assert len(signals) == 1
    assert signals[0].direction == 1
    assert signals[0].entry_time == pd.Timestamp("2024-01-02T09:15:00Z")


def test_atr_uses_completed_signal_bar() -> None:
    times = pd.date_range("2024-01-02", periods=4, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "time": times,
            "open": [10.0] * 4,
            "high": [11.0] * 4,
            "low": [9.0] * 4,
            "close": [10.0] * 4,
            "tick_volume": [1] * 4,
            "spread": [0] * 4,
        }
    )

    bars = prepare_bars(frame, atr_period=2)

    assert pd.isna(bars.loc[0, "atr"])
    assert bars.loc[1, "atr"] == 2.0


def test_same_bar_stop_and_target_uses_adverse_first() -> None:
    bars = pd.DataFrame(
        {
            "time": [pd.Timestamp("2024-01-02T10:00:00Z")],
            "open": [100.0],
            "high": [103.0],
            "low": [99.0],
            "close": [101.0],
            "spread": [0],
        }
    )
    signal = pd.Series(
        {
            "strategy": "T2",
            "pair": "EURUSD",
            "direction": 1,
            "signal_time": pd.Timestamp("2024-01-02T10:00:00Z"),
            "entry_time": pd.Timestamp("2024-01-02T10:00:00Z"),
            "atr": 1.0,
        }
    )

    trade = _simulate_position(signal, bars, 0.00001, 100000, 3.5, 0, 2.0)

    assert trade is not None
    assert trade["exit_reason"] == "STOP"
    assert trade["price_r_before_commission"] == -1.0
