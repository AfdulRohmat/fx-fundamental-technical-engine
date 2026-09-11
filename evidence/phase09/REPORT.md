# Phase 09 - One-Bar VWAP Acceptance Development Result

Status: `NO_PROMOTION`. Locked outcomes accessed: `false`.

## Economic comparison

| Strategy | Trades | Win rate | Expectancy | Net R | Max DD | PF |
|---|---:|---:|---:|---:|---:|---:|
| F2 immediate entry | 839 | 23.00% | -0.0266R | -22.30R | 103.96R | 0.957 |
| Technical-only acceptance | 2623 | 20.17% | -0.1182R | -309.96R | 309.96R | 0.824 |
| F2 one-bar acceptance | 571 | 24.17% | +0.0492R | +28.07R | 60.46R | 1.076 |

Observed frequency: 2.63 trades/week and 11.44 trades/month.

## Attribution and robustness

- Incremental expectancy versus immediate entry: +0.0757R.
- Incremental expectancy versus technical-only acceptance: +0.1673R.
- Bias-placebo expectancy: REVERSED -0.1294R, ONE_SNAPSHOT_LAG +0.0253R, FREQUENCY_MATCHED_SHUFFLE -0.0817R.
- Positive pairs: 3/5; positive years: 3/5.
- Bootstrap 95% interval: [-0.1998R, +0.2733R].
- Added slippage: +2 points -0.0057R; +5 points -0.0774R.
- One additional entry-delay bar: +0.0709R.
- Maximum winner: +18.33R; reached +2R: 167 trades.
- Price PnL after spread but before commission: +92.19R; commission: -64.12R; net: +28.07R.
- Median holding time: winners 5.38h; losses 0.50h.

## Frozen promotion checks

- PASS - `minimum_development_trades`
- PASS - `positive_expectancy`
- PASS - `improves_immediate_entry_control`
- PASS - `improves_technical_only_acceptance`
- PASS - `beats_every_bias_placebo`
- FAIL - `drawdown`
- PASS - `positive_pairs`
- PASS - `positive_calendar_years`
- FAIL - `pair_concentration`
- FAIL - `positive_bootstrap_lower_bound`
- FAIL - `two_point_slippage`
- FAIL - `five_point_slippage`
- PASS - `additional_entry_delay`

## Interpretation

The candidate is not promoted and the locked slice remains unopened.
