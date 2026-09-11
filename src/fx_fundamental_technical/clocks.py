"""DST-aware clocks used by canonical data and technical rules."""

from __future__ import annotations

from datetime import date
from typing import cast

import pandas as pd  # type: ignore[import-untyped]


def require_utc(timestamps: pd.Series) -> None:
    """Reject naive or non-UTC canonical timestamp series."""

    timezone = timestamps.dt.tz
    if timezone is None or str(timezone) != "UTC":
        raise ValueError("canonical timestamps must be UTC-aware")


def fx_day_id(timestamp: pd.Timestamp) -> date:
    """Return the New York 17:00-to-17:00 FX-day identifier."""

    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    local = timestamp.tz_convert("America/New_York") - pd.Timedelta(hours=17)
    return cast(date, local.date())


def london_clock(timestamp: pd.Timestamp) -> tuple[date, int, int]:
    """Return London local date, hour, and minute with IANA DST semantics."""

    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    local = timestamp.tz_convert("Europe/London")
    return local.date(), local.hour, local.minute
