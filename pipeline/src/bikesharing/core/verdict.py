"""Decides whether a batch commits, and checks that a MERGE only inserted rows.

The shell runs ``dbt build`` over a batch and collects every node's status; a
batch commits only if no node fails or errors, which includes a model that
breaks its contract, and each warning is logged and stops nothing (d008,
Transformation in dbt). The fact table keeps every row once written: this holds
because the MERGE has only an insert clause, and is checked on the metrics each
MERGE returns (d008 D3, Runtime rules checked by the skeleton).
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

type NodeStatus = Literal["success", "pass", "warn", "fail", "error", "skipped"]
type Severity = Literal["error", "warn"]

_BLOCKING_STATUSES: frozenset[NodeStatus] = frozenset({"fail", "error"})
_RULE_ID = re.compile(r"DQR\d+")


@dataclass(frozen=True, slots=True)
class NodeResult:
    """The outcome of one node of ``dbt build``.

    Attributes
    ----------
    unique_id : str
        dbt's unique ID of the node.
    name : str
        The node's name; a runtime rule's data test is named by its DQR ID.
    resource_type : {"model", "test", "unit_test"}
        The kind of node; ``test`` is a data test.
    status : {"success", "pass", "warn", "fail", "error", "skipped"}
        The node's status as dbt reports it.
    severity : {"error", "warn"} or None
        The severity configured on a data test; None for other nodes.
    failures : int or None
        The number of failing rows a data test reports, if any.
    rows : int or None
        The number of rows a model affected, if reported.
    duration_s : float
        How long the node ran, in seconds.
    """

    unique_id: str
    name: str
    resource_type: Literal["model", "test", "unit_test"]
    status: NodeStatus
    severity: Severity | None
    failures: int | None
    rows: int | None
    duration_s: float


@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether a batch commits, and the nodes that decide or qualify it.

    Attributes
    ----------
    commit : bool
        True when no node ended in ``fail`` or ``error``.
    blocking : tuple[NodeResult, ...]
        The nodes in ``fail`` or ``error``, in the order dbt reported them.
    warnings : tuple[NodeResult, ...]
        The nodes in ``warn``, in the order dbt reported them, to be logged.
    """

    commit: bool
    blocking: tuple[NodeResult, ...]
    warnings: tuple[NodeResult, ...]


@dataclass(frozen=True, slots=True)
class MergeMetrics:
    """The row counts a Delta MERGE reports.

    Attributes
    ----------
    rows_inserted : int
        Rows the MERGE inserted.
    rows_updated : int
        Rows the MERGE updated.
    rows_deleted : int
        Rows the MERGE deleted.
    """

    rows_inserted: int
    rows_updated: int
    rows_deleted: int


def judge_batch(results: Sequence[NodeResult]) -> Verdict:
    """Decide whether a batch commits from the statuses of its dbt nodes.

    Parameters
    ----------
    results : Sequence[NodeResult]
        Every node of the batch's ``dbt build``, in the order dbt reported them.

    Returns
    -------
    Verdict
        Commits only if no node is in ``fail`` or ``error``; carries the
        blocking nodes and the nodes in ``warn``.
    """
    blocking = tuple(r for r in results if r.status in _BLOCKING_STATUSES)
    warnings = tuple(r for r in results if r.status == "warn")
    return Verdict(commit=not blocking, blocking=blocking, warnings=warnings)


def rule_id(result: NodeResult) -> str | None:
    """Return the runtime rule a node checks, if it checks one.

    Parameters
    ----------
    result : NodeResult
        A node of ``dbt build``.

    Returns
    -------
    str or None
        The node's name when it is a data test named by a DQR ID (``DQR``
        followed by digits); None otherwise.
    """
    if result.resource_type == "test" and _RULE_ID.fullmatch(result.name):
        return result.name
    return None


def is_insert_only(metrics: MergeMetrics) -> bool:
    """Return whether a MERGE only inserted rows, as DQR2 requires.

    Parameters
    ----------
    metrics : MergeMetrics
        The metrics the MERGE returned.

    Returns
    -------
    bool
        True when the MERGE updated and deleted no row.
    """
    return metrics.rows_updated == 0 and metrics.rows_deleted == 0
