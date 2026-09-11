"""Validation and inventory for the MT5 Economic Calendar export."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class CalendarExportError(ValueError):
    """Raised when exported calendar evidence is incomplete or malformed."""


REQUIRED_COLUMNS = frozenset(
    {
        "value_id",
        "event_id",
        "release_time_server",
        "reference_period_server",
        "revision",
        "actual",
        "forecast",
        "previous_as_reported",
        "revised_previous",
        "country_code",
        "currency",
        "event_code",
        "event_name",
        "sector",
        "importance",
        "source_url",
        "server_utc_offset_seconds_at_export",
    }
)


@dataclass(frozen=True)
class CalendarInventory:
    row_count: int
    first_release_server: str
    last_release_server: str
    currencies: dict[str, int]
    sectors: dict[str, int]
    with_actual: int
    with_forecast: int
    with_previous: int
    with_revised_previous: int
    duplicate_value_ids: int
    sha256: str


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_server_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y.%m.%d %H:%M:%S")
    except ValueError as exc:
        raise CalendarExportError(f"invalid server timestamp: {value!r}") from exc


def load_calendar_rows(path: Path) -> list[dict[str, str]]:
    """Load and minimally validate an immutable MQL5 calendar export."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
            reader = csv.DictReader(handle, delimiter=delimiter)
            fields = frozenset(reader.fieldnames or ())
            missing = REQUIRED_COLUMNS - fields
            if missing:
                raise CalendarExportError(
                    f"calendar export missing columns: {', '.join(sorted(missing))}"
                )
            rows = list(reader)
    except OSError as exc:
        raise CalendarExportError(f"cannot read calendar export: {path}") from exc
    if not rows:
        raise CalendarExportError("calendar export has no rows")
    malformed = [index for index, row in enumerate(rows, start=2) if None in row]
    if malformed:
        sample = ", ".join(str(index) for index in malformed[:3])
        raise CalendarExportError(f"calendar export has malformed rows: {sample}")
    return rows


def inventory_calendar(path: Path) -> CalendarInventory:
    rows = load_calendar_rows(path)
    release_times = [_parse_server_time(row["release_time_server"]) for row in rows]
    currencies = Counter(row["currency"] for row in rows)
    sectors = Counter(row["sector"] for row in rows)
    value_ids = Counter(row["value_id"] for row in rows)
    return CalendarInventory(
        row_count=len(rows),
        first_release_server=min(release_times).isoformat(sep=" "),
        last_release_server=max(release_times).isoformat(sep=" "),
        currencies=dict(sorted(currencies.items())),
        sectors=dict(sorted(sectors.items())),
        with_actual=sum(bool(row["actual"]) for row in rows),
        with_forecast=sum(bool(row["forecast"]) for row in rows),
        with_previous=sum(bool(row["previous_as_reported"]) for row in rows),
        with_revised_previous=sum(bool(row["revised_previous"]) for row in rows),
        duplicate_value_ids=sum(count - 1 for count in value_ids.values() if count > 1),
        sha256=file_sha256(path),
    )
