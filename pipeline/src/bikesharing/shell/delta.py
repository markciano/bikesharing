"""The lakehouse's Delta tables: their creation, the processing state and each batch's commits.

Each batch commits twice: its station stock first, with an insert-only MERGE on
the natural key, and its objects in ``processed_objects`` second, with an
insert-only MERGE on the key, so that a run that stops between the two leaves
the batch pending and processing it again adds no row (d008 #4, Delta writes).
No row is ever updated or deleted (d005 D4, Business processes and the grain of
the stock).

A run opens each table once, with ``ensure_tables``, and every other call reads
and writes through those handles: each of the module's writes refreshes its
handle, and so does a MERGE before its retry, so that opening a table replays
its log once per run (d010, Common table access).

The tables are read through ``deltalake``'s query engine, which returns Arrow
streams that DuckDB writes as dbt's Parquet inputs (d008 #9, Bronze reading).
The SQL the module builds takes only the run's own typed values (instants,
dates and system names), never feed values.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Any, Final, Literal

from arro3.core import Array, ChunkedArray, DataType, Table
from deltalake import DeltaTable, Field, QueryBuilder, Schema
from deltalake.exceptions import CommitFailedError
from deltalake.schema import PrimitiveType

from bikesharing.core.settings import (
    CHECKPOINT_INTERVAL,
    LAKEHOUSE_BUCKET,
    LOCAL_TIMEZONE,
    TABLE_PATHS,
    TOMBSTONE_RETENTION,
    System,
    SystemFeed,
    TableName,
)
from bikesharing.core.verdict import MergeMetrics
from bikesharing.shell.duckdb_session import ArrowStream

_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_EPOCH_ORDINAL: Final = _EPOCH.date().toordinal()
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
            The table's path under the root, one of ``TABLE_PATHS``' values.

        Returns
        -------
        str
            The table's URI.
        """
        return f"{self.uri.rstrip('/')}/{path}"


@dataclass(frozen=True, slots=True)
class Tables:
    """A run's handle on each table, opened once by ``ensure_tables``.

    Only this module reads the handles: it refreshes one after its own writes
    and before a retried MERGE.

    Attributes
    ----------
    lakehouse : Lakehouse
        The lakehouse that holds the tables.
    _handles : Mapping[TableName, DeltaTable]
        Each table's handle, by table name.
    """

    lakehouse: Lakehouse
    _handles: Mapping[TableName, DeltaTable]


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
        _field("utc_date", "date"),
        _field("station_count", "integer"),
        _field("status", "string"),
        _field("run_id", "string"),
        _field("code_version", "string"),
    ]
)

TABLE_SCHEMAS: Final[Mapping[TableName, Schema]] = {
    "station_stock": STATION_STOCK_SCHEMA,
    "processed_objects": PROCESSED_OBJECTS_SCHEMA,
}

# Each table is partitioned by the range its readers filter by (d010,
# processed_objects layout).
PARTITION_COLUMNS: Final[Mapping[TableName, tuple[str, ...]]] = {
    "station_stock": ("local_date",),
    "processed_objects": ("system", "feed", "utc_date"),
}

# Each table's date partition, and the time zone its dates are in.
DATE_PARTITION: Final[Mapping[TableName, tuple[str, tzinfo]]] = {
    "station_stock": ("local_date", LOCAL_TIMEZONE),
    "processed_objects": ("utc_date", UTC),
}

# The columns capture_history returns, those dbt's capture_volume reads: a
# column processed_objects gains, such as utc_date, stays out of dbt's input
# (d010, Common table access).
_CAPTURE_HISTORY_COLUMNS: Final = (
    "key",
    "system",
    "feed",
    "captured_at",
    "station_count",
    "status",
    "run_id",
    "code_version",
)

# The columns latest_captures returns, those of station_stock's dbt contract.
_LATEST_CAPTURES_COLUMNS: Final = (
    "system",
    "station_id",
    "captured_at",
    "local_date",
    "local_minute",
    "num_vehicles_available",
    "num_docks_available",
    "num_vehicles_disabled",
    "num_docks_disabled",
    "is_installed",
    "is_renting",
    "is_returning",
    "last_reported",
    "last_updated",
    "run_id",
    "code_version",
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


def _utc_date(value: datetime) -> date:
    """Return an aware datetime's UTC date, ``processed_objects``' partition."""
    if value.tzinfo is None:
        raise ValueError(f"expected a datetime with a time zone, got {value!r}")
    return value.astimezone(UTC).date()


def _query(tables: Tables, table: TableName, sql: str) -> ArrowStream:
    """Run ``sql`` over the run's handle on ``table``, registered as ``t``."""
    return QueryBuilder().register("t", tables._handles[table]).execute(sql)


def _interval(value: timedelta) -> str:
    """Return a whole number of days as a Delta table property's interval."""
    if value % timedelta(days=1):
        raise ValueError(f"expected a whole number of days, got {value!r}")
    return f"interval {value.days} days"


def _table_properties(table: TableName) -> dict[str, str | None]:
    """Return the table properties ``ensure_tables`` creates ``table`` with.

    The daily maintenance cleans the log itself, so no commit lists the log to
    clean it; and tombstones outlive vacuum's retention, so the daily vacuum
    finds each removed file on several days (d010, Daily maintenance; d010,
    Vacuum and tombstone retention).
    """
    return {
        "delta.checkpointInterval": str(CHECKPOINT_INTERVAL[table]),
        "delta.enableExpiredLogCleanup": "false",
        "delta.deletedFileRetentionDuration": _interval(TOMBSTONE_RETENTION),
    }


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


def ensure_tables(lakehouse: Lakehouse) -> Tables:
    """Create each missing table, then open each once.

    A missing table is created with its explicit schema, its partition columns
    and its maintenance properties; existing tables are kept as they are.

    Parameters
    ----------
    lakehouse : Lakehouse
        The lakehouse that holds the tables.

    Returns
    -------
    Tables
        The run's handle on each table, at its latest version.
    """
    options = dict(lakehouse.storage_options)
    for name, path in TABLE_PATHS.items():
        DeltaTable.create(
            lakehouse.table_uri(path),
            TABLE_SCHEMAS[name],
            mode="ignore",
            partition_by=list(PARTITION_COLUMNS[name]),
            configuration=_table_properties(name),
            storage_options=options,
        )
    return Tables(
        lakehouse=lakehouse,
        _handles={
            name: DeltaTable(lakehouse.table_uri(path), storage_options=options)
            for name, path in TABLE_PATHS.items()
        },
    )


def _feed(feed: SystemFeed) -> str:
    """Return the condition on a system and feed's partition columns."""
    system, name = feed
    return f"system = {_string(system)} and feed = {_string(name)}"


def processed_keys(
    tables: Tables, since: Mapping[SystemFeed, datetime]
) -> frozenset[str]:
    """Return the keys of each system and feed's objects captured at or after its instant.

    Each condition states the feed's partitions from the instant's UTC date and
    the capture range, so that the read prunes every other system, feed and
    date (d010, Bounded calls).

    Parameters
    ----------
    tables : Tables
        The run's tables.
    since : Mapping[SystemFeed, datetime]
        Per system and feed, the first capture instant included; a system and
        feed left out is not read.

    Returns
    -------
    frozenset[str]
        The keys in ``processed_objects`` within those ranges.
    """
    if not since:
        return frozenset()
    conditions = " or ".join(
        f"({_feed(feed)} "
        f"and utc_date >= {_date(_utc_date(instant))} "
        f"and captured_at >= {_timestamp(instant)})"
        for feed, instant in sorted(since.items())
    )
    table = Table.from_arrow(
        _query(tables, "processed_objects", f"select key from t where {conditions}")
    )
    return frozenset(_values(table["key"]))


def latest_processed(tables: Tables) -> dict[SystemFeed, datetime]:
    """Return each system and feed's latest processed capture instant, reading no data file.

    It is the maximum of ``captured_at``'s statistics over the files of the
    feed's latest ``utc_date`` partition, from the log the run's handle holds
    (d010, Bounded calls). The statistics keep milliseconds, which is exact
    here: a capture instant derives from its bronze key, in whole seconds.

    Parameters
    ----------
    tables : Tables
        The run's tables.

    Returns
    -------
    dict[SystemFeed, datetime]
        Per system and feed with processed objects, its latest ``captured_at``,
        in UTC; one with none is left out.
    """
    actions = Table.from_arrow(
        tables._handles["processed_objects"].get_add_actions(flatten=True)
    )
    if actions.num_rows == 0:
        return {}
    latest: dict[SystemFeed, tuple[date, datetime]] = {}
    for system, feed, utc_date, captured_at in zip(
        _values(actions["partition.system"]),
        _values(actions["partition.feed"]),
        _values(actions["partition.utc_date"]),
        _values(actions["max.captured_at"]),
        strict=True,
    ):
        candidate = (utc_date, captured_at)
        latest[(system, feed)] = max(latest.get((system, feed), candidate), candidate)
    return {
        feed: captured_at.astimezone(UTC) for feed, (_, captured_at) in latest.items()
    }


def capture_history(
    tables: Tables,
    *,
    feeds: Collection[SystemFeed],
    since: datetime,
    until: datetime,
) -> ArrowStream:
    """Return the objects of ``feeds`` captured in ``[since, until)``.

    They are the history ``capture_volume`` compares a batch's captures with
    (d008 #14, Transformation in dbt). The read states the feeds' partitions
    and the range's UTC dates, so that it prunes every other system, feed and
    date (d010, Bounded calls).

    Parameters
    ----------
    tables : Tables
        The run's tables.
    feeds : Collection[SystemFeed]
        The systems and feeds read; none reads no row.
    since : datetime
        The first capture instant included.
    until : datetime
        The first capture instant excluded.

    Returns
    -------
    ArrowStream
        The rows of ``processed_objects``, in every column but ``utc_date``.
    """
    partitions = " or ".join(f"({_feed(feed)})" for feed in sorted(set(feeds)))
    return _query(
        tables,
        "processed_objects",
        f"select {', '.join(_CAPTURE_HISTORY_COLUMNS)} from t "
        f"where ({partitions or 'false'}) "
        f"and utc_date >= {_date(_utc_date(since))} "
        f"and utc_date <= {_date(_utc_date(until))} "
        f"and captured_at >= {_timestamp(since)} "
        f"and captured_at < {_timestamp(until)}",
    )


def merge_station_stock(
    tables: Tables,
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
    commit that conflicts with another writer's is retried on the run's handle
    refreshed, which reads that writer's rows (d008, Delta writes).

    Parameters
    ----------
    tables : Tables
        The run's tables.
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
    handle = tables._handles["station_stock"]
    for attempt in range(1, attempts + 1):
        try:
            metrics = (
                handle.merge(
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
            handle.update_incremental()
            continue
        handle.update_incremental()
        return MergeMetrics(
            rows_inserted=metrics["num_target_rows_inserted"],
            rows_updated=metrics["num_target_rows_updated"],
            rows_deleted=metrics["num_target_rows_deleted"],
        )
    raise ValueError(f"attempts must be at least 1, got {attempts}")


def record_processed(tables: Tables, objects: Sequence[ProcessedObject]) -> None:
    """Record the batch's objects in ``processed_objects``, each key once.

    The insert-only MERGE on ``key`` makes a second writer of the same batch
    add no row (d008 #4, Delta writes). Its predicate also states the batch's
    systems, feeds, UTC dates and capture range, so that it reads only the
    partitions and files the batch writes; the match is the same, since the
    capture instant derives from the key (d010, Bounded calls).

    Parameters
    ----------
    tables : Tables
        The run's tables.
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
        elif name == "utc_date":
            days = [
                _utc_date(obj.captured_at).toordinal() - _EPOCH_ORDINAL
                for obj in objects
            ]
            arrays.append(Array(days, type=DataType.int32()).cast(field))
        else:
            arrays.append(Array([getattr(obj, name) for obj in objects], type=field))
    source = Table.from_arrays(arrays, schema=schema)
    systems = ", ".join(
        _string(system) for system in sorted({o.system for o in objects})
    )
    feeds = ", ".join(_string(feed) for feed in sorted({o.feed for o in objects}))
    dates = ", ".join(
        _date(utc_date)
        for utc_date in sorted({_utc_date(o.captured_at) for o in objects})
    )
    captures = [obj.captured_at for obj in objects]
    predicate = (
        "target.key = source.key "
        f"and target.system in ({systems}) "
        f"and target.feed in ({feeds}) "
        f"and target.utc_date in ({dates}) "
        f"and target.captured_at >= {_timestamp(min(captures))} "
        f"and target.captured_at <= {_timestamp(max(captures))}"
    )
    handle = tables._handles["processed_objects"]
    (
        handle.merge(
            source=source,
            predicate=predicate,
            source_alias="source",
            target_alias="target",
        )
        .when_not_matched_insert_all()
        .execute()
    )
    handle.update_incremental()


def latest_captures(tables: Tables, latest: Mapping[System, datetime]) -> ArrowStream:
    """Return the ``station_stock`` rows of each system's latest capture.

    The read is pruned by each capture's local date, its partition (d008,
    Publishing).

    Parameters
    ----------
    tables : Tables
        The run's tables.
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
    return _query(
        tables,
        "station_stock",
        f"select {', '.join(_LATEST_CAPTURES_COLUMNS)} from t where {where}",
    )
