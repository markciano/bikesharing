# Spike steps

Applies when the argument is a spike ID (sNNN). The spike doc is in `docs/spikes/` and follows the spike template. The Step protocol and the Change report in SKILL.md apply with the changes below; what is not mentioned here applies unchanged.

## Changes to the Step protocol

- **Precondition.** State must be Ready 🎬 or Running 🔄. A ✅ step needs a commit in `git log` only if it has a Commit line.
- **First step.** State goes to Running 🔄, Started is set (UTC date), and the task to 🔄.
- **No tests first.** Point 4 does not apply: spike code is throwaway and is validated by the step's Check and by the Owner step that runs it.
- **Deviations.** Once the owner gives the OK, record them in 2. Method › Decision log (date, decision, reason), not in Close. If one changes an exit criterion, say so in the report.
- **Production inputs.** A point worth taking to production that the step does not need is not fixed in the spike code. Add it as a row in 4. Findings › Production inputs with its origin and no destination, and list it in the report. The owner can also name one at any time; record it the same way.

## Owner steps

For a step with Who: Owner.

1. Check the precondition as usual.
2. Give the owner the step's actions as written, with exact commands in code blocks, and what to report back. Do not run them yourself.
3. Stop and wait for the owner's result.
4. With the result:
   - If it is evidence the spike needs (figures, behaviour, errors), write it as the next Finding (F), with step, date and source. The owner approves on the diff.
   - Check passes: the step goes to ✅. Check fails: it stays 🔄 and the report says why.
   - Gate fails: the step goes to ⛔. Report the consequence the Gate states; once the owner confirms it, record it in the Decision log and update the affected steps.
5. End with the Change report: "Owner step N" instead of "Step N"; Check is the owner's result in one line; Commit only if the step has one.

## Findings

- Claude steps that produce evidence (an analysis output, an observed behaviour) also add Findings, approved on the diff.
- One fact per finding. Numbering continues and is never reused.
- An earlier finding is not rewritten to fit a later result; the later finding says which one it corrects.

## Conclusion step

Owner + Claude. Draft each part in this order; the owner approves on the diff:

1. Observed window.
2. Answers, one per Q, citing Findings.
3. Exit criteria, one result per criterion and variant.
4. Verdict.
5. Not verified: each item with its risk and mitigation.
6. Production inputs: a destination for every P: a design (naming its task), or discarded with a reason. No new task rows from Production inputs.
7. Follow-ups: ADRs to write, each in its own commit; new tasks proposed to the owner as rows in `docs/tasks.md`.
8. README › How we got here: 5–10 lines of narrative for the portfolio, linking to Findings and Decision log entries instead of repeating their detail.
9. Tear-down: what is torn down and what is kept; a kept resource gets a Decision log entry. The owner runs the tear-down.

Then set State to Concluded ✅ and Finished (UTC date), and the task to ✅, in the commit of this step.
