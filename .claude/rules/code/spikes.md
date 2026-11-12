---
paths:
  - "spikes/**"
---

# Spike code rules

Spike and analysis code is throwaway but readable, in any language. The comment rules in `general.md` and the language rules do not apply.

## Folder

- Each spike folder has a short `README.md` that reads as a procedure, top to bottom: the question and a link to its report in `docs/spikes/` or its design; the prerequisites (input data, runtimes with their versions); then one section per check, in the order they are run, each with the same items: its question, inputs and downloads, what each script does, the command, its output and its approximate run time.
- A spike folder holds one subfolder per check, named after its question, with that check's scripts only; validation scripts and trial runs of a check stay in its subfolder.
- The README cites the decision each check is evidence for, never an open question, which leaves its document when it closes.
- No component imports from `spikes/`. Code worth keeping is rewritten in its component through a design.

## Code

- Each script or notebook starts with a short comment: what it does, its inputs and outputs. Non-obvious steps are commented.
- A script that runs for more than about 30 s prints its progress per unit of work (an archive, a day, a check) and ends with its total elapsed time.

## Checks

- No test suite or test pyramid. Add a quick check or a targeted test where a conclusion depends on logic that could be wrong (parsing, aggregation, time handling).
