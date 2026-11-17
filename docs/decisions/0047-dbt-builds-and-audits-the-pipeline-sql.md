---
status: Accepted
date: 2026-11-17
---

# dbt builds and audits the pipeline's SQL

## Context and problem statement

The pipeline's transformations are SQL models directed by Python ([ADR-0025](0025-sql-models-directed-by-python.md)), which left open where dbt applies. The Python code is a functional core that plans and decides, and an imperative shell that performs all I/O ([ADR-0046](0046-functional-core-imperative-shell-for-the-pipeline.md)). Around the SQL, the pipeline needs:

- models run in dependency order, for one batch at a time, with the batch's window in the bronze file paths the models read; the core plans the batches ([ADR-0045](0045-catch-up-in-bounded-batches.md));
- the column schema of each table checked, and the runtime rules run with their severity, before anything is written ([ADR-0042](0042-data-quality-classes-and-severity.md), Write-Audit-Publish);
- results written to Delta tables on R2 with MERGE or partition overwrite ([ADR-0022](0022-delta-lake-for-silver-and-gold.md));
- each model's logic tested on its own, with no real data;
- table-level lineage in the model's documentation ([ADR-0043](0043-lineage-at-four-levels.md));
- every event of a run in the log convention shared by all components ([ADR-0036](0036-log-convention-across-components.md)).

Without a tool, the pipeline builds the ordered runner, the schema checks, the rules' runner, the test scaffolding and the lineage by hand. The project follows the practice of a company data team, where a SQL transformation framework is the usual answer to these needs.

## Considered Options

### 1. dbt builds and audits, the shell publishes

dbt runs every model and runtime rule for one batch in a scratch database discarded at the end of the run; the shell invokes it with the batch's window and, only if the audit passes, writes the result to Delta.

- Pros:
  - dbt covers the runner, the window in file paths, the schema checks as model contracts, the rules as data tests with their severity, unit tests and table-level lineage;
  - audit happens before publishing, and all writes, credentials and retries stay in the shell;
  - models stay `SELECT` statements, so the choice can be undone.
- Cons:
  - one more tool, with its own start-up time and its own events to translate into the log convention;
  - lineage stops at the hand-off to Delta;
  - dbt does not report the rows a model builds with this engine, so the shell counts them.

### 2. dbt writes Delta itself

dbt writes the Delta tables through Python models or a custom materialization.

- Pros:
  - one graph from bronze to the published tables.
- Cons:
  - it writes to R2 while the batch is built, before its tests run;
  - model contracts do not apply to Python models;
  - writes, credentials and retries move inside dbt, out of the shell.

### 3. No dbt

Python runs the SQL models in order, as ADR-0025 states, with a runner of its own for the rules.

- Pros:
  - the fewest moving parts.
- Cons:
  - every piece that dbt covers is built and maintained by hand.

### 4. DuckLake instead of Delta

The engine's own table format, which dbt writes natively with MERGE.

- Pros:
  - one lineage graph, and incremental models managed by dbt.
- Cons:
  - it reopens ADR-0022 and adds a metadata database to run;
  - it still neither audits before publishing nor bounds batches in bytes.

## Decision Outcome

**Chosen option:** 1. dbt builds and audits, the shell publishes

Rationale: it is the only option that covers what the Context needs while keeping both Write-Audit-Publish and the split of ADR-0046. dbt writes to the scratch database and audits it; the shell publishes. Within ADR-0046:

- The core plans each batch and turns dbt's results into a verdict with each rule's severity.
- The shell invokes dbt through its programmatic entry point, passes the batch's window as variables, reads each model's and test's result as values, and hands the audited tables to the Delta writer as Arrow. dbt is the runner of rule 8: each runtime rule is a dbt data test named after its catalog ID.
- A callback registered by the shell receives dbt's events as they happen and forwards a model's start and end, a test's result and errors to the standard logging, under the pipeline's own event names and with dbt's invocation ID as a field. dbt writes no log of its own, and a run killed inside dbt still logs the model it had reached.
- SQL models are tested with dbt unit tests, and the Python code with pytest.

Why not the others:

- dbt writes Delta itself: it publishes before it audits.
- No dbt: it builds by hand what a standard tool already covers, for no gain in control.
- DuckLake: it changes the table format to gain features that ADR-0045 already covers in its own way.

**Scope:** the pipeline's SQL models, runtime rules and their tests. It does not cover how batches are planned (ADR-0045), how Delta is written (ADR-0022), capture, or the quality catalog's content.

### Consequences

#### Positive

- **Less code to build:** about 70 lines of glue replace the runner, the schema checks, the rules' runner and the test scaffolding.
- **Audit before publish:** a batch that fails a rule of severity error writes nothing to R2.
- **Standard practice:** models, contracts, tests and lineage follow a dbt project's conventions.
- **Fast SQL tests:** each model's logic is tested on hand-written rows, in seconds.

#### Negative

- **A second test tool:** dbt's tests have a time budget of their own, longer than pytest's, since dbt's start-up alone exceeds it.
- **Lineage seam:** dbt's graph ends at the scratch tables; the tables on R2 join it only as documentation.
- **Coupling to the adapter:** the shell reads the scratch tables with the adapter's connection settings, and dbt's result objects are not a stable contract, so an upgrade is checked against the glue.
- **A release line to follow:** the newer dbt line does not yet cover what this decision needs, and the current one has an end of support.

## More information

- Release line: `dbt-core` 1.12 with the `dbt-duckdb` adapter, supported until 2027-07-15; T070 checks the move to dbt v2 three months before that date. The newer line's DuckDB adapter is in beta and lacks extensions, callbacks and a stable Python API ([s017 › D2](../spikes/s017-dbt-in-the-pipeline.md#d2-dbt-v1-dbt-core-112-with-dbt-duckdb)).
- Decision at framing, its fit-gap and the evidence: [s017 › D1, D3, D4](../spikes/s017-dbt-in-the-pipeline.md#12-decided-at-framing), [Conclusion](../spikes/s017-dbt-in-the-pipeline.md#5-conclusion).
- Programmatic invocations: <https://docs.getdbt.com/reference/programmatic-invocations>
