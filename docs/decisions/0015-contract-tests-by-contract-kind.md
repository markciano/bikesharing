---
status: accepted
date: 2026-10-21
---

# Contract tests by contract kind: test vectors or ODCS schema

## Context and Problem Statement

Components are decoupled by contracts: the collector output of ADR-0012 now, silver and gold tables later. Each side may be written in a different language (JS and Python today), and a contract change must fail the tests of both sides.

How is a contract between two components defined and tested, independently of the language of each side?

## Considered Options

* Shared golden test vectors: one JSON file with valid cases (input → expected output) and invalid cases, read by the tests of both sides
* A schema: JSON Schema, or the Open Data Contract Standard (ODCS) for tables

## Decision Outcome

Chosen option: depends on the contract kind, scored with the same weighted matrix for each (`docs/spikes/s008-testing-conventions.md`, matrix D).

* **Format and behaviour contracts** (keys, naming, encoding): shared golden test vectors (90 against 50). They express what a schema cannot: a date folder consistent with the timestamp, bytes unchanged. Proven in s008 on the collector contract: one changed rule failed the producer tests (JS) and the consumer tests (Python) (F18, F35).
* **Data-shape contracts** (silver, gold): an ODCS schema (84 against 54). It declares columns, types, nullability and quality rules, which vectors only show by example. Justified on paper only (F36).

How to write and use the vectors is in `.claude/rules/testing.md` › Contracts between components; the testing model is in `docs/testing-strategy.md` › Contract.

### Consequences

* One contract file serves every language without code generation; it must be inside the CI path filters of every job that reads it.
* The ODCS form is not proven in this project: the first design that defines a data-shape contract validates it, and records the outcome.
* The content of data contracts (semantics, freshness, quality, ownership) stays in the pipeline design.
