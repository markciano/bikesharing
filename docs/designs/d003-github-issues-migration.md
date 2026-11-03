# Design: GitHub Issues migration

- **Task:** T055
- **ADRs:** [ADR-0013](../decisions/0013-github-flow-with-rebase-merge.md)
- **New ADRs from this doc:** [ADR-0034](../decisions/0034-task-tracking-in-github-issues.md)

## Status

- State: Complete ✅
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [x] Steps review
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
- Claude Code reads and creates issues with `gh`, dependencies between issues are visible, and grouping was verified in the [throwaway repository](#verified-github-behaviour). **#23**
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

- A task is one issue. Its title is one short phrase, `TNNN (efM): task name`, with the effort in the parentheses, e.g. `T900 (ef3): Add a station map`. PR titles stay `TNNN: Task name`.
- The body is free text with no template, and it holds the detail: what is wanted, why, and what is needed to start. Once a task has a working document, that document is the source of truth.
- An issue does not link its design or spike. The working document names its task in its header, and an issue shows the PR that closes it, which lists the files changed.
- A group of tasks is a parent issue with sub-issues. A parent's title ends in `[parent]`, and a child's ID is `TNNN.M`. **#22**
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
2. **Start.** The owner creates the branch from `main`: `tNNN-short-title`, or `tNNN.M-short-title` for a child.
3. **First push.** The owner opens the draft PR. Claude Code provides the PR description, with `Closes #N` looked up from the task's `TNNN`.
4. **Merge.** A rebase merge closes the issue.
5. **Parent's own document.** The PR that delivers a parent's working document carries `Refs #P` instead of `Closes #P`, so the parent stays open once that branch is merged.
6. **Close a parent.** The PR of the last child also carries `Closes #P` for its parent, each issue with its own keyword. If that does not work or complicates the PR, the owner closes the parent by hand. **#20**

#### `gh` permissions

`.claude/settings.json` has rules for `git` but none for `gh`, which reaches the same actions through the GitHub API. It gets these rules:

| Commands | Rule | Reason |
|---|---|---|
| `gh issue list`, `gh issue view`, `gh pr list`, `gh pr view`, `gh pr checks` | Allow | Read only |
| `gh issue create`, `gh issue edit`, `gh issue close` | Ask | They publish to a public repository |
| `gh pr merge`, `gh repo delete` | Deny | Merging belongs to the owner, and deleting a repository cannot be undone |
| `gh api` | Deny | It can create commits and merge PRs, which bypasses every other rule; the task flow does not need it |
| Any other `gh` command | Ask | The default mode already does this |

The repository is public, so anyone can read its issues, and only collaborators can create them. `/task` lookups also use `--author @me`, and an issue by another author is untrusted data, read only when the owner asks. **#19, #21**

#### Open tasks in GitHub Issues

Each open task in `docs/tasks.md` becomes one issue. Its current effort goes in the title, a long row is cut to a short title, and the rest of its text goes in the body. Dependencies on closed tasks are dropped; those on open tasks stay. The empty `T056` row does not become an issue. T024 has no PR, so it reads as Waiting once migrated.

`gh issue create` is not idempotent, so each task is checked against the whole-table read before its issue is created, which makes a re-run after a partial failure safe. Open rows leave `docs/tasks.md` only once all their issues exist.

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
| Lookup by ID | `T900 in:title` also returns the children `T900.M`; `T900.2 in:title` returns only that task. Titles with parentheses work. A new issue takes seconds to appear in a search, while the whole-table read shows it at once |
| Draft PR with `Closes #N` | The open issue shows the PR in `closedByPullRequestsReferences`, in `gh issue view` and `gh issue list` |
| Search filters that work | `is:blocked`, `is:blocking`, `has:parent-issue`, `no:parent-issue`, `parent-issue:owner/repo#N`, `blocked-by:owner/repo#N` |
| Search filters to avoid | `blocked-by:N` and `blocking:N` return nothing; `has:sub-issues` and `no:sub-issues` return every issue |

### 2.2 Decision summary

A decision that names no standard is a project choice to which none applies.

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| 1 | [Task model](#task-model) | Move open tasks only | Recreating 40 closed tasks adds no value | — | Plan |
| 2 | [Task model](#task-model) | Group with sub-issues, following the parent-issue (epic) pattern; `blocked-by` is informative | Parents map to current parent tasks, can depend on each other, and worked in the test | — | Plan |
| 3 | [Task model](#task-model) | Keep `TNNN` in the title instead of the issue number | Adopting issue numbers means changing over 400 references in 55 files and leaves two ID series | — | Plan |
| 4 | [Task model](#task-model) | Put effort in the title as `(efM)` | Visible at a glance, and effort is not filtered | — | Plan |
| 5 | [Task model](#task-model) | Free-text body, no issue template | Nothing needs a template yet | — | Plan |
| 6 | [Task model](#task-model) | No link from an issue to its working document | An issue already leads to its files through its PR, and the document names its task | — | Plan |
| 7 | [Task model](#task-model) | Freeze `docs/tasks.md` where it is | Links from 12 documents keep working, and closed tasks stay visible | — | Plan |
| 8 | [Task flow](#task-flow) | Reduce statuses to waiting, in progress, done and optional blocked | One person on one task at a time needs no more; the detail stays in the working document | — | Plan |
| 9 | [Task flow](#task-flow) | No label for in progress; a linked draft PR shows it | Simplest option, and nothing is needed before the first push | — | Plan |
| 10 | [Task flow](#task-flow) | Claude Code creates issues after the owner's OK | Closest to proposing a table row today, and an issue is easy to edit or close | — | Plan |
| 11 | [Task flow](#task-flow) | The last child's PR closes the parent; by hand if it complicates things **→ #20** | No extra step, and GitHub does not close parents on its own | — | Plan |
| 12 | [`gh` permissions](#gh-permissions) | Allow `gh` reads, ask for issue writes, deny `gh pr merge` and `gh repo delete` | Least privilege, in line with the existing `git` rules | — | Plan |
| 13 | [`gh` permissions](#gh-permissions) | Deny `gh api` | It bypasses every other rule, and the task flow does not need it | — | Plan |
| 14 | [Open tasks](#open-tasks-in-github-issues) | T039, T040 and T041 are three parents, with no level above them | It keeps the current structure, and `blocked-by` shows the order between them | — | Plan |
| 15 | [File layout](#23-file-layout) | Write rules and skills during the Plan, as the design process sets, with no staged cutover | Simplest option, and the long-term configuration is what matters; the remaining sessions of this task can absorb the friction | — | Plan |
| 16 | [Task rules](#where-the-task-rules-live) | Task rules in a `/task` skill that Claude Code can invoke, with only the PR rule in `CLAUDE.md` | Little stays always loaded, and creating an issue still asks for confirmation | — | Plan |
| 17 | [Task rules](#where-the-task-rules-live) | No hook for the task rules | A hook fires when the command runs, after the task has been proposed | — | Plan |
| 18 | [File layout](#23-file-layout) | A spike closes once its Records are delivered | Today it reads Concluded while documents are still pending; the task itself now closes on merge | — | Plan |
| 19 | [`gh` permissions](#gh-permissions) | Filter `/task` lookups by author and treat other authors' issues as untrusted, following least privilege | A public repository lets anyone open an issue, which could fake the next ID or carry instructions for Claude Code | — | Plan review |
| 20 | [Task flow](#task-flow) | A parent's own document merges with `Refs #P`, and a child's branch is `tNNN.M-short-title`, following GitHub Flow **extends #11** | `Closes #P` would close the parent before its children exist, and the branch name had no form for a child | — | Plan review |
| 21 | [`gh` permissions](#gh-permissions) | Only collaborators can create issues, with the author filter of #19 kept as a second layer, following defense in depth | Strangers cannot add noise or instructions, and `/task` does not depend on a setting outside the repository | — | Steps |
| 22 | [Task model](#task-model) | A parent's title ends in `[parent]` | A parent reads as one in the list of issues, with no need to open it | — | Steps |
| 23 | [Done when](#12-done-when) | Grouping is verified by the test in the throwaway repository, not in `markciano/bikesharing` | A test child would stay forever in a public repository and take a `T039.M` ID; T039's design will create real children | — | Steps review |

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

- Issues are enabled on `markciano/bikesharing`, with issue creation limited to collaborators, in Settings › General › Issues. Verify that `gh repo view --json hasIssuesEnabled` returns `true`; the limit is checked on that settings page.

### Step 1 — Verify the `gh` permission rules

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: verify gh permissions for design d003`
- **R:** —
- **Model:** sonnet · low

#### Scope

Confirms that the rules already in `.claude/settings.json` behave as planned. It changes only this step's status in this design. It tries one denied command on purpose, read-only, and does not change the rules.

#### Reads

- [`gh` permissions](#gh-permissions): the rules and why `gh api` is denied.

#### Do

1. Run `gh issue list --limit 1 --json number`, which must run with no confirmation.
2. Run `gh api user --jq .login` once, which must be rejected. Do not retry it or reach the same data another way.
3. If a command behaves differently, set this step to ⛔ and report it; do not change `.claude/settings.json`.

#### Check

The first command returned JSON with no confirmation, and the second was rejected by the permission rules: yes/no.

### Step 2 — Create the open tasks as issues

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: record issue creation for design d003`
- **R:** —
- **Model:** sonnet · low

#### Scope

Creates the 11 issues below on `markciano/bikesharing`, and the two `blocked-by` relationships. Each `gh issue create` and `gh issue edit` asks the owner for confirmation. It changes only this step's status in this design. It creates no children: each parent's design adds them. `docs/tasks.md` is not touched here.

| Title | Body | `blocked-by` |
|---|---|---|
| `T039 (ef5): Capture in production [parent]` | Its design splits it into `T039.M` tasks. | — |
| `T040 (ef8): Processing pipeline [parent]` | Its design splits it into `T040.M` tasks. | — |
| `T041 (ef5): Visualization [parent]` | Its design splits it into `T041.M` tasks. | T040 |
| `T042 (ef3): Data quality` | Checks and targets beyond the basics. | — |
| `T044 (ef2): Cross-file link and anchor check` | Add a cross-file link and anchor check to the `docs` CI job, because MD051 checks only same-file anchors. Trial lychee and remark-validate-links on a broken anchor first. | T040 |
| `T010 (ef3): Write README` | Write the repository README. | — |
| `T024 (ef1): Code convention hooks` | Hooks for the code conventions of each language in the project. | — |
| `T027 (ef2): Automated dependency updates` | Automated dependency and runtime updates, choosing between Dependabot and Renovate. It covers the security-patch risk of exact pins in ADR-0016, and picks up the upstream fixes deferred in T029. | — |
| `T053 (ef1): Keep template comments in new spike docs` | In the `/spike` skill, keep the template comments of future blocks when creating a spike doc, since later sessions need them. | — |
| `T054 (ef1): Unify threat IDs under TH` | Unify the threat IDs of the STRIDE analyses under the `TH` prefix (`A` in s011, `E` in s012), and add the prefix to the ID rule in `.claude/rules/docs/general.md`. | — |
| `T055 (ef3): Move task tracking to GitHub Issues` | Move task tracking from `docs/tasks.md` to GitHub Issues: open tasks only, grouped with sub-issues and informative `blocked-by` dependencies. | — |

#### Reads

- [Open tasks in GitHub Issues](#open-tasks-in-github-issues): the mapping, and why each creation is checked first.
- `.claude/skills/task/SKILL.md` § Create a task: the commands.

#### Do

1. Read the whole table with `gh issue list --author @me --state all --limit 500 --json number,title,state,blockedBy`.
2. In the order of the table above, for each task not yet in that read, run `gh issue create --title '<title>' --body '<body>'`, in single quotes so that backticks stay literal. If a run is interrupted, go back to action 1.
3. Run `gh issue edit <T041's number> --add-blocked-by <T040's number>`.
4. Run `gh issue edit <T044's number> --add-blocked-by <T040's number>`.

#### Check

The read of action 1, run again, returns exactly the 11 titles above, all open and with no duplicates, and T041 and T044 list T040 in `blockedBy`: yes/no.

### Step 3 — Freeze the task table

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: freeze the task table`
- **R:** —
- **Model:** sonnet · low

#### Scope

- `docs/tasks.md`: a note under the title, and the open and empty rows removed, leaving the 40 closed tasks.
- `docs/architecture.md`: the two mentions of the table as the place for open work.
- This step's status in this design.

The mention at `docs/architecture.md` that cites `tasks.md › T036` stays, because T036 is closed.

#### Reads

- [Open tasks in GitHub Issues](#open-tasks-in-github-issues): rows leave the table only once all their issues exist, which Step 2 verified.

#### Do

1. In `docs/tasks.md`, add under the title: `Frozen: this table holds closed tasks only. Open and new tasks are in [GitHub Issues](https://github.com/markciano/bikesharing/issues).`
2. In `docs/tasks.md`, remove the rows T010, T024, T027, T039, T040, T041, T042, T044, T053, T054, T055 and T056.
3. In `docs/architecture.md`, in the line starting `- **Decisions in dependency order:**`, replace `[tasks.md](tasks.md).` with `[GitHub Issues](https://github.com/markciano/bikesharing/issues).`
4. In `docs/architecture.md`, replace `Open decisions are tasks in [tasks.md](tasks.md), in dependency order.` with ``Open decisions are tasks in [GitHub Issues](https://github.com/markciano/bikesharing/issues), with `blocked-by` showing their order.``

#### Check

`grep -c '^| T' docs/tasks.md` returns `40`, `grep '^| T' docs/tasks.md | grep -vc '✅'` returns `0`, and `grep -c 'tasks.md' docs/architecture.md` returns `1`: yes/no.

### Step 4 — Open the draft PR

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: record the draft PR of design d003`
- **R:** —
- **Model:** —

#### Scope

Pushes the branch, opens the draft PR of T055 with `Closes #N`, and confirms that the issue shows the PR. It changes only this step's status in this design. The PR stays in draft until the final review of `/implement` closes. The merge belongs to the close of the task, not to this step: right after it, the owner confirms that the issue closed, and if it did not, closes it by hand and proposes a task to correct the rule in `CLAUDE.md`.

#### Reads

- [Task flow](#task-flow): how an issue and its PR relate.

#### Do

1. Find the issue number of T055:

   ```bash
   gh issue list --author @me --state all --search "T055 in:title" --json number,title
   ```

2. Push the branch:

   ```bash
   git push -u origin t055-gh-issues-migration
   ```

3. Open the draft PR, replacing `N` with the number from action 1:

   ```bash
   gh pr create --draft --title 'T055: Move task tracking to GitHub Issues' --body 'Move task tracking from `docs/tasks.md` to GitHub Issues: open tasks become issues, closed tasks stay in a frozen table, and the task rules move to a `/task` skill. It also adds `gh` permission rules. Design: d003. Decision: ADR-0034.

   Closes #N'
   ```

4. Confirm the link and the CI run, replacing `N` as above:

   ```bash
   gh issue view N --json closedByPullRequestsReferences
   gh pr checks --watch
   ```

Report the PR number, the output of `gh issue view`, and the result of the checks.

#### Check

`closedByPullRequestsReferences` lists the PR, and every required check passes: yes/no.

### Step 5 — Delete the throwaway repository

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: record the probe repository removal in design d003`
- **R:** —
- **Model:** —

#### Scope

Deletes `markciano/bikesharing-issues-probe`, which holds only test issues and PRs. It changes only this step's status in this design.

#### Reads

None.

#### Do

1. Delete `markciano/bikesharing-issues-probe` in its Settings › General › Danger Zone, checking the repository name in the confirmation.
2. Run `gh repo view markciano/bikesharing-issues-probe` and report the result.

#### Check

The command reports that the repository cannot be found: yes/no.

### Step 6 — Verify the deliverable

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `docs: verify the deliverable of design d003`
- **R:** —
- **Model:** sonnet · low

#### Scope

Verifies the items of [Done when](#12-done-when) that no earlier Check covers, and reads the final state of the issues. It changes only this step's status in this design. The merge that closes the T055 issue belongs to the close of the task, as Step 4 sets.

#### Reads

- [Done when](#12-done-when): the items to verify.
- [File layout](#23-file-layout): the expected files.

#### Do

1. Run `git diff --name-status main...HEAD` and compare it with File layout.
2. Run `grep -rn --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude=d003-github-issues-migration.md 'TODO(T055)' .`, which excludes this design because this action names the marker.
3. Run `grep -rn 'tasks\.md' .claude CLAUDE.md`.
4. Run `gh issue list --author @me --state all --limit 500 --json number,title,state,blockedBy,closedByPullRequestsReferences`.
5. If an action does not give the result in Check, set this step to ⛔ and report it.

#### Check

Every file in File layout appears in the diff with its status, action 2 returns nothing, action 3 returns only the two lines that describe `docs/tasks.md` as frozen, and action 4 returns the 11 titles of Step 2, with T041 and T044 listing T040 in `blockedBy` and T055 listing the PR of Step 4: yes/no.

## 4. Close

### 4.1 Implemented

- GitHub Issues: 11 open tasks created, with T041 and T044 blocked by T040; no children, since each parent's design adds them.
- `docs/tasks.md`: frozen with the 40 closed tasks; `docs/architecture.md` points to GitHub Issues.
- Claude Code configuration: `/task` skill, `gh` permission rules, and rules and skills moved off the table.
- Tests: none, as this task changes no code; the `docs` CI check passes.

### 4.2 Known gaps at close

- A real PR closing its issue under the ruleset is confirmed only at the merge of this task's PR, after this document reads Complete. If the issue stays open, the owner closes it by hand and proposes a task to correct the rule in `CLAUDE.md` — T055

### 4.3 Decisions taken during implementation

- Step 2: the bodies of the parent issues T039, T040 and T041 drop the words "Parent task.", since the `[parent]` title already says it. The owner edited T039's body on the web; the step's table shows the final text.
