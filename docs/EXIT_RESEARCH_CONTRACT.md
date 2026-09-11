# Phase 08 Exit-Asymmetry Research Contract

Status: registered before any new no-target price-path outcome was calculated.

## Question

Does replacing the fixed two-R target with a thesis-invalidation exit allow the
F2_T3 hybrid to preserve small losses while capturing a positively skewed
intraday return distribution?

This is a new strategy hypothesis. It does not reopen, repair, or reinterpret
the completed Phase 00-07 result.

## Information boundary

- Development: `[2021-07-01, 2025-08-28)` UTC. The formerly named validation
  slice is now development because its results informed this hypothesis.
- Locked: `[2025-08-28, 2026-09-11)` UTC.
- Phase 08 may not load a price, signal, event, bias snapshot, trade, or return
  at or after the locked boundary.
- Coverage metadata may establish that a locked file exists, but no locked
  market outcome may influence code, parameters, or promotion.

## Frozen entry and execution

F2_T3 is unchanged: a London-session tick-VWAP reclaim is permitted only when
the point-in-time structural-policy bias and two-year-yield confirmation agree
with its direction. News blackout, next-M15 entry, spread, Raw commission,
slippage, one entry per pair per FX day, two concurrent positions, bias-flip
exit, and pre-rollover liquidation remain frozen.

## Compared exits

`E0_FIXED_2R` is the existing control: one-ATR hard stop and two-R target.

`E1_VWAP_INVALIDATION` is the sole candidate:

- initial hard stop is one entry-time M15 ATR and never widens;
- there is no fixed take-profit;
- London VWAP starts at 08:00 Europe/London and updates through the session;
- after 17:00 London, the last completed session VWAP is held constant;
- a long invalidates on a completed close below VWAP and a short invalidates on
  a completed close above VWAP;
- invalidation executes at the next available M15 open;
- an active hard stop has adverse-first priority;
- all positions still close before rollover.

There is no chandelier multiplier, breakeven trigger, partial take-profit, or
parameter grid in this phase.

## Path diagnostic

The candidate ledger records executable-side MFE and MAE in initial-R units.
For trades that reach +2R, the report measures continuation to +3R, +4R, and
+5R before exit. These measurements explain the payoff path; they do not tune
the exit rule or become retrospective entry filters.

## Development promotion gate

Every check in `config/exit_research_v0_1.json` must pass. In particular, E1
must be positive after costs, improve E0, remain within 25R drawdown, be
positive across at least three pairs and three calendar years, avoid
single-pair profit concentration, have a positive three-month-block bootstrap
lower bound, survive two-point slippage, avoid severe failure at five points,
and stay positive when invalidation execution is delayed by one bar.

Failure keeps the locked slice closed and ends this hypothesis as
`NO_PROMOTION`. Passing creates one immutable candidate freeze and permits one
separate locked run. No Phase 08 result authorizes live or demo trading.
