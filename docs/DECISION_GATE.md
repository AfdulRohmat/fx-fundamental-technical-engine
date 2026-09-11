# Decision Gate

## Mandatory preconditions

- mandatory source families pass or explicitly fail closed;
- point-in-time and revision tests pass;
- bias freeze verifies by hash;
- one candidate was selected without locked outcomes;
- deterministic and MQL5 decision parity passes on frozen fixtures;
- primary cost inputs and current real-tick overlap are available.

## Promotion economics

`PROCEED_TO_FORWARD_DEMO` requires all of:

1. at least 100 locked trades across the basket;
2. positive locked net expectancy after primary spread, commission, swap, and
   slippage;
3. higher locked net expectancy than the identical technical-only baseline;
4. positive net result in at least three of five pairs;
5. no pair contributes more than 50% of positive net profit;
6. maximum locked drawdown no worse than 12R;
7. no complete destruction under the registered delay/slippage stress;
8. no unresolved signal or execution reconciliation failure.

`RESEARCH_INCONCLUSIVE` applies when the system is economically nonnegative but
a mandatory evidence minimum such as coverage or trade count is not met.

`DO_NOT_PROCEED` applies when locked net expectancy is negative, the fundamental
filter fails to improve its baseline, or a mandatory integrity gate fails.

A locked failure is not permission to reverse a signal or tune the same slice.
A subsequent hypothesis requires a new contract and information boundary.
