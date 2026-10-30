---
status: Proposed
date: 2026-10-30
---

# Retention per layer

## Context and problem statement

Each medallion layer ([ADR-0018](0018-medallion-architecture.md)) grows with every capture pass, and storage is billed above R2's free quota ([ADR-0019](0019-own-lakehouse-on-cloudflare-r2.md)).

- Silver and gold are rebuilt from bronze ([d002/R13](../designs/d002-requirements.md#requirements)), so whatever is deleted from bronze can never be rebuilt.
- Bronze is the captured objects ([ADR-0020](0020-bronze-as-captured-objects.md)) and grows every month ([s010/F21](../spikes/s010-storage-table-format.md#4-findings)).
- The longest gold windows span 12 months, and one question covers changes since the earliest history archive loaded ([architecture.md](../architecture.md)).
- Gold is small and is what the public sees.
- Delta tables keep old file versions until vacuum removes them, and vacuum runs only when the pipeline runs it.
- The project runs within a small monthly budget ([d002/R4](../designs/d002-requirements.md#requirements)).

Without a retention rule per layer, either data that cannot be rebuilt is lost, or storage grows without bound in every layer.

## Considered Options

Each option is judged on data at risk, storage growth, the cost of rebuilding, and whether a rule change can be applied to older data.

### 1. Decreasing retention per layer

Bronze is kept indefinitely, silver keeps a rolling window that covers the longest gold window, gold is kept indefinitely, and Delta tables keep 7 days of history.

- Pros:
  - no data at risk: whatever is deleted is rebuilt from bronze;
  - silver's storage is bounded;
  - gold is recomputed from silver without re-parsing bronze.
- Cons:
  - the pipeline deletes old silver partitions and runs vacuum itself;
  - silver older than the window is rebuilt from bronze when needed.

### 2. Every layer kept indefinitely

No layer deletes data.

- Pros:
  - simpler: no silver partitions are deleted.
- Cons:
  - silver grows without bound alongside bronze, which brings the cost review earlier ([s010/F21](../spikes/s010-storage-table-format.md#4-findings), [s010/F23](../spikes/s010-storage-table-format.md#4-findings)).

### 3. Bronze in a rolling window

Bronze keeps the longest gold window plus a margin, and older objects are deleted.

- Pros:
  - bronze's storage is bounded.
- Cons:
  - a rule change can no longer be applied to older data;
  - changes since the earliest archive depend on what silver kept.

## Decision Outcome

**Chosen option:** 1. Decreasing retention per layer

Bronze is the only layer that cannot be rebuilt, so it is the only one whose retention puts data at risk; it is kept. Silver and gold are rebuildable, so their retention trades storage against rebuild cost: silver keeps what gold needs to be recomputed, and gold, small and public, is kept. This is the usual decreasing retention: bronze longest, silver shorter, gold by its use.

Why not the others:

- Every layer kept indefinitely: silver's growth adds to bronze's for no data it could not rebuild.
- Bronze in a rolling window: it deletes the only data that cannot be rebuilt.

**Scope:** How long each layer keeps its data. It does not cover how silver deletion and vacuum are implemented, which belongs to the pipeline design, or how bronze is protected (ADR-0023).

### Consequences

#### Positive

- **No data at risk:** only rebuildable data is deleted.
- **Bounded silver:** silver's storage stops growing once its window fills ([s010/F21](../spikes/s010-storage-table-format.md#4-findings)).
- **Works on R2:** vacuum with 7 days of history works on R2 ([s010/F18](../spikes/s010-storage-table-format.md#4-findings)).

#### Negative

- **Bronze grows without bound:** storage cost rises every month, and bronze's growth is what eventually triggers the review ([s010/F23](../spikes/s010-storage-table-format.md#4-findings)).
- **Maintenance in the pipeline:** the pipeline runs vacuum and deletes old silver partitions; delta-rs does not do either on its own.
- **Short history:** Delta time travel reaches back 7 days only.
- **Older silver costs a rebuild:** querying silver beyond its window means rebuilding it from bronze.

## More information

- Framing decisions: [s010/D5](../spikes/s010-storage-table-format.md#d5-bronze-is-kept-indefinitely-reviewed-only-above-a-cost-threshold), [s010/D6](../spikes/s010-storage-table-format.md#d6-silver-keeps-a-rolling-12-months-gold-is-kept-indefinitely-and-delta-keeps-7-days-of-history); outcomes in [s010 Decisions to record](../spikes/s010-storage-table-format.md#decisions-to-record).
