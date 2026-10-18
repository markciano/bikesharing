---
status: proposed
date: 2026-10-15
---

# Collectors decoupled by an output contract

## Context and Problem Statement

Raw data arrive through two collectors that do the same job in two places: the cloud capture (ADR-0011, JS on Cloudflare Workers) and an on-demand local capture (Python). ADR-0010 makes ingestion portable by sharing Python logic behind platform adapters. A collector only fetches and stores bytes, so it has no logic to share, and a JS collector cannot share Python code.

How should the collectors stay interchangeable for the pipeline?

## Considered Options

* An output contract that every collector meets (decoupled landing zone)
* Shared Python logic behind platform adapters (ADR-0010 as written)

## Decision Outcome

Chosen option: "An output contract that every collector meets", because the pipeline depends only on the files, so each collector can change platform or language without affecting it.

The contract:

* **Key:** `raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`.
* **Timestamp:** the capture time in UTC (ADR-0005), one value per pass for the key and the date folder.
* **Payload:** the gzip bytes served by the origin, unchanged (ADR-0006). No collector decompresses or recompresses.
* Decompression happens in the bronze layer.

This amends ADR-0010: ports and adapters stays for processing, and no longer applies to collectors.

### Consequences

* Good: the pipeline cannot tell which collector produced a file.
* Good: full reprocessing from raw is possible whenever bronze, silver or gold logic changes.
* Bad: each collector's naming code is written once per language and is checked against the contract, not shared.
* The local collector must request gzip and store the bytes as received.
* When this ADR is accepted, ADR-0010 gets the line "Amended by ADR-0012".
