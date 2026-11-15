# Plan review

Your goal: find what would make this design wrong or incomplete before the Steps are written. For a document-only or parent task (Kind in the header), this is the final review, and its deliverables are checked against the Spec.

## Precondition

Phase shows Plan checked and Plan review unchecked. Otherwise stop and tell the owner.

## Read

- The design doc `docs/designs/dNNN-*.md`: Status, Spec and Plan.
- ADRs linked in its header, only when a check needs them.
- The rule documents listed in File layout, for check 6, and the deliverables of a document-only or parent task, for check 7.
- Nothing else unless a finding needs confirming; announce it in one line, within the reading budget in CLAUDE.md.

## Checklist

1. **Coverage.** Every requirement, failure cases (*If… then*) included, is resolved by a decision, a component or the Test plan. Nothing in the Plan covers an item listed in Out of scope.
2. **Soundness.** Would a senior data engineer approve this Plan for these requirements? Look at least at: what happens on re-runs and partial writes; whether each decision is the simplest that meets the requirements; whether the named standard fits the problem.
3. **Consistency.** Decisions do not contradict each other or existing ADRs. Cross-cutting decisions have their ADR. Each decision names the standard that applies, or has an ADR for the deviation.
4. **Verifiability.** Every requirement can be checked by something in the Test plan; every Done when item, by a test, a command or an owner check.
5. **No gaps.** No decision is left implicit. File layout is complete, the documents the change affects included, and its names follow the conventions in CLAUDE.md. Pending items follow the conventions in CLAUDE.md.
6. **Rule documents.** Every file in File layout that states rules or decisions (ADRs, `.claude/**`, `CLAUDE.md`) is written; each matches the Decision summary and adds no decision of its own. New ADRs are linked in the header.
7. **Deliverables** (document-only or parent). Every file in File layout is written and listed in Approach; each says what the Spec and the Plan decided, with no decision of its own and none missing.
8. **Children** (parent). Every open question and requirement of the parent is closed by the parent or by one child; each child has a scope, what it closes and a Done when that can be checked; dependencies follow the map's order, with no cycle.

## Severity

- **Blocking:** the Steps or `/implement` would build the wrong thing or could not proceed; for a document-only or parent task, a deliverable or a child would carry the wrong decision.
- **Important:** it would cause rework or a deviation later.
- **Minor:** clarity or wording only.

## Close

Check Plan review in Phase and update Status in the same change. Tell the owner that the Steps can start with `/design dNNN`.

For a document-only or parent task, the review closes the task instead:

1. A parent proposes its children with `/task`, as sub-issues in the Children order with their `blocked-by`; they are created once the owner approves.
2. Write Close. With the owner's OK, State goes to Complete ✅ and the template's comments are removed, in the same commit; propose its message.
