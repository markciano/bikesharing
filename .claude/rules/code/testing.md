---
paths:
  - "src/**"
  - "tests/**"
  - "capture/**"
  - "contracts/**"
---

# Testing rules (all languages)

Reasons and per-component detail: [testing strategy](../../../docs/testing-strategy.md); read only the section of the component you touch. Tool-specific rules are in `python.md` and `cloudflare-worker.md`.

## Principles

- Follow the test pyramid.
- Every requirement has a verification method in its design's Test plan (IADT: Inspection, Analysis, Demonstration, Test); those verified by Test have at least one test, at the lowest level that can verify it.
  - A test that verifies a Test plan row says so in a comment above it, `Verifies <design ID> <R>` (e.g. `Verifies d004 R7`, after `//` or `#`): a traceability tag, cited by requirement since that is what the Test plan lists.
- Tests verify observable behaviour, not implementation details.
- Tests are written first (TDD: red, green, refactor).
- Arrange–Act–Assert; one concept per test; no shared state or order dependency between tests.
- A test's name states the behaviour and the condition; its form is in each language rule.
- No test touches the network: use recorded fixtures (ADR-0037); edge cases are written by hand.
- Code that depends on the current time, a timeout or a size limit receives it as a parameter; tests pass a fixed UTC time and small values, never the production ones.
- Data quality checks on the data itself belong to the pipeline design, not to the test suite.

## Running tests

- Claude runs tests from the project root, as a single command, in exactly the form `.claude/settings.json` allows, so they run without a permission prompt; each language rule gives that command. A variant (a `cd`, a reordered flag) is not allowed and prompts.

## Contracts between components

- A contract is tested as soon as it is defined, before either side is written.
- Format and behaviour contracts (keys, naming, encoding) use shared test vectors in `contracts/` at the root, owned by no component: one JSON file per contract, with `valid` cases (input → expected output) and `invalid` cases, each breaking exactly one rule and stating its `reason`.
- Producer and consumer tests read the same file by relative path. Binary payloads are built in memory by the tests.
- A contract change makes the valid data stop meeting it; the vectors never relax it.
