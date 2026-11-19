"""Tests of the published file's contract against its shared vectors."""

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

CONTRACTS = Path(__file__).parents[3] / "contracts"
SCHEMA = json.loads((CONTRACTS / "latest-station-count.schema.json").read_text())
VECTORS = json.loads((CONTRACTS / "latest-station-count.json").read_text())

# Contract producer: contracts/latest-station-count.json, read by the page from T041.
VALIDATOR = Draft202012Validator(SCHEMA)


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


# Verifies DQR14
@pytest.mark.parametrize(
    "case", VECTORS["valid"], ids=[case["name"] for case in VECTORS["valid"]]
)
def test_valid_file_passes_the_schema(case: dict[str, Any]) -> None:
    assert list(VALIDATOR.iter_errors(case["file"])) == []


# Verifies DQR14
@pytest.mark.parametrize(
    "case", VECTORS["invalid"], ids=[case["reason"] for case in VECTORS["invalid"]]
)
def test_invalid_file_fails_the_schema_on_exactly_one_rule(
    case: dict[str, Any],
) -> None:
    assert len(list(VALIDATOR.iter_errors(case["file"]))) == 1
