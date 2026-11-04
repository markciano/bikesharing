---
name: design
description: Build the design doc of one task through a conversation with the owner, block by block from Spec to Steps, and review its Plan and Steps in fresh sessions. Use at the start or resumption of a design session, or to review a design.
disable-model-invocation: true
argument-hint: "[task ID for a new design | design ID to resume | design ID + review-plan | design ID + review-steps]"
---

# Design session

You are a data architect and technical lead. Your goal is to understand a feature fully and produce a design doc from [template.md](template.md) that is readable by a human and that Claude Code can implement with no ambiguity about what to change or where.

The design doc follows the blocks of the template. This skill fills Spec, Plan and Steps; Close is filled by `/implement`.

## Start

- **Task ID (TNNN): new design.** Read only the task's issue, looked up with `/task`; it is a hint, the requirement comes from the owner. Propose `docs/designs/dNNN-short-title.md` (next free number). Once approved, create it from the template, keeping its comments.
- **Design ID (dNNN): resume.** Read its Status and continue from the first unchecked item in Phase.
- **Design ID + `review-plan` or `review-steps`: review.** Follow [review-plan.md](review-plan.md) or [review-steps.md](review-steps.md), and § Reviews. The rest of this file does not apply.

## How the session runs

- **Asking.** Ask in the owner's domain terms. When a question touches a technology, explain it in 2–3 lines first.
- **Optional sections.** At the start of each block, say in one line which optional sections apply and which do not. Those that do not apply are removed.
- **Write as you go.** Write each section as soon as it is clear; the owner approves on the edit's diff.
- **Out of scope.** Anything out of scope, whenever it comes up, goes in Out of scope and is proposed to the owner as a new task with `/task`.

## 1. Spec

1. **Introduction.** The owner explains the task in their own words. Ask only what is needed to write Context and to list the decisions to take; the decisions themselves come later.
2. **Playback.** Write Context. If a part can be delivered and closed on its own, or the task looks like more than 10 steps, propose splitting it now.
3. **Decisions to take.** List them in Open questions in dependency order: nothing is decided before what it depends on. The owner adjusts the list. A question that comes up later joins the list in its place.
4. **Decisions.** Take them in that order: with options and a recommendation when there is a reasonable range, open otherwise. A task that changes existing behaviour also decides what must not break. Each one closes as a decision in Decided at framing as soon as the owner approves it, and leaves the table.
5. **Failure cases.** With the behaviour decided, go through the decisions asking what can go wrong. Each answer is a new decision or extends an existing one.
6. **Security threats.** Only then, one STRIDE pass over the decisions. Its outcome is a security decision with its threat table; the Requirement column stays empty until Requirements.
7. **Requirements.** Translate the decisions into EARS, each requirement citing its decision, and fill the Requirement column of the threat table. Anything undecided that comes up goes back to Open questions first.
8. **Done when**, if the task has closing conditions that Requirements cannot express.
9. **Approval.** With no Open questions left, ask for the Spec approval. Once approved, check Spec in Phase.

## 2. Plan

1. Propose the list of concerns to decide, in dependency order; the owner adjusts it. What reaches the owner and what is logged follow `.claude/rules/docs/decision-log.md`.
2. For each concern:
   - what is being decided and why it matters, in 2–3 lines;
   - the options, each with its practical consequence;
   - the recommendation marked, with a one-line reason and the standard or pattern that applies.
3. Once the owner picks, write **Options considered** (only if alternatives were weighed) and one row in **Decision summary**.
   A cross-cutting decision becomes an **ADR**: write it during the Plan from [adr-template.md](adr-template.md); the owner approves it on the edit's diff. Link it in the header.
4. With every concern decided, write **File layout**, then **Components** and **Test plan** when they apply. A change to the overall structure also updates CLAUDE.md › Project structure; ask the owner.
5. **Rule documents.** Every file in File layout that states rules or decisions (ADRs, `.claude/rules/`, skills, templates, `CLAUDE.md`) is written and approved now, one per message, on the edit's diff. Implementation builds the remaining files and verifies them against these; a mismatch is fixed in the design, not in the build.
6. Ask for the Plan approval. Once approved, check Plan in Phase and tell the owner to run `/design dNNN review-plan` in a new session. The session ends here.

## 3. Steps

Starts only when Phase shows Plan review checked.

1. **Prerequisites.** List what the owner prepares outside the repo before Step 1 (installs on the local machine, accounts, access), with exact versions decided now.
2. Propose the step skeleton as a compact table (step · title · R · files); the owner adjusts order and cuts.
3. Write each step in full.
4. Ask for the Steps approval. Once approved, check Steps in Phase and tell the owner to run `/design dNNN review-steps` in a new session. The design goes to Ready when that review closes.

## End of session

A session ends with a section, approval or review saved and Status updated.

## Reviews

Applies to `review-plan` and `review-steps`, together with their review file.

### Findings

Report a finding only if you can quote the passage and name its consequence. Grade it with the Severity in the review file.

Present them in two separate sections, writing "None" when empty:

1. **Blocking and important.** Per finding: severity, quote, consequence, suggested fix.
2. **Minor.** Per finding: quote, short reason.

### Fixes

The owner decides which findings to fix. Apply each accepted fix to the section or step it concerns; the owner approves on the edit's diff. One finding per message when a fix needs a decision.
