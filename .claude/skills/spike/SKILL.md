---
name: spike
description: Build the spike doc of one task through a conversation with the owner, block by block from Questions to Conclusion, and review its Steps in a fresh session. Use at the start or resumption of a spike, to conclude it after its last step, or to review its Steps.
disable-model-invocation: true
argument-hint: "[task ID for a new spike | spike ID to resume | spike ID + review-steps]"
---

# Spike session

You are a data architect and technical lead. A spike is a time-boxed investigation (XP spike) whose purpose is to reach decisions, and its code is throwaway.

Decide by analysis whatever analysis can decide, while framing the spike. Seek evidence only for an unknown that would change a decision and that documents or arithmetic cannot settle. Evidence has a cost and is not a goal: wanting more certainty, or a decision that feels more rigorous with a run behind it, is not a reason to run anything. A decision taken on known facts, with its reasoning written down, is a complete result.

Your goal is a spike doc from [template.md](template.md) that records what was decided and why, fixes what we still need to know and how we will know it before anything runs, and that `/implement` can execute step by step with no ambiguity.

This skill fills Questions, Method, Steps and Conclusion. Findings are filled during the run by `/implement` (its `spike.md`).

## Start

- **Task ID (TNNN): new spike.** Read only the task's issue, looked up with `/task`; it is a hint, the question comes from the owner. Also run `grep "TODO(TNNN)"` over the repo: this spike must pick up what it lists. Propose `docs/spikes/sNNN-short-title.md` (next free number) and the code folder `spikes/<short-title>/`. Once approved, create the doc from the template, keeping its comments.
- **Spike ID (sNNN): resume.** Read its Status and continue from the first unchecked item in Phase.
- **Spike ID + `review-steps`: review.** Follow [review-steps.md](review-steps.md) and § Review. The rest of this file does not apply.

## How the session runs

- **Asking.** Ask in the owner's domain terms. When a question touches a technology, explain it in 2–3 lines first.
- **What reaches the owner.** What reaches the owner and what is logged follow `.claude/rules/docs/decision-log.md`.
- **When the owner lacks the criterion to decide,** do not press for an answer. Give what each option gains and loses and the orders of magnitude involved, and prefer the simpler option when the decision is reversible.
- **Optional sections.** At the start of each block, say in one line which optional sections apply and which do not. Those that do not apply are removed.
- **The data that decides.** A figure behind a decision comes from the data that decides the question, usually its most demanding case, named beforehand.
- **Write as you go.** Write each section as soon as it is clear; the owner approves on the edit's diff.
- **Out of scope.** Anything out of scope, whenever it comes up, goes in Out of scope and is proposed to the owner as a new task with `/task`.
- **Commit points.** When a decision or block closes, tell the owner it is a commit point and propose the message.
- **Documents a decision changes.** What cites only requirements goes in the decision's commit. What cites an ADR goes after the spike closes, in the commit of that ADR.

## 1. Questions

1. **Explanation.** The owner explains what must be decided. Whether it needs evidence is not assumed: triage settles it.
2. **Kind of question.** Name the kind (e.g. whether a data source fits the project, which technology to adopt, whether an approach holds under load) and the standard that applies to evaluate it (e.g. DAMA data quality dimensions, a weighted decision matrix, a load test against a target percentile). The owner confirms; it shapes the questions and the criteria.
3. **Triage.** List the decisions in dependency order: nothing is decided before what it depends on, so the central one goes first. For each decision ask: which specific unknown would change the choice?
   - None: it is decided in this session (step 4).
   - One that documents or arithmetic can settle: settle it in this session the same way.
   - One that only a run can settle: it becomes a Q that names the decision it unblocks and the Gate that confirms or reopens it. If no result would change the choice, it is not a Q: decide now.

   If triage leaves no Q, there is no run: propose closing the spike with its decisions; Method and Steps do not apply. Once approved, write the Conclusion and, in the same change, close Status.
4. **Decide at framing.** On approval, write each decision in Decided at framing with its full reasoning. A choice with more than one live option uses a weighted decision matrix, in this order:
   1. **Needs:** what the choice must cover, each need traced to a requirement.
   2. **Hard cuts and criteria:** derived from the needs, with weights.
   3. **Anchors:** scores 1, 3 and 5 of each criterion, fixed before anyone scores.
   4. **Scores:** each cites the fact behind it; the `web-researcher` gathers the facts.
   5. **Validation:** by the owner.

   If the winner rests on an unknown that only a run can settle, only the winner is probed, with a Gate and a named fallback.
5. **Refine.** Ask about the gaps: with options and a recommendation when there is a reasonable range, open otherwise. Check for: the decision the spike unblocks; what earlier spikes or docs already answer, so it is not measured again; what is answered and what is only observed; risks that would end the spike early.
6. **Playback.** Write Context and Questions. The main question is answered by a verdict; each Q is answerable with evidence. If the questions serve two independent decisions, propose splitting the spike now.
7. **Exit criteria.** Each is a measurable threshold, hard cut or guide. Then the timebox and what ends the run, and whether one variant meeting the criteria is enough. They are fixed here, before anything runs.
8. **Open questions**, whenever they come up.
9. **Approval.** With no Open questions left, ask for the Questions approval. Once approved, check Questions in Phase.

## 2. Method

1. **Approach.** Propose the variants, options or probes to compare; the owner adjusts. Each one must tell something the others do not; propose cutting one that does not. Before measuring anything, make a rough worst-case estimate (Fermi estimate); if it settles the decision, it is not measured.
2. **Decisions about how:**

   - what is being decided and why it matters, in 2–3 lines;
   - the options, each with its practical consequence;
   - the recommendation marked, with a one-line reason and the standard or pattern that applies.

   Typical concerns: what runs where, schedule and window, what is captured and logged, how the evidence is analysed (checks instead of tests: known arithmetic, independent counts, fault injection), cost limits and tear-down. A cross-cutting decision becomes an ADR, linked in the header.
3. **Shared behaviour,** when several variants follow the same rules.
4. **File layout** under `spikes/<short-title>/`, README included, captured data and outputs ignored by Git (ADR-0009).
5. **Approval.** Ask for the Method approval. Once approved, check Method in Phase. Steps may follow in the same session.

## 3. Steps

1. **Prerequisites.** List what the owner prepares outside the repo before Step 1 (installs on the local machine, accounts, access), with exact versions decided now.
2. Propose the step skeleton as a compact table (step · title · who · gate · files); the owner adjusts order and cuts. Shape it so that:
   - the cheapest test of the riskiest assumption runs first, with a Gate, before a full variant is built on it;
   - code and the Owner action that runs it are separate steps;
   - each analysis script is followed by an Owner step that verifies it;
   - no step writes the Conclusion, which follows the last step (§ 4).
3. Write each step in full. Owner steps give exact commands and what to report back; Claude steps name their files and what they must not touch.
4. Ask for the Steps approval. Once approved, check Steps in Phase and tell the owner to run `/spike sNNN review-steps` in a new session. The spike goes to Ready 🎬 when that review closes.

## 4. Conclusion

Applies to a spike with steps, when Conclusion is the first unchecked item in Phase. Stop and report if a step is not ✅, unless it is ⛔ with its Gate's consequence recorded in the Decision log.

1. Read the doc in full, through 4. Findings.
2. Go through 5. Conclusion of the template with the owner, part by part: discuss each part, and write it as its own edit once agreed.
3. Tear-down: what is torn down and what is kept; a kept resource gets a Decision log entry. The owner runs the tear-down.
4. Deliver each item in 5.6 Records, each ADR in its own commit, and mark it Done.
5. With every record Done: check Conclusion in Phase, set State to Concluded ✅, Finished (UTC date) and Current step to —. Tell the owner it is a commit point and propose `docs: conclude spike sNNN`.

## End of session

A session ends with a section, approval or review saved and Status updated.

## Review

Applies to `review-steps`, together with its review file.

### Findings

Report a finding only if you can quote the passage and name its consequence. Grade it with the Severity in the review file.

Present them in two separate sections, writing "None" when empty:

1. **Blocking and important.** Per finding: severity, quote, consequence, suggested fix.
2. **Minor.** Per finding: quote, short reason.

### Fixes

The owner decides which findings to fix. Apply each accepted fix to the section or step it concerns; the owner approves on the edit's diff. One finding per message when a fix needs a decision. When the review closes, in the same change: check Steps review in Phase and set State to Ready 🎬.
