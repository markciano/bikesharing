# Barcelona bike sharing — data engineering project

Data engineering portfolio project on public bike sharing in the Barcelona area (AMBici + Bicing).

Work happens in three session types, each started with its skill: `/spike` (investigate and decide), `/design` (frame and plan a task), `/implement` (build and review). Path-specific rules live in `.claude/rules/`.

## Working rules

- Industry standards and best practices are the default: before proposing a solution, name the standard or pattern that applies. Deviating requires the owner's explicit OK, recorded as an ADR in `docs/decisions/` with the reason.
- When a change alters documented behaviour, the document is updated in the same commit. Within a design, affected documents are planned in its File layout instead.
- Source of truth: the approved working document (design or spike report). Code derives from it, never the other way round (spec-driven development).
- State lives in the working document, not the session: decisions are written when approved (if small, accumulate 2-3); Status is updated at every stop.
- Operational actions (accounts, consoles, billing, production deployments) are done by the owner.
- Permissions are set in `.claude/settings.json`. Never work around an action it asks for or denies: report it.

## Conventions

- **Language:** code, comments and documents in English. Conversation in Spanish.
- **Time:** all stored timestamps in UTC (ADR-0005).
- **Secrets:** in `.env` (ignored by Git); `.env.example` with empty values is committed. Never hard-code or paste secrets.
- **Raw data:** never committed to Git, except test fixtures (ADR-0009).
- **Pending items:** marked `TODO:` followed by a short description, in docs and code alike.
- **File names:** proposed by Claude, approved by the owner. English, lowercase. Docs in kebab-case; Python code in snake_case (PEP 8). ADRs as `NNNN-short-title.md`; designs as `dNNN-short-title.md`. spikes as `sNNN-short-title.md`.

## Git

- Claude runs only `git status`, `diff`, `log` and `show`. The owner reviews the diff, makes every commit and runs every other git command, including removing a leftover `.git/index.lock`.
- Commits follow Conventional Commits, with the task ID as scope: `type(TNNN): description`. Claude proposes the message.
- One logical change per commit: related edits go together; unrelated ones never do.
- A task's status change goes in the commit of the work that causes it.

### Branch, PR and CI procedure (GitHub Flow)

The owner runs every command. `main` is protected by a GitHub ruleset (no bypass): no direct push, PR required, `docs` check green, linear history, rebase merge only.

1. **Start.** `git switch main && git pull`, then `git status` must say "up to date with 'origin/main'" (a local-only commit would travel into the PR). One branch per task: `git switch -c tNNN-short-title`.
2. **Work.** Commits as above. `git push -u origin <branch>` the first time, `git push` after. Force push is allowed on the task branch (`--force-with-lease`), never on `main`.
3. **PR.** Open it to `main`, titled `TNNN: task name`.
4. **CI.** The check `CI / docs` (Markdown lint of `docs/**/*.md`, config in `.markdownlint-cli2.yaml`) must be green. Fix lint errors in the PR, not by disabling rules.
5. **Merge.** **Rebase and merge** is the only method enabled. The remote branch is deleted on merge.
6. **Clean up.** `git switch main && git pull --prune`, check with `git log --oneline -n 15` that the commits are on `main`, then `git branch -D tNNN-short-title` (`-D` because rebase gives the commits new SHAs).
7. **Urgent fix.** Disable the ruleset in GitHub settings, push, enable it again.

**Adding a component to CI.** `.github/workflows/ci.yml` (never renamed) has one job per component, named after it (`docs` now; later `collector`, `pipeline`) with a path filter. When the second component arrives, add a final job `ci-passed` that depends on all and change the required check in the ruleset from `docs` to `ci-passed`.

## Pacing

- One open decision per message. Other decisions are named in one line and parked.
- 2 options per decision (3 if really good), with the recommendation marked (👉) and a one-line reason.
- Keep a parking list (🅿️); parked items are picked up in their phase.

## Repo access

- Before writing, moving or deleting a file, explain in 2–3 plain brief lines what will change, where, and its effect; no full text. Write only after the owner's OK.
- Reading budget: use Project structure before exploring; list a folder before reading in it; read only the file or section the open decision needs; announce what you read and why in one line; ask before reading more than 3 files; do not re-read unchanged files.

## Project structure

```
.
├── CLAUDE.md              Rules for every session
├── .claude/
│   ├── settings.json      Permissions and environment
│   ├── rules/             Path-specific rules (docs, tasks, python, spikes)
│   └── skills/            Session skills: spike, design, implement
├── docs/                  Project documentation
│   ├── tasks.md           Task table
│   ├── decisions/         ADRs
│   ├── designs/           Design documents
│   ├── sources/           Source cards
│   └── spikes/            Spike reports per system
├── src/bikesharing/       Pipeline code
├── tests/                 unit/, integration/, fixtures/
└── spikes/                Throwaway investigation code
```