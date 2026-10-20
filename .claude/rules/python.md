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

General principles are in `testing.md`; reasons and detail in the [testing strategy](../../docs/testing-strategy.md) (Python section).

- Tool: pytest; `pytest` runs every test, `pytest tests/<level>` one level.
- Line coverage (pytest-cov) is reported, never enforced with a threshold. The source is set in `[tool.coverage.run] source`, so the CI command cannot widen the report to the test files.
- Levels are folders: `tests/unit/` (mirrors `src/`), `tests/integration/`, `tests/e2e/`.
- Naming: files `test_<module>.py`; functions `test_<behaviour>_<condition>`.
- Shared fixtures in `conftest.py` (one in `tests/`, plus one per level when needed), function-scoped by default.

### Spark

Detail: [testing strategy](../../docs/testing-strategy.md) (Spark section).

- Each transformation is a function DataFrame → DataFrame, so it can be tested alone.
- Unit tests run on one session-scoped local SparkSession (`local[1]`, UI disabled) in `conftest.py`: the exception to function-scoped fixtures.
- Input DataFrames are built inside the test; compare with `pyspark.testing.assertDataFrameEqual`.
