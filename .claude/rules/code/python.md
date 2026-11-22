---
paths:
  - "pipeline/**/*.py"
  - "pipeline/pyproject.toml"
---

# Python code and testing rules

## Code comments

General comment rules are in `general.md`.

- Docstrings follow numpydoc (NumPy style) on every module, class and public function/method.
- Type hints are mandatory in signatures. For DataFrames, the Parameters and Returns sections list the required columns and their dtypes.

## Style

- `ruff format` formats, `ruff check` lints with its default rule set, and mypy checks types in its standard mode (not `strict`), configured in `pipeline/pyproject.toml`. A rule or a stricter mode is added only when a bug or a review finding shows it would have caught something (s016 › D2).
- A hook formats and fixes after every edit of a `.py` file and reports what remains, and `check-pipeline.sh` fails on it; never run them by hand, the hook output is the result.

## Structure

The package follows a functional core and an imperative shell ([ADR-0046](../../../docs/decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)); import-linter's contracts in `pipeline/pyproject.toml` enforce it.

- `bikesharing.core` holds pure decisions over values: no I/O, and no `duckdb`, `dbt` or HTTP client.
- `bikesharing.shell` does the I/O and the orchestration, and calls the core; the core never imports the shell.
- `pipeline/modal_image.py`, `pipeline/modal_app.py` and `pipeline/modal_one_off.py`, outside `src/`, are the only files that import `modal`, and none imports `duckdb`. The package and its configuration load without Modal's SDK, which sits in the `platform` dependency group.

## Testing

General principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (Python section).

- Tool: pytest; `uv run --directory pipeline pytest` runs every test, `uv run --directory pipeline pytest tests/<level>` one level; `bash pipeline/scripts/check-pipeline.sh` runs every check, from the project root.
- Line coverage (pytest-cov) is reported, never enforced with a threshold. The source is set in `[tool.coverage.run] source`, so the CI command cannot widen the report to the test files.
- Levels are folders under `pipeline/tests/`: `unit/` (mirrors `src/bikesharing/`) and `integration/`. There is no end-to-end level in the repository: the one-off run on Modal is the end-to-end check.
- Naming: files `test_<module>.py`; functions `test_<behaviour>_<condition>`.
- Shared fixtures in `conftest.py` (one in `pipeline/tests/`, plus one per level when needed), function-scoped by default.
