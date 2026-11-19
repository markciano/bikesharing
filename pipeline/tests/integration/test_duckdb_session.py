"""Integration tests of DuckDB's sandbox and memory settings, on local files."""

from pathlib import Path

import duckdb
import pytest

from bikesharing.shell.duckdb_session import Plugin, apply_sandbox


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """The folder standing in for the run's work folder."""
    folder = tmp_path / "work"
    folder.mkdir()
    return folder


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
