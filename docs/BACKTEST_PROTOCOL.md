# Backtest Protocol

## Information boundary

The source matrix, canonical data, sample boundary, bias snapshots, candidate
set, and code hashes are frozen in that order. Technical returns are opened
only after the bias artifact is immutable.

## Split and iteration

The maximum common chronological sample is split 60/20/20 into development,
validation, and locked test. Development supports debugging. Validation selects
at most one of the six registered hybrid cells. The locked slice runs once and
cannot be used for tuning.

Prior related research makes the historical locked slice non-pristine. Only the
post-freeze demo period is genuine out of sample.

## Comparisons

Each hybrid is compared with its identical technical-only baseline. Reversed,
one-period-shifted, and frequency-matched shuffled bias are placebo controls.
F1 and F2 are reported separately; F2 cannot replace a failed F1 without an
explicit interpretation.

## Execution

Entry and exit use the executable bid/ask side. Recorded spread is preferred;
missing historical spread uses a preregistered, documented broker proxy.
Commission, swap, and zero/two/five-point added slippage are included. All fills,
rejections, forced exits, and unavailable prices are recorded.

## Metrics

Reports include trade count, frequency, win rate, average win and loss,
expectancy in R and account currency, profit factor, return, drawdown, holding
time, exposure, cost attribution, pair/year/side results, concentration, and
day-clustered or block-bootstrap uncertainty.

## Reproducibility

Every run stores input and code hashes, versioned configuration, terminal and
Python versions, symbol specifications, sample timestamps, ledger, summary,
and deterministic replay manifest.
