---
paths:
  - "docs/architecture.md"
---

# Architecture document rules

`docs/architecture.md` follows arc42 and is the curated summary of the project's architecture; detail lives in its sources (designs, ADRs, source cards).

- **Current state only:** it states what holds today, with no history or review notes. A task that takes or changes a decision updates the affected sections in the same commit.
- **Section purpose:** each section holds only what its arc42 purpose asks for; anything else goes to the section it belongs to, or stays in its source.
- **Summarise, don't copy:** one line per requirement, goal or decision, linking to its source for the detail.
- **Tables before prose** wherever items share the same attributes.
- **Source line:** every section or table ends with `Source:` followed by links to the designs (with requirement numbers) and ADRs it comes from, e.g. `Source: [d002](designs/d002-requirements.md) R3, R4; [ADR-0018](decisions/0018-medallion-architecture.md)`.
- **References:** decisions are cited by task ID (`T035`) or ADR, never by informal labels.
