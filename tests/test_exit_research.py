from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.exit_research import (
    _simulate_vwap_position,
    add_london_vwap,
    evaluate_promotion,
)


def _signal() -> pd.Series:
    return pd.Series(
        {
            "pair": "EURUSD",
            "direction": 1,
            "signal_time": pd.Timestamp("2024-01-02T09:00:00Z"),
            "entry_time": pd.Timestamp("2024-01-02T09:00:00Z"),
            "atr": 1.0,
            "bias_exit_time": pd.NaT,
        }
    )


def test_london_vwap_freezes_after_session() -> None:
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                [
                    "2024-01-02T07:45:00Z",
                    "2024-01-02T08:00:00Z",
                    "2024-01-02T08:15:00Z",
                    "2024-01-02T17:00:00Z",
                ]
            ),
            "open": [10.0, 10.0, 12.0, 20.0],
            "high": [10.0, 10.0, 12.0, 20.0],
            "low": [10.0, 10.0, 12.0, 20.0],
            "close": [10.0, 10.0, 12.0, 20.0],
            "tick_volume": [1, 1, 1, 1],
            "spread": [0, 0, 0, 0],
        }
    )
    prepared = add_london_vwap(prepare(frame))

    assert pd.isna(prepared.loc[0, "session_vwap"])
    assert prepared.loc[1, "session_vwap"] == 10.0
    assert prepared.loc[2, "session_vwap"] == 11.0
    assert prepared.loc[3, "session_vwap"] == 11.0


def prepare(frame: pd.DataFrame) -> pd.DataFrame:
    london = frame["time"].dt.tz_convert("Europe/London")
    result = frame.copy()
    result["london_date"] = london.dt.date
    result["london_minute"] = london.dt.hour * 60 + london.dt.minute
    return result


def test_no_target_allows_three_r_then_exits_next_open() -> None:
    bars = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-02T09:00:00Z", periods=3, freq="15min"),
            "open": [100.0, 101.0, 100.25],
            "high": [102.5, 103.5, 101.0],
            "low": [99.5, 100.0, 100.0],
            "close": [101.0, 100.0, 100.5],
            "spread": [0, 0, 0],
            "session_vwap": [100.5, 100.5, 100.5],
        }
    )

    trade = _simulate_vwap_position(_signal(), bars, 0.01, 100, 0, 0)

    assert trade is not None
    assert trade["exit_reason"] == "VWAP_INVALIDATION"
    assert trade["exit_time"] == pd.Timestamp("2024-01-02T09:30:00Z")
    assert trade["price_r_before_commission"] == 0.25
    assert trade["maximum_favorable_excursion_r"] == 3.5
    assert trade["reached_3r"] is True


def test_hard_stop_has_adverse_first_priority() -> None:
    bars = pd.DataFrame(
        {
            "time": [pd.Timestamp("2024-01-02T09:00:00Z")],
            "open": [100.0],
            "high": [105.0],
            "low": [98.0],
            "close": [104.0],
            "spread": [0],
            "session_vwap": [100.0],
        }
    )

    trade = _simulate_vwap_position(_signal(), bars, 0.01, 100, 0, 0)

    assert trade is not None
    assert trade["exit_reason"] == "STOP"
    assert trade["price_r_before_commission"] == -1.0
    assert trade["maximum_favorable_excursion_r"] == 0.0


def _ledger(values: list[float]) -> pd.DataFrame:
    size = len(values)
    return pd.DataFrame(
        {
            "entry_time": pd.date_range(
                "2022-01-01", periods=size, freq="31D", tz="UTC"
            ),
            "exit_time": pd.date_range(
                "2022-01-01T01:00:00Z", periods=size, freq="31D"
            ),
            "pair": ["EURUSD", "GBPUSD", "USDCAD", "AUDUSD"] * (size // 4),
            "net_r": values,
            "commission_r": [0.05] * size,
            "spread_cost_r_estimate": [0.01] * size,
            "exit_reason": ["VWAP_INVALIDATION"] * size,
        }
    )


def test_promotion_requires_every_registered_check() -> None:
    candidate = _ledger([0.2] * 12)
    control = _ledger([-0.1] * 12)
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

    result = evaluate_promotion(
        candidate,
        control,
        candidate,
        {2: candidate, 5: candidate},
        gate,
    )

    assert result["eligible_for_locked_test"] is True
    assert all(result["promotion_checks"].values())
