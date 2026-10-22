---
paths:
  - "docs/**"
---

# Documentation rules

- **ADR** (`docs/decisions/`);
- **Design docs:** (`docs/designs/`) record the design of a feature.
- **Spikes** (`docs/spikes/`) document experiments and investigations.
- **Source cards** (`docs/sources/`) contain: Source (provider, URL, licence), Access (endpoint, format, auth, update frequency) and Facts (each with its evidence and the date it was confirmed).
- **Testing strategy** (`docs/testing-strategy.md`) records the testing model per component and the CI flow.
- **Diagrams (Mermaid)** only where a flow branches or has several actors; the text is authoritative.
- **Documents** record decisions, not discussion, without repetition.
- New designs and spikes start from the template in their skill..
- **Markdown lint** (CI job `docs`, config in `.markdownlint-cli2.yaml`) fails the PR on these, so write them right the first time (the owner can lint locally with `bash scripts/lint-docs.sh`):
  - fenced code blocks state their language (`text` if it is not code);
  - URLs go between `<>` or as a link;
  - a title is a heading (`##`), not a bold line; levels go up one at a time;
  - placeholders such as `<name>` go in backticks.
