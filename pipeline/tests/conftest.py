"""Fixtures shared by every test level: a local bronze folder and a local Delta path."""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def bronze_folder(tmp_path: Path) -> Path:
    """A copy of the bronze fixtures, with each object under its bucket key.

    The copy lies in the test's own folder, so that a test may sandbox DuckDB to
    it and change it without touching the repository's fixtures.

    Returns
    -------
    Path
        The folder standing in for the bronze bucket; each object is at
        ``raw/<system>/station_status/<local date>/<instant>.json.gz``.
    """
    folder = tmp_path / "bronze"
    shutil.copytree(FIXTURES / "bronze" / "raw", folder / "raw")
    return folder


@pytest.fixture
def delta_path(tmp_path: Path) -> Path:
    """A local folder standing in for the lakehouse, not yet created.

    Returns
    -------
    Path
        The folder under which the tests' Delta tables are written.
    """
    return tmp_path / "lakehouse"
