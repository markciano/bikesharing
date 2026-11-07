# Spike steps

Applies when the argument is a spike ID (sNNN). The spike doc is in `docs/spikes/` and follows the spike template. The Step protocol and the Change report in SKILL.md apply with the changes below; what is not mentioned here applies unchanged.

## Changes to the Step protocol

- **Precondition.** State must be Ready 🎬 or Running 🔄. A ✅ step needs a commit in `git log` only if it has a Commit line.
- **First step.** State goes to Running 🔄 and Started is set (UTC date).
- **No tests.** Tests first does not apply, and the point that runs the Check and the tests runs only the Check: spike code is throwaway and is validated by the step's Check and by the Owner step that runs it.
- **Deviations.** Once the owner gives the OK, record them in 2. Method › Decision log, not in Close. If one changes an exit criterion, say so in the report.
- **Observations.** A point the step does not need is not fixed in the spike code. Write it as a Finding.

## Owner steps

For a step with Who: Owner.

1. Check the precondition as usual.
2. Give the owner the step's actions as written, with exact commands in code blocks, and what to report back.
3. Stop and wait for the owner's result.
4. With the result:
   - If it is evidence the spike needs (figures, behaviour, errors), write it as the next Finding (F), with step, date and source. The owner approves on the diff.
   - Check passes: the step goes to ✅. Check fails: it stays 🔄 and the report says why.
   - Gate fails: the step goes to ⛔. Report the consequence the Gate states; once the owner confirms it, record it in the Decision log and update the affected steps.
5. End with the Change report: "Paso del owner N" instead of "Paso N"; Check is the owner's result in one line; Commit only if the step has one.

## Findings

- Claude steps that produce evidence (an analysis output, an observed behaviour) also add Findings, approved on the diff.
- One fact per finding. Numbering continues and is never reused.
- An earlier finding is not rewritten to fit a later result; the later finding says which one it corrects.

## After the last step

This skill ends with the last step: it writes neither the Conclusion nor Production inputs. State stays Running 🔄. Tell the owner to continue with `/spike sNNN` in a new session.
