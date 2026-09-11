from __future__ import annotations

import pandas as pd

from fx_fundamental_technical.yield_sources import _boe_workbook, _finish


def test_yield_availability_is_conservatively_lagged() -> None:
    frame = _finish(
        pd.Series(["2024-01-05", "2024-01-08"]),
        pd.Series([4.25, 4.20]),
        "USD",
        "test",
        "test-2y",
    )

    assert frame["available_at_utc"].dt.tz is not None
    assert frame["available_at_utc"].iloc[0].isoformat() == "2024-01-08T12:00:00+00:00"
    assert frame["available_at_utc"].iloc[1].isoformat() == "2024-01-09T12:00:00+00:00"
    assert frame["yield_percent"].tolist() == [4.25, 4.20]


def test_boe_tenor_accepts_published_rounding(tmp_path, monkeypatch) -> None:
    workbook = pd.DataFrame(
        [
            ["years:", 1.91666659, 1.99999992, 2.08333325],
            ["2024-01-02", 3.9, 4.0, 4.1],
        ]
    )
    monkeypatch.setattr(pd, "read_excel", lambda *args, **kwargs: workbook)

    parsed = _boe_workbook(tmp_path / "published.xlsx")

    assert parsed["value"].tolist() == [4.0]
