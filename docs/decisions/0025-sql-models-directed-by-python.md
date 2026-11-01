---
status: Proposed
date: 2026-11-01
---

# SQL models directed by Python

## Context and problem statement

The engine executes the transformations, and the table format library writes their results ([ADR-0024](0024-duckdb-as-processing-engine.md), [ADR-0022](0022-delta-lake-for-silver-and-gold.md)). The pipeline needs a host language for that coordination and a form in which to write the transformations.

- Python is part of what the portfolio shows ([d002/Context](../designs/d002-requirements.md#context)), and MERGE depends on a library whose bindings are Python and Rust.
- Transformations flatten nested input, compare each reading with the previous one, follow episodes across batches, detect gaps against a time grid and aggregate in local time ([d002/Q2–Q7, R12](../designs/d002-requirements.md#guiding-questions)).
- The same logic serves the incremental batch and a rebuild from bronze, changing only the data range ([d002/R11, R13](../designs/d002-requirements.md#requirements)).
- Each transformation is tested before it is written, locally and with no infrastructure ([testing strategy](../testing-strategy.md)).
- Data quality rules are added later at any layer, without rewriting transformations ([task T042](../tasks.md)).
- The project follows the practice of a company data team. Its owner has very strong SQL and basic Python.

## Considered Options

Every option passes two hard cuts first: it runs on the chosen engine and hands its result to the write library through Arrow, and it is open source with no per-use cost and stable, maintained releases. Each is then scored on team practice, workload fit, testing, reuse, path to dbt, data quality, learning curve and portability to the fallback engine. dbt is not an option: it manages SQL or Python rather than being a form of writing them.

### 1. SQL

Models in `.sql` files that Python runs in order.

- Pros:
  - the common standard in data teams;
  - covers every transformation with the language's own constructs;
  - a `SELECT` becomes a dbt model with minor changes.
- Cons:
  - the data range is a parameter for values, but not confirmed for file paths;
  - storing data quality results needs a small runner.

### 2. Mixed

SQL by default, Python only where SQL falls short.

- Pros:
  - the same as SQL wherever SQL is used;
  - room for logic that SQL cannot express.
- Cons:
  - the Python parts become Python models in dbt;
  - relies on basic Python skills.

### 3. DuckDB's Python API

Chained operations on the engine's relations.

- Pros:
  - the data range is a plain function parameter.
- Cons:
  - no usage data in data teams;
  - window functions and join conditions still need SQL strings;
  - no path to the fallback engine.

### 4. Ibis

A Python library that writes transformations as DataFrames and translates them for the engine.

- Pros:
  - native in-memory tables for testing;
  - the data range is a plain function parameter.
- Cons:
  - fails the first hard cut: no release supports the engine's current major version;
  - a community dbt integration of unconfirmed status.

## Decision Outcome

**Chosen option:** 1. SQL, in models directed by Python.

Python hosts the pipeline, since the portfolio and the write library both call for it; it runs the models in order, prepares inputs the engine cannot read directly and hands results to the write library. SQL wins as the form of the transformations because it expresses every one of them directly, it is the practice of data teams and it matches the owner's skills. It scores 9.1 out of 10, against 8.7 for Mixed and 6.0 for the Python API.

If a transformation cannot be written in SQL, only that step goes to Python, with the reason documented.

Why not the others:

- Mixed: no transformation was found that SQL does not cover, and without one Mixed is the same as SQL.
- DuckDB's Python API: it still needs SQL strings for the hardest operations, and it is the furthest from team practice and the owner's skills.
- Ibis: it fails a hard cut, and even if fixed it scores 7.2.

**Scope:** The host language and the form of the transformations. It does not cover where dbt applies or how tables are written and committed (T040), or where data quality rules live and their format (T042).

### Consequences

#### Positive

- **Open path to dbt:** existing models become dbt models with minor changes, wherever dbt turns out to apply.
- **Data quality stays separate:** a rule is one more `SELECT` over any result, with no change to the transformations.

#### Negative

- **Testing needs some scaffolding:** models are tested on an in-memory database with `pytest`, with no official guide.
- **Parameters are not fully confirmed:** if they do not work in file paths, the data range needs more care. The choice holds either way, since SQL and Mixed lose the same.
- **Only partly portable:** a move to the fallback engine rewrites part of the SQL, since its dialect differs on some operations.

## More information

- Framing decision, with the matrix, its scores and the inputs for T040: [s011/D3](../spikes/s011-engine-pipeline-language.md#d3-pipeline-language); outcome in [s011 Decisions to record](../spikes/s011-engine-pipeline-language.md#22-decisions-to-record).
- Ibis on the first hard cut: `to_pyarrow_batches` fails on DuckDB 2.0 ([issue 12196](https://github.com/ibis-project/ibis/issues/12196), open on 2026-11-01).
