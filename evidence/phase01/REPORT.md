# Phase 01 Source Qualification Report

Status: `PASS_WITH_SOURCE_DRIVEN_WINDOW_AMENDMENT`.

## What qualified

- The MT5 Economic Calendar export contains 97,511 unique event values from
  2017-01-02 through the cutoff, with zero duplicate value IDs. All 18 frozen
  inflation, labour, and policy mappings have actual observations beginning in
  2017. Forecast, previous-as-reported, and revision fields are retained when
  the provider supplies them.
- Six official two-year sovereign-yield series produced 14,539 canonical daily
  observations. They are permitted only as F2 confirmation proxies and receive
  a conservative one-business-day, 12:00 UTC availability lag.
- Exness MT5 supplied all five requested symbols, broker spread fields, and
  positive tick volume. A recent one-hour real-tick probe returned usable bid
  and ask ticks for every pair (1,074 to 4,910 ticks), sufficient for later
  current-period execution parity checks.

## Important source findings

The broker accepted an M15 request back to 2017 but did not return M15 history
for the entire period. The archive contains approximately one D1 bar per active
day through November 2020, approximately 24 H1 bars per active day from December
2020 through May 2021, a mixed June 2021 transition, and 96 M15 bars per full
active day from July 2021 onward. The common backtest window is therefore frozen
at `2021-07-01T00:00:00Z` through `2026-09-11T13:00:00Z`. Earlier rows are
excluded; they will not be relabelled or silently upsampled.

Free point-in-time historical Exness swap schedules did not qualify. Before FX
returns or PnL were opened, contract v0.2 therefore added a forced 20:45 UTC
flat time. No tested position may cross rollover, and the backtest must verify
zero swap-bearing positions. The original Phase 00 contract remains intact.

The official yield files are current historical archives, not vintage market
databases. This creates a small revision risk; the F2 proxy is kept separate
from F1, is lagged conservatively, and cannot rescue a failed F1 interpretation.

## Frozen evidence

- Active contract: `config/research_contract_v0_2.json`
- Active contract SHA-256:
  `94d4f5f23a7d4b5912151aed5534f25cf89171f9247e19c55da279e88d79cf67`
- Calendar payload SHA-256:
  `41e54c9e2c91d2d4399d8bdb87e47b5b861ebfc4cdbe26e6463e7abbf56596e7`
- Yield canonical rows: 14,539
- Source matrix: `evidence/phase01/source_qualification.json`
- Price audit: `evidence/phase01/price_source_audit.json`
- Yield audit: `evidence/phase01/yield_source_audit.json`
- Real-tick probe: `evidence/phase01/real_tick_probe.json`

## Gate interpretation

Phase 01 passes for an honest July 2021 onward test. It does not establish an
edge. Phase 02 may reconstruct and freeze point-in-time feature states; FX PnL
remains closed until those artifacts pass their integrity tests.
