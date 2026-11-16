<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Pipeline code architecture

- **Task:** T064
- **ADRs:** [ADR-0029](../decisions/0029-pipeline-code-architecture.md) (under revision: this spike replaces it)
- **Code:** `spikes/pipeline-code-architecture/`

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decisions this spike takes, which of them depend on evidence and why, and the spikes or designs it builds on. -->

### 1.2 Decided at framing

#### D1. Pipeline code architecture style

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

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

- **A. Thin platform wrapper:** the current [ADR-0029](../decisions/0029-pipeline-code-architecture.md): inward dependencies, no interfaces.
- **B1. Functional core, imperative shell:** pure functions take values (such as the current time) and return values or decisions; an outer shell performs all I/O. No interfaces.
- **B2. B1 with selective driven ports:** interfaces only for external I/O that happens mid-flow (such as the clock or a notifier), with fakes in tests.
- **C. Full ports and adapters (hexagonal):** every external system, the engine and storage included, behind a port.

**Needs.** N7 was withdrawn: historical statistical analysis reads gold outside the pipeline (Out of scope).

| N | The architecture must let | Origin |
|---|---|---|
| N1 | Failure behaviour (retries, alert, heartbeat) be tested without the platform or the network | [d002](../designs/d002-requirements.md#requirements) R8, R23; [ADR-0031](../decisions/0031-heartbeat-alerts-for-the-pipeline.md) |
| N2 | Time-dependent logic (catch-up since the last run, Europe/Madrid hour and day boundaries) be tested deterministically | R11, R12; [ADR-0041](../decisions/0041-utc-timestamps-local-calendar-keys.md), [ADR-0045](../decisions/0045-catch-up-in-bounded-batches.md) |
| N3 | The real SQL be tested on the real engine | R13, R19; [ADR-0024](../decisions/0024-duckdb-as-processing-engine.md), [ADR-0025](../decisions/0025-sql-models-directed-by-python.md) |
| N4 | A change of execution platform touch only the edge | [ADR-0027](../decisions/0027-modal-as-execution-platform.md) |
| N5 | Adding a data quality rule or an observability metric be cheap | Q2, R7, R14; [ADR-0042](../decisions/0042-data-quality-classes-and-severity.md), [ADR-0043](../decisions/0043-lineage-at-four-levels.md) |
| N6 | Adding the load of a new source, one-off or recurring, leave the station flow untouched | Owner goal, no requirement |
| N8 | One person understand and maintain the structure | Single developer ([ADR-0029](../decisions/0029-pipeline-code-architecture.md) › Context) |
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
| C3 (15) | 5: one SQL file or list row and its test case | 5: as A | 5: rules are SQL and need no port | 2: the SQL lives in the adapter; each operation touches the port, the real adapter, the fake and their tests ([ADR-0029](../decisions/0029-pipeline-code-architecture.md) › Cost compared) |
| C4 (15) | 3: one entry point; the history load and the rebuild assemble their own sequence | 5: one operation over a window; entry points only compute it | 5: as B1 | 5: one shared use case |
| C5 (10) | 4: a platform change touches the edge only; a recurring source mixes HTTP and logic in the package | 5: a new read at the edge and a pure function that interprets it | 5: a new adapter | 5: a new adapter |
| C6 (25) | 5: no extra concept; 1–2 files per operation | 4: one extra concept (core and shell exchange values); 2 files per operation | 3: ports, adapters, fakes and their wiring; 2–4 files per operation | 1: four or more concepts; 7 files in the skeleton, 4 or more per operation |
| **Total (of 500)** | **375** | **475** | **450** | **355** |

Facts on the patterns from the web research of 2026-11-16 (§ 6. Sources): no source recommends a fake of a SQL engine, and dbt tests SQL by running it on fixtures; an engine adapter is justified by many engines, as in dbt; functional data engineering makes every task a pure, idempotent function over a partition.

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

### 1.3 Questions

<!-- The main question, answered by the Verdict. Then Q1..Qn, each answerable with evidence.
"Observe only": things to note during the run with no dedicated effort. -->

Main question: `<one sentence>`

- **Q1.** `<question>`
- **Observe only:** `<item>`

### 1.4 Exit criteria

<!-- Fixed before the first run; a later change is recorded in the Decision log.
Derived from the standard that applies to this kind of question, named in the first line: e.g. DAMA data quality dimensions for a data source, a weighted decision matrix for a technology choice.
Each criterion is measurable and says whether it is a hard cut or a guide. The timebox says what ends the run. State whether one variant meeting the criteria is enough. -->

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

<!-- Optional. What someone could expect this spike to answer and it will not, each item pointing to the task that covers it. -->

- `<item>` — TNNN

### 1.6 Open questions

<!-- Optional. Unresolved questions about what to find out. Questions about how belong to Method. -->

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

-

#### `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git. The README is always included. -->

```text
spikes/<name>/
├── README.md        Question, setup and commands, what each script does, link to the report
└── <file>           <purpose>
```

## 3. Steps
<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.5 Production inputs

<!-- Optional. What a later task must take into account when it builds, from any part of the spike: done when that task runs. Each one has a Destination: a design (with its task) or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | `<e.g. D1, #2, F3>` | |

### 5.6 Records

<!-- Documents this spike updates before it closes: ADRs from Decided at framing (each in its own commit), architecture, requirements, source cards and new tasks agreed with the owner. A decision that updates no document has no row. Commit: "Done", or "Pending" until delivered; the spike closes when every row is Done. Production inputs are not repeated here. -->

| Output | From | Destination | Commit |
|---|---|---|---|
| `<ADR, requirement, source card or task>` | `<e.g. D1, F3>` | `<document and section>` | `<Done, or Pending>` |

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

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
