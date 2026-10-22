# Design: Production stack versions and dependency tooling

- **Task:** T021
- **ADRs:** ADR-0013
- **New ADRs created by this design:** ADR-0016, ADR-0017

## Status

- State: In progress 🔄
- Phase: [x] Spec · [x] Plan · [x] Plan review · [x] Steps · [ ] Steps review
- Current step: 1

## 1. Spec — what and why

### Context

The project has no single source of truth for the versions of its stack (language runtimes, Spark, Java, tools) or for its dependency tooling. Spikes pinned them ad hoc (s008: `venv` + `pip freeze`, `npm`, versions in each CI job), and the docs lint pins `markdownlint-cli2` in two places kept in sync by a comment. This task sets the project-wide rule: each component, and the repository's own tooling, declares its versions in one place, aligned with where it runs, with one dependency tool per language ecosystem. It does not choose the versions of each component; each component design does, against its runtime.

### Done when

- Every requirement passes its test.
- Every item in File layout is delivered.
- Every TODO citing this task is resolved or re-pointed.
- The docs lint runs the same `markdownlint-cli2` version locally and in CI, declared in one place.
- The s008 statement "the production Java version is decided in T021" is re-pointed to where that decision now belongs.
- A future component design finds, from the project rules alone, where to declare its stack versions and dependency tooling.

### Requirements

- **R1** The docs lint shall run, locally and in CI, the `markdownlint-cli2` version locked in the repository lockfile, pinned exactly in its manifest.
- **R2** If the lockfile does not match its manifest, then the CI job shall fail.
- **R3** If the declared tools are not installed locally, or not at the locked version, then the docs lint shall stop with a message naming the install command.

### Out of scope

- Deployment target and the replacement of ADR-0003 — T022
- Choice and configuration of code-style tools (linters, formatters) for Python and JS; this task only sets where their versions are declared — T024
- The concrete stack versions of each component: the collector (Node, Workers `compatibility_date`) — T007; the pipeline (Python, PySpark, Java) — T025

## 2. Plan — how

### Options considered

#### Concern 1 · Python dependency tooling

##### Option A — `uv` + `pyproject.toml` + `uv.lock` (chosen)

One tool manages the Python version, the virtual environment, the lockfile and command execution (`uv run`). Dependencies are declared in `pyproject.toml` (PEP 621) and locked in a cross-platform `uv.lock` with hashes.

**Pros:** full reproducibility with one tool; `uv sync --locked` fails on a lockfile out of sync with its manifest; dependency groups (PEP 735) separate dev from runtime; installs and pins the Python version; fast; the default for new Python projects.
**Cons:** a third-party tool (Astral, acquisition by OpenAI announced 2026-03-19); mitigated by its permissive licence and by export to the standard `pylock.toml` (PEP 751).

##### Option B — `pip` + `venv` + `pip-tools` (rejected)

Dependencies are declared in `pyproject.toml` and `pip-compile` locks them, with hashes, into a `requirements.txt` installed with `pip`.

**Pros:** community tools (PyPA, Jazzband); every file is a standard format.
**Cons:** rejected because it needs three tools where `uv` needs one, does not manage the Python version (a separate install or `pyenv`), and is slower.

`pip freeze` (the spikes' approach) was discarded without weighing: it does not separate declared from locked dependencies, so R2 cannot hold.

#### Concern 2 · Where each component declares its runtime versions

##### Option A — One native file per runtime, inside each component (chosen)

Python in `.python-version`, Node in `.nvmrc`, Java in `.java-version`; a Cloudflare Worker's runtime in the `compatibility_date` of its wrangler configuration. CI reads each file through `astral-sh/setup-uv` for Python (it installs `uv`, which reads `.python-version`) and the `*-version-file` input of `actions/setup-node` and `actions/setup-java`.

**Pros:** each ecosystem's tools read their own file with no extra configuration (`uv` reads `.python-version`); one value per file, so a single source of truth holds by construction.
**Cons:** one small file per runtime.

##### Option B — One `.tool-versions` file per component (rejected)

Every runtime of a component in one file, in the asdf/mise format.

**Pros:** one file per component.
**Cons:** rejected because `uv` does not read it, so the Python version would be repeated in `.python-version` (two sources of truth), and every machine would need asdf or mise installed.

#### Concern 3 · Repository tooling (docs lint)

`markdownlint-cli2-action` bundles its own `markdownlint-cli2` version and cannot read ours, so CI moves to `actions/setup-node` (root `.nvmrc`) + `npm ci` + the lint command, with the version pinned exactly in a root `package.json` (root `.npmrc` with `save-exact=true`) and locked in `package-lock.json`. The open choice was the command that runs the lint.

##### Option A — `scripts/lint-docs.sh` as the single entry point (chosen)

The script checks with `npm ls --depth=0` that `markdownlint-cli2` is installed at the pinned version (with the exact pin, the locked one), stops with "Run `npm ci` first" if not, and runs the installed version without downloading anything. The owner and CI call the same script.

**Pros:** the same command runs locally and in CI; the owner's way of running it does not change; the existing mention of the script in `.claude/rules/docs.md` stays valid.
**Cons:** a shell script where npm has a native mechanism.

##### Option B — An npm script (`npm run lint:docs`) only (rejected)

The `.sh` is deleted and the lint is declared in `package.json` `scripts`.

**Pros:** the native npm style.
**Cons:** rejected because, without the install, npm fails with a generic "command not found" that does not name the fix, so R3 needs a separate check script (two pieces again), and the mention in `.claude/rules/docs.md` changes.

#### Concern 4 · Where the rule is written

Path-specific rules in `.claude/rules/` load only when matching files are touched; in a `/design` session the manifests and version files do not exist yet, so a rule alone would not be found in time.

##### Option A — ADR + path rule + template line + CLAUDE.md line (chosen)

ADR-0016 and ADR-0017 record the why; `.claude/rules/dependencies.md` holds the how, loaded when manifests or version files are touched; one line in the File layout comment of the design template and one line in CLAUDE.md › Conventions point to it. `.claude/rules/ci.md` is updated to the new pattern. Follows the precedent of the CI job recipe.

**Pros:** each piece loads when it is needed (progressive disclosure, as the repo already does for CI); no content is repeated: the ADR gives the why, the rule the how, the other two only point.
**Cons:** four places to keep consistent.

##### Option B — ADR + the full rule in CLAUDE.md (rejected)

**Pros:** always loaded.
**Cons:** rejected because it fills CLAUDE.md with detail needed only when touching manifests, against the project's pattern of path-specific rules in `.claude/rules/`.

### Decision summary

| Concern | Decision | R |
|---|---|---|
| Python dependency tooling | `uv` with `pyproject.toml` (PEP 621) and `uv.lock`, for every Python component | R2 |
| Runtime version declaration | One native file per runtime inside each component (`.python-version`, `.nvmrc`, `.java-version`, each holding an exact version in the full format of its runtime's tooling, e.g. `major.minor.patch` for Node and Python; the wrangler `compatibility_date`, a fixed date, for a Worker), read by CI through `astral-sh/setup-uv` for Python and `*-version-file` for Node and Java; never a version written in `ci.yml`. `requires-python` in `pyproject.toml` stays a compatibility range, the exact pin is `.python-version`. The Java distribution required by `setup-java` is decided, with its declaration place, in T025 | R1 |
| Repository tooling | Node-based tools that act on the whole repository are pinned exactly in a root `package.json` (root `.npmrc` with `save-exact=true`) and locked in `package-lock.json`, with Node in a root `.nvmrc`; component tools live in their component's manifest. The docs lint runs through `scripts/lint-docs.sh`, locally and in CI (`setup-node` + `npm ci` + the script), replacing `markdownlint-cli2-action`; a single entry script for local and CI follows GitHub's scripts-to-rule-them-all pattern | R1, R2, R3 |
| Where the rule is written | ADR-0016 (runtime versions) and ADR-0017 (dependencies), the why; `.claude/rules/dependencies.md` (how, including "only the locked versions run; installing them automatically is fine, running any other version is not"); one line in the design template's File layout comment and one in CLAUDE.md › Conventions pointing to them; `.claude/rules/ci.md` updated to `astral-sh/setup-uv` / `*-version-file`, `uv sync --locked` / `npm ci` and the uv/npm cache | — |

### File layout

```text
.
├── CLAUDE.md                     (modified)  Conventions: one line on stack versions and dependency tooling, pointing to ADR-0016, ADR-0017 and the rule
├── .nvmrc                        (new)       Node version of the repository tooling
├── .npmrc                        (new)       `save-exact=true`: npm writes exact versions to `package.json`
├── package.json                  (new)       Repository tooling manifest: `markdownlint-cli2` 0.23.2, exact, as a dev dependency
├── package-lock.json             (new)       Lockfile generated by npm
├── .claude/
│   ├── rules/
│   │   ├── dependencies.md       (new)       How components and repository tooling declare runtime versions and dependencies; exact versions in version files; ranges in component manifests, exact versions in their lockfiles and in the repository tooling manifest; "only the locked versions run"
│   │   ├── ci.md                 (modified)  Job recipe: runtime from `astral-sh/setup-uv` (Python) or `*-version-file`, install with `uv sync --locked` or `npm ci`, uv/npm cache
│   │   └── docs.md               (modified)  Local lint needs `npm ci` once per clone
│   └── skills/design/
│       └── template.md           (modified)  File layout comment: a component lists its manifest and version files (rule in `dependencies.md`)
├── .github/workflows/
│   └── ci.yml                    (modified)  `docs` job: `setup-node` (`.nvmrc`) + `npm ci` + `scripts/lint-docs.sh`, replacing `markdownlint-cli2-action`; `timeout-minutes: 10` (ci.md)
├── docs/
│   ├── decisions/
│   │   ├── 0016-runtime-versions-pinned-per-component.md  (new)  Why: each runtime pinned exactly in its native version file, read by CI
│   │   └── 0017-dependencies-locked-per-component.md      (new)  Why: manifest and lockfile per component, `uv` for Python, `npm` for JS, repository tooling as a root component
│   ├── spikes/
│   │   └── s008-testing-conventions.md  (modified)  New Decision log row, correcting both rows that cite T021: the production Java version is decided in T025, not T021
│   └── tasks.md                  (modified)  T021 status
└── scripts/
    └── lint-docs.sh              (modified)  Runs the installed `markdownlint-cli2`; stops with "Run `npm ci` first" if it is missing or not at the locked version (`npm ls --depth=0`)
```

Written and approved in the design (Plan amendment, 2026-10-22), because they state rules or decisions: ADR-0016, ADR-0017, `.claude/rules/dependencies.md`, `.claude/rules/ci.md`, `.claude/rules/docs.md`, `.claude/skills/design/template.md`, `CLAUDE.md` and the s008 Decision log row. Implementation builds the remaining files and verifies them against these; a mismatch is fixed in the design, not in the build.

### Test plan

| R | Test concept | Level |
|---|---|---|
| R1 | The version banner printed by `markdownlint-cli2` is the one locked in `package-lock.json`, in the local run of `scripts/lint-docs.sh` and in the `docs` job log | e2e (manual) |
| R2 | On a throwaway branch with its own draft PR, the `markdownlint-cli2` version in `package.json` is changed without regenerating the lockfile: the `docs` job fails at `npm ci`; the PR is closed without merging and the branch deleted | e2e (manual) |
| R3 | `scripts/lint-docs.sh` exits non-zero and prints "Run `npm ci` first" in two cases: with `node_modules/` removed, and with a different `markdownlint-cli2` version installed in `node_modules/` | e2e (manual) |
| Done when | From CLAUDE.md › Conventions, the design template's File layout comment and `.claude/rules/dependencies.md` alone, a reader finds where a new component declares its runtime versions, manifest and lockfile | review (manual) |

### What does not change

- The CI job name `docs`: it is the ruleset's required check (ADR-0013).
- The lint configuration `.markdownlint-cli2.yaml` and the glob `docs/**/*.md`.
- The `markdownlint-cli2` version (0.23.2): this task moves where it is declared, it does not upgrade it.
- Spike code under `spikes/`: throwaway, not migrated to the new tooling.

## 3. Implementation

### Prerequisites

Owner, on the local machine, before Step 1: Node 26.12.1 installed and selected through a version manager that reads `.nvmrc` (e.g. `fnm install 26.12.1`). Done on 2026-10-22 with `fnm`. Decided in the design on 2026-10-22: the latest Node 26 release; Node 26 enters Active LTS on 2026-10-28 (<https://nodejs.org/en/about/previous-releases>).

### Steps

#### Step 1 — Repository tooling manifest

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `build: pin markdownlint-cli2 in root package.json`
- **R:** R1

##### Scope

The repository tooling as a root component, per `.claude/rules/dependencies.md`: `.nvmrc` (new, `26.12.1`, see Prerequisites), `.npmrc` (new, `save-exact=true`), `package.json` (new, `"private": true`, no `scripts`, `markdownlint-cli2` `0.23.2` as a dev dependency) and `package-lock.json` (new, generated by npm, never hand-edited). No test of its own: R1 is verified in Step 4.

##### Reads

| What | Contains | For |
|---|---|---|
| `.claude/rules/dependencies.md` › Where each component declares its stack; Dependencies | Root component files, exact pinning of repository tooling | Which files to create and how |
| d001 › What does not change | `markdownlint-cli2` stays at 0.23.2 | The version to pin |

##### Check

`node --version` prints `v$(cat .nvmrc)`; `npm ci && npm ls --depth=0` lists `markdownlint-cli2@0.23.2`; `package.json` has `"0.23.2"` with no range prefix (yes/no).

##### Do

1. Write `.nvmrc` with `26.12.1` and `.npmrc` with `save-exact=true`.
2. Write `package.json` with `"private": true` only.
3. Run `npm install --save-dev markdownlint-cli2@0.23.2`, which adds the dev dependency and generates `package-lock.json`.
4. Run the Check.

#### Step 2 — `lint-docs.sh` runs the locked version

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `build: run locked markdownlint-cli2 in lint-docs.sh`
- **R:** R1, R3

##### Scope

`scripts/lint-docs.sh` (modified): before linting, it checks that `markdownlint-cli2` is installed at the locked version and otherwise stops with exit code 1 and "Run `npm ci` first"; it then runs the installed binary, never downloading one. Its header comment states it is the single entry point, locally and in CI, and drops the "keep equal to the action" note. Covers the Test plan row for R3.

##### Reads

| What | Contains | For |
|---|---|---|
| `scripts/lint-docs.sh` | Current `npx --yes markdownlint-cli2@0.23.2` call and header comment | What to replace |
| `.claude/rules/dependencies.md` › Running | Only locked versions run; entry script checks and names the install command | The behaviour to implement |
| d001 › Concern 3, Option A | Check with `npm ls --depth=0`, message, no download | How the check works |
| d001 › Test plan, row R3 | The two failure cases | The Check |

##### Check

Three runs of `bash scripts/lint-docs.sh; echo $?`: (a) after `npm ci`, it passes and prints the `markdownlint-cli2 v0.23.2` banner; (b) after `rm -rf node_modules`, it exits 1 with "Run `npm ci` first"; (c) after `npm ci && npm install --no-save markdownlint-cli2@0.23.1`, it exits 1 with the same message. `npm ci` afterwards restores the locked state.

##### Do

1. Replace the `npx --yes` line with a check: `npm ls --depth=0 markdownlint-cli2` (it fails when the package is missing or does not match the exact pin), printing "Run `npm ci` first" to stderr and exiting 1 on failure; keep `set -euo pipefail` from cutting the script before the message.
2. Run the installed version with `npx --no markdownlint-cli2 "docs/**/*.md"` (`--no` refuses to download).
3. Update the header comment.
4. Run the three cases of the Check, then `npm ci`.

#### Step 3 — `docs` job on the locked toolchain

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `ci: run docs lint through setup-node, npm ci and lint-docs.sh`
- **R:** R1, R2

##### Scope

`.github/workflows/ci.yml` (modified), `docs` job, name unchanged: follows the recipe for repository tooling jobs in `.claude/rules/ci.md` (`actions/checkout`, `actions/setup-node` with `node-version-file: .nvmrc` and `cache: npm`, `npm ci`, `bash scripts/lint-docs.sh`, `timeout-minutes: 10`) and drops `DavidAnson/markdownlint-cli2-action`. The `# TODO:` block above `docs` stays unchanged. R1 and R2 are verified on the PR in Step 4.

##### Reads

| What | Contains | For |
|---|---|---|
| `.claude/rules/ci.md` › Job per component; Repository tooling jobs | The recipe | The job's steps |
| `.github/workflows/ci.yml` | Current `docs` job and the `# TODO:` block | What to replace, what to keep |
| d001 › What does not change | Job name `docs` is the required check | Must not be renamed |

##### Check

`grep -n "markdownlint-cli2-action" .github/workflows/ci.yml` finds nothing; the `docs` job has `node-version-file: .nvmrc`, `cache: npm`, `npm ci`, `bash scripts/lint-docs.sh` and `timeout-minutes: 10`; the `# TODO:` block is unchanged (yes/no).

##### Do

1. Replace the `markdownlint-cli2-action` step with `actions/setup-node@v7` (latest major, checked in the design on 2026-10-22), `npm ci` and the script; add `timeout-minutes: 10`.
2. Run the Check.

#### Step 4 — End-to-end verification

- **Status:** 💤 todo
- **Who:** Owner (push, throwaway PR) and Claude (review)
- **Commit:** `docs: close d001 after end-to-end verification`
- **R:** R1, R2

##### Scope

Runs the Test plan rows for R1, R2 and Done when (R3 was covered in Step 2), and checks that the built files match the rules written in the design. `docs/tasks.md`: T021 → ✅. d001 › Close filled in.

##### Reads

| What | Contains | For |
|---|---|---|
| d001 › Test plan | R1, R2 and Done when rows | What to run |
| d001 › Spec › Done when | Closing conditions | The final tick list |
| `.claude/rules/dependencies.md`, `.claude/rules/ci.md` | The rules written in the design | Built files match them |

##### Check

R1 banner seen locally and in the `docs` job log; R2 job failed at `npm ci`; built files match both rules; every Done when item met; the `docs` check of the T021 PR is green (yes/no each).

##### Do

1. Owner: push the branch; the draft PR exists.
2. Run `bash scripts/lint-docs.sh` locally; Owner: read the `docs` job log of the PR. Both show `markdownlint-cli2 v0.23.2`.
3. Owner: create a throwaway branch from `t021-production-stack-versions`, change `markdownlint-cli2` in `package.json` to `0.23.1` without touching the lockfile, open a draft PR against `main`, confirm the `docs` job fails at `npm ci`, close the PR without merging and delete the branch.
4. Review the root files, `scripts/lint-docs.sh` and the `docs` job against `dependencies.md` and `ci.md`; a mismatch goes back to the design.
5. Tick every Done when item: the TODOs with `grep -rn "TODO:.*T021" --exclude-dir=node_modules --exclude-dir=spikes .` (none left); the pointers from CLAUDE.md › Conventions, the design template's File layout comment and `dependencies.md` alone.
6. Update `docs/tasks.md` and fill in d001 › Close.

## 4. Close

### Implemented

### Known gaps at close

- `<gap>` — TNNN

### Decisions taken during implementation
