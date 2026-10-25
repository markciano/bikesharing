---
status: Proposed
date: 2026-10-24
---

# Data flows through bronze, silver and gold layers

## Context and problem statement

The project ingests data from 2 bike-sharing services, published in different GBFS versions, as one-minute snapshots, plus monthly archives of one operator. The guiding questions ([d002 › Guiding questions](../designs/d002-requirements.md#guiding-questions)) need data that the feeds do not publish directly: movements derived from consecutive snapshots, episodes, hourly and daily aggregates.

Two forces apply:

- The project is a portfolio piece: it should follow an industry-recognised layering an engineer can read at a glance.
- Every derived table must be rebuildable from what was captured (d002 R13).

Without a decision, each consumer would clean and reshape raw data its own way, and a rule change would mean finding every place that applied it.

## Considered Options

### 1. Three layers: bronze, silver, gold (medallion)

Bronze keeps data as captured, silver holds it cleaned and conformed to one model, gold holds tables modelled for the questions.

- Pros: cleaning and conforming happen once and are shared by every question; each layer rebuilds from the one before; widely recognised pattern.
- Cons: one more stored copy than two layers; more pipeline steps.

### 2. Two layers: raw and modelled

Question tables are built straight from raw data.

- Pros: fewer steps and less storage.
- Cons: cleaning and conforming are repeated in every question's model, or hidden in a shared step that is a silver layer in all but name.

## Decision Outcome

**Chosen option:** Three layers: bronze, silver, gold (medallion)

Rationale: it is the only option where cleaning and conforming to the common model happen once, which keeps the two operators comparable and makes a rule change a single rebuild from bronze.

- Bronze MUST hold data exactly as captured, as ADR-0006 sets, because every other layer is rebuilt from it.
- Silver MUST hold data cleaned, deduplicated and conformed to the common model (ADR-0008), with timestamps in UTC (ADR-0005), because every question needs the same clean base.
- Gold MUST hold tables modelled for the guiding questions (d002), because consumers need answers, not records.
- Each layer MUST be built only from the layer before it, because skipping a layer duplicates the rules it applies.
- Silver and gold MUST be rebuildable from bronze, because formulas and rules will change (d002 R13).
- Consumers such as the visualization SHOULD read only gold, because silver's grain and fields may change without notice to them.

Why not the others:

- Two layers: the conformance between operators would be either repeated per question or a silver layer without the name.

**Scope:** applies to all data the project ingests, real-time and archives. It does not decide where layers are stored, the table format, retention per layer, the engine, or the gold data model; those belong to T035, T036 and each slice's design.

### Consequences

#### Positive

- **Rebuild:** any rule change is applied by rebuilding from bronze, with no data lost.
- **Comparability:** both operators reach gold on one model.
- **Readability:** the layering is a recognised pattern for anyone reviewing the project.

#### Negative

- **Storage:** silver adds a stored copy; retention per layer (T035) must keep it within d002 R4.
- **Latency:** each layer adds a step between capture and gold, which counts against d002 R3.
