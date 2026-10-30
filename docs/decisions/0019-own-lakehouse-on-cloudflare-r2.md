---
status: Proposed
date: 2026-10-30
---

# Own lakehouse on Cloudflare R2

## Context and problem statement

ADR-0018 sets three medallion layers. Bronze already exists: capture writes the source responses to Cloudflare R2 (ADR-0011). Silver and gold have no storage yet, and where they live constrains which engines can process them (T036) and what the project pays.

- The project runs within a small monthly budget ([d002/R4](../designs/d002-requirements.md#requirements)).
- TODO(T036): The processing engine is not chosen yet.
- Silver deduplication and rebuilds from bronze ([d002/R13](../designs/d002-requirements.md#requirements)) need atomic table updates, which depend on what the store guarantees under concurrent writes.
- Bronze cannot be rebuilt, so it needs protection against delete and overwrite.
- Object stores bill storage and operations, and many also bill egress.

## Considered Options

Each option is judged on cost within the budget, independence from any engine, whether bronze has to move, and the guarantees the store gives (atomic conditional writes, protection against delete).

### 1. Own lakehouse on Cloudflare R2

Every layer is stored as open-format files in R2, and compute runs separately.

- Pros:
  - bronze is already there; R2 charges no egress;
  - it enforces atomic put-if-absent and offers a bucket lock.
- Cons:
  - storage and operations are billed above the free quotas;
  - storage depends on one vendor.

### 2. Silver and gold in a managed analytics platform

Bronze stays in R2; silver and gold are loaded into a warehouse that stores and queries them.

- Pros:
  - storage, engine and table management come as one service.
- Cons:
  - storage is tied to that platform's engine and free quotas.

### 3. Own lakehouse on another object store

The same pattern on another S3-compatible store (e.g. Backblaze B2).

- Pros:
  - the same openness as option 1.
- Cons:
  - bronze moves or is split across two stores.

## Decision Outcome

**Chosen option:** 1. Own lakehouse on Cloudflare R2

R2 meets every force in the Context from one service. Bronze stays where capture writes it. No egress fee keeps the engine choice open. R2 enforces atomic put-if-absent under a race ([s010/F19](../spikes/s010-storage-table-format.md#4-findings)), which delta-rs relies on for safe commits with no external lock ([s010/F1](../spikes/s010-storage-table-format.md#4-findings)), and its bucket lock blocks overwrite and delete of bronze ([s010/F19](../spikes/s010-storage-table-format.md#4-findings)). With the pipeline run on demand, the mode the spike judged, the monthly bill stays within the budget over the 12 months modelled ([s010/F20](../spikes/s010-storage-table-format.md#4-findings)).

Why not the others:

- Managed analytics platform: it fixes the engine.
- Another object store: it moves or splits bronze, and no constraint argues against R2.

**Scope:** Where each medallion layer is stored. It does not cover the engine (T036), how gold is served (T038), capture's runtime (ADR-0011, which holds and which this ADR extends to every layer), the table format (ADR-0022), retention (ADR-0021), or buckets and access (ADR-0023).

### Consequences

#### Positive

- **Engine anywhere:** R2 charges no egress, so the engine can run anywhere without paying to read the data.
- **Bronze in place:** capture keeps its current destination.
- **Safe commits and protected bronze:** the store gives what the table format and bronze need, with no extra service ([s010/F1](../spikes/s010-storage-table-format.md#4-findings), [s010/F19](../spikes/s010-storage-table-format.md#4-findings)).
- **Measurable cost:** R2 reports operations per bucket through the GraphQL Analytics API, filtered by exact UTC windows; its totals matched an independent count within 0.02% ([s010/F14](../spikes/s010-storage-table-format.md#4-findings)), so the cost can be measured and recalibrated.
- **Within budget:** with the pipeline run on demand, the monthly bill stays within the budget ([s010/F20](../spikes/s010-storage-table-format.md#4-findings)).

#### Negative

- **Commit frequency counts:** each pipeline commit adds R2 operations, so how often the pipeline commits weighs on cost and is set with that in view ([s010/F20](../spikes/s010-storage-table-format.md#4-findings), [s010/P5](../spikes/s010-storage-table-format.md#production-inputs)).
- **Dashboard is not exact:** the Cloudflare dashboard's operation figures are not exact, so exact counts come from the API ([s010/#36](../spikes/s010-storage-table-format.md#decision-log)).
- **One vendor:** storage, capture and cost metrics all depend on Cloudflare.
- **Separate compute:** the engine is one more component to choose and run (T036).

## More information

- Framing decisions: [s010/D1](../spikes/s010-storage-table-format.md#d1-own-lakehouse-on-object-storage), [s010/D2](../spikes/s010-storage-table-format.md#d2-cloudflare-r2-is-the-object-store-for-every-layer-subject-to-the-volume-and-operations-calculation); outcomes in [s010 Decisions to record](../spikes/s010-storage-table-format.md#decisions-to-record).
