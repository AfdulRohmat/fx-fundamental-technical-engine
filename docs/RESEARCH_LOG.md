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

## Phase 08 - cut losses and let winners run

Status: `NO_PROMOTION`; locked test not authorized.

- Registered one new exit candidate before opening no-target paths. All data
  before 2025-08-28 became development because the earlier validation result
  informed this hypothesis.
- Kept F2_T3 entries, one-ATR hard stop, costs, news blackout, bias rules, and
  portfolio constraints unchanged. Removed the fixed target and exited at the
  next M15 open after a completed close invalidated London VWAP.
- E1 improved expectancy from -0.1193R to -0.0266R across 839 trades and reduced
  average loss from -1.1158R to -0.8118R, but it remained net negative.
- The payoff became strongly right-skewed: maximum winner +20.16R. Of 206 trades
  reaching +2R, 72.82% reached +3R and 41.75% reached +5R before exit.
- The gross price result after spread but before commission was +74.90R;
  -97.20R commission reduced it to -22.30R net.
- Only EURUSD and USDCAD were positive; only 2024 and the partial 2025 period
  were positive. Maximum drawdown was 103.96R and the block-bootstrap interval
  was [-0.2277R, +0.1040R].
- Two-point slippage produced -0.0766R/trade, five points produced
  -0.1834R/trade, and a one-bar exit delay remained negative at -0.0205R/trade.
- Deterministic replay reproduced the primary ledger SHA-256
  `a199bb8be1bfb51aac46071d61010867a31cb644733349e820c0db6fdeca6f8e`.
- No locked observation was loaded, zero locked runs were consumed, and no
  candidate freeze was created.

## Phase 09 - one-bar VWAP acceptance

Status: `NO_PROMOTION`; locked test not authorized.

- Registered one mechanical confirmation before reading its outcome: after the
  first T3 London-VWAP reclaim, observe one completed M15 candle and enter on
  the following open only when that candle closes on the reclaimed side.
- Kept F2 as the mandatory direction filter, rechecked its point-in-time state
  at actual entry, and retained the Phase 08 stop, no-target VWAP invalidation,
  costs, blackout, portfolio limits, and locked boundary.
- F2 acceptance produced 571 trades, 24.17% wins, +0.0492R expectancy, +28.07R
  net, 1.076 profit factor, and 60.46R maximum drawdown. Average winner was
  +2.8782R versus -0.8525R average loss; the maximum winner was +18.33R.
- It improved the immediate-entry F2 control by +0.0757R/trade and the
  technical-only acceptance control by +0.1673R/trade. Reversed bias was
  -0.1294R, one-snapshot-lag bias +0.0253R, and shuffled bias -0.0817R.
- Three of five pairs and three of five calendar years were positive, but
  USDCAD contributed 57.24% of positive-pair profit. The block-bootstrap 95%
  interval was [-0.1998R, +0.2733R].
- Price PnL after spread but before commission was +92.19R; -64.12R commission
  reduced it to +28.07R. Two-point slippage produced -0.0057R/trade and five
  points produced -0.0774R/trade.
- The candidate passed attribution, sample-size, pair-count, year-count, and
  extra-delay checks. It failed drawdown, pair concentration, uncertainty, and
  both slippage gates, so no candidate freeze was created.
- Primary ledger SHA-256:
  `c9fd8ef696f3f233ca19d378edd51344d35b147415dcd47e687495b0ba2aede6`.
- No locked observation was loaded and zero locked runs were consumed.
