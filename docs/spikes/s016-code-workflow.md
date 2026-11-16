<!--
Spike doc template. A spike is a time-boxed investigation of one task: it reaches the decisions a task needs, by analysis where possible and with evidence only where an unknown would change the choice. Its output is knowledge (decisions, answers, a verdict, inputs for designs and ADRs); its code is throwaway and lives in spikes/<name>/.
Blocks: Questions (what we need to know), Method (how we find out), Steps, Findings (filled during execution), Conclusion (filled after the last step).
Sections marked Optional are kept only when they apply.
-->

# Spike: Code workflow for the pipeline

- **Task:** T069
- **ADRs:** [ADR-0013](../decisions/0013-github-flow-with-rebase-merge.md), [ADR-0014](../decisions/0014-ci-test-layers.md), [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md)
- **Code:** `spikes/code-workflow/`

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

The pipeline (T060.1 onwards) is the first large codebase in the project, built by one developer with Claude Code. This spike is a gap analysis of the code workflow in `.claude/` against reference practices (Anthropic's Claude Code best practices, Google's code review practices, shift-left testing), keeping a gap only when its value outweighs its upkeep for one developer. It decides code review (D1), automatic checks (D2) and any further gap (D3), in that order. All three are settled by documents and arithmetic, so the spike has no run. It builds on the pipeline architecture of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md).

### 1.2 Decided at framing

#### D1. Code review

Code is reviewed at review points planned in the design, following risk-based review and Google's guidance on small changes. Each design step carries a **Review** field (`yes`, with its reason, or `no`), set when the steps are written and checked in the design's steps review; a point goes where logic carries risk (time handling, aggregations, parsing) or after about 400 changed lines since the previous one, and the last step is always a point. At a point, the implementing session runs the built-in `/code-review` at `low` effort, without `--fix`, over the changes since the previous point; it runs as a background subagent with its own context, and its findings go into the Change report, where the owner decides the fixes, applied within the step's Scope and taken in the step's commit. Conformance to the design stays in the end-of-task review (`review.md`). The exact `/code-review` target for "since the previous point, uncommitted changes included" is set in the edit to `/implement`.

- **Would change it:** bugs that a review point should have caught reach the PR, or review points end up on nearly every step: move to a review on every step (option D below).
- **Would not change it:** a task diff of any size, since the points bound each review, not the task.

Rejected: a review of the whole task (A, B), because a pipeline task can exceed the size a review handles well (K3); a review on every step (C, D), because it asks the owner to decide findings at every step for little gain on steps with no risk. E beats D by 0.15 on owner effort only; with a lower weight on C5 (5 instead of 15) the order holds.

Needs:

| N | Need | Source |
|---|---|---|
| N1 | Catch correctness defects (logic, edge cases, time handling) before merge | Gap: [implement › review](../../.claude/skills/implement/review.md) checks conformance to the design only |
| N2 | A reviewer independent of the context that wrote the code | Anthropic's Claude Code best practices; already in `review.md` |
| N3 | Moderate cost for one developer: few extra sessions, little owner effort, little context used in the implementing session | Owner requirement of moderate complexity; Anthropic's context management practice |
| N4 | Fit with the current flow: steps committed by the owner, PRs by rebase merge, findings by severity | [ADR-0013](../decisions/0013-github-flow-with-rebase-merge.md), `review.md` |
| N5 | Findings early enough to be cheap to fix | Shift-left testing |

Hard cuts:

- **K1 (N2):** the reviewer does not share the context of the session that wrote the code.
- **K2 (N4):** the reviewer reports and applies nothing on its own; the owner decides the fixes and makes every commit.
- **K3 (N1, N5):** each review covers a small change, bounded where the steps are known; about 400 changed lines as a guide. Detection falls beyond about 400 lines per review (SmartBear/Cisco, second-hand) and Google calls 1,000 lines "usually too large".

Criteria:

| C | Criterion | Need | Weight |
|---|---|---|---|
| C1 | Detection depth: finds logic defects and edge cases, not only conformance | N1 | 30 |
| C2 | Owner effort: extra sessions and manual actions per task | N3 | 20 |
| C3 | Context used in the implementing session | N3 | 15 |
| C4 | Timeliness: how much code accumulates before a finding | N5 | 20 |
| C5 | Fit and upkeep: new files to maintain in `.claude/`, fit with steps and PRs | N4, N3 | 15 |

Anchors:

| C | 1 | 3 | 5 |
|---|---|---|---|
| C1 | Conformance to the design only (checklist) | Reviews the code with a generic quality checklist | Reviews the logic against the Spec, with a dedicated bug pass and each finding verified |
| C2 | One owner action per step | One extra session per task | No new action: runs inside an existing session |
| C3 | Loads the full diff and findings into the implementing session | A compact summary of findings only | None: runs outside that session |
| C4 | At the end of the task, every step done (about 5–10) | Mid-task (about 3 steps, one Produce session) | After each step |
| C5 | New files and a change to the step or PR flow | An edit to an existing file | No files to maintain: a built-in tool |

Options:

- **A.** A code-quality checklist added to `review.md`, end of task.
- **B.** `/code-review` over the branch diff in the end-of-task review session.
- **C.** A custom read-only reviewer subagent that compares each step with the Spec.
- **D.** `/code-review` over each step's diff, run by `/implement`.
- **E.** `/code-review` at review points planned in the design.

All pass K1 (a background subagent or fresh session does not see the conversation) and K2 (`/code-review` without `--fix` only reports; C is read-only). A and B fail K3: they review the whole task.

| C (weight) | C | D | E |
|---|---|---|---|
| C1 (30) | 4: against the Spec; no verification of findings | 4: dedicated bug pass; no Spec, finding verification not documented | 4: as D |
| C2 (20) | 2: findings to decide at every step | 2: as C | 4: findings only at planned points |
| C3 (15) | 3: only a summary returns | 3: findings return from a background subagent | 3: as D |
| C4 (20) | 5: every step | 5: every step | 4: within the bound, by design |
| C5 (15) | 1: a new agent file and a change to the step | 3: built-in, one change to the step | 3: built-in; a field in the design template and one change to the step |
| **Total** | 3.20 | 3.50 | **3.65** |

Sensitivity: with C5 at 5, E 3.72, D 3.56, C 3.44.

Sources: [Claude Code › Local code review](https://code.claude.com/docs/en/code-review-local), [Claude Code › Subagents](https://code.claude.com/docs/en/sub-agents), [Google › What to look for](https://google.github.io/eng-practices/review/reviewer/looking-for.html), [Google › Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html), [SmartBear › Best practices for peer code review](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/).

#### D2. Automatic checks

Python code is checked in three layers, following shift-left: each check runs in the earliest layer where it is fast enough. Rules with no exceptions sit in deterministic mechanisms (hooks, CI), as Anthropic's best practices advise.

| Layer | When | What runs | Purpose |
|---|---|---|---|
| Hook | After each edit of a `.py` file | `ruff format` and `ruff check --fix` on that file; what remains goes to stderr with exit 2, so Claude sees it | Claude fixes format and lint at once; neither reaches the diff or the review (D1) |
| Step Check | Before a step is marked ✅ | `scripts/check-pipeline.sh`: ruff over the component, mypy, `lint-imports`, pytest; stops at the first failure | Full verification before the owner's commit |
| CI | Every push to a PR | The same script, in the pipeline job | Enforces it on every change, edits outside Claude included |

`uv run pytest` stays the test command inside a step's red-green loop; the script is the single entry point for "ready to commit", in the same pattern as the `docs` job and `scripts/lint-docs.sh`. Each tool starts from its default configuration: ruff's default rule set, mypy in standard mode (not `strict`), import-linter with the contracts of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md) only. A rule or a stricter mode is added only when a bug or a review finding shows it would have caught something.

The configuration (`pyproject.toml`), the script, the hook and the CI job are created by the pipeline's first design (T060.1), so the hook comes with the ruff configuration it runs. This covers T024, which closes; the Capture Worker (JS) gets no hook while it has no active development.

- **Would change it:** the hook slows editing or its output is noise: drop it and keep the Step Check and CI.

Rejected:

- **No hook, Step Check and CI only:** nothing to maintain, but format and lint errors surface only at the end of a step, adding iterations and reformatting diffs; the hook costs one script and ruff runs in well under a second per file.
- **pyright instead of mypy:** reported as faster, with no reliable benchmark at this project's size; mypy is the reference implementation of Python's type system (PEP 484) and the most documented, and at this size the speed gap is seconds.

Sources: [Claude Code › Hooks](https://code.claude.com/docs/en/hooks), [Claude Code › Best practices](https://code.claude.com/docs/en/best-practices), [Ruff](https://docs.astral.sh/ruff/), [Import Linter › Caching](https://import-linter.readthedocs.io/en/stable/caching/).

#### D3. Further gaps

The rest of `.claude/` is compared with Anthropic's Claude Code best practices; a gap is closed only when its value outweighs its upkeep for one developer.

- **Code rules for the pipeline.** `python.md` gains two short sections: Tooling, from D2, and Pipeline architecture, one line per rule of [ADR-0046](../decisions/0046-functional-core-imperative-shell-for-the-pipeline.md) and [s015](s015-pipeline-code-architecture.md) that constrains code, each citing its source. An ADR is not loaded into a session on its own, and Anthropic's practice is that rules hold what Claude cannot infer from the code. Rejected: citing ADR-0046 in every step's Reads, which depends on no step omitting it. SQL rules wait for the first SQL files: the design of T060.1 sets their layout and conventions.
- **ADRs carried into rules.** Most ADRs reach the code through the design that reads them and turns them into its Spec, or through a module built once that later code follows. A rule in `.claude/rules/` is kept for a convention that applies to every edit in a path, that no tool enforces and that the code does not show; such an ADR adds a one-line rule citing it to the rule file where it applies, in the same commit as the ADR. `adr.md` gains this in Lifecycle. An audit of ADR-0036 to ADR-0046 against this criterion leaves only ADR-0046, whose dependency rules import-linter enforces (D2) and whose other code rules go to `python.md`, as in the item above; ADRs before 0036 are not audited, with no evidence of a gap. Rejected: a check in the reviews, which comes later and depends on someone remembering it.
- **Security review.** When a task touches secrets, permissions or external input, the Review field of its last step reads `yes, security`, with its reason, and the implementing session runs the built-in `/security-review` with `/code-review`, in the same way as D1. One review mechanism, set where the risk is known. Rejected: a checklist item in `review.md`, which keeps that session on conformance only.

Practices already covered or not worth their cost:

| Practice | Outcome | Reason |
|---|---|---|
| A check in a Stop hook at the end of each turn | Not adopted | It would also run in spike and design sessions; the Step Check covers sessions that write code |
| Plan mode; explore, plan, then code | Covered | `/design` and `/spike` |
| Context management (`/clear`, short sessions) | Covered | One session per skill, about 3 steps per session, a stop past half context |
| Worktrees, Claude in parallel | Not adopted | One developer working sequentially |
| Claude in CI (headless) | Not adopted | A cost per PR; D1 already reviews locally |
| Design review against reference practices | No change beyond D1's Review field | No evidence of a gap; design reviews have worked |

<!-- In this order, so the reader finds what matters first:
1. The decision and why, in one short paragraph. If it depends on a Q, name it and what happens if its Gate fails.
2. What would change it, and what would not, each with the action to take. Only when a later event could reopen it.
3. The options rejected and how robust the result is.
4. The evaluation behind it: the table or weighted matrix (needs, cuts, anchors and scores) if one was used. A security decision lists its threats in a table: `| # | Threat (STRIDE) | Impact | Control | Requirement |`, with IDs `TH1`, `TH2`… per document. -->

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

-
