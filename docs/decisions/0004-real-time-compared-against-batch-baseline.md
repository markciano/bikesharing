---
status: proposed
date: 2026-10-03
---

# Real-time flow compares against a batch-computed baseline

## Context and Problem Statement

Real-time ingestion only adds value if it answers something history cannot.

What should the real-time flow do that the historical data cannot?

## Considered Options

* Compare the current state against a batch-computed baseline
* Real time as a separate live dashboard
* Merge real-time snapshots into the historical tables only

## Decision Outcome

Chosen option: "Compare the current state against a batch-computed baseline". Batch computes the normal behaviour of each station (by weekday and time slot) from history; the real-time flow compares the current state against that baseline (stations unusually empty, stations about to run out of bikes).

### Consequences

* Real time depends on batch outputs, which creates a clear contract between both flows.
