from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.clocks import fx_day_id, london_clock


def test_london_anchor_moves_with_dst() -> None:
    assert london_clock(pd.Timestamp("2024-01-15T08:00:00Z"))[1:] == (8, 0)
    assert london_clock(pd.Timestamp("2024-07-15T07:00:00Z"))[1:] == (8, 0)


def test_new_york_fx_day_moves_with_dst() -> None:
    before_winter_close = pd.Timestamp("2024-01-15T21:59:00Z")
    after_winter_close = pd.Timestamp("2024-01-15T22:01:00Z")
    before_summer_close = pd.Timestamp("2024-07-15T20:59:00Z")
    after_summer_close = pd.Timestamp("2024-07-15T21:01:00Z")

    assert fx_day_id(before_winter_close).isoformat() == "2024-01-14"
    assert fx_day_id(after_winter_close).isoformat() == "2024-01-15"
    assert fx_day_id(before_summer_close).isoformat() == "2024-07-14"
    assert fx_day_id(after_summer_close).isoformat() == "2024-07-15"
