# Data Contract

## Source priority

| Family | Primary | Secondary | Prohibited interpretation |
|---|---|---|---|
| Calendar metadata | MT5 Economic Calendar | Forex Factory, FXStreet | official macro archive |
| Actual macro value | official release or qualified vintage | MT5, then FF/FXStreet | current revised history as past knowledge |
| Consensus | preserved MT5/FF value before release | FXStreet | forecast observed after release |
| Policy rate | BIS and official central bank | none | decision surprise without expectations |
| Two-year yield | official public market source | qualified public mirror | pure OIS path |
| FX execution | Exness MT5 | none for primary result | centralized spot volume |

## Mandatory fields

Each canonical release stores provider identity, stable event identity,
currency, normalized indicator, unit, reference period, actual, consensus,
previous as reported, revised previous, publication time, availability time,
retrieval time, raw source URL, raw SHA-256, and quality status.

## Point-in-time rules

- An observation enters features only at `available_at_utc`.
- Observation period end is never substituted for publication time.
- Revisions append a version and never overwrite the original fact.
- A consensus must have been captured before the actual value was available.
- Later-final history cannot fill a historical missing release.
- State carries forward only until the indicator-specific freshness limit.
- Mandatory missingness produces an unavailable currency and pair `FLAT`.

## Clock rules

Canonical storage is UTC. Original timestamp and timezone are retained. MT5
calendar times are interpreted using the observed trade-server offset and its
DST regime. London and New York rules use IANA timezone semantics rather than
fixed UTC offsets.

## Raw preservation

Raw payloads are immutable and ignored by Git. Every research artifact includes
a manifest of URL, retrieval time, byte size, media type, and SHA-256. Parser
versions and normalization mappings are committed.

## Outcome firewall

Source selection, series mappings, freshness, common sample, and quality flags
are frozen before FX returns or trading PnL are computed.
