---
paths: # mirrors the lint scope (globs) in .markdownlint-cli2.yaml; keep both in sync
  - "*.md"
  - "docs/**"
  - ".claude/**/*.md"
  - "spikes/**/*.md"
---

# Documentation rules

- **Documents** record decisions, not discussion, without repetition.
- **Diagrams (Mermaid)** only where a flow branches or has several actors; the text is authoritative.
- **Markdown lint** (scope and rules in `.markdownlint-cli2.yaml`; how it runs in `docs/testing-strategy.md`): a hook fixes cosmetic issues and reports the rest after every edit, and the CI job `docs` fails the PR on them. Write these right the first time:
  - fenced code blocks state their language (`text` if it is not code);
  - URLs go between `<>` or as a link;
  - a title is a heading (`##`), not a bold line; levels go up one at a time;
  - placeholders such as `<name>` go in backticks.

## Tone & writing style guidelines

- **Professional & Accessible:** Maintain a rigorous, technical, yet clear and approachable tone. Avoid complex phrasing, or pretentious vocabulary.
- **Clarity First:** Prioritize practical understanding over formal complexity.
- **Direct & Action-Oriented:** Use active voice and concise sentences.
- **Plain Technical English:** Use precise industry terms (e.g., *idempotency, schema evolution, pipeline latency*) without unnecessary buzzwords or fluff.
