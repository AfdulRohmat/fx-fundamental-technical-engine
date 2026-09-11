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

### Phase 08 exit follow-up

A separately registered development experiment replaced the fixed two-R target
on F2_T3 with a no-target, next-bar London-VWAP invalidation exit. It confirmed
that some winners continue far beyond two R: 41.75% of the 206 trades reaching
+2R also reached +5R, and the largest realized winner was +20.16R.

The overall strategy nevertheless remained negative after commission at
-0.0266R/trade over 839 development trades. Only two pairs and two calendar
years were positive, drawdown was 103.96R, the bootstrap interval crossed zero,
and two points of added slippage reduced expectancy to -0.0766R. Phase 08 is
therefore `NO_PROMOTION`; its locked slice remains unopened and operational
permission is still denied. See the
[Phase 08 readable report](evidence/phase08/REPORT.md).

### Phase 09 entry-quality follow-up

A pre-registered one-bar acceptance rule required the candle immediately after
the T3 reclaim to close on the reclaimed side of causal London VWAP. F2 remained
the mandatory directional permission and was checked again at the delayed
entry. No new indicator or threshold was introduced.

This was the first follow-up to produce positive development economics:
+0.0492R/trade and +28.07R over 571 trades, compared with -0.0266R for immediate
F2 entry and -0.1182R for the identical acceptance rule without fundamental
bias. Reversed and shuffled bias placebos were negative; a one-snapshot-lag
placebo was positive but weaker at +0.0253R.

It is still `NO_PROMOTION`. Maximum drawdown was 60.46R, 57.24% of positive-pair
profit came from USDCAD, the bootstrap interval crossed zero, and two points of
added slippage reduced expectancy below zero. The locked slice remains
unopened; Telegram, demo EA, and live execution remain unauthorized. See the
[Phase 09 readable report](evidence/phase09/REPORT.md).

See [the PRD](docs/PRD.md), [technical plan](docs/TECHNICAL_PLAN.md), and
[research log](docs/RESEARCH_LOG.md).

## Development

```powershell
python -m pytest
python -m ruff check .
python -m mypy src
python -m fx_fundamental_technical.cli phase09-acceptance-research
```

Large raw and generated data are ignored. Reviewer-visible reports, contracts,
hashes, and compact evidence belong in Git.
