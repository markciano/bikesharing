---
paths:
  - "docs/**"
---

# Documentation rules

- **ADR** (`docs/decisions/`);
- **Design docs:** (`docs/designs/`) record the design of a feature.
- **Spikes** (`docs/spikes/`) document experiments and investigations.
- **Source cards** (`docs/sources/`) contain: Source (provider, URL, licence), Access (endpoint, format, auth, update frequency) and Facts (each with its evidence and the date it was confirmed).
- **Architecture** (`docs/architecture.md`, arc42) states only what holds today, with no history or review notes. A task that takes or changes a decision updates the affected sections in the same commit.
- **Testing strategy** (`docs/testing-strategy.md`) records the testing model per component and the CI flow.
- **Diagrams (Mermaid)** only where a flow branches or has several actors; the text is authoritative.
- **Documents** record decisions, not discussion, without repetition.
- **Markdown lint** (CI job `docs`, config in `.markdownlint-cli2.yaml`) fails the PR on these, so write them right the first time (the owner can lint locally with `bash scripts/lint-docs.sh`, after `npm ci` once per clone):
  - fenced code blocks state their language (`text` if it is not code);
  - URLs go between `<>` or as a link;
  - a title is a heading (`##`), not a bold line; levels go up one at a time;
  - placeholders such as `<name>` go in backticks.
