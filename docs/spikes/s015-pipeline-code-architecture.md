# Spike: Pipeline code architecture

- **Task:** T064
- **ADRs:** [ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md) (replaced by [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md))
- **Code:** none: the spike has no run

## Status

- State: Concluded ✅
- Phase: [x] Questions · Method, Steps and Steps review: not applicable, no run · [x] Conclusion
- Started: — · Finished: 2026-11-16
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

This spike revisits the pipeline's code architecture, set by [ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md) from [s012 › D4](s012-execution-target.md#d4-processing-logic-separated-from-the-platform), before T060.1 builds the walking skeleton whose patterns every later child of [d007](../designs/d007-pipeline-design.md) follows. It decides the architecture style (D1, the central decision), the collaborators at the edge (D2), the shape of runtime rules in the code (D3), how configuration enters (D4) and how the rules are checked in CI (D5). None depends on evidence: D1 is settled by a weighted decision matrix over code skeletons, and the facts behind it and D5 come from the tools' documentation, so the spike has no run.

### 1.2 Decided at framing

#### D1. Pipeline code architecture style

**B1. Functional core, imperative shell.** The pipeline's logic is pure functions over values: the current time, the last run and the configuration enter at the edge as values, and the core returns results and decisions (the window to process, whether to send a heartbeat) that the shell acts on. The shell holds all I/O: the engine, the network and the platform. The SQL still runs on DuckDB in the shell, unchanged, so tests run it on the real engine. B1 scores 475 of 500: it keeps the failure paths, time and entry points testable as values (C1, C2, C4) at a cost of one extra concept (C6).

**Evolution rule:** a driven port with a fake (B2) is introduced for one collaborator only when external I/O must happen mid-flow, and cannot wait for the shell, such as reading a paginated external API with retries while processing. A port is justified by two real implementations, or by a real one that is slow, non-deterministic or external and that a test must avoid; a fake of the engine never qualifies.

What would change it:

- External I/O that must happen mid-flow: apply the evolution rule to that collaborator only; the rest stays B1.
- A second engine, or business rules in Python that dominate the SQL: reopen D1.
- A new source loaded from static files, or a change of platform: neither changes D1, since both stay at the edge.

Options rejected, and how robust the result is:

- **B2** (450): it wins nothing over B1 while no I/O happens mid-flow; the 25-point gap is all C6. Moving from B1 to B2 is a small, reversible change, which the evolution rule covers.
- **A** (375): it leaves the clock and the heartbeat inside the logic and lets each entry point build its own sequence. B1 still leads with C6 weighted at 40.
- **C** (355): the SQL moves into the adapter, so the core stays almost empty and each operation touches four places. It stays last with C6 weighted at 0.

Options:

- **A. Thin platform wrapper:** the current [ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md): inward dependencies, no interfaces.
- **B1. Functional core, imperative shell:** pure functions take values (such as the current time) and return values or decisions; an outer shell performs all I/O. No interfaces.
- **B2. B1 with selective driven ports:** interfaces only for external I/O that happens mid-flow (such as the clock or a notifier), with fakes in tests.
- **C. Full ports and adapters (hexagonal):** every external system, the engine and storage included, behind a port.

**Needs.** N7 was withdrawn: historical statistical analysis reads gold outside the pipeline ([Out of scope](#13-out-of-scope)).

| N | The architecture must let | Origin |
|---|---|---|
| N1 | Failure behaviour (retries, alert, heartbeat) be tested without the platform or the network | [d002](../designs/d002-requirements.md#requirements) R8, R23; [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) |
| N2 | Time-dependent logic (catch-up since the last run, Europe/Madrid hour and day boundaries) be tested deterministically | R11, R12; [ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md) |
| N3 | The real SQL be tested on the real engine | R13, R19; [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md) |
| N4 | A change of execution platform touch only the edge | [ADR-0027](../decisions/0027-modal-as-execution-platform.md) |
| N5 | Adding a data quality rule or an observability metric be cheap | Q2, R7, R14; [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), [ADR-0043](../decisions/0043-lineage-at-four-levels.md) |
| N6 | Adding the load of a new source, one-off or recurring, leave the station flow untouched | Owner goal, no requirement |
| N8 | One person understand and maintain the structure | Single developer ([ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md) › Context) |
| N9 | Credentials enter only at the edge and never reach logs | R22, R25 |
| N10 | The scheduled run, the history load and the rebuild be the same operation over a different window, with no duplicated logic | R5, R11, R13; functional data engineering (Beauchemin) |

**Hard cuts.** All four options pass them; they set the floor the chosen one keeps.

| K | Cut | From |
|---|---|---|
| K1 | The real SQL is tested on the real engine | N3 |
| K2 | The logic is imported and tested without the platform's SDK | N1, N4 |
| K3 | Credentials enter only at the edge | N9 |

**Criteria.** C6 carries the highest weight so that more structure does not win on hypothetical changes alone.

| C | Criterion | From | Weight |
|---|---|---|---|
| C1 | Failure paths testable without the network | N1 | 20 |
| C2 | Determinism with respect to time | N2 | 15 |
| C3 | Cost of adding a quality rule or a metric | N5 | 15 |
| C4 | One operation for every entry point | N10 | 15 |
| C5 | Cost of a change: new source or platform | N4, N6 | 10 |
| C6 | Simplicity: concepts to learn and files touched per new operation | N8 | 25 |

**Anchors.** Fixed before scoring; scores 2 and 4 sit between two anchors and cite the fact that places them.

| C | 1 | 3 | 5 |
|---|---|---|---|
| C1 | A failure path is tested only with the real network or a running service | Tested without the network, but by patching a module-level call | Every failure branch is tested without the network and without patching globals: an assert on a returned value, or a fake passed as an argument |
| C2 | The logic reads the system clock inside; tests must freeze global time | The current time can be overridden in some places (optional parameter or environment variable) | The current time enters only at the edge, as a value; every window is computed by a pure function |
| C3 | 4 or more files (class, registration, adapter, tests) | 2–3 files | One entry (a SQL file or a row in a list) and its test case |
| C4 | Each entry point has its own sequence of logic | Shared functions, but each entry point assembles the sequence | One function over a window; entry points only compute the window and call it |
| C5 | The platform or the new source touches core modules | Touches the edge and one core module | Only new edge modules or SQL models are added; the core is unchanged |
| C6 | 4 or more concepts beyond functions and modules (ports, adapters, composition root, fakes) and 4 or more files per new operation | 2–3 extra concepts, 2–3 files | Only functions and modules, 1–2 files per new operation |

**Scores.**

| C (weight) | A | B1 | B2 | C |
|---|---|---|---|---|
| C1 (20) | 3: the package sends the heartbeat itself ([s012 › D5](s012-execution-target.md#d5-pipeline-logs)), so "no heartbeat on failure" needs a patched HTTP call | 5: the heartbeat decision is a returned value | 5: a fake notifier passed as an argument | 5: as B2 |
| C2 (15) | 2: nothing fixes how the time enters; it is read inside and overridden case by case | 5: the time enters at the edge; the window is a pure function of it and the last run | 5: a clock port with a fake | 5: as B2 |
| C3 (15) | 5: one SQL file or list row and its test case | 5: as A | 5: rules are SQL and need no port | 2: the SQL lives in the adapter; each operation touches the port, the real adapter, the fake and their tests ([ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md) › Cost compared) |
| C4 (15) | 3: one entry point; the history load and the rebuild assemble their own sequence | 5: one operation over a window; entry points only compute it | 5: as B1 | 5: one shared use case |
| C5 (10) | 4: a platform change touches the edge only; a recurring source mixes HTTP and logic in the package | 5: a new read at the edge and a pure function that interprets it | 5: a new adapter | 5: a new adapter |
| C6 (25) | 5: no extra concept; 1–2 files per operation | 4: one extra concept (core and shell exchange values); 2 files per operation | 3: ports, adapters, fakes and their wiring; 2–4 files per operation | 1: four or more concepts; 7 files in the skeleton, 4 or more per operation |
| **Total (of 500)** | **375** | **475** | **450** | **355** |

Facts on the patterns from the web research of 2026-11-16 ([Sources](#3-sources)): no source recommends a fake of a SQL engine, and dbt tests SQL by running it on fixtures; an engine adapter is justified by many engines, as in dbt; functional data engineering makes every task a pure, idempotent function over a partition.

#### D2. Collaborators at the edge, and no driven ports

No collaborator needs a driven port today: each one's I/O can wait for the shell, before or after the core, so it enters the core as a value or leaves it as a returned decision. The one exception is logging, which happens mid-flow by nature: the core logs through Python's standard `logging`, and the shell configures its handlers at start-up, so tests capture logs with pytest's `caplog`. `logging` already separates the call from its destination, which is the port-and-adapter split, so no own interface is added.

What would change it: a collaborator whose I/O must happen mid-flow, such as a recurring external API read page by page with retries, takes a driven port under D1's evolution rule; the others stay as they are.

Options rejected: for logging, the core returning a list of events for the shell to write; a run that breaks mid-flow loses the events before the failure, the ones most needed, and it reimplements what `logging` does.

| Collaborator | When its I/O happens | In the core |
|---|---|---|
| Clock | Start | The current time, as a value |
| Last run, for the catch-up ([ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md)) | Start | Read by the shell, passed as a value; the core computes the window |
| Configuration and credentials | Start | One configuration value (D4) |
| Engine and storage | During the run | None: the shell runs the SQL on the location the configuration names; tests use a local path (D1) |
| Heartbeat ([ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md)) | End | Returns whether to send it and what |
| Published file ([ADR-0033](../decisions/0033-data-published-by-redeploying-static-assets.md)) | End | Returns what is published |
| Lineage records ([ADR-0043](../decisions/0043-lineage-at-four-levels.md)) | End | Returns the records |
| Retries (R23) | Around the run | None: the shell retries; the core is idempotent (N10) |
| Logs ([ADR-0036](../decisions/0036-log-convention-across-components.md)) | During the run | Logs through `logging`; the shell sets the handlers |

#### D3. Runtime rules as SQL files run by one runner

Each runtime rule of the [quality catalog](../data-quality.md) is one SQL file named after its ID that returns the rows breaking it, as in dbt's singular data tests; the catalog stays the rules' source ([d005 › D29](../designs/d005-data-model.md#d29-data-contract-of-the-model)), and the file cites it. One generic runner in the shell runs every rule on the tables just built and on the published file. The core receives the results as values and turns them into a verdict (fail, warn or pass) with the severity of [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), as a pure function. Adding a rule is one SQL file and its test case. Quality indicators need nothing apart: they are gold models like any other.

This fixes the shape of a rule in the code, not which rules exist, when they run within a run, or a test tool: a tool's file would be derived from the catalog (d005 › D29).

Options rejected: a Python list with each rule's SQL inline; it saves a file per rule but keeps SQL in strings, without SQL highlighting or lint, and apart from how models live ([ADR-0025](../decisions/0025-sql-models-directed-by-python.md)).

#### D4. Configuration as one typed value, read at the edge

Configuration and credentials arrive as environment variables, set by the platform's secret store (R25), as Twelve-Factor's Config asks. One function in the shell, and only that one, reads the environment and returns a frozen dataclass of the standard library; the core receives it as a value, and tests build it directly with no environment. Each credential is wrapped in a type whose text form is masked, so a log or a printed configuration never shows it (R22). A missing variable fails at start-up. This narrows [ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md)'s rule 3, from the package to that one function.

What would change it: configuration that grows in number of variables, holds non-trivial types or becomes nested moves to `pydantic-settings`; the change stays in the configuration module, since the rest of the code sees only the value.

Options rejected: `pydantic-settings` now; its type coercion and validation have little to do with a handful of text variables, and it adds two dependencies to pin and maintain ([ADR-0017](../decisions/0017-dependencies-locked-per-component.md)).

#### D5. Architecture rules checked in CI with import-linter

The rules of D1, D2 and D4 are checked in CI, so a departure fails the PR instead of waiting for review. Import contracts use import-linter, the reference tool for import rules in Python, declared in `pyproject.toml` and run by the pipeline's CI job as a development dependency. The core and the shell are separate subpackages of the pipeline package, and the platform module lives outside the package; their names are chosen when T060.1 creates them. These boundaries are what makes the rules checkable: an import contract holds between modules, so a module mixing core and shell could not satisfy rule 2, and the package could not satisfy rules 1 and 5 if the module importing the platform's SDK lived inside it.

| # | Rule | Check |
|---|---|---|
| 1 | The package never imports the platform's SDK | `forbidden` contract |
| 2 | The core never imports the engine or an HTTP client | `forbidden` contract |
| 3 | Dependencies point from the shell to the core, never back | `layers` contract |
| 4 | The platform module never imports the engine | `forbidden` contract |
| 5 | The pipeline starts without the platform's SDK installed | A CI test |
| 6 | Only the configuration function reads the environment (D4) | Review: an import check cannot tell this use of `os` from others |

Rules 1, 4 and 5 carry over [ADR-0029](../decisions/archive/0029-pipeline-code-architecture.md)'s rules 1, 2 and 4; rules 2 and 3 are new with B1. A driven port added under D1's evolution rule breaks no contract; the engine imported into the core does.

Not verified: a `forbidden` contract on an external package such as `duckdb` needs `include_external_packages` set, as summarised from import-linter's documentation; T060.1 confirms it when it configures the contracts.

Options rejected: PyTestArch, the same rules as pytest tests; it needs no extra CI step but is less established, and the rules become code rather than declarations.

### 1.3 Out of scope

- The module names, the rest of the package's layout and where SQL models, rules and tests live — T060.1
- When runtime rules run within a run, and whether a test tool replaces the runner (D3) — T060
- Historical statistical analysis and environmental data, read from gold outside the pipeline — T067

## 2. Conclusion

### 2.1 Verdict

The pipeline's code follows a functional core with an imperative shell (D1): the shell holds all I/O, the engine included, and the core takes values and returns decisions. No driven port exists today, and one is added only under D1's evolution rule. Its rules (D2–D5) are checked in CI with import-linter; it replaces ADR-0029's thin platform wrapper and keeps its rules.

### 2.2 Not verified

- `include_external_packages` is needed for a `forbidden` contract on `duckdb` (D5) — rule 2 cannot be expressed that way — T060.1 checks it when it configures the contracts; if it fails, PyTestArch, D5's rejected option.
- The scores come from code skeletons, not from built code — B1 costs more than estimated — T060.1 is its first real use, and D1 states what reopens it.
- Functional data engineering was read through summaries, as its page refused automated access — a nuance cited wrongly — it supports N10 only and decides no score.

### 2.3 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | The names of the core, the shell and the platform module, and the rest of the package's layout | D5, [Out of scope](#13-out-of-scope) | [d007](../designs/d007-pipeline-design.md) › T060.1 |
| P2 | Import contracts for rules 1–4, the CI test for rule 5, and the `include_external_packages` check | D5 | d007 › T060.1 |
| P3 | Each run is one operation over a window that overwrites its output (idempotent), shared by the scheduled run, the history load and the rebuild | D1 (N10) | d007 › T060.1 |
| P4 | Runtime rules as SQL files with one runner and the verdict in the core | D3 | d007 › T060.1 for its first rules; T060 for the rest |

### 2.4 Records

| Output | From | Destination | Commit |
|---|---|---|---|
| ADR-0046, pipeline code architecture: functional core with imperative shell; ADR-0029 superseded and archived | D1–D5 | `docs/decisions/` | Done |
| Platform separation input re-pointed to ADR-0046 | D5 | [d007 › Carried-over inputs](../designs/d007-pipeline-design.md#carried-over-inputs) | Done |
| Lines citing ADR-0029 | D1 | `docs/architecture.md` and the links to ADR-0029, in ADR-0046's commit | Done |
| T067, historical analysis of bike use with environmental data | Out of scope | GitHub Issues | Done |
| T068, detect operator rebalancing | Raised while framing | GitHub Issues | Done |

## 3. Sources

Web research of 2026-11-16, for D1:

- Hexagonal architecture, Alistair Cockburn: <https://alistair.cockburn.us/hexagonal-architecture/>
- Functional core, imperative shell, Gary Bernhardt: <https://www.destroyallsoftware.com/screencasts/catalog/functional-core-imperative-shell>
- Functional data engineering, Maxime Beauchemin (2018; read through summaries, the page refused automated access): <https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a>
- Don't mock types you don't own, Google Testing Blog: <https://testing.googleblog.com/2020/07/testing-on-toilet-dont-mock-types-you.html>
- dbt unit tests: <https://docs.getdbt.com/docs/build/unit-tests>
- dbt adapters, why they exist: <https://docs.getdbt.com/guides/dbt-ecosystem/adapter-development/1-what-are-adapters>
- Dagster, testing assets with mocked resources: <https://dagster.io/docs/guides/test/unit-testing-assets-and-ops>
- Architecture Patterns with Python (Percival and Gregory, O'Reilly 2020): <https://www.oreilly.com/library/view/architecture-patterns-with/9781492052197/preface01.html>
- import-linter contract types: <https://import-linter.readthedocs.io/en/stable/contract_types/>
