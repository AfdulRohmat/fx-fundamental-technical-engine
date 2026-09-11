# Technical Entry Contract

All decisions use completed bars. Orders execute on the next tradable M15 open.
Rules are symmetric for long and short, and all time windows are DST-aware.

## T1 - previous FX-day breakout and retest

The prior FX day runs from 17:00 New York to 17:00 New York. For a long signal,
an H1 bar must close above the prior FX-day high. During the next four completed
M15 bars, a retest bar must trade at or below that high and close above it. Enter
long on the next M15 open. Short rules mirror the prior low.

## T2 - London opening-range breakout

The opening range is 08:00 through 09:00 Europe/London. After it completes, the
first M15 close outside the range in an allowed direction triggers entry at the
next M15 open. Only signals inside the common entry window are valid.

## T3 - London-anchored tick-VWAP reclaim

VWAP resets at 08:00 Europe/London and uses completed M15 HLC3 weighted by
Exness tick volume. A long setup requires at least one completed close below
VWAP followed by a completed close above it; short is symmetric. Entry is at
the next M15 open. VWAP is an execution anchor, not claimed fair value.

## Common controls

- Technical-only baselines permit both directions.
- Hybrid variants permit only the active fundamental direction.
- No new entry begins from 30 minutes before through 30 minutes after a
  high-impact event for either pair currency.
- Maximum one entry per pair per FX day and two concurrent portfolio positions.
- Initial stop distance is one M15 ATR(14); take profit is two initial R.
- Position exits after 24 hours, at 20:45 UTC before the earliest broker
  rollover, at Friday 16:45 New York, or after an effective fundamental
  flip/FLAT state, whichever occurs first. The pre-rollover exit was registered
  during source qualification because free historical swap schedules are not
  available; therefore no tested trade may incur swap.
- Ambiguous same-bar stop/target ordering uses the adverse-first result unless
  real ticks resolve the order.
