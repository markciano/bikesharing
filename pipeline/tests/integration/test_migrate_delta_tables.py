"""Integration tests of the one-off migration of the Delta tables.

The script lives outside the package, so it is loaded by path. Each test writes
a local lakehouse in the layout the migration starts from: ``processed_objects``
with no ``utc_date`` and no partitions, and ``station_stock`` partitioned by
``local_date``, both with no table properties (d008, Delta writes).
"""

import importlib.util
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import duckdb
import pytest
from arro3.core import Table
from deltalake import DeltaTable, QueryBuilder, Schema, write_deltalake

from bikesharing.core.settings import TABLE_PATHS, TableName
from bikesharing.shell.delta import (
    PARTITION_COLUMNS,
    PROCESSED_OBJECTS_SCHEMA,
    STATION_STOCK_SCHEMA,
    ensure_tables,
    latest_processed,
    local_lakehouse,
)

SCRIPT = Path(__file__).parents[2] / "scripts" / "migrate_delta_tables.py"
CODE_VERSION = "0123456789abcdef0123456789abcdef01234567"

# The processed objects of two runs, the first two on either side of a UTC
# midnight, which is not the local one, so their utc_date differs.
PROCESSED_ROWS = [
    (
        "raw/ambici/station_status/2026-11-20/2026-11-19T23:50:00Z.json.gz",
        "ambici",
        "2026-11-19 23:50:00+00",
        "run-1",
        "aaa111",
    ),
    (
        "raw/ambici/station_status/2026-11-20/2026-11-20T00:10:00Z.json.gz",
        "ambici",
        "2026-11-20 00:10:00+00",
        "run-2",
        "bbb222",
    ),
    (
        "raw/bicing/station_status/2026-11-19/2026-11-19T12:00:00Z.json.gz",
        "bicing",
        "2026-11-19 12:00:00+00",
        "run-1",
        "aaa111",
    ),
    (
        "raw/bicing/station_status/2026-11-20/2026-11-20T00:00:00Z.json.gz",
        "bicing",
        "2026-11-20 00:00:00+00",
        "run-2",
        "bbb222",
    ),
]

PROCESSED_TABLE_SQL = """
create table processed (
    key varchar not null,
    system varchar not null,
    feed varchar not null,
    captured_at timestamp with time zone not null,
    station_count integer not null,
    status varchar not null,
    run_id varchar not null,
    code_version varchar not null
)
"""


def load_migration() -> ModuleType:
    """The migration script, imported from its path."""
    spec = importlib.util.spec_from_file_location("migrate_delta_tables", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = load_migration()


def table_uri(lakehouse: Path, table: TableName) -> str:
    """The URI of ``table`` in the local lakehouse."""
    return str(lakehouse / TABLE_PATHS[table])


def write_processed_objects(lakehouse: Path) -> None:
    """Write ``processed_objects`` in its layout before the migration.

    Each run's rows are one append, as each run records its batch.
    """
    uri = table_uri(lakehouse, "processed_objects")
    DeltaTable.create(
        uri,
        Schema([f for f in PROCESSED_OBJECTS_SCHEMA.fields if f.name != "utc_date"]),
    )
    con = duckdb.connect()
    con.execute(PROCESSED_TABLE_SQL)
    for key, system, captured_at, run_id, code_version in PROCESSED_ROWS:
        con.execute(
            "insert into processed values "
            "($key, $system, 'station_status', $captured_at, 2, 'processed', "
            "$run_id, $code_version)",
            {
                "key": key,
                "system": system,
                "captured_at": captured_at,
                "run_id": run_id,
                "code_version": code_version,
            },
        )
    for run_id in ("run-1", "run-2"):
        rows = con.sql(f"select * from processed where run_id = '{run_id}'")
        write_deltalake(uri, rows, mode="append")


def write_station_stock(lakehouse: Path) -> None:
    """Write ``station_stock`` in its layout, which the migration keeps."""
    uri = table_uri(lakehouse, "station_stock")
    DeltaTable.create(uri, STATION_STOCK_SCHEMA, partition_by=["local_date"])
    rows = duckdb.connect().sql(
        "select 'ambici' as system, '1' as station_id, "
        "timestamptz '2026-11-19 23:50:00+00' as captured_at, "
        "date '2026-11-20' as local_date, 50::smallint as local_minute, "
        "3 as num_vehicles_available, 5 as num_docks_available, "
        "null::integer as num_vehicles_disabled, null::integer as num_docks_disabled, "
        "true as is_installed, true as is_renting, true as is_returning, "
        "timestamptz '2026-11-19 23:50:00+00' as last_reported, "
        "timestamptz '2026-11-19 23:50:00+00' as last_updated, "
        "'run-1' as run_id, 'aaa111' as code_version"
    )
    write_deltalake(uri, rows, mode="append")


@pytest.fixture
def lakehouse(delta_path: Path) -> Path:
    """A local lakehouse with both tables in their layout before the migration."""
    write_processed_objects(delta_path)
    write_station_stock(delta_path)
    return delta_path


@pytest.fixture
def processed_uri(lakehouse: Path) -> str:
    """The URI of the lakehouse's ``processed_objects``."""
    return table_uri(lakehouse, "processed_objects")


def rows(uri: str) -> list[tuple[Any, ...]]:
    """Every row of the table at ``uri``'s latest version, sorted."""
    reader = QueryBuilder().register("t", DeltaTable(uri)).execute("select * from t")
    return sorted(duckdb.from_arrow(reader).fetchall())


def commits_since(uri: str, version: int) -> list[dict[str, Any]]:
    """The commits of the table at ``uri`` after ``version``, oldest first."""
    history = [c for c in DeltaTable(uri).history() if c["version"] > version]
    return sorted(history, key=lambda c: c["version"])


def append_duplicate_row(uri: str) -> None:
    """Append a copy of one row."""
    reader = (
        QueryBuilder().register("t", DeltaTable(uri)).execute("select * from t limit 1")
    )
    write_deltalake(uri, reader, mode="append")


def alter_key(uri: str) -> None:
    """Change one row's key."""
    DeltaTable(uri).update(
        updates={"key": "'raw/ambici/station_status/other.json.gz'"},
        predicate=f"key = '{PROCESSED_ROWS[0][0]}'",
    )


def alter_run_id(uri: str) -> None:
    """Change one row's run ID, keeping its key."""
    DeltaTable(uri).update(
        updates={"run_id": "'run-9'"}, predicate=f"key = '{PROCESSED_ROWS[0][0]}'"
    )


# Verifies d010 R6
def test_verify_passes_on_a_correct_rewrite(processed_uri: str) -> None:
    before = DeltaTable(processed_uri).version()
    migration.rewrite(processed_uri, {}, CODE_VERSION)

    assert migration.verify(processed_uri, {}, before=before) == []


def test_rewrite_writes_the_table_ensure_tables_creates(processed_uri: str) -> None:
    migration.rewrite(processed_uri, {}, CODE_VERSION)

    table = DeltaTable(processed_uri)
    assert table.schema().to_json() == PROCESSED_OBJECTS_SCHEMA.to_json()
    assert table.metadata().partition_columns == list(
        PARTITION_COLUMNS["processed_objects"]
    )


def test_rewrite_sets_each_rows_utc_date_from_captured_at(processed_uri: str) -> None:
    migration.rewrite(processed_uri, {}, CODE_VERSION)

    reader = (
        QueryBuilder()
        .register("t", DeltaTable(processed_uri))
        .execute("select key, cast(utc_date as varchar) as utc_date from t")
    )
    assert dict(duckdb.from_arrow(reader).fetchall()) == {
        PROCESSED_ROWS[0][0]: "2026-11-19",
        PROCESSED_ROWS[1][0]: "2026-11-20",
        PROCESSED_ROWS[2][0]: "2026-11-19",
        PROCESSED_ROWS[3][0]: "2026-11-20",
    }


# Verifies d010 R7
@pytest.mark.parametrize(
    ("alter", "failed"),
    [
        (append_duplicate_row, ["rows"]),
        (alter_key, ["keys", "lineage"]),
        (alter_run_id, ["lineage"]),
    ],
    ids=["rows", "keys", "lineage"],
)
def test_verify_names_the_check_an_altered_rewrite_fails(
    processed_uri: str, alter: Callable[[str], None], failed: list[str]
) -> None:
    before = DeltaTable(processed_uri).version()
    migration.rewrite(processed_uri, {}, CODE_VERSION)
    alter(processed_uri)

    assert migration.verify(processed_uri, {}, before=before) == failed


# Verifies d010 R17
def test_migrate_restores_the_table_when_the_rewrite_fails_a_check(
    lakehouse: Path, processed_uri: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = rows(processed_uri)
    before = DeltaTable(processed_uri).version()
    rewrite = migration.rewrite

    def dropping_rewrite(
        uri: str, storage_options: Mapping[str, str], code_version: str
    ) -> None:
        rewrite(uri, storage_options, code_version)
        DeltaTable(uri).delete(f"key = '{PROCESSED_ROWS[0][0]}'")

    monkeypatch.setattr(migration, "rewrite", dropping_rewrite)

    failed = migration.migrate(str(lakehouse), {}, CODE_VERSION)

    table = DeltaTable(processed_uri)
    assert failed
    assert table.metadata().partition_columns == []
    assert rows(processed_uri) == original
    restore = commits_since(processed_uri, before)[-1]
    assert restore["operation"] == "RESTORE"
    assert restore["code_version"] == CODE_VERSION


# Verifies d010 R8
def test_migrate_keeps_station_stocks_data_files(lakehouse: Path) -> None:
    uri = table_uri(lakehouse, "station_stock")
    files = sorted(DeltaTable(uri).file_uris())
    before = DeltaTable(uri).version()

    assert migration.migrate(str(lakehouse), {}, CODE_VERSION) == []

    assert sorted(DeltaTable(uri).file_uris()) == files
    assert [c["operation"] for c in commits_since(uri, before)] == ["SET TBLPROPERTIES"]


# Verifies d010 R9
def test_migrate_records_its_code_version_in_each_commit(lakehouse: Path) -> None:
    versions = {
        name: DeltaTable(table_uri(lakehouse, name)).version() for name in TABLE_PATHS
    }

    migration.migrate(str(lakehouse), {}, CODE_VERSION)

    commits = [
        commit
        for name, version in versions.items()
        for commit in commits_since(table_uri(lakehouse, name), version)
    ]
    assert commits
    assert {commit.get("code_version") for commit in commits} == {CODE_VERSION}


def test_migrate_sets_the_table_properties_ensure_tables_creates(
    lakehouse: Path,
) -> None:
    migration.migrate(str(lakehouse), {}, CODE_VERSION)

    created = ensure_tables(local_lakehouse(lakehouse.parent / "created"))
    for name in TABLE_PATHS:
        migrated = DeltaTable(table_uri(lakehouse, name)).metadata().configuration
        expected = DeltaTable(created.lakehouse.table_uri(TABLE_PATHS[name])).metadata()
        assert migrated == expected.configuration


def test_migrate_skips_the_rewrite_of_a_migrated_table(
    lakehouse: Path, processed_uri: str
) -> None:
    migration.migrate(str(lakehouse), {}, CODE_VERSION)
    migrated = rows(processed_uri)
    before = DeltaTable(processed_uri).version()

    assert migration.migrate(str(lakehouse), {}, CODE_VERSION) == []

    assert rows(processed_uri) == migrated
    assert [c["operation"] for c in commits_since(processed_uri, before)] == [
        "SET TBLPROPERTIES"
    ]


def test_migrated_processed_objects_gives_each_feeds_latest_capture(
    lakehouse: Path, processed_uri: str
) -> None:
    migration.migrate(str(lakehouse), {}, CODE_VERSION)

    actions = Table.from_arrow(DeltaTable(processed_uri).get_add_actions(flatten=True))
    latest = latest_processed(ensure_tables(local_lakehouse(lakehouse)))

    maxima = actions["max.captured_at"]
    assert all(maxima[i].as_py() is not None for i in range(len(maxima)))
    assert {feed: instant.isoformat() for feed, instant in latest.items()} == {
        ("ambici", "station_status"): "2026-11-20T00:10:00+00:00",
        ("bicing", "station_status"): "2026-11-20T00:00:00+00:00",
    }
