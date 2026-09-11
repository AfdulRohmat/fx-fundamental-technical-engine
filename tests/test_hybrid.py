from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.hybrid import align_signals_to_bias, transform_bias


def _bias() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "snapshot_id": ["one", "two"],
            "pair": ["EURUSD", "EURUSD"],
            "effective_from_utc": pd.to_datetime(
                ["2024-01-02T06:00:00Z", "2024-01-02T12:00:00Z"]
            ),
            "expiry_utc": pd.to_datetime(
                ["2024-01-02T12:00:00Z", "2024-01-03T06:00:00Z"]
            ),
            "direction_f1": ["LONG_BASE", "FLAT"],
            "direction_f2": ["LONG_BASE", "FLAT"],
        }
    )


def test_alignment_never_reverses_technical_direction() -> None:
    signals = pd.DataFrame(
        {
            "strategy": ["T2", "T2"],
            "pair": ["EURUSD", "EURUSD"],
            "direction": [1, -1],
            "signal_time": pd.to_datetime(
                ["2024-01-02T09:00:00Z", "2024-01-02T10:00:00Z"]
            ),
            "entry_time": pd.to_datetime(
                ["2024-01-02T09:00:00Z", "2024-01-02T10:00:00Z"]
            ),
            "atr": [0.001, 0.001],
        }
    )

    accepted, rejected = align_signals_to_bias(signals, _bias(), "F1")

    assert accepted["direction"].tolist() == [1]
    assert accepted["bias_exit_time"].iloc[0] == pd.Timestamp("2024-01-02T12:00:00Z")
    assert rejected["reason"].tolist() == ["BIAS_NOT_ALIGNED"]


def test_reversed_placebo_preserves_flat_frequency() -> None:
    reversed_bias = transform_bias(_bias(), "REVERSED", seed=7)

    assert reversed_bias["direction_f1"].tolist() == ["SHORT_BASE", "FLAT"]
