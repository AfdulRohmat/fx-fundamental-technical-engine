# Research Log

## Phase 00 - contract foundation

Status: passed.

- Registered the hybrid separation and initial six-cell candidate matrix.
- Registered five pairs, a target start of 2017, chronological 60/20/20 splits,
  realistic Exness Raw costs, and a one-shot locked test.
- Registered three technical entries and F1/F2 fundamental variants.
- No source qualification or FX PnL has been opened.
- Contract validator: 6 tests passed; Ruff and strict mypy passed.
- Canonical contract SHA-256:
  `ea6c709579d3626f0d969b5f0be98432aadea14b475a0422cf027bbf89c86c49`.

## Phase 01 - source qualification

Status: passed with source-driven amendments.

- Exported and validated 97,511 MT5 calendar rows and froze 18 macro mappings.
- Qualified official two-year yield histories for all six currencies (14,539
  canonical observations) with a conservative publication lag.
- Detected that the broker's nominal 2017 M15 request contains D1/H1 history;
  true common M15 coverage begins July 2021. No upsampling is permitted.
- Confirmed current-period bid/ask real ticks for all five pairs.
- Preserved contract v0.1 and registered v0.2 before opening PnL. Version 0.2
  forces a 20:45 UTC flat exit because free historical swap schedules did not
  qualify. SHA-256:
  `94d4f5f23a7d4b5912151aed5534f25cf89171f9247e19c55da279e88d79cf67`.
- FX returns and strategy PnL remained closed throughout qualification.
