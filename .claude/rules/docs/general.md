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
  - placeholders such as `<name>` go in backticks;
  - an ordered list is changed in one Edit, since the hook renumbers it after each one; then check the references to its items (e.g. `Do 3`) in the same document only, since other documents cite headings or IDs, never list positions.
- **Heading depth:** at most `####`; deeper detail goes in nested lists.

## References

- **Link, don't copy:** cite a source when the reader needs it to verify or act, or when one item changes another; content lives in one place and other places link to it. A mere mention is not a reason to link.
- **IDs:** citable items carry an ID with a type prefix (e.g. `Q1` question, `F12` finding, `R3` requirement, `#22` decision, `T036` task); decisions outside a working document are cited by task ID or ADR, never by informal labels.
- **Citable item:** an item cited from elsewhere is a heading (`###` or `####`) that starts with its ID, e.g. `### F12. Partition pruning on R2`; its text is not renamed once cited: the anchor is generated from it, so a rename silently breaks the links to it. Items in a table are cited by ID; from another document, the link targets the table's section.
- **Same document:** the ID in plain text (`#22`, `F12`); link only when naming a section or a citable item, e.g. `[Probe A](#probe-a)`.
- **Other document:** name the document and, after `›`, the section or the items; the target is the section's anchor when there is one, the file otherwise. E.g. `[s010 › #22, F12](spikes/s010-storage-table-format.md#23-decision-log)`, `[d002 › Guiding questions](designs/d002-requirements.md#guiding-questions)`, `[task T036](tasks.md)`.
- **ADR:** by number, linking to the file, e.g. `[ADR-0018](decisions/0018-medallion-architecture.md)`.

## Tone & writing style guidelines

- **Professional & Accessible:** Maintain a rigorous, technical, yet clear and approachable tone. Avoid complex phrasing, or pretentious vocabulary.
- **Clarity First:** Prioritize practical understanding over formal complexity.
- **Direct & Action-Oriented:** Use active voice and concise sentences.
- **Plain Technical English:** Use precise industry terms (e.g., *idempotency, schema evolution, pipeline latency*) without unnecessary buzzwords or fluff.
