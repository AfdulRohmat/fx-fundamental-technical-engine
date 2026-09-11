# Phase 02 Canonical Data Report

Status: `PASS`.

## Frozen dataset

- 1,923 mapped macro releases became 2,175 vintage observations, including 252
  later-known revisions of a previous reference period.
- 15,174 weekday currency snapshots were reconstructed at 06:00 UTC. In the
  July 2021 onward test window, every currency is complete on every snapshot
  except USD on four stale-data days; those four days fail closed rather than
  being imputed.
- 647,968 source-qualified M15 bars cover all five pairs from 2021-07-01
  through the last complete UTC date, 2026-09-10.
- 4,290 high-impact release timestamps are retained for the registered
  plus/minus 30-minute entry blackout.
- 14,536 official two-year yield observations are preserved with the
  conservative availability timestamp registered in Phase 01.

## Information-boundary checks

- Every feature source timestamp is at or before its snapshot timestamp.
- A later revision becomes usable only at the later release time; it never
  overwrites earlier knowledge retroactively.
- Three-month lag references precede the corresponding current reference.
- No FX return, trade, or PnL was calculated while selecting sources, the
  common window, or split boundaries.

The chronological split is now frozen:

| Slice | Start inclusive | End exclusive |
|---|---:|---:|
| Development | 2021-07-01 | 2024-08-13 |
| Validation | 2024-08-13 | 2025-08-28 |
| Locked test | 2025-08-28 | 2026-09-11 |

The historical locked slice is single-use but is not described as pristine
out-of-sample because related FX research predates this project. A post-freeze
demo period remains the genuine OOS test.

## Reproducibility

- Dataset contract SHA-256:
  `71a5a4db12c86f633138b6d9e3a8c5d6f6fd83f3bf28c61ca1ed965a2cf3b3af`
- Manifest: `evidence/phase02/canonical_data_audit.json`
- Generated parquet files remain outside Git; their row counts and SHA-256
  hashes are committed in the manifest.
- Integrity suite: 19 tests passed before the Phase 02 build; Ruff and strict
  mypy passed.

## Gate interpretation

Phase 02 passes. Phase 03 may train only against future policy-rate change using
past-complete policy labels. It may not read FX returns or technical outcomes.
