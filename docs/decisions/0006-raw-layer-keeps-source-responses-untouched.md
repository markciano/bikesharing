---
status: accepted
date: 2026-10-03
---

# The raw layer keeps source responses untouched

## Context and Problem Statement

Parsing at ingestion fixes modelling choices (fields, types) before the data is understood; mistakes cannot be undone.

What should the first storage layer keep?

## Considered Options

* Each source response exactly as received (compressed), plus ingestion metadata stored separately
* Parse into tables at ingestion time

## Decision Outcome

Chosen option: "Each source response exactly as received (compressed), plus ingestion metadata stored separately".

### Consequences

* Everything downstream can be reprocessed from the original.
* Storage is larger than parsed data; compression mitigates it.
