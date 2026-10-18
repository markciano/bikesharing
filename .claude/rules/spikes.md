---
paths:
  - "spikes/**"
---

# Spike code rules

- Spike and analysis code is throwaway but readable: each script or notebook starts with a short comment (what it does, inputs, outputs), and non-obvious steps are commented. The full docstring rule for `src/` does not apply.
- No test suite or test pyramid. Add a quick check or a targeted test where a conclusion depends on logic that could be wrong (parsing, aggregation, time handling).
- Nothing in `spikes/` is imported from `src/` or `tests/`. Code worth keeping is rewritten in `src/` through a design.
- Each spike folder has a short `README.md`: the question, how to run it, and a link to its report in `docs/spikes/`.