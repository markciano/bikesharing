# Design: GitHub Issues migration

- **Task:** T055
- **ADRs:** [ADR-0013](../decisions/0013-github-flow-with-rebase-merge.md)
- **New ADRs from this doc:** [ADR-0034](../decisions/0034-task-tracking-in-github-issues.md)

## Status

- State: Draft 📝
- Phase: [x] Spec · [x] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
- Current step: —

## 1. Spec — what and why

### 1.1 Context

Tasks are tracked in a markdown table, `docs/tasks.md`, which has no native way to group tasks or to show dependencies, and whose statuses are updated by hand. Building the pipeline will split large tasks into many smaller ones, so tracking moves to GitHub Issues before that work starts (T039, T040, T041). The owner works alone and on one task at a time, so tasks need only basic statuses, and dependencies inform the order without blocking any work. Claude Code must read and create tasks in GitHub Issues as it does today in the table.

### 1.2 Done when

This task changes no code, so it has no requirements or tests: this list is the acceptance criteria, and the Check of each step verifies its items.

- Every item in File layout is delivered.
- Every TODO citing this task is resolved or re-pointed.
- Issues are enabled on `markciano/bikesharing`, and every open task from `docs/tasks.md` exists there as an issue.
- A real PR into `main`, under its ruleset and with a rebase merge, closes its linked issue.
- The throwaway repository `markciano/bikesharing-issues-probe` is deleted.
- Claude Code reads, creates and groups issues with `gh`, and dependencies between issues are visible.
- No rule or skill treats `docs/tasks.md` as the live task table.

### 1.3 Out of scope

No task covers these items, because none of them is planned:

- Migrating the 40 closed tasks: they stay in `docs/tasks.md`.
- A GitHub Project board: the basic statuses do not need one, and it requires a wider token scope.
- Rewriting the `TNNN` references already written in documents and code: they stay as they are.

## 2. Plan — how

Open tasks move to GitHub Issues, keeping their `TNNN` IDs, while closed tasks stay in a frozen `docs/tasks.md`. A throwaway repository verified how GitHub behaves before this plan was written.

### 2.1 Approach

#### Task model

- A task is one issue. Its title is one short phrase, `TNNN (efM): task name`, with the effort in the parentheses, e.g. `T056 (ef3): Write README`. PR titles stay `TNNN: Task name`.
- The body is free text with no template, and it holds the detail: what is wanted, why, and what is needed to start. Once a task has a working document, that document is the source of truth.
- An issue does not link its design or spike. The working document names its task in its header, and an issue shows the PR that closes it, which lists the files changed.
- A group of tasks is a parent issue with sub-issues. A child's ID is `TNNN.M`.
- `blocked-by` shows the order between tasks and between groups. It informs and does not block.
- The next ID is the highest `TNNN` in use, looked up when a task is created.
- `docs/tasks.md` stays where it is, frozen, with the 40 closed tasks and a note pointing to GitHub Issues.

#### Task flow

| Status | In GitHub | How it changes |
|---|---|---|
| Waiting | Open issue, no linked PR | On creation |
| In progress | Open issue with a linked draft PR | On the first push; before it, work happens only on the local branch |
| Done | Closed issue | On merging the PR that closes it |
| Blocked (optional) | Open issue with `blocked-by` | When it applies |

The detailed state of a task with a working document stays in that document's Status.

1. **Create.** Claude Code proposes the title, body, parent and dependencies. Once the owner approves, it runs `gh issue create`. The owner can also create issues on the web.
2. **Start.** The owner creates the branch `tNNN-short-title`, as today.
3. **First push.** The owner opens the draft PR. Claude Code provides the PR description, with `Closes #N` looked up from the task's `TNNN`.
4. **Merge.** A rebase merge closes the issue.
5. **Close a parent.** The PR of the last child also carries `Closes #P` for its parent, each issue with its own keyword. If that does not work or complicates the PR, the owner closes the parent by hand.

#### `gh` permissions

`.claude/settings.json` has rules for `git` but none for `gh`, which reaches the same actions through the GitHub API. It gets these rules:

| Commands | Rule | Reason |
|---|---|---|
| `gh issue list`, `gh issue view`, `gh pr list`, `gh pr view`, `gh pr checks` | Allow | Read only |
| `gh issue create`, `gh issue edit`, `gh issue close` | Ask | They publish to a public repository |
| `gh pr merge`, `gh repo delete` | Deny | Merging belongs to the owner, and deleting a repository cannot be undone |
| `gh api` | Deny | It can create commits and merge PRs, which bypasses every other rule; the task flow does not need it |
| Any other `gh` command | Ask | The default mode already does this |

#### Open tasks in GitHub Issues

Each open task in `docs/tasks.md` becomes one issue. Its current effort goes in the title, a long row is cut to a short title, and the rest of its text goes in the body. Dependencies on closed tasks are dropped; those on open tasks stay. The empty `T056` row does not become an issue.

| Task | Effort | Group | `blocked-by` |
|---|---|---|---|
| T039 | 5 | Parent; its design adds the children | — |
| T040 | 8 | Parent; its design adds the children | — |
| T041 | 5 | Parent; its design adds the children | T040 |
| T042 | 3 | None | — |
| T044 | 2 | None | T040 |
| T010 | 3 | None | — |
| T024 | 1 | None | — |
| T027 | 2 | None | — |
| T053 | 1 | None | — |
| T054 | 1 | None | — |
| T055 | 3 | None | — |

#### Where the task rules live

| Place | Content |
|---|---|
| `/task` skill | Task definition, title and body format, effort scale, groups, `blocked-by` and how to create an issue. Claude Code can invoke it, and so can the owner |
| `CLAUDE.md` | The PR description carries `Closes #N`, and the last child's also closes its parent; `/task` in the list of skills |
| Design and spike skills | Anything out of scope is proposed as a task with `/task` |

`.claude/rules/docs/tasks.md` is removed, because its `paths` scope would stop loading it once `docs/tasks.md` is frozen.

#### Verified GitHub behaviour

Tested on 2026-11-03 with `gh` 2.103.3 in a public repository of a personal account, with no ruleset.

| Behaviour | Result |
|---|---|
| Sub-issues and `blocked-by` | Work on a personal account, created and read with `gh` |
| Whole-table read | `gh issue list --state all --json number,title,state,parent,blockedBy,subIssuesSummary` returns all fields in one call, newest first |
| Order of children | Reorderable on the web and through the API, and kept when read with `gh issue view` |
| Closing a blocked issue | Allowed; the `blocked-by` relationship stays |
| `Closes #N` in a PR body, rebase merge | Closes the issue and links the PR; `closingIssuesReferences` was empty just after the PR was created and correct after the merge |
| Closing all children | The parent stays open at 100%; it is closed by hand |
| Numbering | Issues and PRs share one sequence, so issue numbers never match `TNNN` |
| Lookup by ID | `T900 in:title` also returns the children `T900.M`; `T900.2 in:title` returns only that task. Titles with parentheses are untested |
| Search filters that work | `is:blocked`, `is:blocking`, `has:parent-issue`, `no:parent-issue`, `parent-issue:owner/repo#N`, `blocked-by:owner/repo#N` |
| Search filters to avoid | `blocked-by:N` and `blocking:N` return nothing; `has:sub-issues` and `no:sub-issues` return every issue |

### 2.2 Decision summary

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Task model](#task-model) | Move open tasks only | Recreating 40 closed tasks adds no value | — | Plan |
| 2 | [Task model](#task-model) | Group with sub-issues, following the parent-issue (epic) pattern; `blocked-by` is informative | Parents map to current parent tasks, can depend on each other, and worked in the test | — | Plan |
| 3 | [Task model](#task-model) | Keep `TNNN` in the title instead of the issue number | Adopting issue numbers means changing 171 references in 25 files and leaves two ID series | — | Plan |
| 4 | [Task model](#task-model) | Put effort in the title as `(efM)` | Visible at a glance, and effort is not filtered | — | Plan |
| 5 | [Task model](#task-model) | Free-text body, no issue template | Nothing needs a template yet | — | Plan |
| 6 | [Task model](#task-model) | No link from an issue to its working document | An issue already leads to its files through its PR, and the document names its task | — | Plan |
| 7 | [Task model](#task-model) | Freeze `docs/tasks.md` where it is | Links from 12 documents keep working, and closed tasks stay visible | — | Plan |
| 8 | [Task flow](#task-flow) | Reduce statuses to waiting, in progress, done and optional blocked | One person on one task at a time needs no more; the detail stays in the working document | — | Plan |
| 9 | [Task flow](#task-flow) | No label for in progress; a linked draft PR shows it | Simplest option, and nothing is needed before the first push | — | Plan |
| 10 | [Task flow](#task-flow) | Claude Code creates issues after the owner's OK | Closest to proposing a table row today, and an issue is easy to edit or close | — | Plan |
| 11 | [Task flow](#task-flow) | The last child's PR closes the parent; by hand if it complicates things | No extra step, and GitHub does not close parents on its own | — | Plan |
| 12 | [`gh` permissions](#gh-permissions) | Allow `gh` reads, ask for issue writes, deny `gh pr merge` and `gh repo delete` | Least privilege, in line with the existing `git` rules | — | Plan |
| 13 | [`gh` permissions](#gh-permissions) | Deny `gh api` | It bypasses every other rule, and the task flow does not need it | — | Plan |
| 14 | [Open tasks](#open-tasks-in-github-issues) | T039, T040 and T041 are three parents, with no level above them | It keeps the current structure, and `blocked-by` shows the order between them | — | Plan |
| 15 | [File layout](#23-file-layout) | Write rules and skills during the Plan, as the design process sets, with no staged cutover | Simplest option, and the long-term configuration is what matters; the remaining sessions of this task can absorb the friction | — | Plan |
| 16 | [Task rules](#where-the-task-rules-live) | Task rules in a `/task` skill that Claude Code can invoke, with only the PR rule in `CLAUDE.md` | Little stays always loaded, and creating an issue still asks for confirmation | — | Plan |
| 17 | [Task rules](#where-the-task-rules-live) | No hook for the task rules | A hook fires when the command runs, after the task has been proposed | — | Plan |
| 18 | [File layout](#23-file-layout) | A spike closes once its Records are delivered | Today it reads Concluded while documents are still pending; the task itself now closes on merge | — | Plan |

### 2.3 File layout

```text
CLAUDE.md                                (modified)  /task in the skills list, Closes #N in the PR flow, task status rule removed, Pending items, structure
docs/
├── tasks.md                             (modified)  Frozen: 40 closed tasks and a note; open rows removed
├── architecture.md                      (modified)  Two mentions of the table as the place for open work
├── designs/d003-github-issues-migration.md  (new)   This design
└── decisions/0034-task-tracking-in-github-issues.md  (new)  The decision
.claude/
├── settings.json                        (modified)  gh permission rules
├── rules/docs/
│   ├── tasks.md                         (removed)   Replaced by the /task skill
│   └── general.md                       (modified)  Example of how to cite a task
└── skills/
    ├── task/SKILL.md                    (new)       Task rules, invocable by Claude Code and the owner
    ├── design/SKILL.md                  (modified)  Read the issue, propose tasks with /task, no status change
    ├── design/template.md               (modified)  Comment naming the table
    ├── design/review-steps.md           (modified)  No task row at Ready
    ├── spike/SKILL.md                   (modified)  Same as the design skill; a spike closes once its Records are delivered
    ├── spike/template.md                (modified)  Comment naming the table; Records status
    ├── implement/SKILL.md               (modified)  No task status on the first step
    ├── implement/spike.md               (modified)  No task status on the first step
    └── implement/review.md              (modified)  No task status at close, gaps proposed with /task
```

### 2.4 What does not change

- [ADR-0013](../decisions/0013-github-flow-with-rebase-merge.md): branches, PRs, checks and rebase merge stay as they are.
- `.github/workflows/`: no job depends on `docs/tasks.md`.
- Closed spikes, designs and ADRs that cite `docs/tasks.md` or a `TNNN`: their links stay valid.
- `docs/architecture.md` where it cites a closed task.
- The State field of designs and spikes, which keeps its detailed values.

## 3. Steps

### 3.1 Prerequisites

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:**
- **R:** —
- **Model:** `<model · effort>` (or —)

#### Scope

#### Reads

#### Do

#### Check

## 4. Close

### 4.1 Implemented

### 4.2 Known gaps at close

- `<gap>` — TNNN

### 4.3 Decisions taken during implementation
