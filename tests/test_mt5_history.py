from __future__ import annotations

import pandas as pd
import pytest

from fx_fundamental_technical.mt5_history import (
    HistoryError,
    rates_frame,
    resolve_symbols,
    summarize_bars,
)


def test_resolve_symbols_prefers_exact_and_rejects_ambiguity() -> None:
    assert resolve_symbols(["EURUSD"], ["EURUSD", "EURUSDm"]) == {"EURUSD": "EURUSD"}

    with pytest.raises(HistoryError, match="exactly one"):
        resolve_symbols(["EURUSD"], ["EURUSD.a", "EURUSD.b"])


def test_rates_summary_detects_source_quality() -> None:
    raw = [
        (1_704_067_200, 1.1, 1.2, 1.0, 1.15, 10, 2, 0),
        (1_704_068_100, 1.15, 1.25, 1.1, 1.2, 12, 3, 0),
    ]
    dtype = [
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "i8"),
        ("spread", "i4"),
        ("real_volume", "i8"),
    ]
    import numpy as np

    frame = rates_frame(np.array(raw, dtype=dtype), "EURUSD")
    summary = summarize_bars(frame, "EURUSD")

    assert summary["rows"] == 2
    assert summary["duplicate_timestamps"] == 0
    assert summary["positive_spread_fraction"] == 1.0
    assert isinstance(frame["time"].dtype, pd.DatetimeTZDtype)
