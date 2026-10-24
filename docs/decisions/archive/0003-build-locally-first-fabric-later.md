---
status: rejected
date: 2026-10-03
---

# Build locally first, Microsoft Fabric later

Rejected on 2026-10-24 (T022): it bundled three decisions (table format, engine, execution target) taken before the requirements; they are now taken in dependency order (`docs/architecture.md`).

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
