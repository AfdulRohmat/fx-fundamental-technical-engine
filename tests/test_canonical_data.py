from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.canonical_data import (
    _latest_vintage_at_or_before,
    build_vintage_values,
)


def test_revision_is_unavailable_before_later_release() -> None:
    releases = pd.DataFrame(
        {
            "currency": ["USD", "USD"],
            "family": ["inflation", "inflation"],
            "reference_period_utc": pd.to_datetime(
                ["2024-01-01", "2024-02-01"], utc=True
            ),
            "available_at_utc": pd.to_datetime(["2024-02-15", "2024-03-15"], utc=True),
            "value_id": [1, 2],
            "actual": [2.0, 2.2],
            "revised_previous": [float("nan"), 2.1],
        }
    )
    vintages = build_vintage_values(releases)
    january = pd.Timestamp("2024-01-31", tz="UTC")

    before = _latest_vintage_at_or_before(
        vintages, pd.Timestamp("2024-03-01", tz="UTC"), january
    )
    after = _latest_vintage_at_or_before(
        vintages, pd.Timestamp("2024-03-20", tz="UTC"), january
    )

    assert before is not None and before["value"] == 2.0
    assert after is not None and after["value"] == 2.1
    assert after["version_kind"] == "REVISED_PREVIOUS"
