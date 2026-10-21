---
status: accepted
date: 2026-10-21
---

# CI test layers and up-to-date branches before merge

## Context and Problem Statement

ADR-0013 sets GitHub Flow, a protected `main` and one CI job per component, but not which tests run where. Spike s008 ran a proof of concept per component (Python, Spark, Cloudflare Worker, contract) locally and in CI, and measured each layer.

Which test level runs in each layer, and do the PR checks run on exactly what `main` will contain?

## Considered Options

* Four layers (local, pull request, `main`, scheduled), the PR run as the gate, branches required to be up to date before merging
* The same four layers, without requiring up-to-date branches
* CI on every `push` to feature branches as well as on the pull request

## Decision Outcome

Chosen option: "Four layers, the PR run as the gate, branches required to be up to date before merging".

| Layer | When | What runs |
|---|---|---|
| Local | Before each commit, run by `/implement` | Unit and integration tests of the touched component |
| Pull request (the gate) | Every push to a branch with an open PR | Every automated level of every affected component, contract tests and `docs` lint; at most 10 min wall-clock |
| `main` | `push` to `main` after the merge | The same workflow on the merged result; tests moved out of the PR run; later, post-deploy smoke tests |
| Scheduled | A separate `schedule` workflow | Checks against live sources; not a required check |

* No CI on `push` to feature branches: the first push opens a draft PR, whose `pull_request` run fires on every later push. A `push` trigger would run every check twice.
* Moving tests: when the PR run passes 10 min wall-clock, the slowest group of tests moves to the `main` run, starting with the heaviest job. It stays in the local layer, and a red `main` run is fixed at once in a new PR.
* The ruleset on `main` adds "require branches to be up to date before merging", so the gate tests the content `main` will have.

Without up-to-date branches, a PR can pass on a base that `main` no longer has. CI on feature-branch pushes doubles every run and adds no check the PR run lacks. The procedure is in `docs/testing-strategy.md` › CI flow; the evidence is in `docs/spikes/s008-testing-conventions.md` (F37–F42).

### Consequences

* The PR run takes 42–52 s today, against a budget of 10 min (s008 F39); no test needs to move.
* A rebase re-runs the PR checks; with one owner, `main` rarely moves under an open PR.
* Before a PR exists, only the local layer runs.
* The scheduled workflow and the post-deploy smoke tests exist on paper only, until a design builds them.
* Amends ADR-0013: the ruleset gains one rule, which the owner enables.
