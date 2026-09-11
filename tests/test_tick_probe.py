from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fx_fundamental_technical.tick_probe import run_tick_probe


def test_tick_probe_rejects_naive_interval(tmp_path) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        run_tick_probe(
            tmp_path / "terminal64.exe",
            ["EURUSD"],
            datetime(2024, 1, 1),
            datetime(2024, 1, 2, tzinfo=UTC),
            tmp_path / "evidence.json",
        )
