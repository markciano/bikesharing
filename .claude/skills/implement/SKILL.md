---
name: implement
description: Produce the code of one design or spike step by step, make a one-step change, or review a finished task.
disable-model-invocation: true
argument-hint: "[design ID | spike ID] [step N | review]"
---

# Implementation session

Cycle: Produce → Review. Produce runs over several sessions of about 3 steps each; Review is its own session, started after the last step.

## Modes

- **Design step:** the owner asks for a step or a range of a design ("dNNN step 3", "steps 3–5"), in any wording. Follow the Step protocol.
- **Spike step:** the same for a spike ("sNNN step 3"). Follow the Step protocol as adapted in [spike.md](spike.md).
- **One-step change** (no design): propose (what, why) → owner approves → write the test, see it fail → apply → Change report.
- **Review:** `/implement dNNN review`, in a fresh session once every step is ✅. Follow `review.md`.

## Step protocol

1. **Precondition.** Read only the design's Status, the current step row and the Reads listed in the step. Stop and report if State is not Ready 🎬 or In progress 🔄, if a previous step is not ✅, or if a ✅ step has no commit in `git log`.
2. Work only within the step's Scope and the File layout. Anything else is a deviation (like a change to Spec, File layout, a component contract, Test plan): set the step to ⛔, stop and report it, do not decide it. A deviation is valid only with the owner's OK. Once given, write it at once in the design's 4. Close › Decisions taken during implementation. Record only what changes.
3. **Tests first.** Write the step's tests from the Test plan and run them: they must fail (red). Then write the code until they pass (green). Tests may be added, never dropped.
4. Run the Check and, if the step touches code, all unit and integration tests of the touched component, not only the step's (local layer, for reference see [testing strategy](../../../docs/testing-strategy.md)).
5. If the Check and the tests pass, mark the step ✅ and set Current step; the mark goes into the owner's commit of the step. On the first step, State goes to In progress 🔄 and the task to 🔄. If either fails, the step stays 🔄 and the report says why.
6. End with the Change report.
7. When running a range, stop before a step in another area, or past half context. The commit of a step must exist before the next step starts.

## Change report

Report by exception: what follows the plan is not described; the owner reads the diff.

```text
Step N ✅ — <one line: what the system does now>
Check: <last line of the output, literal>
Exceptions: none
Commit: Follow Git conventions in CLAUDE.md.
```

- **Step line:** ✅ if the Check passes, 🔄 or ⛔ otherwise. For a one-step change, "Change" instead of "Step N".
- **Check:** the summary line only, literal. If it fails, the full output, literal. For a one-step change, the test run.
- **Exceptions:** "none", or one line each for:
  - deviations, and their status (pending OK or approved);
  - files touched outside the step's Scope;
  - tests added, or planned tests that did not fail before the code;
  - new TODOs.
- **Commit:** the step's Commit line, adjusted only if the step's content changed. For a one-step change, following the Git conventions in CLAUDE.md.
