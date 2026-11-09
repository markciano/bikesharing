---
paths:
  - "src/**"
  - "tests/**"
  - "capture/**"
  - "scripts/**"
---

# Code rules (all languages)

Language-specific format (docstring or JSDoc style) is in `python.md` and `cloudflare-worker.md`; test rules are in `testing.md`.

## Code comments

- Every module starts by stating its responsibility, and every public item is documented, with its types, in the language's standard format.
- Inline comments explain *why* a non-obvious decision was made, never *what* the code does.
- A comment can be understood on its own: it states the rule or the reason in words, never only a document ID.
- A comment that cites a document writes `(<doc ID> <item ID>, <item title>)`, e.g. `(d004 D8, Capture failure behaviour)` or `(ADR-0012, Collectors decoupled by output contract)`. Never a bare item ID such as `(D3)`, and no file paths or anchors, which neither the editor nor GitHub follows from a comment; the doc ID finds the file, since file names start with it.
  - An item without a title, such as a requirement, is cited through the decision it comes from: `(d004 D12, Capture security)` rather than `R21`.
  - A section without an item ID is cited by document and section title: `(d004, Pass logs)`.
