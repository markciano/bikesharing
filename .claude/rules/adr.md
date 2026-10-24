---
paths:
  - "docs/decisions/*.md"
---

# Architecture Decision Records

## Files and numbering
- Name: `NNNN-kebab-case-title.md`
- One decision per ADR. If you find two, split them.

## Lifecycle
- Statuses: Proposed → Accepted | Rejected; Accepted → Deprecated | Superseded.
- Only ADRs in force stay in `docs/decisions/`. A Rejected, Deprecated or Superseded ADR moves to `docs/decisions/archive/`, with one line under its title stating the date, the task and why. Numbers are never reused; links to a moved ADR are updated in the same commit.
- New ADRs are always `Proposed`. Never set `Accepted` yourself; only the decision-makers do.
- Accepted ADRs are immutable. Allowed edits: status, `superseded-by`, typos, broken links. To change a decision, write a new ADR that supersedes it and link both ways.

## Writing each section
- **Context:** facts, constraints and forces only. No solution vocabulary.
- **Options:** at least two real alternatives, including "do nothing / keep current" when plausible. Evaluate every option against the same criteria.
- **Decision Outcome:** rationale must reference the Context. State rules normatively using MUST / SHOULD / MAY (RFC 2119), one rule per sentence, each followed by its reason.
- **Consequences:** include negatives honestly; an ADR with no downsides is incomplete.

## Style
- Concise: Links to content instead of pasting it.
- Present tense, active voice, plain language.
- Audience and register: Write for an engineer who joins in two years, was not in the discussion, and needs to know what rule to follow and why. 

## Level of abstraction
- Lead with the principle, then the mechanism, then (optionally) one example.
- Generalize concrete cases: name the category they belong to and the criterion that unites them; keep at most one or two as "e.g." illustrations. Never start a paragraph with an example.
- Staleness test: if a sentence would become false by swapping a library, bumping a version or renaming a file, it is implementation detail. Remove it or move it to More information — unless that specific item IS the subject of the decision.

## Before drafting
1. Write the decision as a single sentence. If you can't, ask.
2. Group the input notes into principles; discard narrative and anecdote.
3. Only then fill in the template.