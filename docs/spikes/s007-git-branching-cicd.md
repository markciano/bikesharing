# Spike: Git branches and CI/CD flow

- **Task:** T018
- **ADRs:** none
- **Code:** none: the trial changes production files

## Status

- State: Ready 🎬
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### Context

The project needs a Git branching model and a CI flow suited to a single owner, who makes every commit while Claude only reads Git (CLAUDE.md › Git). The output is a working procedure for branches and CI that the owner can follow day to day. Today there is no `src/`, no tests and no CI; the GitHub repo is public with a fresh history on `main` only (T019), so branch protection rules are available. Choosing the model can be done from published standards; whether the procedure works with the project's rules only shows by running it once.

### Questions

Main question: Which branching model and CI flow does the project adopt, and what procedure does the owner follow day to day?

- **Q1.** Which published branching models pass C1–C6, and which is the simplest?
- **Q2.** Which merge strategy (merge commit, squash, rebase) keeps C3 and C7?
- **Q3.** What does CI run, on which events (branch push, PR, `main`), and how does it stay green while `src/` is empty?
- **Q4.** Which protection rules on `main` enforce C4 without blocking a single owner (no required approval)?
- **Q5.** Does the full cycle (branch → commits → push → PR → CI → merge) run end to end in the real repo following the written procedure, and where does it break?
- **Observe only:** CI run time.

### Exit criteria

- **Standard:** screening of published branching models (GitHub Flow, trunk-based development, Git Flow) against the project's constraints as pass/fail; the simplest model that passes wins. The procedure is then validated by one trial run of the full cycle in the real repo.
- **Timebox:** about 2 active days, as a guide only. The run ends when both checks pass: one real PR merged with CI green, and one deliberate CI failure blocked by the protection on `main`. One model meeting the criteria is enough: the simplest one that passes.
- C1. Works for a single person: no reviewer or second approval needed — pass/fail — hard cut
- C2. Every Git write command (branch, merge, push) is run by the owner; Claude only reads (CLAUDE.md › Git) — pass/fail — hard cut
- C3. Fits `type(TNNN)` commits, one logical change per commit, task status change in the work commit — pass/fail — hard cut
- C4. `main` stays green: no direct push, CI must pass before merging — pass/fail — hard cut
- C5. Fits tasks that span several sessions (design → implement) — pass/fail — hard cut
- C6. Low ceremony: no long-lived branch that is not justified — pass/fail — hard cut
- C7. History reads well as a portfolio — judgement — guide
- C8. Simple enough to learn from, extensible step by step without renaming what exists — judgement — guide

### Out of scope

- CD (deployment): nothing is deployed yet; the procedure leaves room to add it later.
- Reviewing the repo before making it public: T019.
- TODO: owner verifies later the friction between Claude Code permissions and commands such as `gh pr`.

## 2. Method — how we find out

### Approach

| Variant | What it is | What it tells |
|---|---|---|
| P3. Trial in the real repo | GitHub Flow with a minimal GitHub Actions workflow and protection rules on `main`, following the written procedure. Trial = adoption: its first PR is a real one and nothing is thrown away | Q3, Q4, Q5 and the Observe only items |

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-18 | Run T018 as a light spike, not a design | A design is too heavy for this choice; no rigorous comparison is needed, only exploring the models and picking the best fit. |
| 2026-10-18 | Trial run in the real repo, after T019 makes it public | Owner's choice; the CI workflow stays as real code, and branch protection can be part of the trial. |
| 2026-10-18 | Adopt GitHub Flow (`main` + short-lived branch, PR, CI, merge); screening P1 dropped as a probe | Passes C1–C6. Trunk-based development commits directly to `main` and fails C4; Git Flow keeps long-lived `develop` and release branches and fails C6. Answers Q1. |
| 2026-10-18 | Rebase merge, one branch per task; P2 dropped as a probe | Keeps every `type(TNNN)` commit on `main` as is (C3) with a linear history (C7). Squash would need one branch per logical change (against C6); merge commits add "Merge pull request" commits outside the convention (C7). Answers Q2. |
| 2026-10-18 | The trial CI runs one language-agnostic check: Markdown lint on the docs. Pattern: one workflow per component (deployable unit, see `docs/ideas/project-ideas-0.md` § 7), triggered by its paths, plus one always-run final check that is the only required check on `main` | The spike validates the flow, not toolchains. A required check that is skipped by a path filter leaves the PR pending forever; the final check avoids that and keeps the protection rules unchanged as components are added. Each component's design picks its tools and adds its workflow. |
| 2026-10-18 | Protect `main` with a GitHub ruleset, no bypass for the admin: PR required with 0 approvals, the required check of the current CI stage (`docs` in stage 1, `ci-passed` in stage 2), linear history, rebase merge only, no force push or deletion, branch deleted on merge | Without bypass C4 holds by rule, not by discipline, and the trial can prove the block. Urgent fixes: disable the ruleset briefly and re-enable it. |
| 2026-10-18 | Replaces the CI pattern row above. Stage 1 (now): one workflow `.github/workflows/ci.yml` (name `CI`), run on every PR, with one job `docs` (Markdown lint) as the required check. Stage 2 (second component): each component adds a job named after it (`collector`, `pipeline`) with a path filter, plus a final job `ci-passed`, which becomes the only required check. The file is never renamed | C8: each piece appears when it solves a problem. Fixed names mean adding a component is adding a job; the only change at stage 2 is the required check in the ruleset. |
| 2026-10-18 | Markdown lint with markdownlint-cli2 and its official action; config in `.markdownlint-cli2.yaml` at the root, default rules except MD013 (line length). Existing docs are fixed in the first trial PR | De facto standard, one config file, readable failures. MD013 would flag almost every existing doc and adds nothing in a docs repo. |
| 2026-10-18 | Markdown lint covers only `docs/**/*.md` | Owner's choice: the lint targets the project documentation; `CLAUDE.md`, `.claude/` and `spikes/` stay outside. |
| 2026-10-18 | The procedure lives in `CLAUDE.md` › Git, extended and kept short; no new document | Owner's priority is an easy learning flow with no extra documents; no contributors are expected. Both the owner and Claude follow it every session. |

### File layout

```
.
├── .github/workflows/ci.yml   CI workflow; job `docs` (Markdown lint)
├── .markdownlint-cli2.yaml    Lint config: defaults except MD013
├── CLAUDE.md                  § Git extended with the branch, PR and CI procedure
└── docs/**/*.md               Fixes for lint errors found in the first PR
```

Ruleset on `main`: GitHub setting, not a file; set by the owner.

Evidence: each finding records the PR number, the Actions run URL and its duration. No data is captured, so ADR-0009 does not apply.

## 3. Steps

#### Step 1 — CI workflow and lint config

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - `.github/workflows/ci.yml`: workflow `CI`, triggered on `pull_request` to `main` and on `push` to `main`; `permissions: contents: read`; one job `docs` on `ubuntu-latest` that checks out the repo and runs the official markdownlint-cli2 action on `docs/**/*.md`. Actions pinned to their current major version, looked up by Claude and noted in Findings.
  - `.markdownlint-cli2.yaml`: default rules, MD013 disabled.
  - `docs/tasks.md`: T018 → 🔄.
  - Must not touch any other file; existing lint errors are left for step 3.
- **Reads:** 2. Method › Decision log, File layout
- **Check:** both files exist, and the job id is exactly `docs`
- **Commit:** `ci(T018): add CI workflow with Markdown lint`

#### Step 2 — Branch, first push and PR #1

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**
  1. Create the task branch from an up-to-date `main`: `git switch main && git pull && git switch -c t018-git-branching-cicd`
  2. If this spike doc or `docs/tasks.md` have uncommitted planning changes, commit them first: `docs(T018): plan spike s007`.
  3. Commit step 1 with its message, then `git push -u origin t018-git-branching-cicd`.
  4. Open the PR to `main`, on GitHub or with `gh pr create --base main --title "T018: Git branches and CI flow" --body "Spike s007"`.
  5. Open the Checks tab of the PR and wait for the `docs` job.
  6. Report back: PR number; run URL; result (red is expected); duration; the lint output, or a summary of errors per rule and file.
- **Gate:** the `docs` job runs on the PR → if not, step 1 is reopened to fix the trigger.
- **Check:** the PR shows a `CI / docs` check with a result

#### Step 3 — Fix the lint errors

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - Fix in the existing `.md` files under `docs/` every error reported in step 2: format only, never meaning.
  - If one rule causes most errors and adds nothing, stop and propose disabling it in `.markdownlint-cli2.yaml`, with a Decision log row, instead of editing many files.
  - Must not touch `.github/workflows/ci.yml`.
- **Reads:** the lint output from step 2; only the files it names
- **Check:** every file and line in the step 2 output is fixed, or covered by an approved rule change
- **Commit:** `docs(T018): fix Markdown lint errors`

#### Step 4 — CI green and ruleset on `main`

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**
  1. Commit step 3, `git push`, and wait for `CI / docs` to turn green on the PR.
  2. Settings → General → Pull Requests: allow only **rebase merging**; turn on **Automatically delete head branches**.
  3. Settings → Rules → Rulesets → New branch ruleset:
     - name `main`; enforcement **Active**; bypass list **empty**; target **default branch**;
     - rules: Restrict deletions; Require linear history; Require a pull request before merging (0 approvals, allowed merge method Rebase); Require status checks to pass, with `docs` added and "Require branches to be up to date" off; Block force pushes.
  4. Report back: the run URL and duration of the green run; whether `docs` could be selected as a required check; the final list of settings; anything that differed from these instructions.
- **Gate:** `docs` is selectable as required and the ruleset asks for no approval → if not, Q4 is re-decided before step 5.
- **Check:** the PR shows CI green and the merge button is enabled

#### Step 5 — Fault injection

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**
  1. Break the lint on the branch: `printf '\n#Broken heading\n' >> docs/tasks.md && git commit -am "test(T018): break lint on purpose" && git push`.
  2. Wait for CI and report: the check result, the run URL and duration, and whether the merge button is blocked.
  3. Remove the commit from the branch (allowed: only `main` is protected): `git reset --hard HEAD~1 && git push --force-with-lease`. Check that CI turns green again.
  4. Try a direct push to `main`: `git switch main && git commit --allow-empty -m "test(T018): direct push to main" && git push origin main`. Report the exact rejection message.
  5. Undo it locally: `git reset --hard origin/main && git switch t018-git-branching-cicd`.
- **Gate:** both the merge with red CI and the direct push are blocked → if not, the ruleset is reviewed and step 5 is repeated.
- **Check:** both rejections reported; the branch has no test commit; local `main` equals `origin/main`

#### Step 6 — Procedure in `CLAUDE.md`

- **Status:** 💤 todo
- **Who:** Claude
- **Scope:**
  - Extend `CLAUDE.md` › Git with the procedure, short:
    - one branch per task (`tNNN-short-title`) from up-to-date `main`;
    - commits as today; push; PR to `main`;
    - CI must be green; rebase merge; the branch is deleted on merge;
    - local clean-up after merge;
    - how a component adds its CI job (stage 2 in the Decision log).
  - Keep the rule that Claude runs only `git status`, `diff`, `log` and `show`.
  - Must not touch other sections of `CLAUDE.md`.
- **Reads:** 2. Method › Decision log; 4. Findings from steps 2–5; `CLAUDE.md` › Git
- **Check:** every Decision log row about the flow appears in the procedure; nothing is in the procedure that the Decision log does not support
- **Commit:** `docs(T018): add branch, PR and CI procedure to CLAUDE.md`

#### Step 7 — Rebase merge of PR #1

- **Status:** 💤 todo
- **Who:** Owner
- **Scope:**
  1. Commit step 6, `git push`, and wait for CI green.
  2. On GitHub: **Rebase and merge**.
  3. Locally: `git switch main && git pull --prune`; check with `git log --oneline -n 15` that every branch commit is on `main`, then `git branch -D t018-git-branching-cicd` (`-D` because rebase merge gives the commits new SHAs).
  4. Report back: `git log --oneline -n 15`, and whether the remote branch was deleted.
- **Check:** `main` history is linear with no merge commit; every commit of the branch is on `main` with its `type(T018)` message

#### Step 8 — Conclusion

- **Status:** 💤 todo
- **Who:** Owner + Claude
- **Scope:**
  - Runs as PR #2 that follows `CLAUDE.md` › Git literally, with no other guidance.
  - Owner: creates the branch (reusing `t018-git-branching-cicd`, deleted in step 7) and opens the PR as the procedure says, and notes every point where the procedure was unclear or missing.
  - Claude writes:
    - 5. Conclusion (C5 judged from this spike's own sessions), and the destination of every Production input;
    - fixes to `CLAUDE.md` › Git for the points the owner noted;
    - T018 → ✅ in `docs/tasks.md`.
  - Owner: merges PR #2 following the procedure.
  - There is no spike code to tear down.
- **Reads:** 1. Questions, 2. Method › Decision log, 4. Findings
- **Check:** every Q answered; every exit criterion has a result; every P has a destination
- **Commit:** `docs(T018): conclude spike s007`

## 4. Findings

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|

## 5. Conclusion

Observed window:

### Answers

### Exit criteria

### Verdict

### Not verified

### Follow-ups

## Sources

-
