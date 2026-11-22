"""Builds each function's configuration from its environment and runs the pipeline end to end.

A run discovers the pending bronze objects, processes them oldest first in
bounded batches, and builds, validates and deploys the published file from the
lakehouse's committed state (d008, Bronze reading and Publishing). A batch that
does not commit stops the run with no further batch and no publishing, so the
next run retries it (d008 D9, A failed batch halts the pipeline until T060.5).
The run logs every step as an event, uploads its log at its end and pings its
heartbeat check, and it never raises: every failure ends as a failed outcome
(d008, Observability).
"""

import json
import resource
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, Literal, cast

from obstore.store import ObjectStore

from bikesharing.core import events, settings
from bikesharing.core.batching import (
    Batch,
    may_start_batch,
    plan_batches,
    stage_drained,
    within_end_instant,
)
from bikesharing.core.discovery import (
    BronzeObject,
    parse_exclusion_list,
    pending_objects,
    plan_listing,
)
from bikesharing.core.events import Event, RunContext, SystemDiscovery
from bikesharing.core.published_file import (
    build_published_file,
    validate_published_file,
)
from bikesharing.core.read_schema import STATION_FIELDS, STATION_STATUS_COLUMNS
from bikesharing.core.settings import SYSTEMS, System
from bikesharing.core.verdict import NodeResult, is_insert_only, judge_batch, rule_id
from bikesharing.shell import duckdb_session
from bikesharing.shell.dbt_runner import DbtPaths, dbt_build
from bikesharing.shell.delta import (
    Lakehouse,
    ProcessedObject,
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
from bikesharing.shell.event_log import EventLog
from bikesharing.shell.heartbeat import Signal, ping
from bikesharing.shell.publishing import deploy_page, write_published_file
from bikesharing.shell.r2 import download_batch, list_keys, r2_store, upload_log
from bikesharing.shell.run_settings import RUN_SETTINGS

# The paths a run reads under its root: the repository locally and in tests,
# /repo in Modal's image, which holds the same relative paths.
_DBT_PROJECT: Final = Path("pipeline") / "dbt"
_EXCLUSION_LIST: Final = Path("pipeline") / "config" / "excluded_objects.txt"
_WEB: Final = Path("web")
_FILE_SCHEMA: Final = Path("contracts") / "latest-station-count.schema.json"

# The Worker's assets directory, as web/wrangler.jsonc declares it.
_ASSETS_DIR: Final = "public"
# The window over which capture_volume takes each capture's median, so the
# history holds the captures before the batch's first one in that window
# (d008 #14, Transformation in dbt).
_VOLUME_WINDOW: Final = timedelta(hours=24)
_CHECKED_STATUSES: Final = frozenset({"pass", "warn", "fail", "error"})


class GoldBuildFailed(RuntimeError):
    """The gold layer's build ended with a node in ``fail`` or ``error``."""


@dataclass(frozen=True, slots=True)
class PublishTarget:
    """Where and how a run deploys the page with the published file.

    Attributes
    ----------
    web_dir : Path
        The page's component, holding ``wrangler.jsonc`` and the locked
        ``wrangler``.
    account_id : str
        The Cloudflare account the page is deployed to.
    api_token : str
        The pipeline's Cloudflare token; a secret.
    """

    web_dir: Path
    account_id: str
    api_token: str


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Everything a run needs, built by ``scheduled_config`` or ``one_off_config``.

    Attributes
    ----------
    version : str
        The code version every row and event carries.
    bronze : ObjectStore
        The bronze bucket's store.
    lakehouse : Lakehouse
        Where the Delta tables live.
    log_store : ObjectStore or None
        The store the run's log object is uploaded to; None uploads nothing.
    publish : PublishTarget or None
        Where the page is deployed; None deploys nothing.
    heartbeat_url : str or None
        The heartbeat check's ping URL, a secret; None pings nothing.
    secrets : frozenset[str]
        The value of every secret the run holds, redacted from its events.
    file_schema : Mapping[str, object]
        The published file's JSON Schema, which every run validates against.
    dbt_project_dir : Path
        The dbt project.
    exclusion_list : Path
        The list of bronze objects never processed.
    work_dir : Path
        The folder under which each run creates its own work folder.
    container_memory_mib : int
        The container's hard memory limit, in MiB.
    end_instant : datetime or None
        The end of the first load's current stage, or None for no stage.
    max_objects : int
        The batch bound.
    time_budget : timedelta
        The time after which the run opens no further batch.
    lookback : timedelta
        How far before the latest processed capture a listing starts.
    clock : Callable[[], datetime]
        The current instant, timezone-aware.
    """

    version: str
    bronze: ObjectStore
    lakehouse: Lakehouse
    log_store: ObjectStore | None
    publish: PublishTarget | None
    heartbeat_url: str | None
    secrets: frozenset[str]
    file_schema: Mapping[str, object]
    dbt_project_dir: Path
    exclusion_list: Path
    work_dir: Path
    container_memory_mib: int
    end_instant: datetime | None
    max_objects: int
    time_budget: timedelta
    lookback: timedelta
    clock: Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(UTC)


def _required(env: Mapping[str, str], name: str) -> str:
    """Return a variable of the environment, raising if it is missing or empty."""
    value = env.get(name, "")
    if not value:
        raise ValueError(f"{name} is missing or empty")
    return value


def _config(
    *,
    root: Path,
    container_memory_mib: int,
    work_dir: Path,
    version: str,
    bronze: ObjectStore,
    lakehouse: Lakehouse,
    log_store: ObjectStore | None,
    publish: PublishTarget | None,
    heartbeat_url: str | None,
    secrets: frozenset[str],
) -> RunConfig:
    """Return a run's configuration, with the core's constants and the paths under ``root``."""
    schema = json.loads((root / _FILE_SCHEMA).read_text(encoding="utf-8"))
    return RunConfig(
        version=version,
        bronze=bronze,
        lakehouse=lakehouse,
        log_store=log_store,
        publish=publish,
        heartbeat_url=heartbeat_url,
        secrets=secrets,
        file_schema=schema,
        dbt_project_dir=root / _DBT_PROJECT,
        exclusion_list=root / _EXCLUSION_LIST,
        work_dir=work_dir,
        container_memory_mib=container_memory_mib,
        end_instant=settings.END_INSTANT,
        max_objects=settings.MAX_OBJECTS_PER_BATCH,
        time_budget=RUN_SETTINGS.time_budget,
        lookback=settings.LISTING_LOOKBACK,
        clock=_now,
    )


def _work_dir() -> Path:
    return Path(tempfile.gettempdir()) / "bikesharing"


def scheduled_config(
    env: Mapping[str, str], *, root: Path, container_memory_mib: int
) -> RunConfig:
    """Build the scheduled function's configuration: R2's lakehouse, the page and the heartbeat.

    Parameters
    ----------
    env : Mapping[str, str]
        The function's environment, holding ``CODE_VERSION`` and its secrets.
    root : Path
        The folder that holds ``pipeline/``, ``web/`` and ``contracts/``.
    container_memory_mib : int
        The container's hard memory limit, in MiB.

    Returns
    -------
    RunConfig
        A run that writes the lakehouse and its log to ``bikesharing-lakehouse``,
        deploys the page and pings the heartbeat.

    Raises
    ------
    ValueError
        If ``CODE_VERSION`` or any secret is missing or empty: a run never
        starts without its code version (d008 #20, Environments and
        configuration).
    """
    version = _required(env, "CODE_VERSION")
    bronze_id = _required(env, "BRONZE_R2_ACCESS_KEY_ID")
    bronze_secret = _required(env, "BRONZE_R2_SECRET_ACCESS_KEY")
    lakehouse_id = _required(env, "LAKEHOUSE_R2_ACCESS_KEY_ID")
    lakehouse_secret = _required(env, "LAKEHOUSE_R2_SECRET_ACCESS_KEY")
    api_token = _required(env, "CLOUDFLARE_API_TOKEN")
    heartbeat_url = _required(env, "HEARTBEAT_URL")
    account_id = settings.CLOUDFLARE_ACCOUNT_ID
    return _config(
        root=root,
        container_memory_mib=container_memory_mib,
        work_dir=_work_dir(),
        version=version,
        bronze=r2_store(
            settings.BRONZE_BUCKET,
            account_id=account_id,
            access_key_id=bronze_id,
            secret_access_key=bronze_secret,
        ),
        lakehouse=r2_lakehouse(
            account_id=account_id,
            access_key_id=lakehouse_id,
            secret_access_key=lakehouse_secret,
        ),
        log_store=r2_store(
            settings.LAKEHOUSE_BUCKET,
            account_id=account_id,
            access_key_id=lakehouse_id,
            secret_access_key=lakehouse_secret,
        ),
        publish=PublishTarget(
            web_dir=root / _WEB, account_id=account_id, api_token=api_token
        ),
        heartbeat_url=heartbeat_url,
        secrets=frozenset(
            {
                bronze_id,
                bronze_secret,
                lakehouse_id,
                lakehouse_secret,
                api_token,
                heartbeat_url,
            }
        ),
    )


def one_off_config(
    env: Mapping[str, str], *, root: Path, container_memory_mib: int
) -> RunConfig:
    """Build the one-off function's configuration: bronze only, a local lakehouse.

    Parameters
    ----------
    env : Mapping[str, str]
        The function's environment, holding bronze's read-only credentials.
    root : Path
        The folder that holds ``pipeline/`` and ``contracts/``.
    container_memory_mib : int
        The container's hard memory limit, in MiB.

    Returns
    -------
    RunConfig
        A run with the version ``unreleased`` that writes its tables under a
        work folder created for this configuration, so it starts from empty
        tables, and uploads no log, deploys nothing and pings nothing (d008
        #20, Environments and configuration).

    Raises
    ------
    ValueError
        If a bronze credential is missing or empty.
    """
    bronze_id = _required(env, "BRONZE_R2_ACCESS_KEY_ID")
    bronze_secret = _required(env, "BRONZE_R2_SECRET_ACCESS_KEY")
    # A folder of its own, so that a run in a reused container, or a second
    # local run, never starts from an earlier run's tables.
    work_dir = Path(tempfile.mkdtemp(prefix="bikesharing-one-off-"))
    return _config(
        root=root,
        container_memory_mib=container_memory_mib,
        work_dir=work_dir,
        version=settings.UNRELEASED_VERSION,
        bronze=r2_store(
            settings.BRONZE_BUCKET,
            account_id=settings.CLOUDFLARE_ACCOUNT_ID,
            access_key_id=bronze_id,
            secret_access_key=bronze_secret,
        ),
        lakehouse=local_lakehouse(work_dir / "lakehouse"),
        log_store=None,
        publish=None,
        heartbeat_url=None,
        secrets=frozenset({bronze_id, bronze_secret}),
    )


@dataclass(frozen=True, slots=True)
class _Inputs:
    """The files of the run's work folder that dbt reads, fixed at the run's start."""

    empty: Path
    capture_history: Path
    latest_captures: Path


@dataclass
class _Run:
    """A run's configuration, log and running totals."""

    config: RunConfig
    run_id: str
    log: EventLog
    paths: DbtPaths
    inputs: _Inputs
    batches: int = 0
    rows_inserted: int = 0
    failed: bool = False
    failing: list[str] = field(default_factory=list)

    def emit(self, event: Event) -> None:
        """Log an event, keeping it for the failure ping when it is an error."""
        line = self.log.emit(event)
        if event.level == "error":
            self.failing.append(line)

    def fail(self, event: Event) -> None:
        """Log the event that fails the run."""
        self.failed = True
        self.emit(event)

    def now(self) -> datetime:
        return self.config.clock()


def run(config: RunConfig) -> Literal["succeeded", "failed"]:
    """Run the pipeline end to end and return its outcome; it never raises.

    In order: it creates the run's work folder, pings ``start`` and logs
    ``run_started``; discovers the pending objects; applies the end instant;
    processes each batch while the time budget allows, stopping at the first
    that does not commit; unless a batch failed, builds, validates and deploys
    the published file; and finally removes the work folder, logs
    ``run_finished``, uploads the log and pings ``success`` or ``fail``.

    Parameters
    ----------
    config : RunConfig
        The run's configuration.

    Returns
    -------
    {"succeeded", "failed"}
        ``failed`` when a batch does not commit, the file breaks its schema,
        the deployment fails, or any exception is raised.
    """
    started_at = config.clock()
    run_id = str(uuid.uuid7())
    work = config.work_dir / run_id
    log = EventLog(
        RunContext(run_id=run_id, version=config.version), config.secrets, sys.stdout
    )
    state = _Run(
        config=config,
        run_id=run_id,
        log=log,
        paths=DbtPaths(
            project_dir=config.dbt_project_dir,
            scratch_database=work / "scratch.duckdb",
            allowed_directory=work,
            temp_directory=work / "spill",
            # DuckDB keeps below the container's limit, leaving the rest to
            # Python, the Arrow hand-off and dbt (d008 #10, Bronze reading).
            duckdb_memory_limit_mib=int(
                settings.DUCKDB_MEMORY_FRACTION * config.container_memory_mib
            ),
        ),
        inputs=_Inputs(
            empty=work / "empty.json",
            capture_history=work / "capture_history.parquet",
            latest_captures=work / "latest_captures.parquet",
        ),
    )
    error: Exception | None = None
    try:
        work.mkdir(parents=True)
        _ping(state, "start")
        _execute(state, started_at)
    # Any exception fails the run and goes into run_finished's error, so that
    # the log and the failure ping carry its cause (d008, Observability).
    except Exception as raised:  # noqa: BLE001
        error = raised
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return _finish(state, started_at, error)


def _execute(state: _Run, started_at: datetime) -> None:
    """Discover the pending objects, process their batches and publish the file."""
    config = state.config
    excluded = parse_exclusion_list(config.exclusion_list.read_text(encoding="utf-8"))
    state.emit(
        events.run_started(
            state.now(),
            end_instant=config.end_instant,
            excluded_objects=len(excluded),
        )
    )
    pending = _discover(state, excluded)
    if config.end_instant is not None and stage_drained(pending, config.end_instant):
        state.emit(events.stage_drained(state.now(), end_instant=config.end_instant))
    state.inputs.empty.touch()
    batches = plan_batches(
        within_end_instant(pending, config.end_instant), config.max_objects
    )
    for batch in batches:
        if not may_start_batch(
            run_started=started_at, now=state.now(), budget=config.time_budget
        ):
            break
        if not _process_batch(state, batch):
            # A batch that does not commit halts the run, with no publishing,
            # so the next run retries it (d008 D9, A failed batch halts the
            # pipeline until T060.5).
            return
    _publish(state)


def _discover(state: _Run, excluded: frozenset[str]) -> list[BronzeObject]:
    """List each system and return the pending objects, logging what was found."""
    config = state.config
    ensure_tables(config.lakehouse)
    processed = processed_keys(config.lakehouse)
    latest = latest_processed(config.lakehouse)
    pending: list[BronzeObject] = []
    found: dict[System, SystemDiscovery] = {}
    for system in SYSTEMS:
        plan = plan_listing(
            system,
            latest[system],
            now=state.now(),
            lookback=config.lookback,
            timezone=settings.LOCAL_TIMEZONE,
        )
        listed = list_keys(config.bronze, plan)
        objects = pending_objects(listed, processed, excluded)
        pending.extend(objects)
        found[system] = SystemDiscovery(
            listed=len(listed), pending=len(objects), full_sweep=plan.full_sweep
        )
    state.emit(events.objects_discovered(state.now(), systems=found))
    return pending


def _process_batch(state: _Run, batch: Batch) -> bool:
    """Process one batch in its own subfolder; return whether it committed."""
    folder = state.paths.allowed_directory / f"batch-{batch.number}"
    state.emit(events.batch_started(state.now(), batch=batch))
    try:
        return _commit_batch(state, batch, folder)
    # Any exception inside a batch fails it, logged with its type and message.
    except Exception as error:  # noqa: BLE001
        state.fail(
            events.batch_failed(
                state.now(),
                batch=batch.number,
                reason="exception",
                error_type=type(error).__name__,
                error=str(error),
            )
        )
        return False
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _commit_batch(state: _Run, batch: Batch, folder: Path) -> bool:
    """Build, judge and commit one batch; return whether it committed."""
    config = state.config
    files = download_batch(config.bronze, batch, folder)
    bronze_files: dict[System, list[str]] = {}
    for bronze_object, path in zip(batch.objects, files, strict=True):
        bronze_files.setdefault(bronze_object.system, []).append(str(path))
    history = capture_history(
        config.lakehouse,
        since=batch.first_capture - _VOLUME_WINDOW,
        until=batch.first_capture,
    )
    with _connection(state.paths) as con:
        duckdb_session.write_parquet(con, history, state.inputs.capture_history)

    results = _build(state, "silver", bronze_files)
    if not judge_batch(results).commit:
        state.fail(
            events.batch_failed(
                state.now(),
                batch=batch.number,
                reason="nodes_failed",
                error_type=None,
                error=None,
            )
        )
        return False

    with _connection(state.paths) as con:
        for capture in duckdb_session.volume_not_evaluated(con):
            state.emit(
                events.volume_not_evaluated(
                    state.now(),
                    system=capture.system,
                    captured_at=capture.captured_at,
                    captures_in_window=capture.captures_in_window,
                )
            )
        for drift in duckdb_session.schema_drift_fields(con):
            state.emit(
                events.schema_drift_field(
                    state.now(),
                    system=drift.system,
                    field=drift.field,
                    change=drift.change,
                )
            )
        metrics = merge_station_stock(
            config.lakehouse,
            duckdb_session.station_stock(con),
            first_capture=batch.first_capture,
            last_capture=batch.last_capture,
            local_dates=duckdb_session.station_stock_local_dates(con),
        )
        station_counts = duckdb_session.station_counts(con)

    # The fact table keeps every row once written: DQR2 holds when the MERGE
    # inserted only (d008 D3, Runtime rules checked by the skeleton).
    insert_only = is_insert_only(metrics)
    state.emit(
        events.rule_checked(
            state.now(),
            rule="DQR2",
            severity="error",
            status="pass" if insert_only else "fail",
            failures=metrics.rows_updated + metrics.rows_deleted,
        )
    )
    if not insert_only:
        state.fail(
            events.batch_failed(
                state.now(),
                batch=batch.number,
                reason="not_insert_only",
                error_type=None,
                error=None,
            )
        )
        return False

    record_processed(
        config.lakehouse,
        [
            ProcessedObject(
                key=bronze_object.key,
                system=bronze_object.system,
                feed=bronze_object.feed,
                captured_at=bronze_object.captured_at,
                station_count=station_counts[
                    (bronze_object.system, bronze_object.captured_at)
                ],
                status="processed",
                run_id=state.run_id,
                code_version=config.version,
            )
            for bronze_object in batch.objects
        ],
    )
    state.batches += 1
    state.rows_inserted += metrics.rows_inserted
    state.emit(
        events.batch_committed(
            state.now(),
            batch=batch.number,
            rows_inserted=metrics.rows_inserted,
            objects=len(batch.objects),
        )
    )
    return True


def _publish(state: _Run) -> None:
    """Build the file from the lakehouse, validate it and deploy it."""
    config = state.config
    latest = {
        system: captured_at
        for system, captured_at in latest_processed(config.lakehouse).items()
        if captured_at is not None
    }
    if not latest:
        return
    with _connection(state.paths) as con:
        duckdb_session.write_parquet(
            con,
            latest_captures(config.lakehouse, latest),
            state.inputs.latest_captures,
        )
    verdict = judge_batch(_build(state, "gold", {}))
    if not verdict.commit:
        blocking = ", ".join(result.unique_id for result in verdict.blocking)
        raise GoldBuildFailed(f"the gold build failed on {blocking}")
    with _connection(state.paths) as con:
        stations = duckdb_session.latest_station_count(con)

    document = build_published_file(stations)
    violations = validate_published_file(document, config.file_schema)
    state.emit(
        events.rule_checked(
            state.now(),
            rule="DQR14",
            severity="error",
            status="fail" if violations else "pass",
            failures=len(violations),
        )
    )
    if violations:
        # A file that breaks its schema is not deployed: the last file that
        # passed stays published (d008 D9, A failed batch halts the pipeline
        # until T060.5).
        state.fail(events.file_invalid(state.now(), violations=violations))
        return
    state.emit(
        events.file_built(
            state.now(),
            stations=len(stations),
            data_instant=max(cast(datetime, row["captured_at"]) for row in stations),
        )
    )
    if config.publish is None:
        return
    target = config.publish
    write_published_file(document, target.web_dir / _ASSETS_DIR)
    deployed = deploy_page(
        target.web_dir,
        tag=config.version,
        account_id=target.account_id,
        api_token=target.api_token,
    )
    if deployed.exit_code == 0:
        state.emit(
            events.page_deployed(
                state.now(),
                tag=config.version,
                deploy_peak_memory_mb=deployed.peak_memory_mb,
            )
        )
    else:
        state.fail(
            events.page_deploy_failed(
                state.now(), exit_code=deployed.exit_code, output=deployed.output
            )
        )


def _build(
    state: _Run,
    select: Literal["silver", "gold"],
    bronze_files: Mapping[System, Sequence[str]],
) -> list[NodeResult]:
    """Run ``dbt build`` on a layer, logging each node and each rule it checks."""
    inputs = state.inputs
    variables = {
        # DuckDB reads no empty list of files, so a system with no object
        # lists the work folder's empty file, which reads as no rows.
        "bronze_files": {
            system: list(bronze_files.get(system, ())) or [str(inputs.empty)]
            for system in SYSTEMS
        },
        "read_columns": {
            system: dict(columns) for system, columns in STATION_STATUS_COLUMNS.items()
        },
        "station_fields": {
            system: sorted(fields) for system, fields in STATION_FIELDS.items()
        },
        "capture_history_file": str(inputs.capture_history),
        "latest_captures_file": str(inputs.latest_captures),
        "run_id": state.run_id,
        "code_version": state.config.version,
    }
    results = dbt_build(
        state.paths,
        select=select,
        variables=variables,
        on_node=lambda result: state.emit(
            events.node_finished(state.now(), result=result)
        ),
    )
    for result in results:
        rule = rule_id(result)
        # A test dbt skips checked nothing: node_finished already logs it.
        if (
            rule is None
            or result.severity is None
            or result.status not in _CHECKED_STATUSES
        ):
            continue
        state.emit(
            events.rule_checked(
                state.now(),
                rule=rule,
                severity=result.severity,
                status=cast(Literal["pass", "warn", "fail", "error"], result.status),
                failures=result.failures or 0,
            )
        )
    return results


class _connection:
    """Open the scratch database with the run's sandbox, and close it on exit.

    dbt opens the same file between the shell's uses, so the shell never keeps
    a connection across a build (d008, ``bikesharing.shell.dbt_runner``).
    """

    def __init__(self, paths: DbtPaths) -> None:
        self._paths = paths

    def __enter__(self) -> duckdb_session.DuckDBPyConnection:
        self._con = duckdb_session.connect(
            self._paths.scratch_database,
            allowed_directories=[self._paths.allowed_directory],
            temp_directory=self._paths.temp_directory,
            duckdb_memory_limit_mib=self._paths.duckdb_memory_limit_mib,
        )
        return self._con

    def __exit__(self, *_: object) -> None:
        self._con.close()


def _ping(state: _Run, signal: Signal, body: str = "") -> None:
    """Ping the heartbeat check, if set, logging a ping that could not be delivered."""
    url = state.config.heartbeat_url
    if url is None:
        return
    failure = ping(url, signal, body=body)
    if failure is not None:
        state.emit(
            events.heartbeat_failed(
                state.now(),
                signal=failure.signal,
                attempts=failure.attempts,
                error_type=failure.error_type,
            )
        )


def _finish(
    state: _Run, started_at: datetime, error: Exception | None
) -> Literal["succeeded", "failed"]:
    """Log ``run_finished``, upload the log and ping the outcome, as the run's last actions."""
    outcome: Literal["succeeded", "failed"] = (
        "failed" if state.failed or error is not None else "succeeded"
    )
    finished = state.log.emit(
        events.run_finished(
            state.now(),
            outcome=outcome,
            batches=state.batches,
            rows_inserted=state.rows_inserted,
            # The run's wall-clock time, from the clock it is given, so that
            # tests fix it (d008, Observability).
            duration_s=(state.now() - started_at).total_seconds(),
            peak_memory_mb=events.peak_memory_mb(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            ),
            error_type=type(error).__name__ if error is not None else None,
            error=str(error) if error is not None else None,
        )
    )
    log_store = state.config.log_store
    if log_store is not None:
        try:
            upload_log(
                log_store,
                events.log_object_key(state.run_id, started_at),
                state.log.body(),
            )
        # A lost log object changes neither the outcome nor its signal.
        except Exception as raised:  # noqa: BLE001
            state.emit(
                events.log_upload_failed(state.now(), error_type=type(raised).__name__)
            )
    if outcome == "succeeded":
        _ping(state, "success")
    else:
        _ping(state, "fail", body="".join(_lines(finished, state.failing)))
    return outcome


def _lines(first: str, rest: Sequence[str]) -> Iterator[str]:
    """Yield the failure ping's body: ``run_finished`` first, then the failing events."""
    for line in (first, *rest):
        yield f"{line}\n"
