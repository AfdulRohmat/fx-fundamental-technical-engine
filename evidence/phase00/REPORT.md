# Phase 00 Evidence Report

Status: `PASS`.

## Objective

Freeze the research question, candidate count, clocks, execution assumptions,
comparison design, and decision thresholds before qualifying data or observing FX
PnL.

## Registered design

- Fundamental variants: F1 structural macro-policy; F2 F1 plus a relative
  two-year sovereign-yield-change confirmation proxy.
- Technical variants: T1 prior FX-day breakout/retest; T2 London opening-range
  breakout; T3 London-anchored tick-volume VWAP reclaim.
- Candidate matrix: six hybrid cells, with one promoted candidate maximum.
- Control: the matching technical rule without a fundamental filter.
- Split: chronological 60/20/20 development, validation, and single-use locked
  test. The historical locked slice is not claimed as pristine OOS; demo forward
  testing is the genuine OOS stage.

## Reproducibility

- Contract: `config/research_contract_v0_1.json`
- Contract SHA-256:
  `ea6c709579d3626f0d969b5f0be98432aadea14b475a0422cf027bbf89c86c49`
- Automated checks: 6 pytest tests passed; Ruff passed; strict mypy passed.
- FX PnL inspected: no

## Gate

Phase 00 passed because the registered JSON contract is validated and its
canonical hash is recorded. This says nothing about source availability or
strategy edge.
