"""Final registered research verdict derived from immutable phase evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fx_fundamental_technical.evidence import (
    canonical_sha256,
    file_sha256,
    write_json_atomic,
)

VERDICTS = {
    "PROCEED_TO_FORWARD_DEMO",
    "RESEARCH_INCONCLUSIVE",
    "DO_NOT_PROCEED",
}


class FinalGateError(ValueError):
    """Raised when final evidence is missing or internally contradictory."""


def _object(path: Path) -> dict[str, object]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, dict):
        raise FinalGateError(f"expected JSON object: {path}")
    return cast(dict[str, object], decoded)


def determine_verdict(
    phase05: dict[str, object], phase06: dict[str, object]
) -> tuple[str, list[str]]:
    """Apply the decision contract without discretionary threshold changes."""

    promoted = phase05.get("promoted_candidate")
    if promoted is None:
        if phase06.get("status") != "NOT_RUN":
            raise FinalGateError("locked phase ran without a promoted candidate")
        return (
            "RESEARCH_INCONCLUSIVE",
            [
                "No hybrid candidate passed every validation promotion check.",
                (
                    "The best diagnostic cell was economically positive and "
                    "improved its baseline."
                ),
                (
                    "No locked trade metric exists, so this is not a locked "
                    "economic failure."
                ),
            ],
        )
    if phase06.get("status") != "COMPLETE":
        raise FinalGateError("promoted candidate lacks a completed locked result")
    locked = phase06.get("promotion_gate")
    if not isinstance(locked, dict):
        raise FinalGateError("completed locked result lacks promotion checks")
    if all(bool(value) for value in locked.values()):
        return "PROCEED_TO_FORWARD_DEMO", ["Every registered locked gate passed."]
    return "DO_NOT_PROCEED", ["At least one registered locked gate failed."]


def run_phase07(
    phase03_path: Path,
    phase04_path: Path,
    phase05_path: Path,
    phase06_path: Path,
    output_path: Path,
) -> dict[str, object]:
    phase03 = _object(phase03_path)
    phase04 = _object(phase04_path)
    phase05 = _object(phase05_path)
    phase06 = _object(phase06_path)
    verdict, reasons = determine_verdict(phase05, phase06)
    if verdict not in VERDICTS:
        raise FinalGateError(f"invalid verdict: {verdict}")
    diagnostic_candidate = str(phase05["diagnostic_candidate"])
    diagnostic = cast(dict[str, object], phase05["results"])
    candidate = cast(dict[str, object], diagnostic[diagnostic_candidate])
    assessment = cast(dict[str, object], candidate["assessment"])
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "verdict": verdict,
        "operational_permission": "DENIED",
        "telegram_build_authorized": False,
        "demo_ea_forward_test_authorized": False,
        "reasons": reasons,
        "policy_diagnostic": phase03.get("policy_diagnostic"),
        "technical_baseline_status": phase04.get("status"),
        "hybrid_validation_status": phase05.get("status"),
        "best_diagnostic_candidate": diagnostic_candidate,
        "best_candidate_assessment": assessment,
        "locked_test_status": phase06.get("status"),
        "locked_strategy_runs_consumed": phase06.get("locked_strategy_runs_consumed"),
        "tuning_after_result": False,
        "evidence": [
            {"path": str(path), "sha256": file_sha256(path)}
            for path in (phase03_path, phase04_path, phase05_path, phase06_path)
        ],
    }
    payload["summary_sha256"] = canonical_sha256(payload)
    write_json_atomic(output_path, payload)
    return payload
