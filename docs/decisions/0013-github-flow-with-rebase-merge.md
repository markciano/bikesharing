---
status: accepted
date: 2026-10-18
---

# GitHub Flow with rebase merge and a protected main

## Context and Problem Statement

A single owner makes every commit (Claude only reads Git), commits follow `type(TNNN)`, and there is no CI yet. Spike s007 screened branching models against these constraints and validated the chosen flow in the real repo.

Which branching model, merge strategy and protection does the project use?

## Considered Options

* GitHub Flow: `main` plus one short-lived branch per task, PR, CI, rebase merge
* Trunk-based development: commits straight to `main`
* Git Flow: long-lived `develop` and release branches

## Decision Outcome

Chosen option: "GitHub Flow", with rebase merge and a ruleset on `main` without bypass: PR required (0 approvals), check `docs`, linear history, rebase merge only, no force push or deletion. The day-to-day procedure is in `CLAUDE.md` › Git; the evidence is in `docs/spikes/s007-git-branching-cicd.md`.

The CI structure is part of this decision. One workflow `.github/workflows/ci.yml` (never renamed) holds one job per component, named after it (`docs` now; later `collector`, `pipeline`, and so on), each with a path filter. When the second component arrives, a final job `ci-passed` depends on all of them and becomes the only required check. Adding the CI job of a component is done in that component's design and needs no new ADR; a new ADR is needed only if the flow itself changes (branching model, merge method, protection rules or deployment).

Trunk-based development fails the rule that `main` stays green (it commits directly). Git Flow keeps long-lived branches the project does not need. Squash merge would need one branch per logical change; merge commits add commits outside the convention.

### Consequences

* Every `type(TNNN)` commit reaches `main` unchanged, in a linear history.
* CI is the gate: a red check blocks the merge and a direct push is rejected.
* Each new component adds a CI job in its own design; the required check changes from `docs` to `ci-passed` when the second one arrives, the only change to the ruleset.
* Urgent fixes mean disabling the ruleset briefly; this path was not tested.
