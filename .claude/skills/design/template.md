<!--
Design doc template. A design doc is the working document of one task in docs/tasks.md: Spec (what and why), Plan (how), Implementation (steps), Close (what was delivered).
It is detailed enough that Code can implement it without making design decisions.
Sections marked Optional are kept only when they apply.
-->

# Design: <title>

- **Task:** TNNN
- **ADRs:** <ADRs this design must respect, or "none">

## Status

<!-- State: Draft 📝 · Ready for implementation 🎬 · In progress 🔄 · Complete ✅.
Phase: the blocks and reviews completed.
Current step: the step being implemented, or —. -->

- State: Draft 📝
- Phase: [ ] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

## 1. Spec — what and why

<!-- The problem and the expected behaviour, not the solution. External systems and their data (feeds, fields) may be named; our own choices (formats, libraries, files, schemas) belong to the Plan. -->

### Context

<!-- 2–4 sentences: why this exists, what the owner wants, and which design it extends, if any. For a correction: current vs expected behaviour and how to reproduce it. -->

### Done when

<!-- The first three lines are the general closing rule; the first one goes if there are no Requirements. Below them, only what they do not cover: operational actions, checks on real data, understanding. -->

- Every requirement passes its test.
- Every item in File layout is delivered.
- Every TODO citing this task is resolved or re-pointed.
- <extra condition>

### Requirements

<!-- Optional. The acceptance criteria, cited by number in the Test plan and the steps.
One behaviour per requirement, verifiable, with a measurable threshold where one applies. Written in EARS:
- Ubiquitous: The <system> shall <response>.
- Event: When <trigger>, the <system> shall <response>.
- State: While <state>, the <system> shall <response>.
- Unwanted: If <condition>, then the <system> shall <response>.
- Optional: Where <feature is included>, the <system> shall <response>.
Only requirements specific to this task; project-wide rules (CLAUDE.md, ADRs) are not repeated. -->

- **R1** <EARS statement>

### Out of scope

<!-- Optional. What someone could expect and will not be done, each item pointing to the task that covers it. -->

- <item> — TNNN

### Open questions

<!-- Optional. Unresolved questions about the what. Questions about the how are Plan decisions. -->

| Question | Notes |
|---|---|
| | |

## 2. Plan — how

### Options considered

<!-- Optional. One subsection per alternative weighed, rejected ones included. -->

#### Option A — <name> (chosen)

<2–3 sentences.>

**Pros:**
**Cons:**

#### Option B — <name> (rejected)

<2–3 sentences.>

**Pros:**
**Cons:** <including the reason for rejection, in one sentence>

### Decision summary

<!-- One row per concern: the decision in one sentence, naming the standard it follows or the ADR for the deviation, and the requirements it covers. -->

| Concern | Decision | R |
|---|---|---|
| | | |

### Architecture

<!-- Optional. One diagram and 2–3 sentences. -->

### File layout

<!-- Every file and folder the task creates or modifies, documents included, as a tree: (new) or (modified), and its purpose or change in one line. A task that adds a component also lists its CI job in `.github/workflows/ci.yml` (recipe in `.claude/rules/ci.md`). -->

```
<path>/
└── <file>      (new)        <purpose>
```

### Components

<!-- Optional. One subsection per component. The contract is exact, in the component's own language, never pseudocode. -->

#### <ComponentName>

- **Responsibility:** <one sentence>
- **Location:** `path/to/file`
- **Contract:**

```python
```

### Test plan

<!-- Optional. Every requirement has at least one test, at the lowest level that can verify it. -->

| R | Test concept | Level |
|---|---|---|
| R1 | | unit / integration / e2e |

### Breaking changes

<!-- Optional. Shared models or interfaces this design changes, and how their dependants are handled. -->

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### What does not change

<!-- Optional. Code or documents that must not be modified. Out of scope limits the what; this section limits the how. -->

-

## 3. Implementation

### Steps

<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md. -->

#### Step 1 — <title>

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** 
- **R:** R1, R3 (or —)

##### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

##### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

##### Check

<!-- command/s or verification with a yes/no result. -->

##### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

## 4. Close

<!-- The record of what the task delivered, for whoever opens this design later. -->

### Implemented

<!-- Component — what was delivered; tests passing. -->

### Known gaps at close

<!-- What the task leaves undone or imperfect, each with the task that covers it: requirements not fully met, File layout items not delivered, TODOs citing this task. "None" is valid. -->

- <gap> — TNNN

### Decisions taken during implementation

<!-- Decisions made after the Plan was approved: <decision> — <reason>. "None" is valid. -->
