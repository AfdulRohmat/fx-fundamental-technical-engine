# Phase 05 Hybrid Development and Validation Report

Status: `NO_CANDIDATE_PROMOTED`. The locked test remains unopened.

## Six-cell result

| Candidate | Validation trades | Win rate | Expectancy | Net R | Max DD | PF | Delta vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| F1_T1 | 107 | 32.71% | -0.1508R | -16.14R | 25.93R | 0.796 | -0.0499R |
| F1_T2 | 342 | 29.24% | -0.2317R | -79.23R | 83.51R | 0.704 | -0.1314R |
| F1_T3 | 349 | 37.25% | -0.0052R | -1.82R | 37.39R | 0.993 | +0.1752R |
| F2_T1 | 59 | 40.68% | +0.0587R | +3.46R | 5.59R | 1.090 | +0.1597R |
| F2_T2 | 186 | 33.33% | -0.1074R | -19.98R | 30.86R | 0.854 | -0.0072R |
| F2_T3 | 202 | 40.59% | +0.0979R | +19.78R | 18.75R | 1.148 | +0.2783R |

F2_T3 is the best diagnostic cell. It is positive after primary costs, improves
the same T3 baseline, and is positive in four pairs with only 39.5% of positive
profit from the largest contributor. Its observed frequency is roughly 3.7
trades per week during validation, near the requested operational range.

It fails the frozen promotion gate because validation drawdown is 18.75R versus
the 12R maximum. More importantly, the result is unstable outside that slice:

- development expectancy was -0.1882R across 637 trades and every development
  calendar year was negative;
- the validation block-bootstrap interval was `[-0.172R, +0.275R]`;
- a one-snapshot-lag placebo earned +0.1192R/trade, slightly more than the
  primary timing, while the reversed and shuffled controls were negative;
- two added slippage points retained +0.0561R/trade, but five points changed the
  result to -0.0438R/trade;
- the positive validation result was concentrated in late 2024: 2024 earned
  +22.62R, while the 2025 validation portion lost -2.84R.

F2_T1 is also positive, but only 59 validation trades—below the registered
minimum 100—and its interval is extremely wide. It is not an alternative that
may be promoted after F2_T3 fails.

## Integrity

- The Phase 03 freeze verified before any hybrid run.
- The fundamental layer only permitted or rejected a technical direction; it
  never reversed one.
- All technical, exit, risk, commission, and blackout parameters remained
  unchanged from Phase 04.
- Bias-flip exits were implemented as registered, though no F2_T3 validation
  trade lasted long enough to encounter one.
- No entry at or after the locked boundary was loaded into a ledger.
- Validation config SHA-256:
  `d3767351328e50fd40f4863df649fd7f476967f38a4a99460254091d9e1c12f6`.

## Gate interpretation

This is not a clean failure of the economic idea: F2 materially improved T3 in
validation. It is also not robust evidence of an edge. The development reversal,
drawdown breach, weak timing placebo, confidence interval, and slippage failure
are exactly why a locked gate exists.

Per the pre-registered protocol, Phase 06 must be marked `NOT_RUN` and the locked
slice must remain unopened. Changing the drawdown limit, choosing only 2024,
dropping USDJPY, or reducing assumed cost now would be post-result tuning and is
not allowed under this research contract.
