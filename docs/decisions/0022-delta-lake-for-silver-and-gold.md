---
status: Proposed
date: 2026-10-30
---

# Delta Lake for silver and gold

## Context and problem statement

Silver and gold are stored in R2 as open-format files ([ADR-0019](0019-own-lakehouse-on-cloudflare-r2.md)), and the files need a table format on top.

- Silver deduplicates observations and both layers are rebuilt from bronze ([d002/R13](../designs/d002-requirements.md#requirements)), which needs MERGE and atomic commits.
- More than one writer can commit to the same table at once, so commits must stay safe under concurrency.
- The pipeline runs in Python on a single node, with no JVM or cluster.
- The project runs within a small monthly budget ([d002/R4](../designs/d002-requirements.md#requirements)), so no paid service may break it.
- Atomic commits on an object store depend on what the store guarantees for concurrent writes.

## Considered Options

Every option passes a hard cut first: reads and writes from Python with no JVM or cluster, and no paid service that breaks the budget. Each is then scored on portfolio value, Python single-node maturity, fit with R2, support in single-node engines, operational simplicity and learning value.

### 1. Delta Lake

Tables keep a transaction log next to their data files, and commits are atomic writes to that log.

- Pros:
  - MERGE, optimize and vacuum are stable in Python;
  - commits are safe on R2 with the bucket alone;
  - only the bucket and its credentials to operate.
- Cons:
  - backed by fewer major vendors than Iceberg;

### 2. Apache Iceberg

Tables keep snapshots and manifests, and a catalog records each table's current state.

- Pros:
  - the standard backed by the most major vendors;
  - the richest concepts to learn: snapshots, manifests, catalog.
- Cons:
  - commits need a catalog: a managed one, paid above its quota, or a SQLite one documented for tests only;
  - in Python, compaction is still planned and the library is below 1.0.

### 3. Hive-partitioned Parquet

Plain Parquet files in partition folders, with no table format.

- Pros:
  - native in every engine;
  - only the bucket to operate.
- Cons:
  - no MERGE and no atomic commits.

## Decision Outcome

**Chosen option:** 1. Delta Lake

Delta wins on maturity and operational simplicity: it gives the MERGE and atomic commits that silver and rebuilds need, and on R2 it commits safely with the bucket alone. R2 enforces atomic put-if-absent under a race ([s010/F19](../spikes/s010-storage-table-format.md#4-findings)), which delta-rs relies on for safe commits with no external lock ([s010/F1](../spikes/s010-storage-table-format.md#4-findings)); write, MERGE and concurrent commits pass on R2 ([s010/F2](../spikes/s010-storage-table-format.md#4-findings)).

Why not the others:

- Apache Iceberg: its dependence on a catalog costs it maturity, fit with R2 and simplicity, more than its portfolio value gains.
- Hive-partitioned Parquet: without MERGE or atomic commits it cannot deduplicate silver or rebuild a table safely.

**Scope:** The table format of silver and gold. It does not cover bronze ([ADR-0020](0020-bronze-as-captured-objects.md)), retention and table history ([ADR-0021](0021-retention-per-layer.md)), the engine, or how the pipeline handles commit conflicts, which belongs to the pipeline design.

### Consequences

#### Positive

- **Safe concurrent commits:** a stale MERGE fails with a commit conflict and a stale append is retried, with no duplicate or lost row and no extra service ([s010/F3](../spikes/s010-storage-table-format.md#4-findings), [s010/F15](../spikes/s010-storage-table-format.md#4-findings)).
- **Maintenance and readers work on R2:** optimize, vacuum, Polars and DuckDB work ([s010/F18](../spikes/s010-storage-table-format.md#4-findings)).

#### Negative

- **Conflicts are not auto-resolved:** a MERGE that conflicts with a concurrent commit fails, and the pipeline retries it ([s010/P1](../spikes/s010-storage-table-format.md#production-inputs)).
- **Races on creation and schema changes:** tables are created before any concurrent writer, and concurrent writers do not merge schemas ([s010/P2](../spikes/s010-storage-table-format.md#production-inputs)).
- **Limited DuckDB support:** DuckDB writes INSERT only, and its reads on R2 were not counted ([s010/F6](../spikes/s010-storage-table-format.md#4-findings)).
- **Less portfolio value than Iceberg:** fewer major vendors back Delta.

## More information

- Framing decision, with the decision matrix and its scores: [s010/D4](../spikes/s010-storage-table-format.md#d4-delta-lake-is-the-table-format-for-silver-and-gold-subject-to-the-probe-on-r2); outcome in [s010 Decisions to record](../spikes/s010-storage-table-format.md#decisions-to-record).
