# Research Backbone

This registry separates the economic rationale from the empirical test. A cited
mechanism is not treated as evidence that this implementation has an edge.

## Fundamental and policy transmission

- Taylor (1993), *Discretion versus policy rules in practice*. Establishes a
  systematic link between inflation, economic slack, and policy rates.
- Orphanides (2001), *Monetary policy rules based on real-time data*. Motivates
  point-in-time vintages and forbids revised data from silently entering a
  historical decision.
- Molodtsova and Papell (2009), *Out-of-sample exchange rate predictability with
  Taylor rule fundamentals*. Supports testing relative macro-policy conditions
  in exchange rates, while not guaranteeing implementation-level profitability.
- Kuttner (2001), *Monetary policy surprises and interest rates*. Separates
  anticipated policy from policy surprises and motivates a market-confirmation
  channel.
- Stavrakeva and Tang (2015), *Exchange rates and monetary policy*. Motivates
  evaluating policy divergence using information available at the decision
  timestamp.

## Mechanical execution and replication caution

- Menkhoff, Sarno, Schmeling, and Schrimpf (2012), *Currency momentum
  strategies*. Provides a currency-specific momentum rationale and documents
  material crash and transaction-cost risks.
- Moskowitz, Ooi, and Pedersen (2012), *Time series momentum*. Provides the
  broader trend-continuation mechanism behind breakout-style entries.
- Huang, Li, Wang, and Zhou (2020), *Time series momentum: Is it there?* Adds a
  replication warning against treating a published anomaly as universal.

## Operational sources

- MetaTrader 5 Economic Calendar documentation defines actual, forecast,
  previous, revised, importance, release time, and update identifiers.
- MetaTrader 5 Strategy Tester does not expose Economic Calendar functions;
  point-in-time calendar data must therefore be exported and replayed.
- BIS central-bank policy-rate statistics are an authoritative validation source
  for policy-rate levels, but not a substitute for release-time macro vintages.

## Implementation consequences

1. Fundamental weights may be learned only from the macro-to-policy target, not
   from FX returns.
2. Every observation requires an availability timestamp and source provenance.
3. F2 uses relative two-year sovereign-yield change as a confirmation proxy; it
   must never be reported as an OIS-implied policy path.
4. The technical-only strategy is the required control group. Profitability by
   itself cannot establish incremental fundamental value.
5. Publication evidence determines hypotheses. This repository's locked test and
   later demo forward test determine whether the implementation survives.
