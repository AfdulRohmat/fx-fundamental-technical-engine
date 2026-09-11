from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from fx_fundamental_technical.contracts import (
    ContractError,
    candidate_cells,
    contract_sha256,
    load_contract,
    stable_json,
    validate_contract,
)

CONTRACT_PATH = Path("config/research_contract_v0_1.json")
ACTIVE_CONTRACT_PATH = Path("config/research_contract_v0_2.json")


def test_registered_contract_is_valid() -> None:
    contract = load_contract(CONTRACT_PATH)

    validate_contract(contract)

    assert len(contract_sha256(contract)) == 64


def test_source_amended_contract_is_valid_and_flat_before_rollover() -> None:
    contract = load_contract(ACTIVE_CONTRACT_PATH)

    validate_contract(contract)

    risk = contract["risk"]
    execution = contract["execution"]
    assert isinstance(risk, dict)
    assert isinstance(execution, dict)
    assert risk["flat_before_rollover"] is True
    assert execution["swap_required_when_crossing_rollover"] is False


def test_candidate_cells_are_the_registered_two_by_three_matrix() -> None:
    contract = load_contract(CONTRACT_PATH)

    assert candidate_cells(contract) == (
        "F1_T1",
        "F1_T2",
        "F1_T3",
        "F2_T1",
        "F2_T2",
        "F2_T3",
    )


def test_rejects_pair_outside_currency_universe() -> None:
    contract = deepcopy(load_contract(CONTRACT_PATH))
    contract["pair_universe"] = ["EURUSD", "NZDUSD"]

    with pytest.raises(ContractError, match="outside currency_universe"):
        validate_contract(contract)


def test_rejects_parameter_grid() -> None:
    contract = deepcopy(load_contract(CONTRACT_PATH))
    policy = contract["iteration_policy"]
    assert isinstance(policy, dict)
    policy["parameter_grid_allowed"] = True

    with pytest.raises(ContractError, match="parameter grids are forbidden"):
        validate_contract(contract)


def test_rejects_invalid_json(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{", encoding="utf-8")

    with pytest.raises(ContractError, match="cannot load contract"):
        load_contract(bad_path)


def test_stable_json_is_independent_of_key_order() -> None:
    first = {"b": 2, "a": 1}
    second = json.loads('{"a": 1, "b": 2}')

    assert stable_json(first) == stable_json(second)
