# Phase 04 Technical Baseline Report

Status: `PASS_BASELINES_COMPLETE`; all three baselines are economically
negative after registered Exness Raw costs.

Locked outcomes remained closed. Results below cover development and validation
only, ending before 2025-08-28.

| Rule | Slice | Trades | Win rate | Net expectancy | Net R | Max DD | PF |
|---|---|---:|---:|---:|---:|---:|---:|
| T1 prior-day breakout/retest | Development | 1,289 | 32.35% | -0.1496R | -192.81R | 197.13R | 0.796 |
| T1 | Validation | 368 | 34.78% | -0.1009R | -37.15R | 68.20R | 0.859 |
| T2 London opening-range breakout | Development | 2,672 | 31.32% | -0.1705R | -455.48R | 455.48R | 0.776 |
| T2 | Validation | 873 | 33.79% | -0.1002R | -87.51R | 99.45R | 0.864 |
| T3 London tick-VWAP reclaim | Development | 2,649 | 32.50% | -0.1426R | -377.63R | 378.27R | 0.810 |
| T3 | Validation | 877 | 31.36% | -0.1804R | -158.18R | 160.02R | 0.766 |

The 2R target needs a little above 33.3% wins before costs. T1 and T2 reached
roughly that level in validation, but the conservative maximum Raw commission
(`$3.50/lot/side`) is large relative to a one-M15-ATR stop and pushed them below
zero. T3 was already below break-even before that hurdle. This is not a software
gate failure; it is the economic baseline the fundamental filter must improve.

The engine uses broker-recorded bar spread, explicit bid/ask sides, next-bar
entries, adverse-first same-bar ambiguity, gap-adverse stops, commission, DST
session clocks, event blackouts, portfolio limits, and a forced pre-rollover
exit. It verified that no locked entry timestamp was accessed.

Config SHA-256:
`534260c38f235af4c0eeb920d76e58dca6fed43d73da13a3a489d295c5d55f2c`.
Signals, ledgers, rejections, and their hashes are recorded in
`evidence/phase04/summary.json`; the generated parquet ledgers remain outside
Git.

## Gate interpretation

Phase 04 passes as an implementation phase, but no technical rule has standalone
edge. Phase 05 may now apply the already-frozen F1/F2 permission filter without
changing any technical or execution parameter. A hybrid must become positive
after costs and improve its matching baseline; merely losing less is not enough
for promotion.
