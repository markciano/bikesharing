"""The lakehouse's Delta tables: their creation, the processing state and each batch's commits.

Each batch commits twice: its station stock first, with an insert-only MERGE on
the natural key, and its objects in ``processed_objects`` second, with an
insert-only MERGE on the key, so that a run that stops between the two leaves
the batch pending and processing it again adds no row (d008 #4, Delta writes).
No row is ever updated or deleted (d005 D4, Business processes and the grain of
the stock).

The tables are read through ``deltalake``'s query engine, which returns Arrow
streams that DuckDB writes as dbt's Parquet inputs (d008 #9, Bronze reading).
The SQL the module builds takes only the run's own typed values (instants,
dates and system names), never feed values.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal

from arro3.core import Array, ChunkedArray, DataType, Table
from deltalake import DeltaTable, Field, QueryBuilder, Schema
from deltalake.exceptions import CommitFailedError
from deltalake.schema import PrimitiveType

from bikesharing.core.settings import (
    LAKEHOUSE_BUCKET,
    LOCAL_TIMEZONE,
    SYSTEMS,
    System,
)
from bikesharing.core.verdict import MergeMetrics
from bikesharing.shell.duckdb_session import ArrowStream

STATION_STOCK_PATH: Final = "silver/station_stock"
PROCESSED_OBJECTS_PATH: Final = "control/processed_objects"

_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND: Final = timedelta(microseconds=1)


@dataclass(frozen=True, slots=True)
class Lakehouse:
    """Where the Delta tables live, and how ``deltalake`` reaches them.

    Attributes
    ----------
    uri : str
        The lakehouse's root: an ``s3://`` bucket on R2, or a local folder.
    storage_options : Mapping[str, str]
        The options ``deltalake`` passes to its object store.
    """

    uri: str
    storage_options: Mapping[str, str]

    def table_uri(self, path: str) -> str:
        """Return the URI of the table at ``path`` under the lakehouse's root.

        Parameters
        ----------
        path : str
            The table's path, e.g. ``"silver/station_stock"``.

        Returns
        -------
        str
            The table's URI.
        """
        return f"{self.uri.rstrip('/')}/{path}"


@dataclass(frozen=True, slots=True)
class ProcessedObject:
    """A bronze object a run has processed: one row of ``processed_objects``.

    Attributes
    ----------
    key : str
        The object's bronze key.
    system : System
        The object's system.
    feed : str
        The object's feed.
    captured_at : datetime
        The object's capture instant, in UTC.
    station_count : int
        The number of stations the object lists.
    status : {"processed"}
        The object's processing status.
    run_id : str
        The ID of the run that processed it.
    code_version : str
        The code version of that run.
    """

    key: str
    system: System
    feed: str
    captured_at: datetime
    station_count: int
    status: Literal["processed"]
    run_id: str
    code_version: str


def _field(name: str, kind: str, *, nullable: bool = False) -> Field:
    """Return a Delta field of a primitive type, not nullable by default."""
    return Field(name, PrimitiveType(kind), nullable=nullable)


# The columns of station_stock's dbt contract, in its order, with Delta's type
# for DuckDB's (d008, dbt model contracts).
STATION_STOCK_SCHEMA: Final = Schema(
    [
        _field("system", "string"),
        _field("station_id", "string"),
        _field("captured_at", "timestamp"),
        _field("local_date", "date"),
        _field("local_minute", "short"),
        _field("num_vehicles_available", "integer", nullable=True),
        _field("num_docks_available", "integer", nullable=True),
        _field("num_vehicles_disabled", "integer", nullable=True),
        _field("num_docks_disabled", "integer", nullable=True),
        _field("is_installed", "boolean"),
        _field("is_renting", "boolean"),
        _field("is_returning", "boolean"),
        _field("last_reported", "timestamp"),
        _field("last_updated", "timestamp"),
        _field("run_id", "string"),
        _field("code_version", "string"),
    ]
)

PROCESSED_OBJECTS_SCHEMA: Final = Schema(
    [
        _field("key", "string"),
        _field("system", "string"),
        _field("feed", "string"),
        _field("captured_at", "timestamp"),
        _field("station_count", "integer"),
        _field("status", "string"),
        _field("run_id", "string"),
        _field("code_version", "string"),
    ]
)


def _values(column: ChunkedArray) -> list[Any]:
    """Return a column's values as Python objects.

    arro3's type stubs declare neither ``ChunkedArray``'s iteration nor its
    ``to_pylist`` as a list, so the scalars are read by index.
    """
    return [column[i].as_py() for i in range(len(column))]


def _string(value: str) -> str:
    """Return ``value`` as a SQL string literal."""
    return "'" + value.replace("'", "''") + "'"


def _timestamp(value: datetime) -> str:
    """Return an aware datetime as a SQL timestamp literal in UTC."""
    if value.tzinfo is None:
        raise ValueError(f"expected a datetime with a time zone, got {value!r}")
    return f"TIMESTAMP {_string(value.astimezone(UTC).isoformat())}"


def _date(value: date) -> str:
    """Return a date as a SQL date literal."""
    return f"DATE {_string(value.isoformat())}"


def _table(lakehouse: Lakehouse, path: str) -> DeltaTable:
    """Open a fresh handle on the table at ``path``, at its latest version."""
    return DeltaTable(
        lakehouse.table_uri(path), storage_options=dict(lakehouse.storage_options)
    )


def _query(lakehouse: Lakehouse, path: str, sql: str) -> ArrowStream:
    """Run ``sql`` over the table at ``path``, registered as ``t``."""
    return QueryBuilder().register("t", _table(lakehouse, path)).execute(sql)


def r2_lakehouse(
    *, account_id: str, access_key_id: str, secret_access_key: str
) -> Lakehouse:
    """Return the lakehouse's bucket on R2.

    R2 supports conditional put, which makes concurrent commits safe with no
    locking provider (d008, Delta writes).

    Parameters
    ----------
    account_id : str
        The Cloudflare account that holds the bucket.
    access_key_id : str
        The R2 token's access key ID.
    secret_access_key : str
        The R2 token's secret access key.

    Returns
    -------
    Lakehouse
        ``bikesharing-lakehouse`` on R2's S3 endpoint.
    """
    return Lakehouse(
        uri=f"s3://{LAKEHOUSE_BUCKET}",
        storage_options={
            "AWS_ENDPOINT_URL": f"https://{account_id}.r2.cloudflarestorage.com",
            "AWS_REGION": "auto",
            "AWS_ACCESS_KEY_ID": access_key_id,
            "AWS_SECRET_ACCESS_KEY": secret_access_key,
            "aws_conditional_put": "etag",
        },
    )


def local_lakehouse(path: Path) -> Lakehouse:
    """Return a lakehouse in a local folder, as one-off runs and tests use.

    Parameters
    ----------
    path : Path
        The lakehouse's root folder; it is created with the first table.

    Returns
    -------
    Lakehouse
        The lakehouse, with no storage options.
    """
    return Lakehouse(uri=str(path.resolve()), storage_options={})


def ensure_tables(lakehouse: Lakehouse) -> None:
    """Create each missing table with its explicit schema; keep existing ones.

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse that holds the tables.
    """
    options = dict(lakehouse.storage_options)
    DeltaTable.create(
        lakehouse.table_uri(STATION_STOCK_PATH),
        STATION_STOCK_SCHEMA,
        mode="ignore",
        partition_by=["local_date"],
        storage_options=options,
    )
    DeltaTable.create(
        lakehouse.table_uri(PROCESSED_OBJECTS_PATH),
        PROCESSED_OBJECTS_SCHEMA,
        mode="ignore",
        storage_options=options,
    )


def processed_keys(lakehouse: Lakehouse) -> frozenset[str]:
    """Return the key of every bronze object a run has processed.

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.

    Returns
    -------
    frozenset[str]
        The keys in ``processed_objects``.
    """
    table = Table.from_arrow(
        _query(lakehouse, PROCESSED_OBJECTS_PATH, "select key from t")
    )
    return frozenset(_values(table["key"]))


def latest_processed(lakehouse: Lakehouse) -> dict[System, datetime | None]:
    """Return each system's latest processed capture instant.

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.

    Returns
    -------
    dict[System, datetime | None]
        Per system, the latest ``captured_at`` in ``processed_objects``, in UTC,
        or ``None`` for a system with no processed object.
    """
    table = Table.from_arrow(
        _query(
            lakehouse,
            PROCESSED_OBJECTS_PATH,
            "select system, max(captured_at) as captured_at from t group by system",
        )
    )
    latest: dict[System, datetime | None] = dict.fromkeys(SYSTEMS)
    for system, captured_at in zip(
        _values(table["system"]), _values(table["captured_at"]), strict=True
    ):
        latest[system] = captured_at.astimezone(UTC)
    return latest


def capture_history(
    lakehouse: Lakehouse, *, since: datetime, until: datetime
) -> ArrowStream:
    """Return the processed objects captured in ``[since, until)``.

    They are the history ``capture_volume`` compares a batch's captures with
    (d008 #14, Transformation in dbt).

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.
    since : datetime
        The first capture instant included.
    until : datetime
        The first capture instant excluded.

    Returns
    -------
    ArrowStream
        The rows of ``processed_objects``, in its columns.
    """
    return _query(
        lakehouse,
        PROCESSED_OBJECTS_PATH,
        f"select * from t where captured_at >= {_timestamp(since)} "
        f"and captured_at < {_timestamp(until)}",
    )


def merge_station_stock(
    lakehouse: Lakehouse,
    rows: ArrowStream,
    *,
    first_capture: datetime,
    last_capture: datetime,
    local_dates: Collection[date],
    attempts: int = 3,
) -> MergeMetrics:
    """Insert the batch's rows that ``station_stock`` lacks, with an insert-only MERGE.

    The MERGE matches on the natural key, bounded by the batch's capture range
    and local dates, so that it reads only the partitions the batch writes. A
    commit that conflicts with another writer's is retried on a fresh table
    handle, which reads that writer's rows (d008, Delta writes).

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.
    rows : ArrowStream
        The batch's ``station_stock``, in its contract's columns. It is exported
        once per attempt, so it must export afresh each time, as a DuckDB
        relation does.
    first_capture : datetime
        The earliest capture instant of the batch's rows.
    last_capture : datetime
        The latest capture instant of the batch's rows.
    local_dates : Collection[date]
        The local dates the batch's rows fall on; none for a batch with no row.
    attempts : int
        The attempts in all, the first included.

    Returns
    -------
    MergeMetrics
        The rows the MERGE inserted, updated and deleted.

    Raises
    ------
    CommitFailedError
        If the commit still conflicts on the last attempt.
    """
    if not local_dates:
        return MergeMetrics(rows_inserted=0, rows_updated=0, rows_deleted=0)
    dates = ", ".join(_date(local_date) for local_date in sorted(local_dates))
    predicate = (
        "target.system = source.system "
        "and target.station_id = source.station_id "
        "and target.captured_at = source.captured_at "
        f"and target.captured_at >= {_timestamp(first_capture)} "
        f"and target.captured_at <= {_timestamp(last_capture)} "
        f"and target.local_date in ({dates})"
    )
    for attempt in range(1, attempts + 1):
        try:
            metrics = (
                _table(lakehouse, STATION_STOCK_PATH)
                .merge(
                    source=rows,
                    predicate=predicate,
                    source_alias="source",
                    target_alias="target",
                )
                .when_not_matched_insert_all()
                .execute()
            )
        except CommitFailedError:
            if attempt == attempts:
                raise
            continue
        return MergeMetrics(
            rows_inserted=metrics["num_target_rows_inserted"],
            rows_updated=metrics["num_target_rows_updated"],
            rows_deleted=metrics["num_target_rows_deleted"],
        )
    raise ValueError(f"attempts must be at least 1, got {attempts}")


def record_processed(lakehouse: Lakehouse, objects: Sequence[ProcessedObject]) -> None:
    """Record the batch's objects in ``processed_objects``, each key once.

    The insert-only MERGE on ``key`` makes a second writer of the same batch
    add no row (d008 #4, Delta writes).

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.
    objects : Sequence[ProcessedObject]
        The batch's objects.
    """
    if not objects:
        return
    schema = PROCESSED_OBJECTS_SCHEMA.to_arrow()
    arrays = []
    for name in schema.names:
        field = schema.field(name)
        if name == "captured_at":
            # arro3 builds no timestamp array from datetimes: it casts the
            # instants' microseconds since the epoch instead.
            micros = [(obj.captured_at - _EPOCH) // _MICROSECOND for obj in objects]
            arrays.append(Array(micros, type=DataType.int64()).cast(field))
        else:
            arrays.append(Array([getattr(obj, name) for obj in objects], type=field))
    source = Table.from_arrays(arrays, schema=schema)
    (
        _table(lakehouse, PROCESSED_OBJECTS_PATH)
        .merge(
            source=source,
            predicate="target.key = source.key",
            source_alias="source",
            target_alias="target",
        )
        .when_not_matched_insert_all()
        .execute()
    )


def latest_captures(
    lakehouse: Lakehouse, latest: Mapping[System, datetime]
) -> ArrowStream:
    """Return the ``station_stock`` rows of each system's latest capture.

    The read is pruned by each capture's local date, its partition (d008,
    Publishing).

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse, with its tables created.
    latest : Mapping[System, datetime]
        Per system, its latest capture instant; a system left out has no row.

    Returns
    -------
    ArrowStream
        The rows, in the columns of ``station_stock``.
    """
    conditions = [
        f"(system = {_string(system)} "
        f"and local_date = {_date(captured_at.astimezone(LOCAL_TIMEZONE).date())} "
        f"and captured_at = {_timestamp(captured_at)})"
        for system, captured_at in sorted(latest.items())
    ]
    where = " or ".join(conditions) if conditions else "false"
    return _query(lakehouse, STATION_STOCK_PATH, f"select * from t where {where}")
