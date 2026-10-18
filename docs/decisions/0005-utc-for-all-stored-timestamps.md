---
status: accepted
date: 2026-10-03
---

# UTC for all stored timestamps

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
