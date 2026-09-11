"""Load and validate the pre-registered research contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

type JsonScalar = bool | int | float | str | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


class ContractError(ValueError):
    """Raised when a research contract violates a frozen invariant."""


def _mapping(value: JsonValue, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    return value


def _list(value: JsonValue, field: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ContractError(f"{field} must be a list")
    return value


def _string(value: JsonValue, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field} must be a non-empty string")
    return value


def _integer(value: JsonValue, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ContractError(f"{field} must be an integer")
    return value


def _boolean(value: JsonValue, field: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{field} must be a boolean")
    return value


def _strings(value: JsonValue, field: str) -> tuple[str, ...]:
    items = _list(value, field)
    result = tuple(_string(item, f"{field}[]") for item in items)
    if len(result) != len(set(result)):
        raise ContractError(f"{field} contains duplicates")
    return result


def _ids(value: JsonValue, field: str) -> tuple[str, ...]:
    records = _list(value, field)
    result = tuple(
        _string(_mapping(record, f"{field}[]").get("id"), f"{field}[].id")
        for record in records
    )
    if len(result) != len(set(result)):
        raise ContractError(f"{field} contains duplicate ids")
    return result


def _number(value: JsonValue, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{field} must be numeric")
    return float(value)


def load_contract(path: Path) -> JsonObject:
    """Read JSON and reject non-object or malformed contracts."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"cannot load contract {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ContractError("contract root must be an object")
    return cast(JsonObject, raw)


def candidate_cells(contract: JsonObject) -> tuple[str, ...]:
    """Return the registered Cartesian fundamental/technical candidate cells."""

    fundamentals = _ids(contract.get("fundamental_variants"), "fundamental_variants")
    technicals = _ids(contract.get("technical_variants"), "technical_variants")
    return tuple(
        f"{fundamental}_{technical}"
        for fundamental in fundamentals
        for technical in technicals
    )


def validate_contract(contract: JsonObject) -> None:
    """Validate design constraints that must not drift during research."""

    if _string(contract.get("schema_version"), "schema_version") != "0.1":
        raise ContractError("unsupported schema_version")

    currencies = _strings(contract.get("currency_universe"), "currency_universe")
    pairs = _strings(contract.get("pair_universe"), "pair_universe")
    if not currencies or not pairs:
        raise ContractError("currency and pair universes must not be empty")
    for pair in pairs:
        if len(pair) != 6 or pair[:3] not in currencies or pair[3:] not in currencies:
            raise ContractError(f"pair {pair!r} has legs outside currency_universe")

    if _ids(contract.get("fundamental_variants"), "fundamental_variants") != (
        "F1",
        "F2",
    ):
        raise ContractError("fundamental variants must remain exactly F1 and F2")
    if _ids(contract.get("technical_variants"), "technical_variants") != (
        "T1",
        "T2",
        "T3",
    ):
        raise ContractError("technical variants must remain exactly T1, T2, and T3")

    window = _mapping(contract.get("research_window"), "research_window")
    split = _mapping(
        window.get("chronological_split"), "research_window.chronological_split"
    )
    fractions = tuple(
        _number(split.get(name), f"chronological_split.{name}")
        for name in ("development", "validation", "locked_test")
    )
    if (
        any(fraction <= 0.0 for fraction in fractions)
        or abs(sum(fractions) - 1.0) > 1e-12
    ):
        raise ContractError("chronological split must be positive and sum to one")

    policy = _mapping(contract.get("iteration_policy"), "iteration_policy")
    if _boolean(policy.get("parameter_grid_allowed"), "parameter_grid_allowed"):
        raise ContractError("parameter grids are forbidden")
    if _boolean(
        policy.get("pair_specific_parameters_allowed"),
        "pair_specific_parameters_allowed",
    ):
        raise ContractError("pair-specific parameters are forbidden")
    if (
        _integer(
            policy.get("maximum_promoted_hybrid_candidates"),
            "maximum_promoted_hybrid_candidates",
        )
        != 1
    ):
        raise ContractError("exactly one hybrid candidate may be promoted")
    if (
        _integer(policy.get("locked_test_runs_allowed"), "locked_test_runs_allowed")
        != 1
    ):
        raise ContractError("locked test must remain single-use")

    registered_matrix = _strings(policy.get("development_matrix"), "development_matrix")
    if registered_matrix != candidate_cells(contract):
        raise ContractError(
            "development matrix is not the registered 2x3 Cartesian set"
        )

    gate = _mapping(contract.get("promotion_gate"), "promotion_gate")
    if _integer(gate.get("pair_count"), "promotion_gate.pair_count") != len(pairs):
        raise ContractError("promotion pair_count does not match pair_universe")
    if not _boolean(
        gate.get("requires_improvement_over_technical_baseline"),
        "promotion_gate.requires_improvement_over_technical_baseline",
    ):
        raise ContractError("technical-only baseline comparison is mandatory")


def stable_json(contract: JsonObject) -> str:
    """Return the canonical representation used for reproducibility hashing."""

    return json.dumps(
        contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def contract_sha256(contract: JsonObject) -> str:
    """Hash the canonical contract representation."""

    return hashlib.sha256(stable_json(contract).encode("utf-8")).hexdigest()
