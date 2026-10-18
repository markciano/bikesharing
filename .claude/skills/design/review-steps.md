# Steps review

Your goal: find what would make /implement build the wrong thing, stop to ask, or take a design decision itself.

## Precondition

Phase shows Steps checked and Steps review unchecked. Otherwise stop and tell the owner.

## Read

- The design doc `docs/designs/dNNN-*.md`: Status, Spec, Plan and Steps.
- Nothing else unless a finding needs confirming; announce it in one line, within the reading budget in CLAUDE.md.

## Checklist

1. **Dry run.** For each step in order, act as `/implement` with only the step and its Reads: could you write every file and run its Check without asking a question or taking a design decision? Every point where you could not is a finding.
2. **Traceability.** Every requirement is covered by at least one step. Every step names its requirements (R). No step adds scope the Plan does not contain.
3. **Order.** No step, its Check included, uses something created in a later step.
4. **Shape.** Each step touches at most 2–3 files, all in File layout, and contradicts no decision in Decision summary. A code step includes its tests. The last step verifies the deliverable end to end. Commit follows the Git conventions in CLAUDE.md. Pending items are marked `TODO:`.

## Severity
- **Blocking:** `/implement` would build the wrong thing or could not proceed.
- **Important:** it would cause rework or a deviation during implementation.
- **Minor:** clarity or wording only.

Present them in two separate sections, writing "None" when empty:
1. **Blocking and important.** Per finding: severity, quote, consequence, suggested fix.
2. **Minor.** Per finding: quote, short reason.

## Close

In the same change: check Steps review in Phase, set the design's State to Ready for implementation 🎬 and the task row in `docs/task.md` to 🎬. Tell the owner the design is ready for `/implement dNNN`.
