# Steps review

Your goal: find what would make /implement build the wrong thing, stop to ask, or take a design decision itself.

## Precondition

Phase shows Steps checked and Steps review unchecked. Otherwise stop and tell the owner.

## Read

- The design doc `docs/designs/dNNN-*.md`: Status, Spec, Plan and Steps.
- Nothing else unless a finding needs confirming or a fact needs verifying for check 6; announce it in one line, within the reading budget in CLAUDE.md.

## Checklist

1. **Dry run.** For each step in order, act as `/implement` with only the step and its Reads: could you write every file and run its Check without asking a question or taking a design decision? Every point where you could not is a finding.
2. **Traceability.** Every requirement is covered by at least one step, by the method its Test plan row sets: the step that writes its test, or the step that inspects, analyses or demonstrates it. Every step names its requirements (R), and they match the Test plan rows its tests verify. No step adds scope the Plan does not contain.
3. **Order.** No step, its Check included, uses something created in a later step.
4. **Shape.** Each step touches at most 2–3 files, all in File layout, and contradicts no decision in Decided at framing or Decision summary; an Owner step follows the order and the controls those decisions and the threat table set. A code step includes its tests. The last step verifies the deliverable end to end. Commit follows the Git conventions in CLAUDE.md. Pending items follow the conventions in CLAUDE.md.
5. **Review points.** Every step sets Review; each review closes a reviewable unit, and the last code step has at least `code`.
6. **External facts.** Every fact the Steps rely on and do not decide, such as how a library call behaves or a figure measured elsewhere, cites its source, or is verified before the review closes.

## Severity

- **Blocking:** `/implement` would build the wrong thing or could not proceed.
- **Important:** it would cause rework or a deviation during implementation.
- **Minor:** clarity or wording only.

## Close

In the same change: check Steps review in Phase, set the design's State to Ready for implementation 🎬. Tell the owner the design is ready for `/implement dNNN`.
