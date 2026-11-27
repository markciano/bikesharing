"""Unit tests for the run settings: their parsing, their checks and the schedule."""

import json
from datetime import timedelta
from pathlib import Path

import pytest

import bikesharing.core
from bikesharing.core.settings import (
    TOMBSTONE_RETENTION,
    VACUUM_RETENTION,
    RunSettings,
    parse_run_settings,
    schedule_cron,
)

VALID = {
    "cadence_min": 15,
    "time_budget_s": 420,
    "timeout_s": 600,
    "container_memory_mib": 4096,
}


def _with(**changes: object) -> dict[str, object]:
    return {**VALID, **changes}


def test_parse_run_settings_reads_the_repository_file() -> None:
    path = Path(bikesharing.core.__file__).parent / "run_settings.json"

    settings = parse_run_settings(json.loads(path.read_text()))

    assert settings == RunSettings(
        cadence=timedelta(minutes=15),
        time_budget=timedelta(seconds=420),
        timeout=timedelta(seconds=600),
        container_memory_mib=4096,
    )


def test_parse_run_settings_accepts_valid_values() -> None:
    settings = parse_run_settings(VALID)

    assert settings.cadence == timedelta(minutes=15)
    assert settings.time_budget == timedelta(minutes=7)
    assert settings.timeout == timedelta(minutes=10)
    assert settings.container_memory_mib == 4096


@pytest.mark.parametrize("key", list(VALID))
def test_parse_run_settings_rejects_a_missing_key(key: str) -> None:
    data = {k: v for k, v in VALID.items() if k != key}

    with pytest.raises(ValueError, match=key):
        parse_run_settings(data)


def test_parse_run_settings_rejects_an_unknown_key() -> None:
    with pytest.raises(ValueError, match="extra"):
        parse_run_settings(_with(extra=1))


@pytest.mark.parametrize("key", list(VALID))
@pytest.mark.parametrize("value", [0, -1, 1.5, "10", True, None])
def test_parse_run_settings_rejects_a_value_that_is_not_a_positive_integer(
    key: str, value: object
) -> None:
    with pytest.raises(ValueError, match=key):
        parse_run_settings(_with(**{key: value}))


@pytest.mark.parametrize("cadence", [7, 11, 45, 61])
def test_parse_run_settings_rejects_a_cadence_that_does_not_divide_60(
    cadence: int,
) -> None:
    with pytest.raises(ValueError, match="cadence_min"):
        parse_run_settings(_with(cadence_min=cadence, time_budget_s=60, timeout_s=120))


@pytest.mark.parametrize("time_budget_s", [600, 700])
def test_parse_run_settings_rejects_a_time_budget_not_below_the_timeout(
    time_budget_s: int,
) -> None:
    with pytest.raises(ValueError, match="time_budget_s"):
        parse_run_settings(_with(time_budget_s=time_budget_s))


@pytest.mark.parametrize("timeout_s", [900, 1000])
def test_parse_run_settings_rejects_a_timeout_not_below_the_cadence(
    timeout_s: int,
) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        parse_run_settings(_with(timeout_s=timeout_s))


def test_schedule_cron_gives_the_cadence_in_minutes() -> None:
    settings = parse_run_settings(VALID)

    assert schedule_cron(settings) == "*/15 * * * *"


def test_vacuum_retention_is_7_days_and_below_the_tombstone_retention() -> None:
    # Vacuum runs with deltalake's own retention check turned off, and a file
    # whose tombstone is dropped before vacuum deletes it stays in R2 for good.
    assert VACUUM_RETENTION == timedelta(days=7)
    assert VACUUM_RETENTION < TOMBSTONE_RETENTION
