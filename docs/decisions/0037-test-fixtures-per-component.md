---
status: Accepted
date: 2026-11-06
supersedes: 0009
---

# Trimmed source samples are committed as test fixtures, in each component's tests

## Context and problem statement

Tests run against recorded source responses, never live APIs ([testing strategy](../testing-strategy.md)), and raw data is never committed to Git. [ADR-0009](archive/0009-trimmed-source-samples-as-test-fixtures.md) made one exception: real responses trimmed by a committed script, limited to `tests/fixtures/` at the repository root.

- More than one component needs fixtures: capture, in JavaScript, and the pipeline, in Python.
- Each component owns its runtimes, dependencies and tests in its own folder ([ADR-0016](0016-runtime-versions-pinned-per-component.md), [ADR-0017](0017-dependencies-locked-per-component.md)); `tests/` at the root is the pipeline's.
- Components need the same responses in different forms: capture serves them as a source sends them, the pipeline reads them as bronze stores them.
- What two components must agree on is fixed by shared contract vectors, not by shared test data ([ADR-0015](0015-contract-tests-by-contract-kind.md)).

## Considered Options

Each option is compared on which component owns the fixtures, and on what a change to one component's fixtures does to the other.

### 1. In each component's fixtures folder

Every component keeps its fixtures in its own tests, and its own script trims them.

- Pros:
  - each component owns its test data, as it owns its code and tests;
  - a component changes its fixtures without touching the other's tests.
- Cons:
  - some responses are kept twice, a few KB each.

### 2. In a shared top-level folder

All fixtures live in one folder at the root, read by every component.

- Pros:
  - each response is kept once.
- Cons:
  - a fixture changed for one component can break the other's tests;
  - one script must produce the forms both components need.

### 3. Keep `tests/fixtures/` only

Fixtures stay where ADR-0009 put them, and capture reads them from there.

- Pros:
  - no ADR change.
- Cons:
  - capture depends on the pipeline's test folder.

## Decision Outcome

**Chosen option:** 1. In each component's fixtures folder.

It follows the ownership per component that the Context sets for code, dependencies and tests, and leaves agreement between components to the contract vectors. The duplicated bytes are negligible.

Why not the others:

- A shared folder: it couples the tests of two components through data that is not a contract.
- Keep `tests/fixtures/`: it makes one component depend on another's test folder.

**Scope:** Which source data may be committed for tests, and where. It does not cover contract vectors, which are not source data ([ADR-0015](0015-contract-tests-by-contract-kind.md)), nor how each component's tests use the fixtures.

### The rule

- **What:** real source responses trimmed to a few stations by a committed script, plus hand-written edge cases. Why real samples rather than synthetic data or full responses is in [ADR-0009](archive/0009-trimmed-source-samples-as-test-fixtures.md).
- **Where:** only the fixtures folder of each component's tests; full captures stay out of Git.
- **Provenance:** each fixture records its source and capture date.
- **Licence:** AMBici data is CC0-1.0; Bicing publishes no licence fields, so CC0 applies by the GBFS 3.0 default. Bicing fixtures carry attribution as good practice (see source cards).
- **Refresh:** fixtures are regenerated with the script when a source changes its format.

### Consequences

#### Positive

- **Independent tests:** a component's fixtures change with its code, in the same component.
- **One rule for new components:** a new component adds its own fixtures folder and script.

#### Negative

- **Several exceptions to watch:** raw data may now appear in more than one folder, so a review must check that a fixture sits in a component's fixtures folder and is trimmed.
- **More than one script:** each component maintains the trimming of the responses it needs.

## More information

- Decided in [d004 › File layout](../designs/d004-bronze-data-capture.md#24-file-layout) (T039): capture's fixtures are in `capture/test/fixtures/`, the pipeline's in `tests/fixtures/`.
