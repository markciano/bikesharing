"""The platform module and the package stay apart.

Rules 4 and 5 of the package's structure (ADR-0046, Functional core and imperative
shell for the pipeline). Rule 4: the platform module never imports the engine.
Import-linter takes only packages as root packages and ``modal_app.py`` is a single
module, so this test reads its imports from its syntax tree. Rule 5: the environment
synced by default leaves out the ``platform`` dependency group, so ``modal`` is
absent and the package must still import.
"""

import ast
import importlib
from pathlib import Path

import pytest

PLATFORM_MODULE = Path(__file__).resolve().parents[2] / "modal_app.py"


def imported_top_level_modules(source: str) -> set[str]:
    """Return the top-level names of the modules that a source file imports.

    Only import statements count, wherever they sit in the file, which is what
    import-linter's contract on direct imports checks; an import through
    ``importlib`` is not seen.
    """
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize(
    "source",
    [
        "import duckdb",
        "import duckdb.experimental",
        "import os, duckdb",
        "import duckdb as db",
        "from duckdb import connect",
        "from duckdb.typing import VARCHAR",
        "def run():\n    import duckdb",
    ],
)
def test_import_detector_finds_the_engine(source: str) -> None:
    assert "duckdb" in imported_top_level_modules(source)


@pytest.mark.parametrize(
    "source",
    [
        "import os",
        "from bikesharing.shell.run import run",
        "from . import duckdb_session",
        "name = 'duckdb'",
    ],
)
def test_import_detector_ignores_other_code(source: str) -> None:
    assert "duckdb" not in imported_top_level_modules(source)


def test_platform_module_does_not_import_the_engine() -> None:
    imported = imported_top_level_modules(PLATFORM_MODULE.read_text())

    assert "duckdb" not in imported


def test_modal_import_fails_in_default_environment() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("modal")


@pytest.mark.parametrize(
    "module",
    [
        "bikesharing",
        "bikesharing.core",
        "bikesharing.core.settings",
        "bikesharing.shell",
    ],
)
def test_package_imports_without_modal(module: str) -> None:
    imported = importlib.import_module(module)

    assert imported.__name__ == module
