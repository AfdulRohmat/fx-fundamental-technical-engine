# FX Fundamental Technical Engine

Research and execution project for a hybrid FX process:

```text
point-in-time macro and policy data
    -> currency policy state
    -> pair direction or FLAT
    -> mechanical technical entry
    -> costed MT5 backtest
    -> Telegram notification and demo-account forward test
```

The fixed separation is fundamental bias for direction, technical rules for
entry and exit, and an execution layer for risk and costs. Fundamental models
are never fitted against FX returns. Missing or stale required data fails closed
to `FLAT`.

## Initial scope

- Currencies: USD, EUR, GBP, JPY, AUD, CAD.
- Pairs: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD.
- Fundamental candidates: structural macro-policy (`F1`) and the same signal
  confirmed by a two-year sovereign-yield proxy (`F2`).
- Technical candidates: previous-day breakout/retest (`T1`), London opening
  range breakout (`T2`), and London-anchored tick-VWAP reclaim (`T3`).
- Macro training history: 2017 onward. Costed M15 test history: July 2021 onward
  after rejecting lower-granularity bars returned under the M15 request.

## Status

Phase 03 bias reconstruction is frozen without reading FX outcomes. The policy
forecast improves both baselines in point estimate, but its block-bootstrap
intervals cross zero, so policy skill is `NOT_SUPPORTED`. The project continues
with that caveat fixed in the record. Phase 04 found all three technical-only
baselines negative after registered costs; Phase 05 tests whether the frozen
fundamental permission filter adds enough value to become positive, not merely
whether it reduces losses.

See [the PRD](docs/PRD.md), [technical plan](docs/TECHNICAL_PLAN.md), and
[research log](docs/RESEARCH_LOG.md).

## Development

```powershell
python -m pytest
python -m ruff check .
python -m mypy src
```

Large raw and generated data are ignored. Reviewer-visible reports, contracts,
hashes, and compact evidence belong in Git.
