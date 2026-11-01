---
status: Proposed
date: 2026-11-01
---

# Budget shares per component

## Context and problem statement

The running cost limit of €10 per month covers the whole solution ([d002/R4](../designs/d002-requirements.md#requirements)), and each component is chosen separately. Without a limit per component, each one could take a choice that looks affordable alone and breaks the total.

- Capture costs nothing within free tiers ([ADR-0011](0011-cloudflare-workers-r2-for-realtime-capture.md)).
- Storage has an estimated worst month of €0.83 up to month 12 ([s010/Exit criteria](../spikes/s010-storage-table-format.md#exit-criteria)).
- The engine is free ([ADR-0024](0024-duckdb-as-processing-engine.md)), so the pipeline's cost is where it runs, which is not chosen yet.
- The pipeline is the only component that may need an always-on machine.
- The cost of visualization is not known yet.
- R2 bills in USD, and its cost model is estimated, not measured.

## Considered Options

Both options keep capture at €0 and storage at €2. They differ in how they split the remaining €8 between pipeline, visualization and a reserve.

### 1. Pipeline €4, visualization €2, reserve €2

- Pros:
  - the pipeline gets the largest share;
  - a reserve absorbs the exchange rate and deviations.
- Cons:
  - the pipeline gets €2 less to pay for where it runs.

### 2. Pipeline €6, visualization €2, no reserve

- Pros:
  - more room for where the pipeline runs.
- Cons:
  - any deviation breaks the limit.

## Decision Outcome

**Chosen option:** 1. Pipeline €4, visualization €2, reserve €2.

| Component | Share per month |
|---|---|
| Capture | €0 |
| Storage (R2) | €2 |
| Pipeline (engine and execution) | €4 |
| Visualization | €2 |
| Reserve | €2 |

The pipeline gets the largest share because it is the only component that may need an always-on machine. The reserve is kept because the bill depends on an exchange rate and on an estimated cost model.

Why not the other: with no reserve, any deviation breaks the limit.

**Scope:** The monthly limit each component is sized against. It does not choose where the pipeline runs (T037) or the visualization (T038), and it does not replace the cost alert.

### Consequences

#### Positive

- **Choices are sized against a figure:** each later component has a limit of its own, and the total stays within the requirement.
- **Room for deviations:** the exchange rate or an estimate that falls short does not break the limit at once.

#### Negative

- **Less room for the pipeline:** an execution target above its share has to draw on the reserve.
- **Shares rest on estimates:** the pipeline and visualization shares are set before their prices are known. If real prices exceed a share, the component's decision reopens the split against the reserve.

## More information

- Framing decision: [s011/D2](../spikes/s011-engine-pipeline-language.md#d2-budget-shares); outcome in [s011 Decisions to record](../spikes/s011-engine-pipeline-language.md#22-decisions-to-record).
