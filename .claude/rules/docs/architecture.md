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
- **Source per item:** every table row, bullet and paragraph cites where it comes from: designs with requirement or question numbers, ADRs, spikes or source cards. Tables carry a `Source` column; bullets and paragraphs end with the links, separated by `;`. TODOs and pointers to other sections cite nothing.
- **Source links:** as in `general.md` › References, e.g. `[d002 › R3, R7](designs/d002-requirements.md#requirements)`.
