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

## Phase 02 - canonical point-in-time data

Status: passed.

- Reconstructed 1,923 releases, 2,175 vintages, and 15,174 daily currency
  states; 252 previous-period revisions are effective only when later known.
- Froze 647,968 M15 bars, 4,290 high-impact event times, and 14,536 yield
  observations.
- Registered the exact development, validation, and locked-test dates in
  `config/dataset_contract_v0_1.json` before any FX return or PnL calculation.
- Four USD snapshot-days fail closed because a mandatory input exceeds its
  freshness limit; no forward-fill exception or imputation was introduced.
- Dataset contract SHA-256:
  `71a5a4db12c86f633138b6d9e3a8c5d6f6fd83f3bf28c61ca1ed965a2cf3b3af`.

## Phase 03 - structural policy bias freeze

Status: bias frozen; policy-skill diagnostic not supported.

- Fit 64 expanding monthly models using future six-month policy change only
  after each label was fully known. FX inputs were structurally absent.
- Structural model MAE was 50.95 bp versus 59.58 bp for no change and 63.98 bp
  for three-month policy momentum; nonzero-direction accuracy was 91.1%.
- The paired three-month-block bootstrap intervals crossed zero versus both
  baselines, so the apparent improvement is not statistically secure.
- Frozen F1 is directional 58.1% of snapshots; F2 yield confirmation is
  directional 34.1%. The remaining states are `FLAT` by contract.
- All four files in `evidence/phase03/bias_freeze.json` re-verified by SHA-256.
