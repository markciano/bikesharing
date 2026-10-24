---
status: proposed
date: 2026-10-24
---

# Collectors decoupled by an output contract

## Context and problem statement

Raw source responses reach the platform through a collector, a component that fetches each feed on a schedule and stores the response. Today there is one collector; the tool it runs on is reassessed with the storage decision (T035), so its platform and language can change.

A collector only fetches and stores bytes: it holds no logic that other components could reuse. The pipeline reads what collectors store, and needs to read it the same way whichever collector wrote it, so that changing a collector does not change the pipeline.

The forces are: a collector can change tool or language; the pipeline must not depend on which collector ran; the stored responses must stay reprocessable as received (ADR-0006); and stored time is UTC (ADR-0005).

## Considered Options

### 1. An output contract that every collector meets

Every collector writes its files under the same key layout, timestamp and payload rules, in a landing zone the pipeline reads. Pros: the files are the only interface, so any tool or language can meet it; a contract test checks each collector. Cons: the naming code is written once per collector language.

### 2. Shared logic behind platform adapters

The collector's logic is written once and each platform calls it through a thin adapter. Pros: the naming code is written once. Cons: it binds every collector to the language of the shared logic, and a collector has almost no logic to share.

## Decision Outcome

**Chosen option:** 1. An output contract that every collector meets.

Rationale: it is the only option that lets a collector change tool or language without touching the pipeline, which the Context requires; the shared logic of option 2 is too small to justify binding every collector to one language.

Rules:

- Every collector MUST write each response under the key `raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`, because the pipeline finds files by key alone.
- The timestamp MUST be the capture time in UTC, one value per pass for both the key and the date folder, because files of one pass must sort and group together (ADR-0005).
- The payload MUST be the gzip bytes served by the origin, unchanged; no collector decompresses or recompresses, because the raw layer keeps the response as received (ADR-0006).
- Decompression MUST happen in the first processing step, because it is the first component that needs the content.

**Scope:** every collector that writes raw responses, whatever its tool or language. It does not set where the landing zone lives (T035) nor how processing is structured.

### Consequences

#### Positive

- **Interchangeable collectors:** the pipeline cannot tell which collector produced a file.
- **Reprocessing:** every downstream step can be rebuilt from the raw files, within the retention the storage decision sets.

#### Negative

- **Naming written per language:** a new collector reimplements the key rules; the contract tests (ADR-0015) check it against shared vectors instead of sharing code.
- **Fixed key layout:** changing the layout means migrating stored files or reading two layouts.
