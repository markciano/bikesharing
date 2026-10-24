---
paths: # mirrors the lint scope (globs) in .markdownlint-cli2.yaml; keep both in sync
  - "*.md"
  - "docs/**"
  - ".claude/**/*.md"
  - "spikes/**/*.md"
---

# Documentation rules

- **ADR** (`docs/decisions/`);
- **Design docs:** (`docs/designs/`) record the design of a feature.
- **Spikes** (`docs/spikes/`) document experiments and investigations.
- **Source cards** (`docs/sources/`) contain: Source (provider, URL, licence), Access (endpoint, format, auth, update frequency) and Facts (each with its evidence and the date it was confirmed).
- **Architecture** (`docs/architecture.md`, arc42) is the curated summary of the project's architecture.
- **Testing strategy** (`docs/testing-strategy.md`) records the testing model per component and the CI flow.
- **Diagrams (Mermaid)** only where a flow branches or has several actors; the text is authoritative.
- **Documents** record decisions, not discussion, without repetition.
- **Markdown lint** (scope and rules in `.markdownlint-cli2.yaml`; how it runs in `docs/testing-strategy.md`): a hook fixes cosmetic issues and reports the rest after every edit, and the CI job `docs` fails the PR on them. Write these right the first time:
  - fenced code blocks state their language (`text` if it is not code);
  - URLs go between `<>` or as a link;
  - a title is a heading (`##`), not a bold line; levels go up one at a time;
  - placeholders such as `<name>` go in backticks.
