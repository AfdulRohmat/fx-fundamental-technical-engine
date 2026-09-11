from pathlib import Path

import pytest

from fx_fundamental_technical.calendar_export import (
    CalendarExportError,
    inventory_calendar,
    load_calendar_rows,
)

FIXTURE = Path("tests/fixtures/calendar_export_sample.csv")


def test_calendar_inventory_preserves_point_in_time_fields() -> None:
    inventory = inventory_calendar(FIXTURE)

    assert inventory.row_count == 3
    assert inventory.currencies == {"GBP": 1, "USD": 2}
    assert inventory.with_actual == 3
    assert inventory.with_forecast == 3
    assert inventory.with_previous == 3
    assert inventory.with_revised_previous == 1
    assert inventory.duplicate_value_ids == 0


def test_calendar_loader_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("value_id,event_id\n1,2\n", encoding="utf-8")

    with pytest.raises(CalendarExportError, match="missing columns"):
        load_calendar_rows(path)


def test_calendar_loader_rejects_unescaped_extra_fields(tmp_path: Path) -> None:
    header = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    path = tmp_path / "bad.csv"
    path.write_text(f"{header}\n" + ",".join(["x"] * 30) + "\n", encoding="utf-8")

    with pytest.raises(CalendarExportError, match="malformed rows"):
        load_calendar_rows(path)
