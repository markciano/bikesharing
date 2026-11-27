"""Integration tests of the Delta tables, on a lakehouse in a local folder."""

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from deltalake import DeltaTable, Field, QueryBuilder, Schema
from deltalake.exceptions import CommitFailedError
from deltalake.schema import PrimitiveType

from bikesharing.core.settings import (
    CHECKPOINT_INTERVAL,
    LOCAL_TIMEZONE,
    TABLE_PATHS,
    TOMBSTONE_RETENTION,
    System,
    TableName,
)
from bikesharing.core.verdict import MergeMetrics
from bikesharing.shell.delta import (
    PROCESSED_OBJECTS_SCHEMA,
    STATION_STOCK_SCHEMA,
    ProcessedObject,
    Tables,
    capture_history,
    ensure_tables,
    latest_captures,
    latest_processed,
    local_lakehouse,
    merge_station_stock,
    processed_keys,
    r2_lakehouse,
    record_processed,
)
from bikesharing.shell.duckdb_session import ArrowStream, connect, write_parquet

T0 = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)

# The station stock's columns in the order and types of its dbt contract
# (d008, dbt model contracts), as DuckDB hands them to the shell.
STOCK_TABLE_SQL = """
create table {name} (
    system varchar not null,
    station_id varchar not null,
    captured_at timestamp with time zone not null,
    local_date date not null,
    local_minute smallint not null,
    num_vehicles_available integer,
    num_docks_available integer,
    num_vehicles_disabled integer,
    num_docks_disabled integer,
    is_installed boolean not null,
    is_renting boolean not null,
    is_returning boolean not null,
    last_reported timestamp with time zone not null,
    last_updated timestamp with time zone not null,
    run_id varchar not null,
    code_version varchar not null
)
"""

type StockRow = tuple[System, str, datetime]


@pytest.fixture
def tables(tmp_path: Path) -> Tables:
    """A run's tables, in a lakehouse in a local folder."""
    return ensure_tables(local_lakehouse(tmp_path / "lakehouse"))


@pytest.fixture
def con() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB that builds the batches' rows."""
    return duckdb.connect()


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """The folder standing in for the run's work folder."""
    folder = tmp_path / "work"
    folder.mkdir()
    return folder


def stock(
    con: duckdb.DuckDBPyConnection, name: str, rows: Sequence[StockRow]
) -> duckdb.DuckDBPyRelation:
    """A batch's station stock: one row per system, station and capture instant."""
    con.execute(STOCK_TABLE_SQL.format(name=name))
    for system, station_id, captured_at in rows:
        local = captured_at.astimezone(LOCAL_TIMEZONE)
        con.execute(
            f"insert into {name} values "
            "($system, $station_id, $captured_at, $local_date, $local_minute, "
            "3, 5, null, null, true, true, true, $captured_at, $captured_at, "
            "'run-1', 'abc123')",
            {
                "system": system,
                "station_id": station_id,
                "captured_at": captured_at,
                "local_date": local.date(),
                "local_minute": local.hour * 60 + local.minute,
            },
        )
    return con.table(name)


def merge(
    tables: Tables,
    rows: ArrowStream,
    captures: Sequence[datetime],
    *,
    attempts: int = 3,
) -> MergeMetrics:
    """Merge a batch whose rows were captured at ``captures``."""
    return merge_station_stock(
        tables,
        rows,
        first_capture=min(captures),
        last_capture=max(captures),
        local_dates={capture.astimezone(LOCAL_TIMEZONE).date() for capture in captures},
        attempts=attempts,
    )


def open_table(tables: Tables, path: str) -> DeltaTable:
    """A handle of the test's own on the table at ``path``, at its latest version."""
    return DeltaTable(tables.lakehouse.table_uri(path))


def stock_keys(tables: Tables) -> list[tuple[str, str, datetime]]:
    """The natural key of every row of ``station_stock``, sorted."""
    reader = (
        QueryBuilder()
        .register("t", open_table(tables, TABLE_PATHS["station_stock"]))
        .execute("select system, station_id, captured_at from t")
    )
    return sorted(
        (system, station_id, captured_at.astimezone(UTC))
        for system, station_id, captured_at in duckdb.from_arrow(reader).fetchall()
    )


def processed(key: str, system: System, captured_at: datetime) -> ProcessedObject:
    """A processed bronze object of ``system``'s ``station_status``."""
    return ProcessedObject(
        key=key,
        system=system,
        feed="station_status",
        captured_at=captured_at,
        station_count=2,
        status="processed",
        run_id="run-1",
        code_version="abc123",
    )


class Interfering:
    """An Arrow stream that commits another writer's batch when first exported.

    The other writer, a second run with its own tables, commits its MERGE
    between the moment the module reads its table handle and the moment it
    commits, which is a commit conflict.
    """

    def __init__(
        self,
        tables: Tables,
        rows: duckdb.DuckDBPyRelation,
        other: duckdb.DuckDBPyRelation,
        other_captures: Sequence[datetime],
    ) -> None:
        self.other_tables = ensure_tables(tables.lakehouse)
        self.rows = rows
        self.other = other
        self.other_captures = other_captures
        self.exports = 0

    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object:
        self.exports += 1
        if self.exports == 1:
            merge(self.other_tables, self.other, self.other_captures)
        return self.rows.__arrow_c_stream__(requested_schema)


def test_ensure_tables_creates_station_stock_with_its_schema(
    tables: Tables,
) -> None:
    table = open_table(tables, TABLE_PATHS["station_stock"])

    assert table.schema() == STATION_STOCK_SCHEMA
    assert table.metadata().partition_columns == ["local_date"]


def test_station_stock_schema_follows_its_dbt_contract() -> None:
    # Each column's name, Delta type and nullability, from DuckDB's type and
    # not_null constraint in station_stock's contract.
    columns = [
        ("system", "string", False),
        ("station_id", "string", False),
        ("captured_at", "timestamp", False),
        ("local_date", "date", False),
        ("local_minute", "short", False),
        ("num_vehicles_available", "integer", True),
        ("num_docks_available", "integer", True),
        ("num_vehicles_disabled", "integer", True),
        ("num_docks_disabled", "integer", True),
        ("is_installed", "boolean", False),
        ("is_renting", "boolean", False),
        ("is_returning", "boolean", False),
        ("last_reported", "timestamp", False),
        ("last_updated", "timestamp", False),
        ("run_id", "string", False),
        ("code_version", "string", False),
    ]
    expected = Schema(
        [
            Field(name, PrimitiveType(kind), nullable=nullable)
            for name, kind, nullable in columns
        ]
    )

    assert STATION_STOCK_SCHEMA == expected


def test_ensure_tables_creates_processed_objects_by_system_feed_and_utc_date(
    tables: Tables,
) -> None:
    table = open_table(tables, TABLE_PATHS["processed_objects"])

    assert table.schema() == PROCESSED_OBJECTS_SCHEMA
    assert table.metadata().partition_columns == ["system", "feed", "utc_date"]


@pytest.mark.parametrize("name", list(TABLE_PATHS))
def test_ensure_tables_sets_the_maintenance_properties_of_a_new_table(
    tables: Tables, name: TableName
) -> None:
    table = open_table(tables, TABLE_PATHS[name])

    assert table.metadata().configuration == {
        "delta.checkpointInterval": str(CHECKPOINT_INTERVAL[name]),
        "delta.enableExpiredLogCleanup": "false",
        "delta.deletedFileRetentionDuration": (
            f"interval {TOMBSTONE_RETENTION.days} days"
        ),
    }


def test_ensure_tables_keeps_the_rows_of_existing_tables(
    tables: Tables,
) -> None:
    record_processed(tables, [processed("k1", "ambici", T0)])

    reopened = ensure_tables(tables.lakehouse)

    assert processed_keys(reopened) == frozenset({"k1"})


# Verifies DQR2
def test_merge_station_stock_returns_the_metrics_of_an_insert_only_merge(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    rows = stock(con, "b1", [("ambici", "1", T0), ("ambici", "2", T0)])

    metrics = merge(tables, rows, [T0])

    assert metrics == MergeMetrics(rows_inserted=2, rows_updated=0, rows_deleted=0)


# Verifies DQR2
def test_merge_station_stock_adds_no_row_when_a_batch_is_merged_twice(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    rows = stock(con, "b1", [("ambici", "1", T0), ("bicing", "1", T0)])
    merge(tables, rows, [T0])

    metrics = merge(tables, rows, [T0])

    assert metrics == MergeMetrics(rows_inserted=0, rows_updated=0, rows_deleted=0)
    assert len(stock_keys(tables)) == 2


# Verifies DQR2
def test_merge_station_stock_adds_only_the_rows_the_table_lacks(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    t1 = T0 + timedelta(minutes=10)
    merge(tables, stock(con, "b1", [("ambici", "1", T0)]), [T0])
    rows = stock(con, "b2", [("ambici", "1", T0), ("ambici", "1", t1)])

    metrics = merge(tables, rows, [T0, t1])

    assert metrics.rows_inserted == 1
    assert stock_keys(tables) == [("ambici", "1", T0), ("ambici", "1", t1)]


def test_merge_station_stock_spans_the_local_dates_of_its_batch(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    # 22:50 and 23:10 UTC fall on both sides of Madrid's midnight in November.
    before = datetime(2026, 11, 18, 22, 50, tzinfo=UTC)
    after = datetime(2026, 11, 18, 23, 10, tzinfo=UTC)
    rows = stock(con, "b1", [("ambici", "1", before), ("ambici", "1", after)])
    merge(tables, rows, [before, after])

    metrics = merge(tables, rows, [before, after])

    assert metrics.rows_inserted == 0
    assert len(stock_keys(tables)) == 2


def test_merge_station_stock_retries_a_conflict_on_a_fresh_handle(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    # A conflict is only certain when both writers insert a same key, the case
    # that could duplicate a row; one shared key among others must be enough.
    rows = stock(con, "b1", [("ambici", station, T0) for station in ("1", "2", "3")])
    other = stock(con, "b2", [("ambici", station, T0) for station in ("3", "4")])
    stream = Interfering(tables, rows, other, [T0])

    metrics = merge(tables, stream, [T0])

    assert stream.exports == 2
    assert metrics.rows_inserted == 2
    assert stock_keys(tables) == [
        ("ambici", station, T0) for station in ("1", "2", "3", "4")
    ]


def test_merge_station_stock_raises_a_conflict_after_its_attempts(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    rows = stock(con, "b1", [("ambici", station, T0) for station in ("1", "2", "3")])
    other = stock(con, "b2", [("ambici", station, T0) for station in ("3", "4")])
    stream = Interfering(tables, rows, other, [T0])

    with pytest.raises(CommitFailedError):
        merge(tables, stream, [T0], attempts=1)

    assert stock_keys(tables) == [("ambici", "3", T0), ("ambici", "4", T0)]


def test_record_processed_adds_no_row_for_a_key_already_recorded(
    tables: Tables,
) -> None:
    record_processed(tables, [processed("k1", "ambici", T0)])

    record_processed(
        tables,
        [processed("k1", "ambici", T0), processed("k2", "bicing", T0)],
    )

    assert processed_keys(tables) == frozenset({"k1", "k2"})
    reader = capture_history(tables, since=T0, until=T0 + timedelta(seconds=1))
    assert duckdb.from_arrow(reader).count("*").fetchall() == [(2,)]


def processed_rows(tables: Tables) -> list[tuple[str, str, date]]:
    """The key, system and UTC date of every row of ``processed_objects``, sorted."""
    reader = (
        QueryBuilder()
        .register("t", open_table(tables, TABLE_PATHS["processed_objects"]))
        .execute("select key, system, utc_date from t")
    )
    return sorted(duckdb.from_arrow(reader).fetchall())


def test_record_processed_writes_the_utc_date_of_each_capture(
    tables: Tables,
) -> None:
    # 23:30 UTC falls on the next local date in Madrid; utc_date keeps the UTC one.
    late = datetime(2026, 11, 18, 23, 30, tzinfo=UTC)

    record_processed(tables, [processed("k1", "ambici", late)])

    assert processed_rows(tables) == [("k1", "ambici", date(2026, 11, 18))]


# Verifies d010 R3
def test_record_processed_records_two_systems_in_one_table(
    tables: Tables,
) -> None:
    record_processed(
        tables,
        [processed("k1", "ambici", T0), processed("k2", "bicing", T0)],
    )

    assert processed_rows(tables) == [
        ("k1", "ambici", T0.date()),
        ("k2", "bicing", T0.date()),
    ]


# Verifies d010 R16
def test_a_batch_recorded_twice_adds_no_rows_to_either_table(
    tables: Tables, con: duckdb.DuckDBPyConnection
) -> None:
    rows = stock(con, "b1", [("ambici", "1", T0), ("bicing", "1", T0)])
    objects = [processed("k1", "ambici", T0), processed("k2", "bicing", T0)]
    merge(tables, rows, [T0])
    record_processed(tables, objects)

    merge(tables, rows, [T0])
    record_processed(tables, objects)

    assert len(stock_keys(tables)) == 2
    assert len(processed_rows(tables)) == 2


def test_processed_keys_is_empty_on_new_tables(tables: Tables) -> None:
    assert processed_keys(tables) == frozenset()


def test_latest_processed_returns_each_system_latest_capture(
    tables: Tables,
) -> None:
    t1 = T0 + timedelta(minutes=10)
    record_processed(
        tables,
        [
            processed("k1", "ambici", T0),
            processed("k2", "ambici", t1),
            processed("k3", "bicing", T0),
        ],
    )

    assert latest_processed(tables) == {"ambici": t1, "bicing": T0}


def test_latest_processed_returns_none_for_a_system_with_no_object(
    tables: Tables,
) -> None:
    record_processed(tables, [processed("k1", "bicing", T0)])

    assert latest_processed(tables) == {"ambici": None, "bicing": T0}


# Verifies d010 R1
def test_capture_history_writes_the_objects_captured_in_its_range_as_parquet(
    tables: Tables, work: Path
) -> None:
    since, until = T0, T0 + timedelta(hours=24)
    record_processed(
        tables,
        [
            processed("before", "ambici", since - timedelta(microseconds=1)),
            processed("first", "ambici", since),
            processed("last", "bicing", until - timedelta(microseconds=1)),
            processed("after", "bicing", until),
        ],
    )
    scratch = connect(
        work / "scratch.duckdb",
        allowed_directories=[work],
        temp_directory=work / "spill",
        duckdb_memory_limit_mib=256,
    )
    path = work / "capture_history.parquet"

    write_parquet(scratch, capture_history(tables, since=since, until=until), path)

    rows = scratch.sql(
        f"select key, station_count from read_parquet('{path}') order by key"
    ).fetchall()
    assert rows == [("first", 2), ("last", 2)]
    columns = scratch.sql(f"describe select * from read_parquet('{path}')").fetchall()
    assert [(name, kind) for name, kind, *_ in columns] == [
        ("key", "VARCHAR"),
        ("system", "VARCHAR"),
        ("feed", "VARCHAR"),
        ("captured_at", "TIMESTAMP WITH TIME ZONE"),
        ("station_count", "INTEGER"),
        ("status", "VARCHAR"),
        ("run_id", "VARCHAR"),
        ("code_version", "VARCHAR"),
    ]


# Verifies d008 R6
# Verifies d010 R1
def test_latest_captures_writes_each_system_latest_capture_as_parquet(
    tables: Tables, con: duckdb.DuckDBPyConnection, work: Path
) -> None:
    # Bicing's latest capture falls on the previous local date.
    earlier = datetime(2026, 11, 18, 22, 50, tzinfo=UTC)
    t1 = T0 + timedelta(minutes=10)
    rows = stock(
        con,
        "b1",
        [
            ("ambici", "1", T0),
            ("ambici", "1", t1),
            ("ambici", "2", t1),
            ("bicing", "7", earlier),
        ],
    )
    merge(tables, rows, [earlier, T0, t1])
    scratch = connect(
        work / "scratch.duckdb",
        allowed_directories=[work],
        temp_directory=work / "spill",
        duckdb_memory_limit_mib=256,
    )
    path = work / "latest_captures.parquet"

    write_parquet(
        scratch,
        latest_captures(tables, {"ambici": t1, "bicing": earlier}),
        path,
    )

    result = scratch.sql(
        "select system, station_id, captured_at, local_date "
        f"from read_parquet('{path}') order by system, station_id"
    ).fetchall()
    assert [(s, i, at.astimezone(UTC), d) for s, i, at, d in result] == [
        ("ambici", "1", t1, date(2026, 11, 19)),
        ("ambici", "2", t1, date(2026, 11, 19)),
        ("bicing", "7", earlier, date(2026, 11, 18)),
    ]
    columns = scratch.sql(f"describe select * from read_parquet('{path}')").fetchall()
    assert [name for name, *_ in columns] == [
        field.name for field in STATION_STOCK_SCHEMA.fields
    ]


def test_latest_captures_is_empty_with_no_latest_capture(
    tables: Tables,
) -> None:
    reader = latest_captures(tables, {})

    assert duckdb.from_arrow(reader).count("*").fetchall() == [(0,)]


def test_r2_lakehouse_sets_the_endpoint_and_conditional_put() -> None:
    lakehouse = r2_lakehouse(
        account_id="acc", access_key_id="id", secret_access_key="secret"
    )
    path = TABLE_PATHS["station_stock"]

    assert lakehouse.uri == "s3://bikesharing-lakehouse"
    assert lakehouse.table_uri(path) == f"s3://bikesharing-lakehouse/{path}"
    assert lakehouse.storage_options == {
        "AWS_ENDPOINT_URL": "https://acc.r2.cloudflarestorage.com",
        "AWS_REGION": "auto",
        "AWS_ACCESS_KEY_ID": "id",
        "AWS_SECRET_ACCESS_KEY": "secret",
        "aws_conditional_put": "etag",
    }
