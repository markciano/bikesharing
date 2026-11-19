"""The package loads without Modal's SDK, which only the platform module imports.

Rule 5 of the package's structure (ADR-0046, Functional core and imperative
shell for the pipeline): the environment synced by default leaves out the
``platform`` dependency group, so ``modal`` is absent and the package must still
import.
"""

import importlib

import pytest


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
