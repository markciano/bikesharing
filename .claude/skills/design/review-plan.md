# Plan review

Your goal: find what would make this design wrong or incomplete before the Steps are written.

## Precondition

Phase shows Plan checked and Plan review unchecked. Otherwise stop and tell the owner.

## Read

- The design doc `docs/designs/dNNN-*.md`: Status, Spec and Plan.
- ADRs linked in its header, only when a check needs them.
- The rule documents listed in File layout, for check 6.
- Nothing else unless a finding needs confirming; announce it in one line, within the reading budget in CLAUDE.md.

## Checklist

1. **Coverage.** Every requirement, failure cases (*If… then*) included, is resolved by a decision, a component or the Test plan. Nothing in the Plan covers an item listed in Out of scope.
2. **Soundness.** Would a senior data engineer approve this Plan for these requirements? Look at least at: what happens on re-runs and partial writes; whether each decision is the simplest that meets the requirements; whether the named standard fits the problem.
3. **Consistency.** Decisions do not contradict each other or existing ADRs. Cross-cutting decisions have their ADR. Each decision names the standard that applies, or has an ADR for the deviation.
4. **Verifiability.** Done when and every requirement can be checked by something in the Test plan.
5. **No gaps.** No decision is left implicit. File layout is complete, the documents the change affects included, and its names follow the conventions in CLAUDE.md. Pending items are marked `TODO:`.
6. **Rule documents.** Every file in File layout that states rules or decisions (ADRs, `.claude/**`, `CLAUDE.md`) is written; each matches the Decision summary and adds no decision of its own. New ADRs are linked in the header.

## Severity

- **Blocking:** the Steps or `/implement` would build the wrong thing or could not proceed.
- **Important:** it would cause rework or a deviation later.
- **Minor:** clarity or wording only.

Present them in two separate sections, writing "None" when empty:
1. **Blocking and important.** Per finding: severity, quote, consequence, suggested fix.
2. **Minor.** Per finding: quote, short reason.

## Close

Check Plan review in Phase and update Status in the same change. Tell the owner that the Steps can start with `/design dNNN`.
