# Technical Plan

Status: Phase 05 completed with no promoted candidate. Phase 06 locked testing
is prohibited; Phase 07 closes the research as inconclusive.

## Architecture

```text
MT5 calendar + scraped calendars + official releases + BIS policy rates
                              |
                    point-in-time event store
                              |
                   structural policy model
                              |
                 versioned pair bias snapshots
                  /                         \
        historical CSV replay          current bias file
                |                              |
      deterministic + MT5 test             demo EA
                                               |
                                      Telegram notifier
```

Telegram and the EA receive the same snapshot, but neither depends on the
other. Historical testing never calls a live calendar or web endpoint.

## Phase 00 - contract foundation

- register the PRD, source rules, bias schema, entry definitions, backtest
  protocol, and promotion gate;
- create a standard-library contract validator and CI-friendly test suite;
- record reference-code provenance before porting any implementation.

Exit: all contracts parse, agree, and are committed before outcome access.

## Phase 01 - source qualification

- implement an MQL5 calendar exporter for historical values and metadata;
- retain Forex Factory and FXStreet as inactive fallbacks; do not scrape them
  when the MT5 export already preserves the required historical fields;
- connect the existing MT5 price extractor in read-only mode;
- inventory core inflation, labour, policy decisions, and two-year yield
  coverage for the six currencies;
- normalize MT5 server time, London time, New York FX days, and UTC;
- hand-audit sampled calendar rows against official publications;
- emit an immutable source matrix and raw-payload hashes.

No FX outcome or strategy PnL is opened in this phase.

Exit: passed. Broker-native M15 density freezes the common start at 2021-07-01.
Contract v0.2 also forces positions flat before rollover because free historical
swap schedules did not qualify.

## Phase 02 - canonical historical data

- persist raw payloads immutably outside Git;
- build canonical macro releases, policy observations, market confirmations,
  and MT5 price bars;
- preserve actual, forecast, previous-as-reported, revised previous, reference
  period, publication time, availability time, source, quality, and hash;
- build event-driven latest-known feature states with no future access;
- select a common price and feature window before loading outcomes;
- prove as-of joins and revision behavior with unit and integration tests.

Exit: a hashed, replayable dataset and coverage report.

Result: passed. Split boundaries and six canonical artifact hashes are frozen
in `evidence/phase02/canonical_data_audit.json`.

## Phase 03 - fundamental bias

- port the constrained walk-forward ridge implementation after provenance
  review;
- fit inflation gap, inflation momentum, labour tightness, labour momentum,
  current policy rate, and trailing policy change to six-month policy change;
- select penalties only against past policy labels;
- generate daily and post-event currency predictions;
- produce level and one-month revision divergence for each pair;
- emit F1 when level and revision agree;
- emit F2 only when F1 also agrees with the twenty-business-day change in the
  base-minus-quote two-year sovereign-yield spread;
- fail closed to FLAT on incomplete, stale, or conflicted inputs;
- freeze all historical bias snapshots before technical PnL.

Exit: policy-skill diagnostic, bias coverage report, immutable bias CSV, and
hash manifest.

Result: the artifact passed integrity checks and remained isolated from FX
outcomes. Its MAE point estimate beat both policy baselines, but both paired
bootstrap intervals crossed zero; the diagnostic is `NOT_SUPPORTED`.

## Phase 04 - technical baselines

- build M15 bars from broker-native MT5 data;
- implement T1, T2, and T3 without any fundamental filter;
- execute on the next tradable M15 open with bid/ask-aware costs;
- apply one-ATR stop, two-R target, 24-hour maximum holding period, Friday
  liquidation, and the fixed portfolio constraints;
- produce deterministic ledgers and selected native-MT5 parity fixtures.

Exit: three technical-only baseline reports. No rule is removed merely because
its standalone return is unattractive.

Result: passed as an implementation gate. All development and validation
baselines are negative after cost; locked outcomes remain unopened.

## Phase 05 - hybrid development and validation

- run the registered six-cell F1/F2 by T1/T2/T3 matrix;
- compare each cell with the identical technical-only entry;
- run reversed, shifted, and frequency-matched shuffled bias placebos;
- evaluate pair/year concentration and cost sensitivity;
- use development for debugging and validation for the single promotion choice;
- freeze candidate, code hashes, settings, and locked date boundary.

Exit: at most one promoted hybrid candidate. No promotion produces an
inconclusive result without opening the locked slice.

Result: no promotion. F2_T3 was positive and improved T3 in validation, but it
failed the frozen drawdown gate and multiple robustness diagnostics.

## Phase 06 - locked backtest and execution validation

- execute the frozen candidate exactly once on the locked chronological slice;
- validate current-overlap real ticks where available;
- run zero, two, and five-point additional slippage scenarios;
- account for spread, Raw commission, and rollover swap;
- reconcile Python decisions with an MQL5 EA on frozen sessions;
- archive tester request, report, logs, hashes, and environment metadata.

Exit: locked result bundle. No tuning follows a locked failure.

Result: `NOT_RUN`; Phase 05 produced no eligible frozen candidate.

## Phase 07 - final research review

- report data validity, policy prediction, bias coverage, technical baselines,
  hybrid incremental value, locked economics, uncertainty, concentration, and
  execution sensitivity separately;
- issue exactly one verdict from the registered decision gate;
- update the README with a plain-language outcome and operational permission.

Exit: `PROCEED_TO_FORWARD_DEMO`, `RESEARCH_INCONCLUSIVE`, or
`DO_NOT_PROCEED`.

## Post-research scope

Only `PROCEED_TO_FORWARD_DEMO` authorizes Phase 08-11: live collectors,
Telegram notifier, demo EA integration, and frozen forward-test monitoring.
