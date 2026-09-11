from __future__ import annotations

import pytest

from fx_fundamental_technical.research_gate import (
    FinalGateError,
    determine_verdict,
)


def test_no_validation_promotion_is_inconclusive_without_locked_run() -> None:
    verdict, _ = determine_verdict({"promoted_candidate": None}, {"status": "NOT_RUN"})

    assert verdict == "RESEARCH_INCONCLUSIVE"


def test_locked_run_without_candidate_is_rejected() -> None:
    with pytest.raises(FinalGateError, match="without a promoted"):
        determine_verdict({"promoted_candidate": None}, {"status": "COMPLETE"})
