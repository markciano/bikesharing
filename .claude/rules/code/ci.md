---
paths:
  - ".github/workflows/**"
---

# CI workflow rules

Flow and reasons: [testing strategy](../../../docs/testing-strategy.md) (CI flow section), ADR-0013, ADR-0014, ADR-0016 and ADR-0017. The jobs of each component are created in that component's design; its version files, manifest and lockfile follow `.claude/rules/code/dependencies.md`.

## Job per component

- One job per component in `.github/workflows/ci.yml`, with `defaults.run.working-directory` set to the component folder.
- Take the runtime from the component's pin file; never write a version in the workflow, never rely on the runner's default:
  - Python: `astral-sh/setup-uv`; `uv` reads `.python-version` from the working directory and installs that Python.
  - Node: `actions/setup-node` with `node-version-file: <component folder>/.nvmrc`.
  - `uses:` inputs resolve from the repository root, not from `working-directory`, so file paths include the component folder.
- Install only from the lockfile, in the mode that fails when it does not match its manifest: `uv sync --locked`, `npm ci`.
- Cache dependencies: `enable-cache: true` in `setup-uv`; `cache: npm` with `cache-dependency-path: <component folder>/package-lock.json` in `setup-node`.
- One test command per job, run with the locked tools (`uv run pytest`, `npx vitest run`).
- Set `timeout-minutes: 10` on every job, so a hung test cannot hold the PR for the default 6 hours.
- Keep the `pull_request` run light: at most 10 min wall-clock for the whole workflow. Heavier tests belong to the `push` run on `main`.

```yaml
  <component>:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    defaults:
      run:
        working-directory: <component folder>
    steps:
      - uses: actions/checkout@<version>
      # Node; for Python: astral-sh/setup-uv@<version> with enable-cache: true
      - uses: actions/setup-node@<version>
        with:
          node-version-file: <component folder>/.nvmrc
          cache: npm
          cache-dependency-path: <component folder>/package-lock.json
      - run: npm ci  # Python: uv sync --locked
      - run: <one test command>
```

## Repository tooling jobs

A job for repository-wide tooling (e.g. `docs`) follows the same recipe at the root: no `working-directory`, the root `.nvmrc` and `package-lock.json`, and the tool's entry script in `scripts/` (e.g. `bash scripts/lint-docs.sh`) in place of the test command.

## Aggregator and required check

- `ci-passed` is the only required check in the ruleset of `main` (ADR-0013); the ruleset is changed by the owner.
- `ci-passed` `needs` every other job, runs with `if: always()`, and its only step fails when any of them ends in `failure` or `cancelled`. A job skipped by its path filter is `skipped` and passes. Without `if: always()`, `ci-passed` would be skipped when a job fails, and GitHub treats a skipped required check as passed.
- Path filters live in one job `changes`, using `dorny/paths-filter`, with one output per component. Each component job has `needs: changes` and `if: needs.changes.outputs.<component> == 'true'`.
- `changes` runs `actions/checkout` before the filter, since on `push` it compares commits with git. It sets its own `permissions` (`contents: read`, `pull-requests: read`), since on `pull_request` it lists the changed files through the API.
- The filter of a component includes `.github/workflows/ci.yml`, and the shared contract file of every job that reads it, so a contract change runs the tests of both sides.

```yaml
  ci-passed:
    needs: [changes, <every other job>]
    if: always()
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')
        run: exit 1
```
