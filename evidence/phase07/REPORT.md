# Phase 07 Final Research Review

## Verdict

`RESEARCH_INCONCLUSIVE`

Operational permission is denied. This run does not authorize a Telegram signal
service, an MT5 demo EA forward test, or live-money execution.

## Plain-language result

The research did not prove a tradable edge, but it also did not show that the
fundamental-bias idea is worthless.

The unfiltered mechanical entries were consistently negative after Exness Raw
costs. The strongest fundamental filter, F2 applied to T3, changed validation
expectancy from -0.1804R to +0.0979R, produced 40.59% wins over 202 trades, and
was positive in four of five pairs. This is the first economically interesting
signal in the run.

It was not stable enough to trust. The same combination lost -0.1882R/trade in
development, exceeded the 12R drawdown limit, had an uncertainty interval that
crossed zero, was slightly beaten by the lagged-bias placebo, and became negative
with five points of added slippage. Most validation profit arrived in late 2024;
the 2025 portion was negative.

Therefore Phase 05 correctly promoted nothing and Phase 06 correctly left the
locked slice unopened. Under the registered rules, that maps to
`RESEARCH_INCONCLUSIVE`: there is a positive validation observation worth
remembering, but no authorized candidate and no locked evidence.

## Findings by layer

### Data

- All six currencies have point-in-time inflation, labour, and policy histories
  from 2017, plus official two-year yield proxies.
- Exness M15 data are genuinely continuous only from July 2021. Earlier D1/H1
  rows were rejected rather than upsampled.
- Historical swap schedules were unavailable for free, so the pre-PnL contract
  forced every trade flat before rollover.
- Current bid/ask real ticks exist for all five pairs, but no candidate reached
  the phase where full MQL5 parity was warranted.

### Fundamental model

- Weights were fitted against subsequent policy-rate change, never assigned as
  subjective `+1/+2` scores and never trained on FX returns.
- The model's policy MAE beat two simple baselines and its nonzero directional
  accuracy was 91.1%, but both paired bootstrap intervals crossed zero. Policy
  skill is `NOT_SUPPORTED` at the registered confidence standard.
- F1 was directional in 58.1% of snapshots. Requiring the yield confirmation in
  F2 reduced that to 34.1%, providing a materially stronger filter.

### Technical model

- T1, T2, and T3 were all negative after cost in both development and
  validation. A one-M15-ATR stop makes maximum Raw commission a large fraction
  of initial risk.
- Win rates around the low-to-mid 30% range were not the main problem by
  themselves; at a 2R target, the combined spread/commission hurdle moved the
  required break-even rate higher.

### Hybrid model

- F1 did not create a positive validation system.
- F2_T1 was positive but had only 59 validation trades and extreme uncertainty.
- F2_T3 was the sole adequately sampled positive validation result, but failed
  drawdown, temporal stability, uncertainty, placebo timing, and maximum
  slippage robustness.

## What is and is not justified next

It is not valid to reopen this run by relaxing the drawdown limit, selecting
only late 2024, deleting USDJPY, or reducing cost assumptions. Those choices are
now informed by validation outcomes.

A defensible continuation would be a new, explicitly exploratory contract that
treats F2_T3 as one fixed hypothesis and seeks genuinely new evidence: a later
untouched broker period, passive forward collection, or independently sourced
older intraday history. Any change to stop horizon or execution design would be
a separate strategy hypothesis, not a repair to this test.

## Reproducibility and status

- Final machine-readable verdict: `evidence/phase07/summary.json`
- Phase reports: `evidence/phase00` through `evidence/phase07`
- Automated validation: 30 tests, Ruff, and strict mypy passed.
- Phase branches were committed and merged sequentially; large raw/canonical
  data remain ignored while source, artifact, and evidence hashes are versioned.
