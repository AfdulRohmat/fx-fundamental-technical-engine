# Product and Research Requirements

Status: registered before source qualification or FX PnL.

## Objective

Determine whether a point-in-time, policy-oriented fundamental bias improves a
simple mechanical FX entry after realistic Exness Raw execution costs. If the
combined system clears the frozen research gate, operate the same bias contract
through a Telegram notifier and an MT5 demo-account EA.

## Research question

The project does not ask whether fundamentals alone predict every FX return or
whether a technical strategy is profitable after parameter search. It asks:

> Holding the entry, exit, risk, and execution rule fixed, does permitting only
> trades aligned with a pre-existing fundamental bias improve net expectancy
> relative to the identical technical rule without that bias?

## Required product behavior

1. Fundamental inputs are reconstructed using their historical availability.
2. Fundamental coefficients are learned against central-bank policy outcomes,
   never FX returns.
3. Every pair snapshot is `LONG_BASE`, `SHORT_BASE`, or `FLAT` and expires.
4. Technical code owns entries and exits; it cannot create or reverse bias.
5. Missing, stale, conflicting, or expired mandatory inputs fail closed.
6. Development iterations are finite and registered before PnL.
7. A single promoted candidate receives one locked historical test.
8. Backtest and demo EA consume the same versioned bias schema.
9. Telegram is a human notification channel, not the order transport.

## Initial universe

The initial basket is EURUSD, GBPUSD, USDJPY, AUDUSD, and USDCAD. This keeps the
source problem bounded while allowing a basket-level target of roughly four to
five opportunities per week. Frequency is diagnostic, not a quota; thresholds
must not be loosened simply to create trades.

## Non-goals

- live-money deployment;
- sub-second economic-news trading;
- full-G10 source completeness;
- a claim that sovereign yields are pure OIS expectations;
- LLM-created historical macro values or policy labels;
- per-pair optimization;
- choosing rules after reading the locked result.

## Research success

Success means `PROCEED_TO_FORWARD_DEMO`, not proven production alpha. The
combined candidate must be positive after costs, improve the corresponding
technical-only baseline, diversify across pairs, remain within the risk gate,
and reconcile between deterministic and MT5 implementations.
