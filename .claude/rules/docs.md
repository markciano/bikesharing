---
paths:
  - "docs/**"
---

# Documentation rules

- **ADR** (`docs/decisions/`) records *why* (one cross-cutting decision, following MADR format);
- **Design docs:** (`docs/designs/`) records *how* for one task (frame, explore, decide and plan), detailed enough to implement without making design decisions. Decisions local to a task stay in its design doc; cross-cutting ones become ADRs, linked from it.
- **Spikes** (`docs/spikes/`) document experiments and investigations.
- **Source cards** (`docs/sources/`) contain: Source (provider, URL, licence), Access (endpoint, format, auth, update frequency) and Facts (each with its evidence and the date it was confirmed).
- **Diagrams (Mermaid)** only where a flow branches or has several actors; the text is authoritative.
- **Documents** record decisions, not discussion, without repetition.
- New designs and spikes start from the template in their skill..
- **Markdown lint** (CI job `docs`, config in `.markdownlint-cli2.yaml`) fails the PR on these, so write them right the first time:
  - fenced code blocks state their language (`text` if it is not code);
  - URLs go between `<>` or as a link;
  - a title is a heading (`##`), not a bold line; levels go up one at a time;
  - placeholders such as `<name>` go in backticks.
