"""DuckDB with the run's sandbox and memory settings, and the reads of its scratch database.

DuckDB reads only inside the run's work folder, reaches no network, loads no
extension and keeps its memory below the container's limit; the configuration is
locked last, so that nothing a query does can lift it (d008 #9, #10, Bronze
reading). ``apply_sandbox`` holds these settings for every connection the run
opens: ``connect`` applies them to the shell's, ``Plugin`` to dbt's.

After ``dbt build``, the readers query the scratch database's relations by name,
never with feed values in SQL text, and return every instant in UTC (d008 D10,
Security of the skeleton).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import duckdb
from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection, DuckDBPyRelation

from bikesharing.core.settings import System


class ArrowStream(Protocol):
    """A tabular object exported through Arrow's PyCapsule stream interface."""

    def __arrow_c_stream__(self, requested_schema: object | None = None) -> object:
        """Export the object as an Arrow C stream.

        Parameters
        ----------
        requested_schema : object or None
            A schema capsule the consumer asks for, or ``None``.

        Returns
        -------
        object
            A PyCapsule holding an ``ArrowArrayStream``.
        """
        ...


@dataclass(frozen=True, slots=True)
class NotEvaluated:
    """A capture whose volume was not evaluated, for lack of earlier captures.

    Attributes
    ----------
    system : System
        The capture's system.
    captured_at : datetime
        The capture's instant, in UTC.
    captures_in_window : int
        The captures of its system in the capture's window.
    """

    system: System
    captured_at: datetime
    captures_in_window: int


@dataclass(frozen=True, slots=True)
class DriftField:
    """A station field that the batch's objects add to, or drop from, the read schema.

    Attributes
    ----------
    system : System
        The system whose objects carry the change.
    field : str
        The station field's name.
    change : {"added", "dropped"}
        Whether the field is new to the read schema or missing from the objects.
    """

    system: System
    field: str
    change: Literal["added", "dropped"]


def _literal(value: str) -> str:
    """Return ``value`` as a SQL string literal.

    DuckDB's ``SET`` takes no bound parameters; the values are the run's own
    paths and limits, never feed values.
    """
    return "'" + value.replace("'", "''") + "'"


def _utc(value: object) -> datetime:
    """Return a ``timestamp with time zone`` value as a datetime in UTC.

    DuckDB returns such values in the session's time zone, which is the host's.
    """
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise TypeError(f"expected a datetime with a time zone, got {value!r}")
    return value.astimezone(UTC)


def apply_sandbox(
    con: DuckDBPyConnection,
    *,
    memory_limit: str,
    temp_directory: str,
    allowed_directories: Sequence[str],
) -> None:
    """Apply the sandbox and memory settings to an open connection, and lock them.

    Parameters
    ----------
    con : DuckDBPyConnection
        A connection whose database has just started, with nothing run on it.
    memory_limit : str
        DuckDB's ``memory_limit``, with its unit, e.g. ``"1024MiB"``.
    temp_directory : str
        The folder DuckDB spills to; it lies inside an allowed directory.
    allowed_directories : Sequence[str]
        The only folders DuckDB may read or write.
    """
    directories = ", ".join(_literal(directory) for directory in allowed_directories)
    # The order matters: the paths are set while external access is still on,
    # and the lock goes last.
    con.execute(f"set memory_limit = {_literal(memory_limit)}")
    con.execute(f"set temp_directory = {_literal(temp_directory)}")
    con.execute(f"set allowed_directories = [{directories}]")
    con.execute("set autoinstall_known_extensions = false")
    con.execute("set autoload_known_extensions = false")
    con.execute("set enable_external_access = false")
    con.execute("set lock_configuration = true")


class Plugin(BasePlugin):
    """dbt-duckdb plugin that applies the sandbox once, on dbt's connection.

    dbt-duckdb applies a profile's ``settings`` again on every cursor, which a
    sandboxed and locked DuckDB refuses; ``configure_connection`` runs once per
    database (d008 DI6). ``profiles.yml`` passes the values as the plugin's
    ``config``: ``memory_limit``, ``temp_directory`` and ``allowed_directory``.
    """

    def initialize(self, plugin_config: dict[str, Any]) -> None:
        """Keep the settings the profile passes.

        Parameters
        ----------
        plugin_config : dict[str, Any]
            The plugin's ``config`` in ``profiles.yml``.
        """
        self._memory_limit = str(plugin_config["memory_limit"])
        self._temp_directory = str(plugin_config["temp_directory"])
        self._allowed_directory = str(plugin_config["allowed_directory"])

    def configure_connection(self, conn: DuckDBPyConnection) -> None:
        """Apply the sandbox to dbt's connection.

        Parameters
        ----------
        conn : DuckDBPyConnection
            dbt-duckdb's connection, just opened on the scratch database.
        """
        apply_sandbox(
            conn,
            memory_limit=self._memory_limit,
            temp_directory=self._temp_directory,
            allowed_directories=[self._allowed_directory],
        )


def connect(
    database: Path,
    *,
    allowed_directories: Sequence[Path],
    temp_directory: Path,
    duckdb_memory_limit_mib: int,
) -> DuckDBPyConnection:
    """Open the scratch database with the sandbox and memory settings applied.

    Parameters
    ----------
    database : Path
        The scratch database's file, inside an allowed directory; it is created
        if missing.
    allowed_directories : Sequence[Path]
        The only folders DuckDB may read or write: the run's work folder.
    temp_directory : Path
        The folder DuckDB spills to, inside an allowed directory.
    duckdb_memory_limit_mib : int
        DuckDB's memory limit, in MiB.

    Returns
    -------
    DuckDBPyConnection
        The open connection, with its configuration locked.
    """
    con = duckdb.connect(str(database))
    try:
        apply_sandbox(
            con,
            memory_limit=f"{duckdb_memory_limit_mib}MiB",
            temp_directory=str(temp_directory),
            allowed_directories=[str(directory) for directory in allowed_directories],
        )
    except BaseException:
        # An unsandboxed connection is never handed out.
        con.close()
        raise
    return con


def station_stock(con: DuckDBPyConnection) -> DuckDBPyRelation:
    """Return the batch's ``station_stock`` table as a relation.

    The relation is lazy: its consumer reads it as an Arrow stream, so that
    DuckDB makes no copy of the rows.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    DuckDBPyRelation
        Every row of ``station_stock``, in the columns of its dbt contract.
    """
    return con.table("station_stock")


def station_stock_local_dates(con: DuckDBPyConnection) -> frozenset[date]:
    """Return the local dates the batch's ``station_stock`` rows fall on.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    frozenset[date]
        Each ``local_date`` of ``station_stock``, once.
    """
    rows = con.execute("select distinct local_date from station_stock").fetchall()
    return frozenset(row[0] for row in rows)


def station_counts(con: DuckDBPyConnection) -> Mapping[tuple[System, datetime], int]:
    """Return each capture's station count, a capture that lists no station as 0.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    Mapping[tuple[System, datetime], int]
        The ``station_count`` of ``capture_volume``, keyed by system and
        capture instant in UTC.
    """
    rows = con.execute(
        "select system, captured_at, station_count from capture_volume"
    ).fetchall()
    return {
        (cast(System, system), _utc(captured_at)): station_count
        for system, captured_at, station_count in rows
    }


def volume_not_evaluated(con: DuckDBPyConnection) -> list[NotEvaluated]:
    """Return the captures whose volume was not evaluated.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    list[NotEvaluated]
        The rows of ``capture_volume`` with status ``not_evaluated``, by system
        and capture instant.
    """
    rows = con.execute(
        "select system, captured_at, captures_in_window from capture_volume "
        "where status = $status order by system, captured_at",
        {"status": "not_evaluated"},
    ).fetchall()
    return [
        NotEvaluated(
            system=cast(System, system),
            captured_at=_utc(captured_at),
            captures_in_window=captures_in_window,
        )
        for system, captured_at, captures_in_window in rows
    ]


def schema_drift_fields(con: DuckDBPyConnection) -> list[DriftField]:
    """Return each field the batch adds or drops, once per system.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    list[DriftField]
        The distinct system, field and change of ``schema_drift``, in that
        order.
    """
    rows = con.execute(
        "select distinct system, field, change from schema_drift "
        "order by system, field, change"
    ).fetchall()
    return [
        DriftField(
            system=cast(System, system),
            field=field,
            change=cast(Literal["added", "dropped"], change),
        )
        for system, field, change in rows
    ]


def latest_station_count(con: DuckDBPyConnection) -> list[dict[str, object]]:
    """Return the rows of ``latest_station_count``, the published file's stations.

    Parameters
    ----------
    con : DuckDBPyConnection
        The scratch database, after ``dbt build``.

    Returns
    -------
    list[dict[str, object]]
        One mapping per station, from each column of the model's contract to
        its value, by system and ``station_id``; instants are datetimes in UTC.
    """
    relation = con.table("latest_station_count").order("system, station_id")
    columns = relation.columns
    return [
        {
            column: _utc(value) if isinstance(value, datetime) else value
            for column, value in zip(columns, row, strict=True)
        }
        for row in relation.fetchall()
    ]


def write_parquet(con: DuckDBPyConnection, stream: ArrowStream, path: Path) -> None:
    """Write an Arrow stream to a Parquet file, one of dbt's inputs.

    Parameters
    ----------
    con : DuckDBPyConnection
        A sandboxed connection; ``path`` lies inside one of its allowed
        directories.
    stream : ArrowStream
        The rows to write, such as a Delta table's scan.
    path : Path
        The Parquet file to write; it is replaced if it exists.
    """
    con.from_arrow(stream).write_parquet(str(path))
