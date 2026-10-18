---
status: accepted
date: 2026-10-08
---

# Ingestion logic is separated from the platform that runs it

## Context and Problem Statement

Where ingestion runs is still open (T012: the owner's Mac or a cloud platform such as Cloudflare Workers). Code that mixes fetching, transforming and storing can only be tested on its platform and must be rewritten if the platform changes.

How should ingestion code be structured so it can be tested locally and survive a change of platform?

## Considered Options

* Separate the logic from the platform (ports and adapters)
* A single module per platform that fetches, transforms and stores

## Decision Outcome

Chosen option: "Separate the logic from the platform (ports and adapters)", because the logic can be tested without the platform and the platform can change without touching it.

* **Logic:** parsing, validation and file naming, in plain Python with no platform dependencies.
* **Platform:** a thin layer per platform (scheduler, storage) that calls the logic.

### Consequences

* The logic is covered by pytest against recorded fixtures; the platform layer gets a manual smoke check.
* Changing platform means rewriting only the platform layer.
* The chosen platform must run Python (T012).
