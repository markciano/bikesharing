---
status: accepted
date: 2026-10-07
---

# The common station model follows GBFS 3.0

## Context and Problem Statement

AMBici publishes only GBFS 2.3; Bicing publishes 3.0 and also announces 2.3 and 1.1
(`gbfs_versions`). AMBici is reviewing a 3.0 release (email reply, 2026-10-07).
Both systems must land in one station-level model.

Which GBFS version should the common model follow?

## Decision Drivers

* Follow the current GBFS specification
* Limit the work needed before ingestion design (T007) can start
* Limit the cost of a future version change by either source

## Considered Options

* GBFS 3.0; Bicing read as 3.0, AMBici 2.3 transformed to 3.0
* GBFS 2.3; both systems read as 2.3
* An own model independent of the GBFS version, with one adapter per system and version

## Decision Outcome

Chosen option: "GBFS 3.0; Bicing read as 3.0, AMBici 2.3 transformed to 3.0", because
it follows the current specification, keeps the spike evidence valid and turns
AMBici's future 3.0 release into a configuration change.

### Consequences

* AMBici needs 1 rename and 6 transforms (two POSIX timestamps → RFC 3339, four strings → localised lists), applied after the raw layer (ADR-0006); Bicing maps directly (Bicing spike, 2a–2b).
* The transform is scoped to (system, version), so it is retired when AMBici publishes 3.0.
* Matching versions does not align meaning: `last_reported`, `is_renting`, per-type counts and `ttl` differ between systems and are handled in the model regardless of this decision (spike reports, 3b, 8c, 8j).

## Pros and Cons of the Options

### GBFS 2.3 for both

* Good, because AMBici needs no transforms.
* Bad, because the Bicing 2.3 endpoint was not verified by the spike: capture and
  analysis would have to be repeated.
* Bad, because it chooses a superseded version and needs a migration of both
  systems when AMBici moves to 3.0.

### Own version-independent model

* Good, because it isolates the model from any future GBFS change.
* Bad, because it designs a model ahead of need; GBFS 3.0 already covers both
  systems with minor transforms.

## More Information

* [Bicing spike](../spikes/s002-bicing-realtime-capture.md), Findings 1–2
* [AMBici spike](../spikes/s001-ambici-realtime-capture.md), Findings 1–2
* Revisit if AMBici publishes 3.0 (retire the transform) or if a source drops 3.0.
