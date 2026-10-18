# Design: Workflow v2

- **Task:** T013
- **ADRs:** none

## Status

- State: Complete
- Current step: —
- Next: —

### Implemented

- CLAUDE.md › Workflow, Tasks, Conventions, Git conventions, Chat, Code: rules below.
- `docs/tasks.md` as a status table; `docs/designs/` with T006.1 and T011 drafts.
- `docs/templates/design-doc.md`: task header, Status lines, Check/Done columns, Gates, File layout.
- `.claude/settings.json`: Code permissions.

### Known gaps at close

- Trial of the Step protocol, Code sessions and Git autonomy — first Code step of a design (TODO in CLAUDE.md › Code › Step protocol).
- Spike report template, less rigid than the design one — no task yet.
- Project-wide layout (`src/`, `tests/`, fixtures): decided when project code is first needed.

### Decisions taken during implementation

- **Phases and steps merge.** The first CLAUDE.md draft added the step and session rules as a new section ("Steps and sessions") next to Phases. Both described the same task life cycle, the text overlapped and was hard to follow. It was restructured in five blocks:
  1. Steps live inside the phases: Specify defines them, Produce runs them; step rules sit under the Phases table.
  2. The state rule ("state lives in the working document") moved to Rules, as it applies to every phase.
  3. The task definition moved to Tasks.
  4. The remaining session rules moved to Chat › Pacing, Code › Step protocol and Conventions; the section was removed.
  5. Step protocol and Change report were de-duplicated; the Permissions section was removed (`.claude/settings.json` holds the rules; one line in Code › Change cycle says never work around them).
- **Deliverable catalog simplified.** It still said "Owner places it and commits", which contradicted Chat › Repo access (Chat writes, the owner reviews the diff). The table keeps only Deliverable | Produced by; one line below it says the owner reviews the diff and commits every deliverable. "Lives in" was removed (Project structure already holds the paths) and so was the Working note row (state lives in the working document, not the chat).
- Lesson: new rules are integrated into the existing structure, never added as a parallel section.

## Context

T006 showed that tasks were too coarse for one person working in several sittings and limited chat contexts. All pending tasks were 5+, so planning units, estimation, file layout and Code autonomy needed explicit rules before continuing.

## Done when

- Each of the owner's retrospective points and each friction TODO in CLAUDE.md › Workflow has a verdict.
- Unit of execution, stopping points, estimation and context use are defined.
- Task, backlog and design placement is decided and applied to existing tasks.
- Git and permission rules are in CLAUDE.md and `.claude/settings.json`.

## Decisions

As approved in chat, in order. CLAUDE.md holds the current rules; this is the record of what T013 decided.

- T013 has priority over all pending tasks; depends on nothing.
- Tasks stay in Markdown in the repo; GitHub Issues dropped (extra sync, Chat needs a connector).
- A1. Unit of work: Task → Steps. A task is the change the owner wants, in plain words. Its design defines every step before Code starts; a task is split when a part can be delivered and closed on its own; many steps (10+) is a signal to check, not a rule. Where a result cannot be known in advance, the design includes a planned decision gate: either the branches are written in the design, or execution stops, the result is analysed and the design is updated and approved before continuing.
- A2. Step = one reviewable result, one commit, and one check defined before the step starts, with a yes/no outcome (a test that passes, an output that exists with the expected shape, a section that answers named questions). Size: Code ≤ 2–3 files and a diff readable in ~10 min; Chat ends a step when something is approved and saved (a block of decisions, a design section). If a step plus the owner's review does not fit in one 1–2 h sitting, split it.
- A3. No task file. `docs/tasks.md`: one row per task, linking its working document. Tasks of 2+ steps have one working document (design to build or decide, spike report to investigate) holding Why, Done when, progress and steps.
- A4. Effort (1, 2, 3, 5, 8) is relative size, estimated by analogy with closed tasks when the row is created, and re-estimated when the design defines the steps. 8 triggers the split check of A1.
- A5. State lives in the working document, not the chat: decisions are written when approved, Status is updated at each stop. Chat: one session per block of work (e.g. a design, or ~3 Code steps), starting and ending with Status. Documents record decisions, not discussion, without repetition.
  - On trial: a Code session chains consecutive steps, each with commit and check; new session at each gate, when the next step touches another area, or when context passes half.
  - TODO: validate the Code part in the C trial: does chaining degrade results, are the cut points clear, is "half context" the right threshold.
- B1. `docs/tasks.md` is one table: ID | Task | Effort | Status | Depends on | Doc. Status: todo, in progress, blocked, done. No date (Git has it).
- B2. Rules (A1–A5, B1) go in CLAUDE.md › Workflow; their format goes in the design template (header as task card, Check column, gates). In the template, Context goes right after Status.
  - TODO: the design template is on trial; review it after its first real use (T007).
  - Approved changes: (1) Done when after Context; (2) Status as one item per line: State, Current step, Next; (3) steps table adds Check and Done columns, Gate rows, commit as type(TNNN); (4) File layout section before Components; (5) required sections: Status, Context, Done when, Decision summary, Implementation steps, rest optional; (6) Open questions as its own section, after Decision summary.
- B3. File layout: tree of every file and folder the task creates or modifies, marked (new)/(modified) with a one-line purpose. A new top-level folder or overall change also updates CLAUDE.md › Project structure in the same step. Anything outside the tree is a deviation: stop, update the section, owner's OK.
- B1 amended. Status: ⬜ todo · 📝 design (Draft) · 🟢 ready (design approved) · 🔄 in progress · ⛔ blocked · ✅ done. A task without design goes ⬜ → 🔄 → ✅.
- B4. tasks.md migrated to the table. Frame = creating the design in Draft (Context, Done when). T011 and T006.1 got draft designs; T012 stays as a row only. Design files are named `tNNN-short-title.md` (add to CLAUDE.md conventions in C).
- C1. Step protocol (on trial), in CLAUDE.md › Code. The owner asks for "TNNN step N" or "steps N–M", in any wording. Code: (1) checks Status, previous steps ✓ and no Gate, else stops; (2) reads only Reads; (3) works within Scope and File layout, else stops (deviation); (4) runs the Check and shows its literal output; (5) updates Done and Status; (6) reports files touched, Check result, deviations, commit message; (7) when chaining, stops at a Gate, an area change or half context. The owner confirms every commit. A Claude Code command may invoke the protocol as a shortcut; work never depends on it.
  - TODO: trial on a real step. Accept if Code stops where it should, the report matches the diff, the Check output is literal, the design is updated, and review takes ~10 min. Then decide whether Code gets more autonomy (e.g. commits).
- C2. Git. Now (trial): Code may run only git status, diff, log, show, with GIT_OPTIONAL_LOCKS=0 (no index.lock); enforced in C3 settings. The owner commits. Chat never runs git. A leftover .git/index.lock is removed by the owner after checking no git process is running.
  - Next autonomy level, after the C1 trial passes: Code commits each step on dev (or a task branch); owner review moves to the merge into main.
- C3. Code permissions (on trial with C1), in `.claude/settings.json`: env GIT_OPTIONAL_LOCKS=0; defaultMode acceptEdits; disableBypassPermissionsMode; blockReadsOutsideWorkingDirectories; ask: rm, CLAUDE.md, docs/decisions, docs/templates; deny: read/edit .env, edit **/raw/**, git commands that write. No sandbox for now. Facts: rules are evaluated deny → ask → allow → mode; acceptEdits auto-approves edits and mkdir/mv/cp inside the project only; other commands (scripts, pytest) still prompt; rules match command text (guard against mistakes, not a hard boundary); /rewind restores files Code edited.
  - Personal (settings.local.json), owner's choice: statusLine with context % (set up via /statusline), language spanish, outputStyle Learning.
  - Later options: sandbox (OS-level boundary for shell commands: denyWrite raw, network allowlist); attribution.commit (when Code commits); autoCompactWindow (calibrate A5); hooks (turn protocol rules into automatic checks, e.g. File layout); disableAutoMode.
  - Sources: code.claude.com/docs/en/settings, /permissions, /permission-modes, /sandboxing, /settings-reference
- C4. Commits: `type(TNNN): description` (Conventional Commits, task ID as scope; no scope if no task). Status changes go in the commit of the work that causes them.
- C5 principle: CLAUDE.md text must be short and unambiguous for Claude.
- C6. Verdict on friction TODO "Code shell commands": before every shell command, Code says in one plain sentence what it does and whether it changes anything (all commands, read-only included).
- C7. Verdict on friction TODO "Chat repo access": before writing, moving or deleting a file, Chat explains in 2–3 plain lines what will change, where, and its effect; no full text. Writes only after the owner's OK; the owner reviews the diff and commits.
- C8. The Step protocol trial is not done in T013: it runs on the first Code step of a design (TODO re-pointed in CLAUDE.md › Code › Step protocol).

## Options considered

Options and their discussion are in the T013 working notes (`docs/t013-notes.md`) and in Git history.
