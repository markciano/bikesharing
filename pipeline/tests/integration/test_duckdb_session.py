"""Integration tests of DuckDB's sandbox and memory settings, on local files."""

from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from bikesharing.core.read_schema import STATION_STATUS_COLUMNS
from bikesharing.core.settings import System
from bikesharing.shell.duckdb_session import (
    DriftField,
    NotEvaluated,
    Plugin,
    apply_sandbox,
    connect,
    latest_station_count,
    schema_drift_fields,
    station_counts,
    station_stock,
    station_stock_local_dates,
    volume_not_evaluated,
    write_parquet,
)


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """The folder standing in for the run's work folder."""
    folder = tmp_path / "work"
    folder.mkdir()
    return folder


@pytest.fixture
def scratch(work: Path) -> duckdb.DuckDBPyConnection:
    """The scratch database, opened by ``connect`` inside ``work``."""
    return connect(
        work / "scratch.duckdb",
        allowed_directories=[work],
        temp_directory=work / "spill",
        duckdb_memory_limit_mib=256,
    )


def sandboxed(work: Path) -> duckdb.DuckDBPyConnection:
    """An in-memory connection with the sandbox applied over ``work``."""
    con = duckdb.connect()
    apply_sandbox(
        con,
        memory_limit="256MiB",
        temp_directory=str(work / "spill"),
        allowed_directories=[str(work)],
    )
    return con


# Verifies d008 R28
def test_apply_sandbox_refuses_file_outside_allowed_directory(
    tmp_path: Path, work: Path
) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("a\n1\n")
    con = sandboxed(work)

    with pytest.raises(duckdb.PermissionException):
        con.sql(f"select * from read_csv('{outside}')").fetchall()


def test_apply_sandbox_reads_file_inside_allowed_directory(work: Path) -> None:
    inside = work / "inside.csv"
    inside.write_text("a\n1\n")
    con = sandboxed(work)

    assert con.sql(f"select a from read_csv('{inside}')").fetchall() == [(1,)]


# Verifies d008 R29
def test_apply_sandbox_refuses_extension_load(work: Path) -> None:
    con = sandboxed(work)

    with pytest.raises(duckdb.Error):
        con.execute("load httpfs")


def test_apply_sandbox_locks_configuration(work: Path) -> None:
    con = sandboxed(work)

    with pytest.raises(duckdb.Error):
        con.execute("set memory_limit = '8GiB'")


def test_plugin_applies_sandbox_from_profile_config(work: Path) -> None:
    plugin = Plugin(
        name="duckdb_session",
        plugin_config={
            "memory_limit": "256MiB",
            "temp_directory": str(work / "spill"),
            "allowed_directory": str(work),
        },
    )
    con = duckdb.connect()

    plugin.configure_connection(con)

    settings = con.sql(
        "select current_setting('memory_limit'), "
        "current_setting('enable_external_access'), "
        "current_setting('lock_configuration')"
    ).fetchall()
    assert settings == [("256.0 MiB", False, True)]


def test_connect_opens_database_with_sandbox_and_memory_limit(work: Path) -> None:
    database = work / "scratch.duckdb"

    con = connect(
        database,
        allowed_directories=[work],
        temp_directory=work / "spill",
        duckdb_memory_limit_mib=300,
    )

    settings = con.sql(
        "select current_setting('memory_limit'), "
        "current_setting('temp_directory'), "
        "current_setting('enable_external_access'), "
        "current_setting('lock_configuration')"
    ).fetchall()
    assert settings == [("300.0 MiB", str(work / "spill"), False, True)]
    assert database.is_file()


# Verifies d008 #10
def test_connect_spills_to_temp_directory_with_external_access_off(
    work: Path,
) -> None:
    spill = work / "spill"
    con = connect(
        work / "scratch.duckdb",
        allowed_directories=[work],
        temp_directory=spill,
        duckdb_memory_limit_mib=256,
    )

    # About 320 MB of rows sorted under a 256 MiB limit: the sort must spill.
    con.execute(
        "create table sorted as "
        "select i, random() as r from range(20000000) t(i) order by r"
    )

    assert con.sql("select count(*) from sorted").fetchall() == [(20000000,)]
    assert any(spill.iterdir())


# Verifies d008 #11
@pytest.mark.parametrize("system", ["ambici", "bicing"])
def test_read_json_reads_system_fixtures_with_its_schema(
    work: Path, bronze_folder: Path, system: System
) -> None:
    files = sorted((bronze_folder / "raw" / system / "station_status").rglob("*.gz"))
    con = connect(
        work / "scratch.duckdb",
        allowed_directories=[work, bronze_folder],
        temp_directory=work / "spill",
        duckdb_memory_limit_mib=256,
    )
    columns = dict(STATION_STATUS_COLUMNS[system])

    # The same call dbt's source renders: the file list and the schema as
    # literals, from the run's own paths and the core's constant.
    relation = con.sql(
        f"select * from read_json({[str(file) for file in files]!r}, "
        f"columns = {columns!r})"
    )

    assert relation.columns == list(columns)
    stations = relation.select(
        "len(data.stations) as stations, "
        "list_count(list_transform(data.stations, lambda s: s.station_id)) as with_id"
    ).fetchall()
    assert len(stations) == len(files)
    assert all(count > 0 and count == with_id for count, with_id in stations)


def test_station_stock_returns_the_table_as_a_relation(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    scratch.execute(
        "create table station_stock as select * from (values "
        "('ambici', '1', date '2026-10-19'), "
        "('bicing', '7', date '2026-10-22')) t(system, station_id, local_date)"
    )

    relation = station_stock(scratch)

    assert isinstance(relation, duckdb.DuckDBPyRelation)
    assert sorted(relation.fetchall()) == [
        ("ambici", "1", date(2026, 10, 19)),
        ("bicing", "7", date(2026, 10, 22)),
    ]


def test_station_stock_local_dates_returns_each_date_once(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    scratch.execute(
        "create table station_stock as select * from (values "
        "('ambici', '1', date '2026-10-19'), "
        "('ambici', '2', date '2026-10-19'), "
        "('bicing', '7', date '2026-10-20')) t(system, station_id, local_date)"
    )

    assert station_stock_local_dates(scratch) == frozenset(
        {date(2026, 10, 19), date(2026, 10, 20)}
    )


def create_capture_volume(con: duckdb.DuckDBPyConnection) -> None:
    """Create ``capture_volume`` with one capture of each status."""
    con.execute(
        "create table capture_volume as select * from (values "
        "('ambici', timestamptz '2026-10-19 08:57:45+00', 120, 0, null, "
        "'not_evaluated'), "
        "('bicing', timestamptz '2026-10-22 07:42:19+00', 0, 3, 510.0, 'drop'), "
        "('bicing', timestamptz '2026-10-22 07:43:19+00', 512, 4, 510.0, 'ok')"
        ") t(system, captured_at, station_count, captures_in_window, "
        "median_station_count, status)"
    )


def test_station_counts_maps_each_capture_to_its_count(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    create_capture_volume(scratch)

    counts = station_counts(scratch)

    assert counts == {
        ("ambici", datetime(2026, 10, 19, 8, 57, 45, tzinfo=UTC)): 120,
        ("bicing", datetime(2026, 10, 22, 7, 42, 19, tzinfo=UTC)): 0,
        ("bicing", datetime(2026, 10, 22, 7, 43, 19, tzinfo=UTC)): 512,
    }
    assert all(instant.tzinfo is UTC for _, instant in counts)


def test_volume_not_evaluated_returns_only_unevaluated_captures(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    create_capture_volume(scratch)

    assert volume_not_evaluated(scratch) == [
        NotEvaluated(
            system="ambici",
            captured_at=datetime(2026, 10, 19, 8, 57, 45, tzinfo=UTC),
            captures_in_window=0,
        )
    ]


def test_schema_drift_fields_returns_each_field_once(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    scratch.execute(
        "create table schema_drift as select * from (values "
        "('bicing', timestamptz '2026-10-22 07:42:19+00', 'num_docks_disabled', "
        "'dropped'), "
        "('bicing', timestamptz '2026-10-22 07:43:19+00', 'num_docks_disabled', "
        "'dropped'), "
        "('ambici', timestamptz '2026-10-19 08:57:45+00', 'new_field', 'added')"
        ") t(system, captured_at, field, change)"
    )

    assert schema_drift_fields(scratch) == [
        DriftField(system="ambici", field="new_field", change="added"),
        DriftField(system="bicing", field="num_docks_disabled", change="dropped"),
    ]


def test_latest_station_count_returns_rows_by_system_and_station(
    scratch: duckdb.DuckDBPyConnection,
) -> None:
    scratch.execute(
        "create table latest_station_count as select * from (values "
        "('bicing', '7', 3, 12, true, true, "
        "timestamptz '2026-10-22 07:40:00+00', timestamptz '2026-10-22 07:45:19+00'), "
        "('ambici', '2', null, 5, true, false, "
        "timestamptz '2026-10-19 08:55:00+00', timestamptz '2026-10-19 08:59:45+00')"
        ") t(system, station_id, num_vehicles_available, num_docks_available, "
        "is_renting, is_returning, last_reported, captured_at)"
    )

    rows = latest_station_count(scratch)

    assert rows == [
        {
            "system": "ambici",
            "station_id": "2",
            "num_vehicles_available": None,
            "num_docks_available": 5,
            "is_renting": True,
            "is_returning": False,
            "last_reported": datetime(2026, 10, 19, 8, 55, tzinfo=UTC),
            "captured_at": datetime(2026, 10, 19, 8, 59, 45, tzinfo=UTC),
        },
        {
            "system": "bicing",
            "station_id": "7",
            "num_vehicles_available": 3,
            "num_docks_available": 12,
            "is_renting": True,
            "is_returning": True,
            "last_reported": datetime(2026, 10, 22, 7, 40, tzinfo=UTC),
            "captured_at": datetime(2026, 10, 22, 7, 45, 19, tzinfo=UTC),
        },
    ]
    assert all(row["captured_at"].tzinfo is UTC for row in rows)  # type: ignore[attr-defined]


class Stream:
    """An object that offers only Arrow's PyCapsule stream, like a Delta scan."""

    def __init__(self, sql: str) -> None:
        self._relation = duckdb.connect().sql(sql)

    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object:
        """Export the rows of ``sql`` as an Arrow C stream."""
        return self._relation.__arrow_c_stream__(requested_schema)


def test_write_parquet_writes_stream_inside_allowed_directory(
    work: Path, scratch: duckdb.DuckDBPyConnection
) -> None:
    stream = Stream("select * from (values (1, 'a'), (2, 'b')) t(n, s)")
    path = work / "inputs" / "capture_history.parquet"
    path.parent.mkdir()

    write_parquet(scratch, stream, path)

    assert sorted(scratch.read_parquet(str(path)).fetchall()) == [(1, "a"), (2, "b")]


# Verifies d008 R28
def test_write_parquet_refuses_path_outside_allowed_directory(
    tmp_path: Path, scratch: duckdb.DuckDBPyConnection
) -> None:
    stream = Stream("select 1 as n")

    with pytest.raises(duckdb.PermissionException):
        write_parquet(scratch, stream, tmp_path / "outside.parquet")
