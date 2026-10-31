---
paths:
  - "docs/spikes/**"
  - "docs/designs/**"
---

# Decision log rules

Apply to the Decision log of a spike report and the Decision summary of a design, each time an entry is added, not only when the document is created. Columns are described in the template.

- **Log only:** an entry records the decision and the standard it follows (or the ADR for the deviation), in one line. The content goes in the section where it applies, and the entry links to it from Applies to.
- **Change links:** a decision that changes an earlier one ends its Decision with `**extends #N**`, `**refines #N**` or `**replaces #N**`; the earlier one gets `**→ #M**` at the end of its Decision and is not otherwise rewritten. Both edits go in the same change.
