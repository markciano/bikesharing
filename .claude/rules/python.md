---
paths:
  - "src/**"
  - "tests/**"
---

# Python code and testing rules

## Code comments

- Docstrings follow numpydoc (NumPy style) on every module, class and public function/method.
- Type hints are mandatory in signatures. For DataFrames, the Parameters and Returns sections list the required columns and their dtypes.
- Inline comments explain *why* a non-obvious decision was made, never *what* the code does.

## Testing

Follow the test pyramid.

- Every requirement and "Done when" condition is covered by at least one test, at the lowest level that can verify it.
- Tests verify observable behaviour, not implementation details.
- Unit tests are written first (TDD: red, green, refactor).
- Arrange–Act–Assert; one concept per test; no shared state or order dependency between tests.
- Tool: pytest; `pytest` runs every test, `pytest tests/<level>` one level. Line coverage (pytest-cov) is reported, never enforced with a threshold.
- Levels are folders: `tests/unit/` (mirrors `src/`), `tests/integration/`, `tests/e2e/`.
- Naming: files `test_<module>.py`; functions `test_<behaviour>_<condition>`.
- Shared fixtures in `conftest.py` (one in `tests/`, plus one per level when needed), function-scoped by default.
- No test touches the network: integration and e2e tests use recorded fixtures (ADR-0009); edge cases are written by hand.
- Code that uses the current time receives it as a parameter; tests pass a fixed UTC time.
- Data quality checks on the data itself belong to the pipeline design, not to the test suite.
