from __future__ import annotations

import inspect

import pandas as pd

from fx_fundamental_technical.fundamental_bias import (
    _block_bootstrap_mean_ci,
    build_monthly_policy_panel,
    eligible_training_rows,
    run_phase03,
)


def test_six_month_label_is_purged_until_available() -> None:
    dates = pd.date_range("2023-01-31", periods=7, freq="ME", tz="UTC")
    states = pd.DataFrame(
        {
            "asof_utc": dates,
            "currency": ["USD"] * 7,
            "inflation_value": [2.0] * 7,
            "inflation_lag3_value": [1.9] * 7,
            "labour_value": [4.0] * 7,
            "labour_lag3_value": [4.1] * 7,
            "policy_value": [4.0, 4.0, 4.25, 4.5, 4.5, 4.5, 5.0],
            "policy_lag3_value": [3.5] * 7,
            "mandatory_inputs_available": [True] * 7,
        }
    )
    panel = build_monthly_policy_panel(states)

    assert eligible_training_rows(panel, pd.Timestamp("2023-06-30", tz="UTC")).empty
    eligible = eligible_training_rows(panel, pd.Timestamp("2023-07-31", tz="UTC"))
    assert len(eligible) == 1
    assert eligible.iloc[0]["policy_change_6m_bp"] == 100.0


def test_phase03_runner_has_no_fx_input() -> None:
    assert tuple(inspect.signature(run_phase03).parameters) == (
        "model_config_path",
        "registry_path",
        "canonical_root",
        "output_root",
        "evidence_root",
    )


def test_policy_bootstrap_is_deterministic() -> None:
    first = _block_bootstrap_mean_ci([1.0, 2.0, 3.0], 2, 100, 7)
    second = _block_bootstrap_mean_ci([1.0, 2.0, 3.0], 2, 100, 7)

    assert first == second
