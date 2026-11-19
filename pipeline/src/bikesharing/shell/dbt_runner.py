"""Runs ``dbt build`` in process over a batch and returns its node statuses as values.

The shell passes the batch's variables and the run's paths; dbt builds and audits
the batch in the run's scratch database, and each node's outcome comes back as a
``NodeResult``, for the core to judge (d008 #12, #16, Transformation in dbt).
dbt is parsed once per call: the manifest gives each data test's configured
severity, which dbt's events do not carry.
"""

import gc
import json
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from dbt.adapters.duckdb.connections import DuckDBConnectionManager
from dbt.adapters.factory import reset_adapters
from dbt.cli.main import dbtRunner, dbtRunnerResult
from dbt.contracts.graph.manifest import Manifest
from dbt_common.events.base_types import EventMsg

from bikesharing.core.verdict import NodeResult, NodeStatus, Severity

_RESOURCE_TYPES = frozenset({"model", "test", "unit_test"})
_NODE_FINISHED = "NodeFinished"


class DbtInvocationError(RuntimeError):
    """A dbt invocation that failed outside its nodes, such as a parse error."""


@dataclass(frozen=True, slots=True)
class DbtPaths:
    """The folders and limits of a run's dbt invocations.

    Attributes
    ----------
    project_dir : Path
        The dbt project, which holds ``profiles.yml``.
    scratch_database : Path
        The run's scratch DuckDB file, inside ``allowed_directory``.
    allowed_directory : Path
        The run's work folder, the only folder DuckDB may read or write.
    temp_directory : Path
        The folder DuckDB spills to, inside ``allowed_directory``.
    duckdb_memory_limit_mib : int
        DuckDB's memory limit, in MiB.
    """

    project_dir: Path
    scratch_database: Path
    allowed_directory: Path
    temp_directory: Path
    duckdb_memory_limit_mib: int


@contextmanager
def _dbt_environment(paths: DbtPaths) -> Iterator[None]:
    """Set the variables ``profiles.yml`` reads; on exit, restore them and release dbt.

    dbt-duckdb keeps its DuckDB instance open, with its configuration locked, after
    an invocation returns; it only drops its reference to it (s017 F8). Dropping
    the adapters and collecting makes DuckDB close the file, so that the shell
    opens the scratch database again with ``connect`` and its own sandbox.
    """
    values = {
        "BIKESHARING_SCRATCH_DATABASE": str(paths.scratch_database),
        "BIKESHARING_ALLOWED_DIRECTORY": str(paths.allowed_directory),
        "BIKESHARING_TEMP_DIRECTORY": str(paths.temp_directory),
        "BIKESHARING_MEMORY_LIMIT": f"{paths.duckdb_memory_limit_mib}MiB",
    }
    previous = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        reset_adapters()
        DuckDBConnectionManager.close_all_connections()
        gc.collect()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _fail_on_invocation_error(result: dbtRunnerResult, command: str) -> None:
    """Raise if dbt failed outside its nodes; a failing node is not an invocation error."""
    if result.exception is not None:
        raise DbtInvocationError(f"dbt {command} failed: {result.exception}")
    if not result.success and result.result is None:
        raise DbtInvocationError(f"dbt {command} failed with no result")


def _severity(manifest: Any, unique_id: str, resource_type: str) -> Severity | None:
    """Return the severity configured on a data test, ``None`` for other nodes."""
    if resource_type != "test":
        return None
    node = manifest.nodes.get(unique_id)
    if node is None:
        return None
    return cast(Severity, str(node.config.severity).lower())


def _node_result(
    manifest: Any,
    *,
    unique_id: str,
    name: str,
    resource_type: str,
    status: str,
    failures: int | None,
    duration_s: float,
) -> NodeResult:
    """Build the pipeline's value for a node, from either of dbt's reports of it."""
    kind = cast(Literal["model", "test", "unit_test"], resource_type)
    return NodeResult(
        unique_id=unique_id,
        name=name,
        resource_type=kind,
        status=cast(NodeStatus, status),
        severity=_severity(manifest, unique_id, resource_type),
        # dbt-duckdb reports no rows affected (s017 F9); the shell counts them.
        failures=(failures or 0) if resource_type != "model" else None,
        rows=None,
        duration_s=duration_s,
    )


def dbt_build(
    paths: DbtPaths,
    *,
    select: Literal["silver", "gold"],
    variables: Mapping[str, object],
    on_node: Callable[[NodeResult], None],
) -> list[NodeResult]:
    """Run ``dbt build`` over one layer and return every node's outcome.

    The build has no fail-fast, so a failing data test does not stop the other
    nodes, and it leaves out dbt's unit tests, which run in CI.

    Parameters
    ----------
    paths : DbtPaths
        The dbt project and the run's folders and limits; they reach
        ``profiles.yml`` through environment variables for the call's duration.
    select : {"silver", "gold"}
        The layer to build.
    variables : Mapping[str, object]
        The batch's dbt variables, as JSON-serialisable values.
    on_node : Callable[[NodeResult], None]
        Called once for each node, as it finishes.

    Returns
    -------
    list[NodeResult]
        Every node dbt reported, in the order dbt reported them.

    Raises
    ------
    DbtInvocationError
        If dbt fails outside its nodes, such as on a parse error.
    """
    common = [
        "--project-dir",
        str(paths.project_dir),
        "--profiles-dir",
        str(paths.project_dir),
        "--vars",
        json.dumps(variables),
    ]
    with _dbt_environment(paths):
        parsed = dbtRunner().invoke(["parse", *common])
        _fail_on_invocation_error(parsed, "parse")
        manifest = cast(Manifest, parsed.result)
        reported: set[str] = set()

        def on_event(msg: EventMsg) -> None:
            if msg.info.name != _NODE_FINISHED:
                return
            data = cast(Any, msg.data)
            node = data.node_info
            if node.resource_type not in _RESOURCE_TYPES:
                return
            result = _node_result(
                manifest,
                unique_id=node.unique_id,
                name=node.node_name,
                resource_type=node.resource_type,
                status=data.run_result.status,
                failures=data.run_result.num_failures,
                duration_s=data.run_result.execution_time,
            )
            reported.add(result.unique_id)
            on_node(result)

        built = dbtRunner(manifest=manifest, callbacks=[on_event]).invoke(
            [
                "build",
                *common,
                "--select",
                select,
                "--exclude-resource-type",
                "unit_test",
            ]
        )
        _fail_on_invocation_error(built, "build")

    results = []
    for run_result in cast(Any, built.result).results:
        node = run_result.node
        result = _node_result(
            manifest,
            unique_id=node.unique_id,
            name=node.name,
            resource_type=node.resource_type.value,
            status=run_result.status.value,
            failures=run_result.failures,
            duration_s=run_result.execution_time,
        )
        results.append(result)
        # A node dbt skips may fire no event; the callback still reports it.
        if result.unique_id not in reported:
            on_node(result)
    return results
