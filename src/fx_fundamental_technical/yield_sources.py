"""Parsers for free official two-year sovereign-yield sources."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd  # type: ignore[import-untyped]

from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)

YIELD_PARSER_VERSION = "official-yield-parsers-v0.1"
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class YieldSourceError(ValueError):
    """Raised when an official yield payload cannot meet the source contract."""


def _finish(
    dates: pd.Series,
    values: pd.Series,
    currency: str,
    provider: str,
    series: str,
    *,
    date_format: str | None = None,
) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "observation_date": pd.to_datetime(
                dates, errors="coerce", format=date_format
            ),
            "yield_percent": pd.to_numeric(values, errors="coerce"),
        }
    ).dropna()
    frame = frame.drop_duplicates("observation_date", keep="last").sort_values(
        "observation_date"
    )
    if frame.empty:
        raise YieldSourceError(f"{currency} {series} produced no observations")
    frame["available_at_utc"] = (
        frame["observation_date"] + pd.offsets.BDay(1) + pd.Timedelta(hours=12)
    ).dt.tz_localize(UTC)
    frame["currency"] = currency
    frame["provider"] = provider
    frame["series"] = series
    return frame.loc[
        :,
        [
            "observation_date",
            "available_at_utc",
            "currency",
            "yield_percent",
            "provider",
            "series",
        ],
    ]


def parse_usd(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return _finish(frame["observation_date"], frame["DGS2"], "USD", "FRED", "DGS2")


def parse_eur(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=None, dtype=str)
    first = next(
        (
            index
            for index, value in enumerate(raw.iloc[:, 0].fillna(""))
            if DATE_PATTERN.fullmatch(str(value))
        ),
        None,
    )
    if first is None:
        raise YieldSourceError("Bundesbank payload has no dated observations")
    return _finish(
        raw.iloc[first:, 0],
        raw.iloc[first:, 1],
        "EUR",
        "Deutsche Bundesbank",
        "BBSSY.D.REN.EUR.A610.000000WT0202.A",
    )


def parse_aud(path: Path) -> pd.DataFrame:
    # The published RBA CSV begins with a one-cell title before switching to
    # six-column metadata/data rows.  The standard CSV reader deliberately
    # accepts that ragged preamble while pandas' tabular parser does not.
    rows = read_csv_rows(path)
    marker = [index for index, row in enumerate(rows) if row and row[0] == "Series ID"]
    if len(marker) != 1:
        raise YieldSourceError("RBA payload has no unique Series ID row")
    marker_index = marker[0]
    candidates = rows[marker_index]
    try:
        column = candidates.index("FCMYGBAG2D")
    except ValueError as exc:
        raise YieldSourceError("RBA payload lacks FCMYGBAG2D") from exc
    data_rows = [row for row in rows[marker_index + 1 :] if len(row) > column]
    return _finish(
        pd.Series(row[0] for row in data_rows),
        pd.Series(row[column] for row in data_rows),
        "AUD",
        "Reserve Bank of Australia",
        "FCMYGBAG2D",
        date_format="%d-%b-%Y",
    )


def parse_cad(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    try:
        marker = lines.index('"OBSERVATIONS"')
    except ValueError as exc:
        raise YieldSourceError("Bank of Canada payload lacks OBSERVATIONS") from exc
    frame = pd.read_csv(io.StringIO("\n".join(lines[marker + 1 :])))
    series = "BD.CDN.2YR.DQ.YLD"
    if series not in frame:
        raise YieldSourceError(f"Bank of Canada payload lacks {series}")
    return _finish(frame["date"], frame[series], "CAD", "Bank of Canada", series)


def parse_jpy(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, skiprows=1, dtype=str)
    if "Date" not in frame or "2Y" not in frame:
        raise YieldSourceError("Japan MoF payload lacks Date or 2Y")
    return _finish(
        frame["Date"],
        frame["2Y"].replace("-", pd.NA),
        "JPY",
        "Japan Ministry of Finance",
        "JGB constant-maturity 2Y",
    )


def _boe_workbook(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="3. spot, short end", header=None)
    row_candidates = raw.index[raw.iloc[:, 0].eq("years:")]
    if len(row_candidates) != 1:
        raise YieldSourceError(f"BoE workbook has no unique years row: {path}")
    years_row = int(row_candidates[0])
    maturities = pd.to_numeric(raw.iloc[years_row], errors="coerce")
    # BoE's workbook serialises the two-year tenor as 1.99999992 rather than
    # an exact binary/decimal 2.0, so match within a small tenor tolerance.
    columns = maturities.index[(maturities - 2.0).abs() < 1e-5]
    if len(columns) != 1:
        raise YieldSourceError(f"BoE workbook has no unique 2Y point: {path}")
    column = int(columns[0])
    return pd.DataFrame(
        {
            "date": raw.iloc[years_row + 1 :, 0],
            "value": raw.iloc[years_row + 1 :, column],
        }
    )


def parse_gbp(directory: Path) -> pd.DataFrame:
    workbooks = sorted(directory.glob("*.xlsx"))
    selected = [
        path
        for path in workbooks
        if "2016 to 2024" in path.name or "2025 to present" in path.name
    ]
    if len(selected) != 2:
        raise YieldSourceError("BoE archive lacks required 2016-present workbooks")
    combined = pd.concat((_boe_workbook(path) for path in selected), ignore_index=True)
    return _finish(
        combined["date"],
        combined["value"],
        "GBP",
        "Bank of England",
        "UK nominal government spot curve 2.0 years",
    )


def load_registry(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise YieldSourceError("source registry root must be an object")
    return cast(dict[str, object], decoded)


def run_yield_source_audit(
    source_root: Path,
    registry_path: Path,
    canonical_path: Path,
    evidence_path: Path,
    *,
    cutoff: str = "2026-09-11",
) -> dict[str, object]:
    registry = load_registry(registry_path)
    yield_registry = registry.get("yield_sources")
    if not isinstance(yield_registry, dict):
        raise YieldSourceError("registry yield_sources is invalid")

    source_paths: dict[str, Path] = {
        "USD": source_root / "usd_fred_dgs2.csv",
        "EUR": source_root / "eur_bundesbank_2y.csv",
        "GBP": source_root / "gbp_boe",
        "JPY": source_root / "jpy_mof_jgbcme_all.csv",
        "AUD": source_root / "aud_rba_f2.csv",
        "CAD": source_root / "cad_boc_bond_yields_all.csv",
    }
    parsers: Mapping[str, Callable[[Path], pd.DataFrame]] = {
        "USD": parse_usd,
        "EUR": parse_eur,
        "GBP": parse_gbp,
        "JPY": parse_jpy,
        "AUD": parse_aud,
        "CAD": parse_cad,
    }
    frames = [parsers[currency](source_paths[currency]) for currency in parsers]
    canonical = pd.concat(frames, ignore_index=True)
    cutoff_timestamp = pd.Timestamp(cutoff)
    canonical = canonical[
        (canonical["observation_date"] >= pd.Timestamp("2017-01-01"))
        & (canonical["observation_date"] <= cutoff_timestamp)
    ].sort_values(["available_at_utc", "currency"])
    if canonical.empty:
        raise YieldSourceError("canonical yield table is empty")
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical.to_parquet(canonical_path, index=False)

    inventories: list[dict[str, object]] = []
    for currency, group in canonical.groupby("currency", sort=True):
        inventories.append(
            {
                "currency": str(currency),
                "rows": len(group),
                "first_observation": group["observation_date"].min().date().isoformat(),
                "last_observation": group["observation_date"].max().date().isoformat(),
                "maximum_calendar_gap_days": int(
                    group["observation_date"].diff().dt.days.max()
                ),
                "missing_values": int(group["yield_percent"].isna().sum()),
                "series": str(group["series"].iloc[0]),
            }
        )

    raw_files: list[dict[str, object]] = []
    for currency, path in source_paths.items():
        files = sorted(path.glob("*.xlsx")) if path.is_dir() else [path]
        entry = yield_registry.get(currency)
        url = entry.get("url") if isinstance(entry, dict) else None
        for file in files:
            raw_files.append(
                {
                    "currency": currency,
                    "url": url,
                    "path": str(file),
                    "bytes": file.stat().st_size,
                    "sha256": file_sha256(file),
                }
            )

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "parser_version": YIELD_PARSER_VERSION,
        "status": "QUALIFIED_WITH_CONSERVATIVE_AVAILABILITY_LAG",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "availability_convention": registry.get("availability_convention"),
        "canonical": {
            "path": str(canonical_path),
            "rows": len(canonical),
            "sha256": file_sha256(canonical_path),
        },
        "currencies": inventories,
        "raw_files": raw_files,
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(evidence_path, payload)
    return payload


def read_csv_rows(path: Path) -> list[list[str]]:
    """Test helper exposing standard CSV semantics for source fixtures."""

    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))
