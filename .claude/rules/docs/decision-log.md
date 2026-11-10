---
paths:
  - "docs/spikes/**"
  - "docs/designs/**"
---

# Decision log rules

Apply to the Decision log of a spike report and the Decision summary of a design, each time an entry is added, not only when the document is created. Columns are described in the template.

- **What reaches the owner:** ask the owner only what changes the result, the cost, the security, the scope or how something is measured. Anything else is resolved without asking, and the owner sees it on the edit's diff.
- **What is logged:** only the decisions asked of the owner get an entry; anything else lives in its section and in Git.
- **Log only:** an entry records the decision and the standard it follows (or the ADR for the deviation), in one line, and a short reason. The content goes in the section where it applies, and the entry links to it from Applies to.
- **Change links:** a decision that changes an earlier one ends its Decision with `**extends #N**`, `**refines #N**` or `**replaces #N**`; the earlier one gets `**→ #M**` at the end of its Decision and is not otherwise rewritten. Both edits go in the same change.
- **Change links across documents:** a decision that changes a section of another working document ends with `**extends …**`, `**refines …**` or `**replaces …**`, followed by a link to that section (e.g. `**refines [d004 › D8](d004-bronze-data-capture.md#d8-capture-failure-behaviour)**`). The other document's section is rewritten as Current state in sections sets, and ends with a bold link to the decision instead of `**#M**`; a changed one-line item, such as a requirement, adds the link to the decisions it cites. Both documents change in the same commit.
- **Current state in sections:** a section states the final state, without the reasons, which live in the log; Decided at framing and Options considered keep their reasoning. A section changed later, at any phase (framing, plan, steps, implementation), is rewritten as if written at once, with no trace of the earlier version; if a logged decision changed it, it ends with that entry in bold (`**#M**`). The history lives only in the log and in Git.
