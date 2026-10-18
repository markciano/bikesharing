# Implementation review

Runs in a fresh session: `/implement dNNN review`. You are an independent reviewer. You did not write this code; judge only the design and what was delivered against it.

## Precondition

State is In progress 🔄, every step is ✅ with its commit in `git log`, and the working tree is clean. Otherwise stop and tell the owner.

## Read

- The design doc `docs/designs/dNNN-*.md`: Status, Spec, File layout, Test plan, 3. Implementation and 4. Close.
- ADRs linked in its header, only when a check needs them.
- Code and tests only when a finding needs confirming; announce it in one line, within the reading budget in CLAUDE.md.

## Checklist

1. **Tests.** The full test suite passes; its output is quoted literally.
2. **Coverage.** Every requirement has at least one passing test; no test in the Test plan was dropped.
3. **File layout.** Every item is delivered, and nothing outside it was created or modified (`git diff --stat` from the commit before the first step).
4. **TODOs.** Every TODO in docs and code citing the task is resolved or re-pointed to another task.
5. **Decisions.** Every entry in Decisions taken during implementation had the owner's OK; those affecting other tasks or the project have an ADR. Documents whose behaviour changed were updated.
6. **Done when.** Each item is met, with its evidence.

## Findings

Report a finding only if you can quote the passage or output and name its consequence. Severity:
- **Blocking:** the task cannot close.
- **Important:** the task can close only with a known gap.
- **Minor:** clarity or wording only.

Present them in two separate sections, writing "None" when empty:
1. **Blocking and important.** Per finding: severity, quote, consequence, suggested fix.
2. **Minor.** Per finding: quote, short reason.

## Fixes

The owner decides which findings to fix. A fix within the design's Scope is applied as a one-step change (see SKILL.md); anything else goes to Known gaps. One finding per message when a fix needs a decision.

## Close

1. Draft *Implemented* from the ✅ steps and the test results: component — what was delivered; tests passing.
2. Draft *Known gaps at close*: Done when items not met, File layout items not delivered, TODOs re-pointed, each with the task that covers it. Propose a task row for any gap without one. "None" is written, not left empty.
3. *Decisions taken during implementation* is already written: review it with the owner; write "None" if empty.
4. The owner checks Done when. When accepted, State goes to Complete ✅, Current step to —, and the task to ✅ in the task table, in the same commit; propose its message.
