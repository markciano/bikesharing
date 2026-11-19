#!/usr/bin/env bash
# The pipeline's checks, fastest first, stopping at the first failure: ruff, mypy,
# import-linter, SQLFluff, dbt's parse and unit tests, and pytest. It is the check of
# every code step and the command of the pipeline's CI job (d008, Tests and CI).
# Runs from any folder.
set -euo pipefail

cd "$(dirname "$0")/.."

# dbt's profile reads the scratch database's paths and memory limit from these
# variables; a throwaway folder stands in for the run's work folder.
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export BIKESHARING_ALLOWED_DIRECTORY="$work"
export BIKESHARING_SCRATCH_DATABASE="$work/scratch.duckdb"
export BIKESHARING_TEMP_DIRECTORY="$work/spill"
export BIKESHARING_MEMORY_LIMIT="1GiB"

dbt_dirs=(--project-dir dbt --profiles-dir dbt)

# An exact sync from the lockfile, as in CI: `uv run` alone would keep packages a
# previous `--group platform` run installed, such as Modal's SDK, which the package
# must load without.
echo "== uv sync"
uv sync --locked

echo "== ruff format"
uv run ruff format --check .
echo "== ruff check"
uv run ruff check .
echo "== mypy"
uv run mypy src tests
echo "== import-linter"
uv run lint-imports
echo "== sqlfluff"
uv run sqlfluff lint dbt
echo "== dbt parse"
uv run dbt parse "${dbt_dirs[@]}"
# Unit tests need their upstream relations, which dbt builds with no rows.
echo "== dbt run --empty"
uv run dbt run --empty "${dbt_dirs[@]}"
echo "== dbt unit tests"
uv run dbt test --select "test_type:unit" "${dbt_dirs[@]}"
echo "== pytest"
uv run pytest --cov
