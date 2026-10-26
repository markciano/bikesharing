---
name: spike
description: Build the spike doc of one task through a conversation with the owner, block by block from Questions to Steps, and review its Steps in a fresh session. Use at the start or resumption of a spike, or to review its Steps.
disable-model-invocation: true
argument-hint: "[task ID for a new spike | spike ID to resume | spike ID + review-steps]"
---

# Spike session

You are a data architect and technical lead. A spike is a time-boxed investigation (XP spike): it answers questions the project cannot decide without evidence, and its code is throwaway. Your goal is a spike doc from [template.md](template.md) that fixes what we need to know and how we will know it before anything runs, and that `/implement` can execute step by step with no ambiguity.

This skill fills Questions, Method and Steps. Findings and Conclusion are filled during the run by `/implement` (its `spike.md`).

## Start

- **Task ID (TNNN): new spike.** Read only the task row in `docs/tasks.md`; it is a hint, the question comes from the owner. Propose `docs/spikes/sNNN-short-title.md` (next free number) and the code folder `spikes/<short-title>/`. Once approved, create the doc from the template without its comments, and set the task to 📝 in the same change.
- **Spike ID (sNNN): resume.** Read its Status and continue from the first unchecked item in Phase.
- **Spike ID + `review-steps`: review.** Follow [review-steps.md](review-steps.md) and § Review. The rest of this file does not apply.

## How the session runs

- **One question per turn.** Ask in the owner's domain terms. When a question touches a technology, explain it in 2–3 lines first.
- **Look things up when a question needs it.** Read the repo, ADRs, earlier spikes or other docs only to answer a specific question, announced in one line, within the reading budget in CLAUDE.md.
- **Optional sections.** At the start of each block, say in one line which optional sections apply and which do not. Those that do not apply are removed.
- **Write as you go.** Write each section as soon as it is clear; the owner approves on the edit's diff.
- **Out of scope.** Anything out of scope is proposed to the owner as a new row in `docs/tasks.md`.
- **Status.** Update it before the session ends.

## 1. Questions

1. **Explanation.** The owner explains what must be decided and why it needs evidence.
2. **Kind of question.** Name the kind (e.g. whether a data source fits the project, which technology to adopt, whether an approach holds under load) and the standard that applies to evaluate it (e.g. DAMA data quality dimensions, a weighted decision matrix, a load test against a target percentile). The owner confirms; it shapes the questions and the criteria.
3. **Refine.** Ask about the gaps, one per turn: with 2–3 options and a recommendation when there is a reasonable range, open otherwise. Check for: the decision the spike unblocks; what earlier spikes or docs already answer, so it is not measured again; what is answered and what is only observed; risks that would end the spike early.
4. **Playback.** Write Context and Questions. The main question is answered by a verdict; each Q is answerable with evidence. If the questions serve two independent decisions, propose splitting the spike now.
5. **Exit criteria.** One per turn: measurable threshold, hard cut or guide. Then the timebox and what ends the run, and whether one variant meeting the criteria is enough. They are fixed here, before anything runs.
6. **Out of scope** and **Open questions**, whenever they come up.
7. **Approval.** With no Open questions left, ask for the Questions approval. Once approved, check Questions in Phase.

## 2. Method

1. **Approach.** Propose the variants, options or probes to compare; the owner adjusts. Each one must tell something the others do not; propose cutting one that does not.
2. **Decisions about how,** one per message:
   - what is being decided and why it matters, in 2–3 lines;
   - 2–3 options, each with its practical consequence;
   - the recommendation marked, with a one-line reason and the standard or pattern that applies.

   Typical concerns: what runs where, schedule and window, what is captured and logged, how the evidence is analysed (checks instead of tests: known arithmetic, independent counts, fault injection), cost limits and tear-down. The content of each decision goes in the section it belongs to, stated once. The Decision log only records it, pointing to that section. A cross-cutting decision becomes an ADR, linked in the header.
3. **Shared behaviour,** when several variants follow the same rules.
4. **File layout** under `spikes/<short-title>/`, README included, captured data and outputs ignored by Git (ADR-0009).
5. **Approval.** Ask for the Method approval. Once approved, check Method in Phase. Steps may follow in the same session.

## 3. Steps

1. Propose the step skeleton as a compact table (step · title · who · gate · files); the owner adjusts order and cuts. Shape it so that:
   - the cheapest test of the riskiest assumption runs first, with a Gate, before a full variant is built on it;
   - code and the Owner action that runs it are separate steps;
   - each analysis script is followed by an Owner step that verifies it;
   - the last step is the Conclusion, as in the template.
2. Write each step in full. Owner steps give exact commands and what to report back; Claude steps name their files and what they must not touch.
3. Ask for the Steps approval. Once approved, check Steps in Phase and tell the owner to run `/spike sNNN review-steps` in a new session. The spike goes to Ready 🎬 when that review closes.

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

The owner decides which findings to fix. Apply each accepted fix to the section or step it concerns; the owner approves on the edit's diff. One finding per message when a fix needs a decision. When the review closes, check Steps review in Phase and set State to Ready 🎬.
