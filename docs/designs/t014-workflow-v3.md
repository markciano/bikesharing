# Design: Workflow v3 – Align design template with SDD

- **Task:** T014
- **ADRs:** none

## Status

- State: Complete
- Current step: —
- Next: —

### Implemented

- Design template restructured into Spec, Plan, Tasks and Close blocks, with the rules in Decision summary.
- CLAUDE.md › Workflow › Phases reduced to what each phase fills and who closes it; step rules moved to the template.

### Known gaps at close

- CLAUDE.md › Code › Testing still says "acceptance criterion" instead of requirement — T011.

### Decisions taken during implementation

- Step rules live only in the template, not in CLAUDE.md, to avoid duplication.
- CLAUDE.md › Code › Testing left unchanged: testing conventions belong to T011.

## Context

The design doc already covers what spec-driven development (SDD) splits into spec, plan and tasks, but its sections mix the *what* and the *how* and cannot be filled top to bottom: acceptance criteria sit after components, Out of scope sits at the end, and the "what" has no explicit requirements. This task reorders the design template into ordered blocks (Spec → Plan → Tasks → Close) with explicit requirements, and aligns CLAUDE.md with it. It extends [t013-workflow-v2](t013-workflow-v2.md).

## Done when

- The design template follows the block structure and rules in Decision summary.
- CLAUDE.md is consistent with the new template (phases, approvals, Review).
- Every TODO citing T014 is resolved or re-pointed.

## Decision summary

| Concern | Decision |
|---|---|
| Template structure | One design doc in four ordered blocks, filled top to bottom: 1. Spec (what and why), 2. Plan (how), 3. Tasks (steps), 4. Close. Status stays at the top with State, Current step and Next only; Implemented, Known gaps and Decisions taken during implementation move to Close. |
| Spec block | Context (required) · Done when (required) · Requirements (optional, code/config only) · Out of scope (optional) · Open questions (optional, blocks approval). |
| Plan block | Options considered · Decision summary (required) · Architecture · File layout (required if files change) · Components · Test plan · Breaking changes · What does not change. |
| Approvals | Three approvals, one per block: Spec, Plan, Tasks. They are called *Approval*; *Gate* keeps its meaning of a branching point inside the steps. No new states: State stays Draft until the Tasks approval makes it Ready (🟢); Next records which approvals are done and what is pending; Current step is used only during implementation. tasks.md is unchanged. |
| Requirements | Numbered R1…, written in EARS (ubiquitous, When, While, If…then, Where), with *shall*. They are the acceptance criteria: the Acceptance criteria section is removed and the Test plan and steps cite R. |
| What the Spec may name | External systems and their data (feeds, fields) are domain and may appear; our own choices (formats, libraries, files, schemas) belong to the Plan. |
| Non-functional requirements | Only those specific to the task; project-wide rules (CLAUDE.md, ADRs) are not repeated. |
| Open questions vs options | Questions about the *what* go to Open questions; questions about the *how* are decisions and go to Options considered. |
| Traceability | Decisions and steps cite R where applicable; every R is cited by at least one test and one step. |
| Clarify | Not a new phase: it is the closing activity of Frame. Claude reviews the Spec for ambiguities and contradictions and records them as Open questions before the Spec approval. |
| Analyze | Not a new phase: it is the closing activity of the Tasks block, before the Tasks approval. Claude checks and reports: every R is cited by at least one test and one step; every File layout item is created or modified by a step; no step does anything outside the Plan; no contradiction between Spec and Plan. The template carries this checklist. |
| Affected documents | Documents changed by the task are listed in File layout as `(modified)`, each covered by a step. An unplanned document is a deviation. The "same commit" rule in CLAUDE.md applies only to changes outside a design. |
| Done when | The template pre-fills the general closing rule as fixed lines (every R passes its test; every File layout item is delivered; every TODO citing the task is resolved or re-pointed), followed by task-specific extra conditions (operational, real-data checks, understanding). Without Requirements, the first line is removed. |
| Closing rule location | Lives in the template, not in CLAUDE.md. CLAUDE.md › Review only drops its reference to acceptance criteria. |
| Naming | Keep *task* and *step*. Equivalence with SDD: task = SDD feature/change; step = SDD task. Phase 4 "Specify" is renamed "Plan". |
| Existing designs | Open designs on the current template (T006.1, T011) finish on it; the new template applies to designs created after T014 closes. |
