---
status: accepted
date: 2026-10-08
---

# Trimmed source samples are committed as test fixtures

## Context and Problem Statement

Integration and end-to-end tests run against recorded source responses, not live APIs (CLAUDE.md › Testing). Raw data is never committed to Git, so the tests would have nothing real to run against in a fresh clone.

Which source data, if any, may be committed for tests?

## Considered Options

* Real responses trimmed to a few stations by a committed script, plus hand-written edge cases
* Hand-written synthetic fixtures only
* Full real responses

## Decision Outcome

Chosen option: "Real responses trimmed to a few stations by a committed script, plus hand-written edge cases", because tests see the real quirks of each source while fixtures stay small, readable and reproducible.

### Consequences

* The exception is limited to `tests/fixtures/`; full captures stay out of Git.
* Each fixture records its source and capture date.
* AMBici data is CC0-1.0; Bicing publishes no licence fields, so CC0 applies by the GBFS 3.0 default. Bicing fixtures carry attribution as good practice (see source cards).
* Fixtures are regenerated with the script when a source changes its format.
