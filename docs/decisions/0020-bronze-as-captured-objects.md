---
status: Proposed
date: 2026-10-30
---

# Bronze as captured objects

## Context and problem statement

Bronze is the first medallion layer ([ADR-0018](0018-medallion-architecture.md)), and silver and gold are rebuilt from it ([d002/R13](../designs/d002-requirements.md#requirements)).

- Capture writes each source response to R2 as a `json.gz` object under time-ordered keys ([ADR-0011](0011-cloudflare-workers-r2-for-realtime-capture.md), [ADR-0012](0012-collectors-decoupled-by-output-contract.md)).
- The Bicing history archives arrive as `.7z` files ([d002/R5](../designs/d002-requirements.md#requirements)).
- Raw data keeps the source's bytes untouched ([ADR-0006](0006-raw-layer-keeps-source-responses-untouched.md)).
- Bronze is the largest layer in storage ([s010/F21](../spikes/s010-storage-table-format.md#4-findings)).
- Capture already logs each pass with its feed, time and HTTP status.

The open question is whether bronze is those objects themselves, or a table loaded from them.

## Considered Options

Each option is judged on storage, fidelity to the source, SQL over raw data, how the pipeline knows what it has processed, where capture metadata lives, and the number of pipeline steps.

### 1. Objects as captured

Bronze is the captured `json.gz` objects and the history archives as downloaded, stored once; no table is built over them.

- Pros:
  - one copy of raw data, with the source's bytes;
  - one pipeline step: raw to silver.
- Cons:
  - SQL over raw is slower: engines such as DuckDB read the `json.gz` objects directly from R2;
  - the pipeline tracks what it has processed itself.

### 2. Landing objects plus a bronze table

Captured objects land in a landing zone and are loaded into a bronze table (e.g. the Databricks Auto Loader pattern).

- Pros:
  - fast SQL over raw;
  - the table records what has been loaded, and capture metadata becomes columns.
- Cons:
  - two copies of raw data, each with its own retention;
  - the payload is kept, but in another container than the source's bytes;
  - one more pipeline step: raw to bronze to silver.

## Decision Outcome

**Chosen option:** 1. Objects as captured

The decision is reversible: the objects are kept, so a bronze table can be built from them later with no loss. For a reversible decision the simpler option is taken and complexity is deferred until needed (YAGNI). Option 1 avoids a second copy of the largest layer and keeps the source's bytes as ADR-0006 requires; what it gives up, fast SQL over raw and built-in load tracking, has cheap substitutes.

Why not the others:

- Landing objects plus a bronze table: it pays a second copy and an extra step from day one for benefits that have cheap substitutes.

**Scope:** The form of bronze, for captured feeds and history archives alike. It does not cover retention (ADR-0021), the bucket and its lock (ADR-0023), or the archives' prefix and load procedure, which belong to the archive-load design.

### Consequences

#### Positive

- **One copy:** raw data is stored once, as the source sent it.
- **Shorter pipeline:** one step from raw to silver.
- **Reversible:** a bronze table can be built from the objects later, with no loss.

#### Negative

- **Slower SQL over raw:** queries read the `json.gz` objects directly instead of a table.
- **Own load tracking:** the pipeline tracks what it has processed itself (e.g. a watermark in silver over the time-ordered keys).
- **Metadata outside a table:** capture metadata (feed, time, HTTP status) stays in capture's own log, not in table columns.

## More information

- Framing decision: [s010/D3](../spikes/s010-storage-table-format.md#d3-bronze-is-the-captured-jsongz-objects-as-they-are); outcome in [s010 Decisions to record](../spikes/s010-storage-table-format.md#decisions-to-record).
