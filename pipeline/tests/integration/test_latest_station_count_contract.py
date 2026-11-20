"""Tests of the published file's contract against its shared vectors and the fixtures."""

import json
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from obstore.store import LocalStore

from bikesharing.shell.delta import local_lakehouse
from bikesharing.shell.run import PublishTarget, RunConfig, run

REPO = Path(__file__).resolve().parents[3]
CONTRACTS = REPO / "contracts"
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


def _web_dir(tmp_path: Path) -> Path:
    """Return a web folder whose ``wrangler`` is a stand-in that deploys nothing."""
    folder = tmp_path / "web"
    binary = folder / "node_modules" / ".bin" / "wrangler"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR)
    return folder


# Verifies d008 R7
def test_the_file_built_from_the_fixtures_passes_the_schema(
    tmp_path: Path, bronze_folder: Path, delta_path: Path
) -> None:
    exclusion_list = tmp_path / "excluded_objects.txt"
    exclusion_list.touch()
    web_dir = _web_dir(tmp_path)
    config = RunConfig(
        version="contract",
        bronze=LocalStore(bronze_folder),
        lakehouse=local_lakehouse(delta_path),
        log_store=None,
        publish=PublishTarget(web_dir=web_dir, account_id="acct", api_token="token"),
        heartbeat_url=None,
        secrets=frozenset({"token"}),
        file_schema=SCHEMA,
        dbt_project_dir=REPO / "pipeline" / "dbt",
        exclusion_list=exclusion_list,
        work_dir=tmp_path / "work",
        container_memory_mib=512,
        end_instant=None,
        max_objects=360,
        time_budget=timedelta(hours=1),
        lookback=timedelta(hours=1),
        clock=lambda: datetime(2026, 10, 22, 8, 0, tzinfo=UTC),
    )

    assert run(config) == "succeeded"

    document = json.loads(
        (web_dir / "public" / "latest-station-count.json").read_text()
    )
    assert list(VALIDATOR.iter_errors(document)) == []
