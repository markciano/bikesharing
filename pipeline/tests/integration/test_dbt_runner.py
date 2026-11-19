"""Integration tests of ``dbt build`` in process, over the bronze fixtures."""

import gzip
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pytest

from bikesharing.core.read_schema import STATION_FIELDS, STATION_STATUS_COLUMNS
from bikesharing.core.verdict import NodeResult, judge_batch
from bikesharing.shell.dbt_runner import DbtInvocationError, DbtPaths, dbt_build
from bikesharing.shell.duckdb_session import connect, station_stock_local_dates

DBT_PROJECT = Path(__file__).resolve().parents[2] / "dbt"

CAPTURE_HISTORY_COLUMNS = {
    "key": "varchar",
    "system": "varchar",
    "feed": "varchar",
    "captured_at": "timestamptz",
    "station_count": "integer",
    "status": "varchar",
    "run_id": "varchar",
    "code_version": "varchar",
}

LATEST_CAPTURES_COLUMNS = {
    "system": "varchar",
    "station_id": "varchar",
    "captured_at": "timestamptz",
    "local_date": "date",
    "local_minute": "smallint",
    "num_vehicles_available": "integer",
    "num_docks_available": "integer",
    "num_vehicles_disabled": "integer",
    "num_docks_disabled": "integer",
    "is_installed": "boolean",
    "is_renting": "boolean",
    "is_returning": "boolean",
    "last_reported": "timestamptz",
    "last_updated": "timestamptz",
    "run_id": "varchar",
    "code_version": "varchar",
}

SILVER_NODES = {
    "stg_ambici__station_status",
    "stg_bicing__station_status",
    "station_stock",
    "capture_volume",
    "schema_drift",
    "DQR1",
    "DQR11",
    "DQR12",
    "DQR13",
}


def write_empty_parquet(path: Path, columns: dict[str, str]) -> str:
    """Write a Parquet file with the given columns and no rows; return its path."""
    select = ", ".join(f"null::{type_} as {name}" for name, type_ in columns.items())
    duckdb.connect().sql(f"select {select} limit 0").write_parquet(str(path))
    return str(path)


@pytest.fixture
def paths(tmp_path: Path) -> DbtPaths:
    """The run's paths: the work folder is the test's own folder."""
    return DbtPaths(
        project_dir=DBT_PROJECT,
        scratch_database=tmp_path / "scratch.duckdb",
        allowed_directory=tmp_path,
        temp_directory=tmp_path / "spill",
        duckdb_memory_limit_mib=256,
    )


@pytest.fixture
def batch_variables(tmp_path: Path, bronze_folder: Path) -> dict[str, Any]:
    """The variables of every layer, with bronze's files being every fixture.

    dbt parses the whole project, so each call passes them all (d008, ``dbt_runner``).
    """
    return {
        "bronze_files": {
            system: sorted(
                str(file)
                for file in (bronze_folder / "raw" / system / "station_status").rglob(
                    "*.json.gz"
                )
            )
            for system in STATION_STATUS_COLUMNS
        },
        "read_columns": {
            system: dict(columns) for system, columns in STATION_STATUS_COLUMNS.items()
        },
        "station_fields": {
            system: sorted(fields) for system, fields in STATION_FIELDS.items()
        },
        "capture_history_file": write_empty_parquet(
            tmp_path / "capture_history.parquet", CAPTURE_HISTORY_COLUMNS
        ),
        "latest_captures_file": write_empty_parquet(
            tmp_path / "latest_captures.parquet", LATEST_CAPTURES_COLUMNS
        ),
        "run_id": "test",
        "code_version": "test",
    }


def by_name(results: list[NodeResult]) -> dict[str, NodeResult]:
    """Index the nodes of a build by name."""
    return {result.name: result for result in results}


# Verifies d008 R8
def test_dbt_build_returns_each_node_with_its_status(
    paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    reported: list[NodeResult] = []

    results = dbt_build(
        paths, select="silver", variables=batch_variables, on_node=reported.append
    )

    nodes = by_name(results)
    assert set(nodes) == SILVER_NODES
    # The fixtures' objects lack a declared field or carry an extra one: DQR11 warns.
    assert nodes["DQR11"].status == "warn"
    assert nodes["DQR11"].severity == "warn"
    assert {r.status for r in results if r.name != "DQR11"} == {"success", "pass"}
    assert nodes["station_stock"].resource_type == "model"
    assert nodes["station_stock"].severity is None
    assert nodes["station_stock"].failures is None
    assert nodes["DQR1"].resource_type == "test"
    assert nodes["DQR1"].severity == "error"
    assert nodes["DQR1"].failures == 0
    assert nodes["DQR12"].severity == "warn"
    assert all(result.duration_s >= 0 for result in results)
    assert sorted(reported, key=lambda r: r.unique_id) == sorted(
        results, key=lambda r: r.unique_id
    )
    assert judge_batch(results).commit


def duplicate_first_station(object_file: Path) -> None:
    """Rewrite a bronze object so that its first station is listed twice."""
    body = json.loads(gzip.decompress(object_file.read_bytes()))
    stations = body["data"]["stations"]
    stations.append(stations[0])
    object_file.write_bytes(gzip.compress(json.dumps(body).encode()))


# Verifies d008 R8
def test_dbt_build_ends_a_failing_data_test_in_fail_and_runs_the_others(
    paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    duplicate_first_station(Path(batch_variables["bronze_files"]["ambici"][0]))

    results = dbt_build(
        paths, select="silver", variables=batch_variables, on_node=lambda _: None
    )

    nodes = by_name(results)
    assert set(nodes) == SILVER_NODES
    assert nodes["DQR1"].status == "fail"
    assert nodes["DQR1"].failures is not None
    assert nodes["DQR1"].failures > 0
    assert nodes["capture_volume"].status == "success"
    assert nodes["DQR13"].status == "pass"
    assert not judge_batch(results).commit


def test_dbt_build_raises_on_a_parse_error(
    tmp_path: Path, paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    project = tmp_path / "broken_project"
    shutil.copytree(
        DBT_PROJECT, project, ignore=shutil.ignore_patterns("target", "logs")
    )
    (project / "models" / "silver" / "broken.sql").write_text(
        "select * from {{ ref('does_not_exist') }}\n"
    )
    broken = DbtPaths(
        project_dir=project,
        scratch_database=paths.scratch_database,
        allowed_directory=paths.allowed_directory,
        temp_directory=paths.temp_directory,
        duckdb_memory_limit_mib=paths.duckdb_memory_limit_mib,
    )

    with pytest.raises(DbtInvocationError):
        dbt_build(
            broken, select="silver", variables=batch_variables, on_node=lambda _: None
        )


def test_dbt_build_reads_an_empty_file_as_a_system_with_no_object(
    tmp_path: Path, paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    # DuckDB reads no empty list of files, so the shell passes, for a system with
    # no object in the batch, one empty file of the work folder.
    empty = tmp_path / "empty.json"
    empty.touch()
    batch_variables["bronze_files"]["ambici"] = [str(empty)]

    results = dbt_build(
        paths, select="silver", variables=batch_variables, on_node=lambda _: None
    )

    nodes = by_name(results)
    assert nodes["stg_ambici__station_status"].status == "success"
    assert nodes["station_stock"].status == "success"
    assert judge_batch(results).commit


def test_dbt_build_leaves_the_scratch_database_openable_by_connect(
    paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    dbt_build(paths, select="silver", variables=batch_variables, on_node=lambda _: None)

    con = connect(
        paths.scratch_database,
        allowed_directories=[paths.allowed_directory],
        temp_directory=paths.temp_directory,
        duckdb_memory_limit_mib=paths.duckdb_memory_limit_mib,
    )

    assert station_stock_local_dates(con) == frozenset(
        {date(2026, 10, 19), date(2026, 10, 22)}
    )


def test_dbt_build_runs_two_batches_in_one_process(
    paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    for _ in range(2):
        results = dbt_build(
            paths, select="silver", variables=batch_variables, on_node=lambda _: None
        )

        assert judge_batch(results).commit


def test_dbt_build_builds_gold_with_the_variables_of_every_layer(
    paths: DbtPaths, batch_variables: dict[str, Any]
) -> None:
    results = dbt_build(
        paths, select="gold", variables=batch_variables, on_node=lambda _: None
    )

    assert {result.name: result.status for result in results} == {
        "latest_station_count": "success"
    }
