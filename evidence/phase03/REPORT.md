# Phase 03 Fundamental Bias Report

Status: `PASS_BIAS_FROZEN`; policy-skill diagnostic: `NOT_SUPPORTED`.

## What the model did

The model used six currency fixed effects and six structural inputs to forecast
the subsequent six-month policy-rate change. It was refit monthly in expanding,
past-only folds. The ridge penalty was selected only against policy-label error;
no FX return, technical signal, or strategy PnL was accepted by the runner.

The first four inputs were oriented so a positive value means more hawkish
pressure, and their fitted slopes were constrained nonnegative. The constraint
was active rather than decorative: labour momentum was set to zero in all 64
monthly fits, while the other macro inputs sometimes entered and sometimes
dropped out. This is the research-backed alternative to manually declaring an
indicator worth `+1` or `+2`.

## Policy diagnostic

Across 348 currency-month forecasts and all six currencies:

| Forecast | MAE |
|---|---:|
| Structural policy model | 50.95 bp |
| No policy change | 59.58 bp |
| Extrapolated three-month policy momentum | 63.98 bp |

Directional accuracy on nonzero policy changes was 91.1%. Those point estimates
are encouraging. They are not statistically secure: the three-month block
bootstrap 95% interval for MAE improvement was `[-1.11, 19.96]` bp versus no
change and `[-0.32, 26.67]` bp versus policy momentum. Both intervals cross
zero, so the registered diagnostic is `NOT_SUPPORTED`, not proven policy skill.

## Frozen bias

- 64 monthly walk-forward models generated 14,100 currency predictions.
- Daily 06:00 UTC plus 977 post-event effective times produced 11,555 pair
  snapshots across the five-pair basket.
- F1 was directional in 6,712 snapshots (58.1%); F2's yield confirmation reduced
  that to 3,939 snapshots (34.1%). Missing, stale, or conflicted observations are
  explicitly `FLAT`.
- The prediction schedule includes one month of prehistory so the first tested
  date has a genuinely prior one-month revision, not an artificial zero.

The artifacts are frozen in `evidence/phase03/bias_freeze.json`; all four hashes
re-verified before this report. The model-config SHA-256 is
`0f1c5ad304ac3a16dcf442f068293750b1a077513a33d99cd8f7080483faf819`
and the freeze file SHA-256 is recorded in `evidence/phase03/summary.json`.

## Gate interpretation

The bias artifact is technically valid and may be tested exactly as frozen.
However, Phase 03 does not independently validate the macro-to-policy link at
the registered confidence standard. A favorable hybrid backtest therefore
cannot erase this uncertainty; the final verdict must report it explicitly.
