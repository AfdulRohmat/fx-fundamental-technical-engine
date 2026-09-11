from __future__ import annotations

from pathlib import Path

import pandas as pd

from fx_fundamental_technical.source_qualification import m15_coverage_inventory


def test_m15_window_rejects_lower_granularity_history(tmp_path: Path) -> None:
    pairs = ["EURUSD", "GBPUSD"]
    daily = pd.date_range("2021-05-03", periods=20, freq="D", tz="UTC")
    m15 = pd.date_range("2021-06-01", periods=96 * 20, freq="15min", tz="UTC")
    for pair in pairs:
        pd.DataFrame({"time": daily.append(m15)}).to_parquet(
            tmp_path / f"{pair.lower()}_m15.parquet", index=False
        )

    inventory, common_start = m15_coverage_inventory(tmp_path, pairs)

    assert common_start == "2021-06-01"
    assert {record["first_qualified_m15_month"] for record in inventory} == {"2021-06"}
