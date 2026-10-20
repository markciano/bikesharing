---
paths:
  - "src/**"
  - "tests/**"
  - "collector/**"
---

# Testing rules (all languages)

Reasons and per-component detail: [testing strategy](../../docs/testing-strategy.md); read only the section of the component you touch. Tool-specific rules are in `python.md` and `cloudflare-worker.md`.

## Principles

- Follow the test pyramid.
- Every requirement and "Done when" condition is covered by at least one test, at the lowest level that can verify it.
- Tests verify observable behaviour, not implementation details.
- Tests are written first (TDD: red, green, refactor).
- Arrange–Act–Assert; one concept per test; no shared state or order dependency between tests.
- No test touches the network: use recorded fixtures (ADR-0009); edge cases are written by hand.
- Code that uses the current time receives it as a parameter; tests pass a fixed UTC time.
- Data quality checks on the data itself belong to the pipeline design, not to the test suite.

## Contracts between components

- A contract is tested as soon as it is defined, before either side is written.
- Format and behaviour contracts (keys, naming, encoding) use shared test vectors: one JSON file with `valid` cases (input → expected output) and `invalid` cases, each breaking exactly one rule and stating its `reason`.
- Producer and consumer tests read the same file by relative path. Binary payloads are built in memory by the tests.
- A contract change makes the valid data stop meeting it; the vectors never relax it.

TODO: add the shared contract folder to `paths:` when a design defines it.
