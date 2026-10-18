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
