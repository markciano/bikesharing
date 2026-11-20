"""The platform modules and the package stay apart, and the one-off app holds no production credential.

Rules 4 and 5 of the package's structure (ADR-0046, Functional core and imperative
shell for the pipeline). Rule 4: the platform modules never import the engine.
Import-linter takes only packages as root packages and the platform modules are
single modules, so this test reads their imports from their syntax trees. Rule 5: the
environment synced by default leaves out the ``platform`` dependency group, so
``modal`` is absent and the package must still import.

The one-off app is a module of its own, so that ``modal run`` never creates the
scheduled function with its production Secrets (d008 DI12, Environments and
configuration); the tests below read the modules' names from their syntax trees.
"""

import ast
import importlib
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parents[2]
IMAGE_MODULE = PIPELINE_DIR / "modal_image.py"
SCHEDULED_MODULE = PIPELINE_DIR / "modal_app.py"
ONE_OFF_MODULE = PIPELINE_DIR / "modal_one_off.py"
PLATFORM_MODULES = [IMAGE_MODULE, SCHEDULED_MODULE, ONE_OFF_MODULE]


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


def names_used(source: str) -> set[str]:
    """Return every name that a source file uses or imports, and its string constants.

    A Secret can reach a module as a name (``DEPLOY_SECRET``), as an imported name or
    as a literal (``"bikesharing-pipeline-deploy"``), so all three are collected.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update(alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def functions_defined(source: str) -> set[str]:
    """Return the names of the functions that a source file defines at its top level."""
    return {
        node.name
        for node in ast.parse(source).body
        if isinstance(node, ast.FunctionDef)
    }


@pytest.mark.parametrize("module", PLATFORM_MODULES, ids=lambda path: path.name)
def test_platform_module_does_not_import_the_engine(module: Path) -> None:
    imported = imported_top_level_modules(module.read_text())

    assert "duckdb" not in imported


def test_scheduled_module_defines_no_one_off_function() -> None:
    defined = functions_defined(SCHEDULED_MODULE.read_text())

    assert "scheduled_run" in defined
    assert "one_off_run" not in defined


def test_one_off_module_defines_no_scheduled_function() -> None:
    defined = functions_defined(ONE_OFF_MODULE.read_text())

    assert "one_off_run" in defined
    assert "scheduled_run" not in defined


# Verifies d008 R26
def test_one_off_module_names_only_the_bronze_read_secret() -> None:
    used = names_used(ONE_OFF_MODULE.read_text())

    secrets = {name for name in used if name.endswith("_SECRET")}
    literals = {name for name in used if name.startswith("bikesharing-pipeline-")}
    assert secrets == {"BRONZE_READ_SECRET"}
    # The app's own name shares the Secrets' prefix but is no Secret.
    assert literals <= {
        "bikesharing-pipeline-bronze-read",
        "bikesharing-pipeline-one-off",
    }


# Verifies d008 R27
def test_one_off_module_names_no_deployment_and_no_scheduled_module() -> None:
    used = names_used(ONE_OFF_MODULE.read_text())

    assert "CLOUDFLARE_API_TOKEN" not in used
    assert "scheduled_config" not in used
    assert "modal_app" not in used


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
