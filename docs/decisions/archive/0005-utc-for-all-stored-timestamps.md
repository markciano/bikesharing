---
status: Superseded
date: 2026-10-03
superseded-by: 0041
---

# UTC for all stored timestamps

Superseded on 2026-11-14 (T040) by [ADR-0041](../0041-utc-timestamps-local-calendar-keys.md): stored time stays in UTC, and fact rows also carry local calendar keys, so local days and hours are no longer left to presentation.

## Context and Problem Statement

Local time repeats or skips one hour twice a year (next change: 25 October 2026).

Which time zone should stored timestamps use?

## Considered Options

* UTC everywhere in storage, local time only when presenting
* Local time (Europe/Madrid) everywhere

## Decision Outcome

Chosen option: "UTC everywhere in storage, local time only when presenting". Every stored timestamp, file name and partition is in UTC. Conversion to local time happens only when presenting results.

### Consequences

* No ambiguous or missing hours.
* Analyses by local hour of day need an explicit conversion step.
