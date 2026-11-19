---
paths:
  - "pipeline/dbt/**/*.sql"
  - "pipeline/dbt/**/*.yml"
---

# SQL and dbt rules

## Code comments

General comment rules are in `general.md`.

- Every model, source and column is documented with its `description` in its YAML file, dbt's standard format, from which dbt generates its documentation.
- Inline comments in SQL use `--`, for the *why* only.

## Style

- SQL follows [dbt Labs' SQL style guide](https://docs.getdbt.com/best-practices/how-we-style/2-how-we-style-our-sql).
- SQLFluff checks it with the `duckdb` dialect, its default rules and the dbt templater, configured in `[tool.sqlfluff]` of `pipeline/pyproject.toml`. A hook fixes and reports after every edit of a `.sql` file, and `check-pipeline.sh` fails on what remains; never run it by hand, the hook output is the result.

## Models

- One model per file, named after the model. Staging models are named `stg_<system>__<entity>`, as dbt Labs' project structure guide sets.
- Sources are read only through `source()`, declared in `models/sources.yml`; models only through `ref()`. No relation name is written by hand.
- Every model the shell or a consumer reads has an enforced model contract, with every column's `data_type`.

## Testing

General principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (SQL in dbt section).

- Data tests: each one's `name` is its rule's ID in [data-quality.md](../../../docs/data-quality.md) (e.g. `DQR13`).
- Unit tests: dbt unit tests in the model's YAML file, on hand-written rows that replace its inputs, one or more per model's logic. dbt builds the upstream relations first with `dbt run --empty`.
