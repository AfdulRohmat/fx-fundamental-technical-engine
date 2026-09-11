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

## Phase 04 - technical-only baselines

Status: implementation passed; economics negative.

- Executed T1/T2/T3 through validation with the locked slice closed.
- Validation net expectancy was -0.1009R for T1, -0.1002R for T2, and -0.1804R
  for T3. All three profit factors were below one.
- The observed win-rate band is consistent with a 2R target's raw break-even
  area, but maximum Raw commission is material against a one-M15-ATR stop.
- No rule or parameter was removed after observing the negative baselines. The
  complete six-cell hybrid matrix remains registered for Phase 05.

## Phase 05 - hybrid development and validation

Status: no candidate promoted; locked test remains unopened.

- F2_T3 was the only adequately sampled positive cell: 202 validation trades,
  40.59% wins, +0.0979R expectancy, +19.78R, four positive pairs, and +0.2783R
  incremental expectancy over T3.
- It failed the 12R drawdown gate at 18.75R. Development was -0.1882R/trade,
  its bootstrap interval crossed zero, a lag placebo slightly outperformed it,
  and five-point slippage made it negative.
- F2_T1 was positive but had only 59 validation trades versus the minimum 100.
- The remaining four cells were negative. No pair, year, cost, or threshold was
  changed after observing these results.

## Phase 06 - locked test

Status: not run.

- No Phase 05 candidate passed every promotion check, so the locked runner was
  not authorized.
- Zero locked strategy runs were consumed; no locked ledger or metric exists.
- MQL5 candidate parity and real-tick candidate validation were not run because
  there is no frozen candidate to reconcile.

## Phase 07 - final review

Verdict: `RESEARCH_INCONCLUSIVE`.

- The best validation observation was positive and improved its baseline, so
  this is not recorded as a locked economic failure.
- No candidate passed every promotion requirement and no locked metric exists,
  so `PROCEED_TO_FORWARD_DEMO` is unavailable.
- Telegram, demo EA, and live-money execution remain unauthorized.
- Continuing F2_T3 requires a new exploratory contract and genuinely new data;
  current validation results cannot be reused as confirmation evidence.
