---
paths:
  - "spikes/**"
---

# Spike code rules

Spike and analysis code is throwaway but readable, in any language. The comment rules in `general.md` and the language rules do not apply.

## Folder

- Each spike folder has a short `README.md`: the question, how to run it, what each script does, its approximate run time, and a link to its report in `docs/spikes/`.
- No component imports from `spikes/`. Code worth keeping is rewritten in its component through a design.

## Code

- Each script or notebook starts with a short comment: what it does, its inputs and outputs. Non-obvious steps are commented.
- A script that runs for more than about 30 s prints its progress per unit of work (an archive, a day, a check) and ends with its total elapsed time.

## Checks

- No test suite or test pyramid. Add a quick check or a targeted test where a conclusion depends on logic that could be wrong (parsing, aggregation, time handling).
