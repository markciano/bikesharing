"""Tests of the verdict: batch commit, rule mapping and DQR2's MERGE check."""

from typing import Literal

import pytest
from bikesharing.core.verdict import (
    MergeMetrics,
    NodeResult,
    NodeStatus,
    Verdict,
    is_insert_only,
    judge_batch,
    rule_id,
)

type ResourceType = Literal["model", "test", "unit_test"]


def _node(
    name: str,
    status: NodeStatus,
    resource_type: ResourceType = "test",
) -> NodeResult:
    is_data_test = resource_type == "test"
    return NodeResult(
        unique_id=f"{resource_type}.bikesharing.{name}",
        name=name,
        resource_type=resource_type,
        status=status,
        severity="error" if is_data_test else None,
        failures=0 if is_data_test else None,
        rows=None if is_data_test else 10,
        duration_s=0.1,
    )


# Verifies d008 R8
def test_judge_batch_commits_when_every_node_succeeds_or_passes() -> None:
    results = [
        _node("station_stock", "success", "model"),
        _node("DQR1", "pass"),
        _node("test_station_stock_grain", "pass", "unit_test"),
        _node("DQR13", "skipped"),
    ]

    assert judge_batch(results) == Verdict(commit=True, blocking=(), warnings=())


@pytest.mark.parametrize(
    "failing",
    [
        _node("DQR1", "fail"),
        _node("DQR13", "error"),
        _node("station_stock", "error", "model"),
        _node("test_station_stock_grain", "fail", "unit_test"),
    ],
    ids=["data test fails", "data test errors", "model errors", "unit test fails"],
)
def test_judge_batch_blocks_on_any_node_in_fail_or_error(failing: NodeResult) -> None:
    results = [_node("station_stock", "success", "model"), failing]

    verdict = judge_batch(results)

    assert (verdict.commit, verdict.blocking) == (False, (failing,))


def test_judge_batch_commits_and_returns_warnings_when_nodes_warn() -> None:
    warned = (_node("DQR11", "warn"), _node("DQR12", "warn"))
    results = [_node("station_stock", "success", "model"), *warned]

    assert judge_batch(results) == Verdict(commit=True, blocking=(), warnings=warned)


def test_judge_batch_returns_every_blocking_node_in_order() -> None:
    first, second = _node("DQR1", "fail"), _node("DQR13", "fail")

    assert judge_batch([first, _node("DQR11", "pass"), second]).blocking == (
        first,
        second,
    )


def test_judge_batch_commits_without_nodes() -> None:
    assert judge_batch([]) == Verdict(commit=True, blocking=(), warnings=())


# Verifies d008 R8
@pytest.mark.parametrize("name", ["DQR1", "DQR12", "DQR13"])
def test_rule_id_is_the_name_of_a_data_test_named_by_a_dqr_id(name: str) -> None:
    assert rule_id(_node(name, "pass")) == name


@pytest.mark.parametrize(
    ("name", "resource_type"),
    [
        ("station_stock", "model"),
        ("not_null_station_stock_station_id", "test"),
        ("DQR", "test"),
        ("DQR1a", "test"),
        ("xDQR1", "test"),
        ("dqr1", "test"),
        ("DQR1", "unit_test"),
        ("DQR1", "model"),
    ],
    ids=[
        "model",
        "data test with other name",
        "no digits",
        "trailing text",
        "leading text",
        "lower case",
        "unit test",
        "model named like a rule",
    ],
)
def test_rule_id_is_none_for_a_node_that_is_not_a_runtime_rule(
    name: str, resource_type: ResourceType
) -> None:
    assert rule_id(_node(name, "pass", resource_type)) is None


# Verifies d008 R30
def test_is_insert_only_when_no_row_is_updated_or_deleted() -> None:
    metrics = MergeMetrics(rows_inserted=42, rows_updated=0, rows_deleted=0)

    assert is_insert_only(metrics) is True


@pytest.mark.parametrize(
    "metrics",
    [
        MergeMetrics(rows_inserted=42, rows_updated=1, rows_deleted=0),
        MergeMetrics(rows_inserted=42, rows_updated=0, rows_deleted=1),
        MergeMetrics(rows_inserted=0, rows_updated=3, rows_deleted=2),
    ],
    ids=["row updated", "row deleted", "both"],
)
def test_is_insert_only_fails_when_a_row_is_updated_or_deleted(
    metrics: MergeMetrics,
) -> None:
    assert is_insert_only(metrics) is False
