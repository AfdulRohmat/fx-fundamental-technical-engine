# Phase 09 One-Bar VWAP Acceptance Contract

Status: registered before any one-bar-acceptance outcome was calculated.

## Question

Can one completed M15 acceptance candle remove immediate false VWAP reclaims
while preserving the right-tail payoff found in Phase 08, and does F2 still add
value over the identical technical-only rule?

The hypothesis was generated from Phase 08 development evidence. It is a new
entry rule, not a reinterpretation of Phase 08, and its development result is
not independent confirmation.

## Information boundary

- Development: `[2021-07-01, 2025-08-28)` UTC.
- Locked: `[2025-08-28, 2026-09-11)` UTC.
- Phase 09 may load only rows timestamped before the locked boundary.
- The locked interval may be opened once only if every frozen development gate
  passes and a candidate freeze is written first.

## Frozen decision sequence

1. T3 detects the first completed London-session close crossing tick VWAP.
2. The immediately following M15 candle is observation-only; no position is
   open during that candle.
3. For a long, that candle must close strictly above its causal London VWAP.
   For a short, it must close strictly below VWAP. Equality rejects the setup.
4. Entry occurs at the next available M15 open, still inside 08:00-17:00
   Europe/London. Any gap or missing bar rejects the setup.
5. ATR(14) includes the completed confirmation candle and no later bar.
6. F2 permission is evaluated again at the actual delayed entry. `FLAT`, stale,
   expired, or opposite-direction F2 rejects the setup.
7. The Phase 08 E1 exit remains unchanged: one-ATR hard stop, no fixed target,
   next-open VWAP invalidation, bias-flip exit, and pre-rollover liquidation.

No RSI, MACD, EMA, ADX, VWAP-distance threshold, candle-size threshold, volume
threshold, retest window, breakeven rule, or parameter grid is permitted.

## Required controls

- Phase 08 F2_T3_E1 immediate-entry ledger.
- The identical acceptance entry and E1 exit without fundamental permission.
- Reversed, one-snapshot-lag, and frequency-matched shuffled F2 permission.
- Two- and five-point slippage stress.
- One additional M15 entry-latency stress; it does not become a selectable
  confirmation variant.

The primary must improve both its Phase 08 control and technical-only
acceptance. It must also beat every bias placebo. These checks prevent a
technical-only effect from being attributed to fundamental bias.

## Promotion

Every machine-readable gate in `config/acceptance_research_v0_1.json` must pass.
Failure produces `NO_PROMOTION`, consumes zero locked runs, and forbids tuning
on the locked interval. Passing produces one immutable candidate freeze for a
separate locked run. Neither outcome authorizes demo or live trading.
