# Fundamental Bias Contract

## Separation

The bias engine may read macro releases, central-bank policy, approved market
confirmation, and their historical availability. It may not read future FX
returns, technical indicators, or strategy PnL during fitting or selection.

## Structural model

Predictors are inflation gap, three-month inflation momentum, labour tightness,
labour momentum, current policy rate, and trailing three-month policy change.
The target is the subsequent six-month change in the canonical policy rate.

Coefficients are fitted in expanding, past-only folds. Macro coefficients are
nonnegative after all features are oriented so positive means more hawkish
pressure. Ridge penalty selection minimizes policy-path error only.

## Pair state

For base currency `b` and quote currency `q`:

```text
level_divergence    = predicted_policy[b] - predicted_policy[q]
revision_divergence = one_month_revision[b] - one_month_revision[q]
```

F1 is eligible only when both are nonzero and share a sign. Positive means
`LONG_BASE`, negative means `SHORT_BASE`; disagreement means `FLAT`.

F2 additionally requires the twenty-business-day change in the base-minus-
quote two-year sovereign-yield spread to have the same sign. The yield measure
is explicitly a confirmation proxy containing non-policy premia, not OIS.

## Snapshot schema

Every snapshot contains ID, version, pair, direction, as-of, effective-from,
expiry, source cutoff, level divergence, revision divergence, confirmation
state, data quality, freshness, and machine-readable reason codes.

Snapshots are emitted at 06:00 UTC each trading day and after eligible releases.
An event-driven snapshot becomes effective only after the registered blackout.
An expired snapshot forbids new entries.

## Open positions

The bias does not manage profit targets. When an effective snapshot flips
direction or becomes FLAT because the thesis changed, the execution engine
closes an existing position at the next tradable M15 open. Temporary collector
failure alone forbids new entries but does not force a market exit unless the
last valid snapshot has expired.
