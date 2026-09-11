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

## Research outcome

Final verdict: `RESEARCH_INCONCLUSIVE`.

F2-confirmed structural policy bias materially improved the T3 London VWAP
reclaim in validation: +0.0979R/trade over 202 trades versus -0.1804R for T3.
It did not pass promotion because development was negative, validation drawdown
was 18.75R versus the 12R limit, uncertainty crossed zero, a timing placebo was
slightly better, and five-point slippage made it negative. The locked slice was
not run. Telegram, demo EA, and live execution are not authorized.

Read the [plain-language final review](evidence/phase07/REPORT.md) before using
any result from this repository.

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
