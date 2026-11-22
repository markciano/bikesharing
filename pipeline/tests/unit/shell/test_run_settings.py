"""Unit tests for the shell's read of the run settings file."""

import json
from datetime import timedelta
from pathlib import Path

from bikesharing.shell.run_settings import RUN_SETTINGS


def test_run_settings_equal_the_repository_file() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "bikesharing"
        / "core"
        / "run_settings.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))

    assert RUN_SETTINGS.cadence == timedelta(minutes=data["cadence_min"])
    assert RUN_SETTINGS.time_budget == timedelta(seconds=data["time_budget_s"])
    assert RUN_SETTINGS.timeout == timedelta(seconds=data["timeout_s"])
    assert RUN_SETTINGS.container_memory_mib == data["container_memory_mib"]
