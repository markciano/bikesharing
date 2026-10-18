---
status: proposed
date: 2026-10-03
---

# Build locally first, Microsoft Fabric later

## Context and Problem Statement

The owner studied Microsoft Fabric (DP-700). Managed platforms hide fundamentals (retries, incremental logic, storage layout).

Which platform should the project be built on first?

## Considered Options

* Local stack (Spark + Delta Lake) first, port to Fabric later
* Fabric from day one
* Local only

## Decision Outcome

Chosen option: "Local stack (Spark + Delta Lake) first, port to Fabric later".

### Consequences

* Fundamentals are learned explicitly.
* Code stays portable because Fabric also runs Spark on Delta tables.
* Fabric becomes a later comparison exercise.
