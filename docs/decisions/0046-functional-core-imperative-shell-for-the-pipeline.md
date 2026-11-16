---
status: Accepted
date: 2026-11-16
supersedes: ADR-0029
---

# Pipeline code architecture: a functional core with an imperative shell

## Context and problem statement

What architecture should the pipeline's code follow, so that its logic is tested without the platform, the network or the clock, and each later task extends it the same way?

[ADR-0029](archive/0029-pipeline-code-architecture.md) set a thin platform wrapper before any pipeline code existed. Since then the forces on the code have become clearer:

- The logic is mostly SQL, which the engine runs in-process and reads from object storage or a local path with the same query ([ADR-0024](0024-duckdb-as-processing-engine.md), [ADR-0025](0025-sql-models-directed-by-python.md)). Tests that run that SQL on the real engine already cost little.
- Part of the logic is not SQL and depends on the outside: when to send the heartbeat ([ADR-0031](0031-heartbeat-alerts-for-the-pipeline.md)), which window a catch-up processes from the current time and the last run ([ADR-0045](0045-catch-up-in-bounded-batches.md)), local hour and day boundaries ([ADR-0041](0041-utc-timestamps-local-calendar-keys.md)). ADR-0029 left open how the clock and the network reach it, so testing it would mean patching globals.
- The same work runs from several entry points: the scheduled run, the one-off history load and the rebuild from bronze.
- Quality rules and observability are expected to grow often ([ADR-0042](0042-data-quality-classes-and-severity.md), [ADR-0043](0043-lineage-at-four-levels.md)), so adding one must stay cheap.
- One person writes and operates the code, and must understand and change its structure alone.

No pipeline code exists yet, so changing the architecture now costs nothing.

## Considered Options

The options were scored in a weighted decision matrix ([s015 › D1](../spikes/s015-pipeline-code-architecture.md#d1-pipeline-code-architecture-style)) on failure paths tested without the network, determinism with respect to time, the cost of a new quality rule, one operation for every entry point, the cost of a change of source or platform, and simplicity.

### 1. Thin platform wrapper

The current ADR-0029: inward dependencies and no interfaces; the package reaches the clock and the network wherever it needs them.

- Pros:
  - the fewest concepts;
  - a change of platform touches one module.
- Cons:
  - the heartbeat and the clock live inside the logic, so their branches need patched globals in tests;
  - each entry point assembles its own sequence of steps.

### 2. Functional core, imperative shell

The core is pure functions: it takes values (the current time, the last run, the configuration, the results of the SQL) and returns values and decisions. The shell performs all I/O, the engine included, and acts on those decisions.

- Pros:
  - every decision is tested with an assert on a returned value, with no network, no clock and no fake;
  - one operation over a window serves every entry point;
  - one extra concept over option 1.
- Cons:
  - I/O that must happen mid-flow does not fit a value returned at the end.

### 3. Functional core with selective driven ports

Option 2, plus interfaces with fakes for the external collaborators, such as the clock or a notifier.

- Pros:
  - it also covers I/O that must happen mid-flow.
- Cons:
  - ports, adapters, fakes and their wiring, for collaborators whose I/O can all wait for the shell today.

### 4. Full ports and adapters (hexagonal)

Every external system, the engine and storage included, sits behind a port.

- Pros:
  - every external system can be swapped for a fake.
- Cons:
  - the SQL moves into the engine adapter and the core is left almost empty;
  - a new operation touches the port, the real adapter, the fake and their tests;
  - a fake engine does not run the SQL, where the main failures are expected.

## Decision Outcome

**Chosen option:** 2. Functional core, imperative shell, defined by the rules in [The architecture](#the-architecture).

It makes the non-SQL logic of the Context testable as values, gives the several entry points one operation, and leaves the SQL on the real engine, at the cost of one concept a single developer can hold. The SQL needs no protection a port could add: the engine already reaches storage through a location.

Why not the others:

- Thin platform wrapper: it leaves the clock and the network inside the logic that decides on them.
- Selective driven ports: no collaborator needs one today; the evolution rule adds one where it does.
- Full ports and adapters: its core would be empty and its fakes would not run the SQL.

**Scope:** the internal structure of the pipeline's Python code and how it meets the platform. Not the architecture of the whole solution, in `docs/architecture.md`; not capture, decoupled by its output contract ([ADR-0012](0012-collectors-decoupled-by-output-contract.md)); not which quality rules exist, in the quality catalog, nor when they run within a run; not the test layers, in `docs/testing-strategy.md`.

### The architecture

It combines established patterns:

- **Functional core, imperative shell** (Gary Bernhardt): decisions are pure functions over values; I/O stays in a thin outer shell.
- **Dependency Rule** (Clean Architecture, Robert C. Martin): source dependencies point inward, from the platform module to the shell to the core.
- **Humble Object** (Gerard Meszaros): the platform module, the part hard to test, holds no logic.
- **Config** (The Twelve-Factor App): configuration and credentials arrive as environment variables.
- **Functional data engineering** (Maxime Beauchemin): each run is one idempotent operation over a window, so the scheduled run, the history load and the rebuild differ only in the window.

The pipeline package has two subpackages, the core and the shell; the platform module lives outside the package. These rules define the design:

| # | Rule | Check |
|---|---|---|
| 1 | The package never imports the platform's SDK | Import contract in CI |
| 2 | The core never imports the engine or an HTTP client | Import contract in CI |
| 3 | Dependencies point from the shell to the core, never back | Import contract in CI |
| 4 | The platform module never imports the engine | Import contract in CI |
| 5 | The pipeline starts without the platform's SDK installed | A CI test |
| 6 | Only one configuration function in the shell reads the environment, and returns one immutable value; credentials in it are masked in their text form | Review |
| 7 | The core logs through the standard logging library; the shell configures where logs go | Review |
| 8 | Each runtime rule of the quality catalog is one versioned SQL query, named after its ID, that returns the rows breaking it; one runner in the shell runs them, and the core turns their results into a verdict with the rule's severity | Review |

**Evolution rule:** a driven port with a fake is added for one collaborator only when its external I/O must happen mid-flow and cannot wait for the shell. A port is justified by two real implementations, or by a real one that is slow, non-deterministic or external and that a test must avoid; a fake of the engine never qualifies. Adding a port breaks no rule above.

### Consequences

#### Positive

- **Decisions tested as values:** when to alert, which window to process and what to publish are asserted directly, with no network, clock or platform.
- **One operation, several entry points:** catch-up, history load and rebuild reuse the same path, so a fix reaches all three.
- **Honest SQL tests:** the SQL runs on the real engine against local files, as with ADR-0029.
- **A checked structure:** rules 1–5 fail the PR on a departure, where ADR-0029 left two of its rules to review.
- **Cheap rules:** a new quality rule is one SQL file and its test case.

#### Negative

- **One concept to keep:** the split between core and shell must be held in every task; a decision written in the shell compiles and runs, and only review catches it.
- **Rules 6–8 rest on review:** no import check tells one use of the environment, of logging or of SQL from another.
- **I/O mid-flow needs a port:** a recurring external source read page by page would bring the first port and its fake.
- **Assumes the platform runs Python with environment variables,** as ADR-0029 did.

This decision is reopened if a second engine appears or if business rules in Python come to dominate the SQL. A new source loaded from static files, or a change of platform, does not reopen it: both stay in the shell.

## More information

### Skeleton

Simplified; names and SQL are illustrative.

```python
# core: decides, never acts
def plan_run(now, last_run) -> Window: ...
def evaluate(rule_results) -> Verdict: ...           # severity per rule
def summarize(result) -> Heartbeat | None: ...

# shell: acts, holds no decision
def main():
    config = load_config()                           # the only reader of the environment
    window = plan_run(datetime.now(UTC), read_last_run(config))
    result = run_models(window, config)              # SQL on the engine
    verdict = evaluate(run_rules(config))            # one SQL file per runtime rule
    if verdict.publish:
        publish(config)
    if heartbeat := summarize(result):
        send_heartbeat(config.heartbeat_url, heartbeat)
```

```python
# tests: the core, as values
def test_no_heartbeat_when_run_fails():
    assert summarize(failed_result) is None
```

### Tools

The import contracts use import-linter, declared in `pyproject.toml` and run as a development dependency. Configuration uses a frozen dataclass of the standard library; it moves to `pydantic-settings` if the configuration grows in variables, types or nesting.

### Sources

- Decision at framing and its matrix: [s015 › D1–D5](../spikes/s015-pipeline-code-architecture.md#12-decided-at-framing).
- Functional core, imperative shell: <https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell>
- Hexagonal architecture, Alistair Cockburn: <https://alistair.cockburn.us/hexagonal-architecture/>
- Config: <https://12factor.net/config>
- import-linter contract types: <https://import-linter.readthedocs.io/en/stable/contract_types/>
