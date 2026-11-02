---
status: Proposed
date: 2026-11-02
supersedes: ADR-0010
---

# Pipeline code architecture: a thin platform wrapper with inward dependencies

## Context and problem statement

What architecture should the pipeline's code follow? Without a defined one, each task decides its own structure, and nobody can tell when the code has departed from it.

The pressure comes mostly from where the code runs: the pipeline runs on a managed platform that requires its own SDK around the code ([ADR-0027](0027-modal-as-execution-platform.md)), and a fallback platform is already named in case that one stops being viable. The way platform code and pipeline logic meet decides how far a change of platform reaches and whether the logic can be tested without the platform.

- The logic is mostly SQL, which the engine executes and Python runs in order ([ADR-0025](0025-sql-models-directed-by-python.md)).
- The engine reads the same query from object storage or from a local path, so storage is reached through a location and credentials ([ADR-0024](0024-duckdb-as-processing-engine.md)).
- Tests must run locally and in CI, with no platform account.
- One person writes and operates the code, and must be able to understand and change its structure alone.

[ADR-0010](archive/0010-ingestion-logic-separated-from-platform.md) answered a similar question while the platform was open, for ingestion only. Capture has since been built outside Python ([ADR-0011](0011-cloudflare-workers-r2-for-realtime-capture.md)), so that decision no longer describes any code, and it says nothing about the pipeline.

## Considered Options

Each option is compared on what a change of platform touches, how the SQL gets tested, what one new operation costs and how easy the structure is to understand. Code skeletons of options 1 and 2 are in [More information](#more-information).

### 1. Thin platform wrapper

One Python package holds the pipeline and exposes one entry point. A single module outside the package declares what the platform needs and calls that entry point. Configuration arrives as environment variables.

- Pros:
  - a change of platform replaces one module;
  - tests run the real SQL on the real engine, against local files;
  - one new operation is one function and its test;
  - little structure to learn.
- Cons:
  - tests cannot swap storage for a double through an interface;
  - a platform without Python or environment variables would need more rework.

### 2. Full hexagonal architecture

Also known as ports and adapters. The core logic talks to the outside only through interfaces it defines (**ports**), and one class per technology implements each interface (**adapters**). Adapters exist on two sides: **driving** adapters start the application, and **driven** adapters are what the application uses, such as storage.

- Pros:
  - a change of platform also replaces only outer code;
  - tests can swap every external system for a fake;
  - a known pattern, valuable when a system has several real implementations or complex business rules.
- Cons:
  - the SQL moves into the adapter, leaving the core almost empty;
  - the storage port would have one real implementation, as the engine already isolates storage;
  - one new operation touches the port, the real adapter, a fake adapter and their tests;
  - a fake adapter does not run the SQL, so tests against the engine are still needed;
  - more concepts to hold for a single developer.

### 3. Logic written directly on the platform

One module holds the pipeline and the platform's declarations together.

- Pros:
  - the fewest files;
  - nothing to learn beyond the platform.
- Cons:
  - a change of platform rewrites everything;
  - the logic cannot be tested, or even imported, without the platform's SDK.

## Decision Outcome

**Chosen option:** 1. Thin platform wrapper, defined by the patterns and rules in [The architecture](#the-architecture).

It gives the two things the Context asks for, a change of platform that stops at one module and tests that do not need the platform, without adding structure the pipeline has no use for. Hexagonal architecture earns its cost by protecting business rules written in code from external systems, and here the rules are SQL that the engine runs: the port would hide what is already hidden.

Why not the others:

- Full hexagonal architecture: its core would be almost empty, and its fakes would not exercise the SQL, where the main failures are expected.
- Logic written directly on the platform: it fails both needs in the Context.

**Scope:** The internal structure of the pipeline's Python code and how it meets the platform. It is not the architecture of the whole solution, which is in `docs/architecture.md`. It does not cover capture, which is decoupled by its output contract ([ADR-0012](0012-collectors-decoupled-by-output-contract.md)), or how tests are organised, in `docs/testing-strategy.md`. Where the platform module lives in the repository belongs to T040.

### The architecture

No single name covers this design. It combines three established patterns:

- **Dependency Rule** (Clean Architecture, Robert C. Martin): source dependencies point inward. The platform module knows the package, never the reverse.
- **Humble Object** (*xUnit Test Patterns*, Gerard Meszaros): the part that is hard to test holds no logic, so the logic can be tested without it. Here that part is the platform declaration.
- **Config and Backing Services** (The Twelve-Factor App): configuration and credentials arrive as environment variables, and storage is an attached resource named by that configuration.

It is a subset of hexagonal architecture: the platform module is a driving adapter, and the package has no driven ports. It keeps the central idea, that dependencies point inward, and leaves out the interfaces.

These rules define the design. Each has a check, so a deviation can be detected:

| # | Rule | Check |
|---|---|---|
| 1 | The package never imports the platform's SDK | CI fails on the import |
| 2 | The platform module holds no SQL or data logic: only declarations and the call to the entry point | CI fails if the module imports the engine; review for the rest |
| 3 | The package reads configuration and credentials only from environment variables | Review |
| 4 | The entry point runs without the platform, on a local path | A CI test runs the pipeline with the SDK not installed |

### Consequences

#### Positive

- **A bounded change of platform:** moving to the fallback replaces one module with a timer and a service, and the package does not change.
- **Honest tests:** they run the real SQL on the real engine, with no platform account.
- **Structure one person can defend:** few concepts, each with a check that shows when the code departs from them.

#### Negative

- **No storage double:** tests use the engine against local files or a local S3 endpoint, which is slower than a fake and can miss differences with the real store.
- **Checks to build:** the rules hold only once T040 adds their checks; until then they depend on discipline.
- **Rule 2 and rule 3 rest partly on review:** CI catches the import of the engine, not every piece of logic placed in the wrong file.
- **Assumes the platform runs Python with environment variables:** all the candidates that passed the cuts in [ADR-0027](0027-modal-as-execution-platform.md) do, but a platform that does not would need more rework.

This decision is reopened if a **second real implementation** of the same work appears, such as a second engine alongside the first or a destination the engine cannot write to, or if business rules in Python grow beyond orchestration. Fake adapters do not count as an implementation. A change of platform, of S3-compatible store or of local path does not count either, since none changes how tables are built. Moving from the wrapper to ports then is a bounded refactor.

## More information

### Skeletons

Simplified, to show the difference in shape; the SQL and the names are illustrative. Both reach the same result.

**Option 1, thin platform wrapper:**

```text
src/bikesharing/pipeline.py
deploy/platform_app.py
tests/test_pipeline.py
```

```python
# src/bikesharing/pipeline.py: knows nothing about the platform
def run(data_path=None):
    data_path = data_path or os.environ["DATA_PATH"]   # s3://... in production
    duckdb.sql(f"""
        COPY (SELECT ... FROM read_parquet('{data_path}/bronze/*.parquet'))
        TO '{data_path}/silver/trips.parquet'
    """)

# deploy/platform_app.py: declares and calls, nothing else
@app.function(image=image, memory=4096, secrets=[...], schedule=modal.Cron("*/10 * * * *"))
def scheduled():
    run()

# tests/test_pipeline.py: the real SQL, on a local folder
def test_run(tmp_path):
    create_test_bronze(tmp_path)
    run(str(tmp_path))
    assert read_silver(tmp_path) == expected
```

**Option 2, full hexagonal architecture:**

```text
src/bikesharing/ports.py
src/bikesharing/pipeline.py
src/bikesharing/adapters/duckdb_store.py
tests/fakes.py
deploy/platform_app.py
tests/test_pipeline.py
tests/test_duckdb_store.py
```

```python
# ports.py: what the pipeline needs
class TableStore(Protocol):
    def build_silver(self) -> None: ...

# pipeline.py: the core receives an adapter, and has almost nothing left to do
def run(store: TableStore):
    store.build_silver()

# adapters/duckdb_store.py: this is where the SQL ends up
class DuckDBStore:
    def __init__(self, data_path):
        self.data_path = data_path
    def build_silver(self):
        duckdb.sql(f"COPY (SELECT ... FROM read_parquet('{self.data_path}/bronze/*.parquet')) TO ...")

# tests/fakes.py: a fake adapter
class FakeStore:
    def __init__(self):
        self.called = False
    def build_silver(self):
        self.called = True

# deploy/platform_app.py: wires everything together
def scheduled():
    run(DuckDBStore(os.environ["DATA_PATH"]))

# tests/test_pipeline.py: only checks that it was called
def test_run():
    store = FakeStore()
    run(store)
    assert store.called

# tests/test_duckdb_store.py: the real SQL, as in option 1
```

### Cost compared

Estimates, not measurements:

| | Option 1 | Option 2 |
|---|---|---|
| Files in the skeleton | 3 | 7 |
| Initial cost | The wrapper | A few more hours |
| Adding one operation | One function and its test | Port, real adapter, fake adapter and their tests |
| Tests that exercise the SQL | The same in both | The same in both, plus those using the fake |

The higher cost of option 2 is not writing it once, but what repeats: each change touches more places, without saving any test.

### Sources

- Decision at framing: [s012/D4](../spikes/s012-execution-target.md#d4-processing-logic-separated-from-the-platform); outcome in [s012 Decisions to record](../spikes/s012-execution-target.md#54-decisions-to-record).
- Hexagonal architecture: Alistair Cockburn, 2005.
- Config and Backing Services: <https://12factor.net/config>, <https://12factor.net/backing-services>.
