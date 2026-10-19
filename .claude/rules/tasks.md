---
paths:
  - "docs/tasks.md"
---

# Task table rules

- A task is the change the owner wants, in plain words. A task of 2+ steps has one working document: a design (to build or decide) or a spike report (to investigate). A one-step task has only its row.
- `docs/tasks.md` is one table: ID | Task | Effort | Status | Depends on | Doc. Task is the requirement in a few words; Doc links the working document. Why and Done when live in that document.
- Status: ⬜ todo · 📝 design (Draft) · 🎬 ready (design or spike approved) · 🔄 in progress · ⛔ blocked (add the reason) · ✅ done. A task without a design goes ⬜ → 🔄 → ✅.
- Effort: 1, 2 (half day), 3 (1 day), 5 (2 days), 8 (3 days).
