# Phase 08 - Exit Asymmetry Development Result

Status: `NO_PROMOTION`. Locked outcomes accessed: `false`.

## Economic comparison

| Exit | Trades | Win rate | Expectancy | Net R | Max DD | PF |
|---|---:|---:|---:|---:|---:|---:|
| E0 fixed 2R | 839 | 33.37% | -0.1193R | -100.12R | 131.18R | 0.839 |
| E1 VWAP invalidation | 839 | 23.00% | -0.0266R | -22.30R | 103.96R | 0.957 |

## Winner continuation

- Reached +2R: 206 trades (24.55%).
- Conditional continuation after +2R: +3R 72.82%, +4R 54.85%, +5R 41.75%.
- Maximum realized winner: +20.16R.
- Return skew: +4.214.
- Median MFE giveback: 1.25R.
- Top 5% of trades supplied 66.70% of positive profit.

## Cost and stability

- Price PnL after spread but before commission: +74.90R; commission: -97.20R; net: -22.30R.
- Positive pairs: 2/5; positive calendar years: 2/5.
- Three-month-block bootstrap 95% interval: [-0.2277R, +0.1040R].
- Added slippage expectancy: +2 points -0.0766R; +5 points -0.1834R.
- One-bar delayed invalidation expectancy: -0.0205R.
- Entry overlap with E0: 833/839 (99.28%).

## Frozen promotion checks

- PASS - `minimum_development_trades`
- FAIL - `positive_expectancy`
- PASS - `improves_control`
- FAIL - `drawdown`
- FAIL - `positive_pairs`
- FAIL - `positive_calendar_years`
- FAIL - `pair_concentration`
- FAIL - `positive_bootstrap_lower_bound`
- FAIL - `two_point_slippage`
- FAIL - `five_point_slippage`
- FAIL - `one_bar_exit_delay`

## Interpretation

E1 is not promoted and the locked slice remains unopened.
