---
paths:
  - "**/pyproject.toml"
  - "**/uv.lock"
  - "**/.python-version"
  - "**/package.json"
  - "**/package-lock.json"
  - "**/.npmrc"
  - "**/.nvmrc"
  - "**/wrangler.*"
---

# Runtime versions and dependencies

How to apply ADR-0016 (runtime versions) and ADR-0017 (dependencies). The why is in the ADRs; CI is in `.claude/rules/code/ci.md`.

## Where each component declares its stack

Each component's directory holds its own files; the repository-wide tooling is one more component, at the root.

| Ecosystem | Manifest | Lockfile | Runtime pin |
|---|---|---|---|
| Python | `pyproject.toml` (PEP 621) | `uv.lock` | `.python-version` |
| JavaScript | `package.json` | `package-lock.json` | `.nvmrc` |
| Cloudflare Worker | its JS manifest | its JS lockfile | `compatibility_date` in the wrangler configuration |

A component design lists these files in its File layout and chooses the concrete versions against its deployment runtime.

## Runtime versions

- Pin the exact version in the full format of the runtime's tooling (e.g. `3.12.7`, `24.11.0`), never a major alone or a range.
- `requires-python` in `pyproject.toml` stays a compatibility range; `.python-version` is what runs.
- Upgrade a runtime by changing its pin file only; nothing else repeats the version.

## Dependencies

- Add dependencies with the ecosystem tool, which writes a range to the manifest and updates the lockfile: `uv add <pkg>`, `npm install <pkg>`.
- Development-only dependencies go apart: `uv add --dev <pkg>` (dependency group `dev`), `npm install --save-dev <pkg>`.
- Commit the lockfile together with its manifest, in the same commit; never edit a lockfile by hand.
- Repository tooling (root `package.json`, `"private": true`) is pinned exactly: the root `.npmrc` sets `save-exact=true`.

## Running

- Only the locked versions run. Installing them automatically is fine (`uv sync --locked`, `npm ci`, `uv run`); running any other version is not (no `npx --yes <pkg>@<version>`, `pip install`, global installs).
- A repository tool runs through its entry script in `scripts/`, which checks that the locked version is installed and otherwise stops naming the install command (e.g. `scripts/lint-docs.sh`).

## Out of scope

Code under `spikes/` is throwaway and does not follow this rule.
