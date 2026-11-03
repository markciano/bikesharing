# Design: GitHub Issues migration

- **Task:** T055
- **ADRs:** `<ADRs this design must respect, or "none">`
- **New ADRs from this doc:** `<ADRs created during this design, or "none">`

## Status

- State: Draft 📝
- Phase: [x] Spec · [ ] Plan · [ ] Plan review · [ ] Steps · [ ] Steps review
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
- After the cutover, no rule or skill treats `docs/tasks.md` as the live task table.
- At no point does a rule or skill describe a process that does not exist yet.

### 1.3 Out of scope

No task covers these items, because none of them is planned:

- Migrating the 40 closed tasks: they stay in `docs/tasks.md`.
- A GitHub Project board: the basic statuses do not need one, and it requires a wider token scope.
- Rewriting the `TNNN` references already written in documents and code: they stay as they are.

## 2. Plan — how

### 2.1 Approach

### 2.2 Decision summary

| # | Applies to | Decision | Reason | R | Decided at |
|---|---|---|---|---|---|
| | | | | | |

### 2.3 File layout

```text
<path>/
└── <file>      (new)        <purpose>
```

### 2.4 Breaking changes

| File | Why it breaks | Strategy |
|---|---|---|
| | | |

### 2.5 What does not change

-

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
