<!--
Spike doc template. A spike is a time-boxed investigation of one task in docs/tasks.md: it answers questions the project cannot decide without evidence. Its output is knowledge (answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled in the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: `<title>`

- **Task:** TNNN
- **ADRs:** `<ADRs this spike must respect, or "none">`
- **Code:** `spikes/<name>/`

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first and the last step executed.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

<!-- 2–4 sentences: the decision this spike unblocks, why it cannot be taken without evidence, and the spikes or designs it builds on. -->

### 1.2 Decided at framing

#### 1.2.N D`<N>` Title of decision `<N>`

<!-- Description of description N -->

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

<!-- Optional. What someone could expect this spike to answer and it will not. -->

- `<item>`

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

#### 2.1.2 `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), or `<phase> review` when decided while reviewing that phase.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git (ADR-0009). The README is always included. -->

```text
spikes/<name>/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
```

## 3. Steps
<!-- Each step is one reviewable result and one commit, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- R: the requirements the step implements or tests, or —.
- Commit: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>.
The last step is the Conclusion. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **R:** R1, R3 (or —)
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components, the files created or changed (code, tests, docs), and the tests from the Test plan that cover it. A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

### Step N — Conclusion

<!-- 
Same structure as the example before before but: 
- Scope contains: 
  1. Conclusion
  2. the destination of every Production input in this doc;
  3. How we got here in the README
  4. tear-down of what does not outlive the spike.
- Reads: 1. Questions, 2. Method › Decision log, 4. Findings
- Check: every Q answered; every exit criterion has a result; every P has a destination
- Commit: `conclude spike sNNN` following the Git conventions in CLAUDE.md.
-->

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

**F1. `<one-line statement>`** (step N, YYYY-MM-DD, `<source of evidence>`)

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

### 4.1 Production inputs

<!-- Points worth taking to production that are not fixed in the spike code. Added in the step where they are detected, by Claude or the owner. The Destination is set in the Conclusion: a design (with its task) or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | Step N · FN | |

## 5. Conclusion

<!-- Filled in the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Decisions to record

<!-- Optional: If some arch decisions was taken at the begining of the spike -->

| D | Outcome | Why |
|---|---|---|

### 5.5 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.6 Follow-ups

<!-- ADRs to write (each in its own commit) and new tasks agreed with the owner. Production inputs are not repeated here. -->

- `<ADR or task>`

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

-
