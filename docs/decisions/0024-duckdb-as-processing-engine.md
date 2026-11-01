---
status: Proposed
date: 2026-11-01
---

# DuckDB as the processing engine

## Context and problem statement

The pipeline turns bronze objects into the silver and gold Delta tables on R2 ([ADR-0019](0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0022](0022-delta-lake-for-silver-and-gold.md)), and it needs an engine to do that work.

- The most demanding input is nested `json.gz` read from R2, flattened and compared with each station's previous reading, including episodes that span two batches ([d002/Q2, Q3](../designs/d002-requirements.md#guiding-questions)).
- Queries must read Delta tables filtered by partition without downloading them whole, since R2 bills operations ([d002/R4, R11](../designs/d002-requirements.md#requirements)).
- Silver and gold need MERGE and rebuilds from bronze ([d002/R13](../designs/d002-requirements.md#requirements)).
- The machine that runs the pipeline is not chosen and must fit the budget, so the engine cannot assume that the data fits in memory.
- The solution runs on a single node, within a small monthly budget, and it is a portfolio project.

## Considered Options

Every option passes three hard cuts first: it runs on a single node, it reads and writes Delta on R2 by itself or by handing data to `deltalake`, and it is open source with no per-use cost and stable releases. Each is then scored on portfolio value, workload fit, Delta read on R2, maturity, operational simplicity, memory behaviour, dbt fit and learning value.

### 1. DuckDB

An in-process SQL engine with vectorized execution.

- Pros:
  - reads nested `json.gz` from R2, with window functions and as-of joins;
  - reads Delta natively, with partition and file statistics pruning;
  - most operations spill to disk;
  - a maintained dbt adapter.
- Cons:
  - no Delta MERGE, so it hands MERGE to `deltalake`;
  - the dbt adapter needs custom code to write Delta.

### 2. Polars

An in-process DataFrame library with lazy evaluation.

- Pros:
  - window functions and as-of joins;
  - spills to disk by default.
- Cons:
  - reading the nested files likely needs custom code;
  - hands MERGE to `deltalake`, and whether joins spill is not confirmed;
  - its dbt adapter is in Beta, with one maintainer.

### 3. clickhouse-local

The ClickHouse engine as a separate binary, with no server.

- Pros:
  - detects gzip on S3-compatible stores, with as-of joins;
  - a long-standing, stable engine.
- Cons:
  - called as a subprocess;
  - spilling is opt-in per operator, and hands MERGE to `deltalake`;
  - its dbt adapter needs a server and does not mention Delta.

### 4. pandas

The standard in-memory DataFrame library.

- Pros:
  - widely known and stable for years.
- Cons:
  - eager and in memory only;
  - depends on `deltalake` for every Delta read and write;
  - no dbt adapter.

### 5. Apache DataFusion

An in-process query engine and framework.

- Pros:
  - in-process, with logical and physical plans to learn from.
- Cons:
  - no as-of join in a release, and windows buffer in memory;
  - absent from the market survey read, and its dbt adapter is abandoned.

## Decision Outcome

**Chosen option:** 1. DuckDB, with Polars as the fallback.

DuckDB wins on the two criteria that come directly from the workload: it reads and flattens the nested input from R2 with window functions and as-of joins, and it reads Delta natively with pruning. It scores 8.1 out of 10, against 6.8 for Polars. MERGE does not separate the options, since all of them hand it to `deltalake`; DuckDB exports Arrow tables, which `deltalake` accepts.

Why not the others:

- Polars: reading the nested input likely needs custom code, and it has no solid dbt adapter.
- clickhouse-local: a separate binary and weak dbt fit, with no gain on the workload.
- pandas: in-memory only, which does not suit the volume.
- Apache DataFusion: it lacks as-of joins in a release and has the lowest score.

**Scope:** The single-node engine that runs the transformations. It does not cover the form in which they are written, where the pipeline runs (T037), or how tables are written and committed (T040).

### Consequences

#### Positive

- **Simple to run and test:** an in-process library, installed with the dependencies and testable locally with no infrastructure.
- **Cheap to reverse:** Delta is an open format, so a later change of engine migrates no data; only the transformations are rewritten.

#### Negative

- **Two libraries on the write path:** data crosses from the engine to `deltalake` through Arrow, which can surface type mismatches to fix in the query.
- **Not exercised on real volumes:** the hand-off and the memory use rest on documentation until the pipeline first runs on real data. If either fails beyond repair, the pipeline moves to Polars.
- **Reads on R2 are not counted:** they are measured in production; a heavy read pattern at a high commit cadence could exceed the free quota.
- **Portfolio value is a judgement:** no job-ad data exists per engine, and scoring Polars 5 and DuckDB 1 on that criterion alone reverses the result.

## More information

- Framing decision, with the matrix, its scores, what would change the engine and the inputs for T040: [s011/D1](../spikes/s011-engine-pipeline-language.md#d1-processing-engine); outcome in [s011 Decisions to record](../spikes/s011-engine-pipeline-language.md#22-decisions-to-record).
