---
status: Accepted
date: 2026-11-03
---

# Task tracking in GitHub Issues

## Context and problem statement

The project tracks its work in a task table kept as a file in the repository. Building the pipeline will split large tasks into many smaller ones, which raises the amount of tracking.

- Tasks need grouping, and an order between them that informs without blocking work.
- One person works on one task at a time, so tasks need only basic statuses, and every manual update is a cost.
- A coding agent must read and create tasks as part of the normal workflow.
- Hundreds of references to task IDs already exist in documents, code and PR titles, and they have to remain valid.
- The repository is public, so whatever the tracker publishes is visible to anyone.

## Considered Options

Each option is compared on grouping, dependencies, manual upkeep and what happens to existing task IDs.

### 1. GitHub Issues with sub-issues, keeping task IDs in the title

Each task is an issue titled with its existing ID. A group is a parent issue with sub-issues, and a `blocked-by` relationship shows the order.

- Pros:
  - groups and dependencies are native, and parents can depend on each other;
  - a merged PR closes its issue, so the status needs no manual update;
  - existing references stay valid, with a single ID series.
- Cons:
  - two identifiers per task: the project's ID and the issue number that GitHub assigns;
  - finding an issue from its task ID takes a search, and the next ID has to be looked up;
  - task state leaves Git and depends on a third party.

### 2. Keep the task table in the repository

No change.

- Pros:
  - no migration, and existing references stay valid;
  - task state stays in Git and is reviewed in diffs.
- Cons:
  - grouping and dependencies remain plain text;
  - statuses remain manual.

## Decision Outcome

**Chosen option:** 1. GitHub Issues with sub-issues, keeping task IDs in the title.

It gives native grouping and dependencies, and it removes the manual status upkeep, which are the forces the table does not meet. It keeps the existing references valid at the cost of one search per task, which is small for one person working on one task at a time.

Why not the other:

- Keeping the table: it stays manual, and the pipeline's tasks would make it grow where it is weakest.

**Scope:** Tracking open and future tasks. It does not cover closed tasks, which stay in the frozen table, or GitHub Flow, which [ADR-0013](0013-github-flow-with-rebase-merge.md) sets and this decision does not change.

### Consequences

#### Positive

- **Traceability:** an issue shows the PR that closes it, and through it the files changed.
- **No status upkeep:** merging closes the task.
- **Existing references stay valid:** task IDs do not change, and links to the frozen table keep working.

#### Negative

- **State outside Git:** task changes appear in no diff or commit, and they are public at once, so the agent's writes to issues ask for confirmation.
- **A new way around the permission rules:** the GitHub CLI and its API reach the same actions as the denied Git commands, so they need rules of their own, including denying direct API access.
- **Parents close by hand or through a PR:** GitHub does not close a parent when its children close.
- **Dependence on GitHub:** tracking needs the service available, and moving away means exporting the issues.

## More information

- Task model, flow, permissions and tested GitHub behaviour: [d003 › Approach](../designs/d003-github-issues-migration.md#21-approach).
