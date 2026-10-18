---
status: accepted
date: 2026-10-03
---

# Data sources: AMBici and Bicing

## Context and Problem Statement

The project is a data engineering portfolio piece. It needs a real-time source and an incremental/historical source, with enough volume and real data quality problems.

Which data sources should the project use?

## Considered Options

* Public bike sharing in the Barcelona area: AMBici + Bicing
* Wikimedia EventStreams
* Bluesky Jetstream
* Crypto exchange websockets
* Public transport GTFS-realtime

## Decision Outcome

Chosen option: "Public bike sharing in the Barcelona area: AMBici + Bicing", combining AMBici (metropolitan area) and Bicing (Barcelona city). Details in `docs/sources/`.

### Consequences

* Both systems together cover the whole Barcelona area.
* Bicing provides history since 2019 (real backfill and monthly incremental loads); both provide real-time snapshots.
* The two schemas differ, so a common model is required.
* Bicing data is CC BY 4.0: attribution is mandatory.
