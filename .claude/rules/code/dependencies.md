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
  - "**/versions.tf"
  - "**/.terraform.lock.hcl"
  - "**/.terraform-version"
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
| Terraform | `versions.tf` (`required_version`, `required_providers`) | `.terraform.lock.hcl` | `.terraform-version` |

A component design lists these files in its File layout and chooses the concrete versions against its deployment runtime.

## Runtime versions

- Pin the exact version in the full format of the runtime's tooling (e.g. `3.12.7`, `24.11.0`), never a major alone or a range.
- Choose a release inside the range the component's test tools support, not the version installed on one machine.
- `requires-python` in `pyproject.toml` and `required_version` in `versions.tf` stay compatibility ranges; `.python-version` and `.terraform-version` are what runs.
- Upgrade a runtime by changing its pin file only; nothing else repeats the version.

## Dependencies

- Add dependencies with the ecosystem tool, which writes a range to the manifest and updates the lockfile: `uv add <pkg>`, `npm install <pkg>`.
- A Terraform provider is added to `required_providers` with a pessimistic range (`~>`), and `terraform providers lock` writes the lockfile with the hashes of every platform that runs it, the owner's machine and CI's.
- Development-only dependencies go apart: `uv add --dev <pkg>` (dependency group `dev`), `npm install --save-dev <pkg>`.
- Commit the lockfile together with its manifest, in the same commit; never edit a lockfile by hand.
- Repository tooling (root `package.json`, `"private": true`) is pinned exactly: the root `.npmrc` sets `save-exact=true`.
- Install scripts (`preinstall`, `install`, `postinstall`) stay unapproved (npm `allowScripts`): approve one, by package, only when the package fails without it, and record why in the design or change that needs it.

## Running

- Only the locked versions run. Installing them automatically is fine (`uv sync --locked`, `npm ci`, `uv run`, `terraform init -lockfile=readonly`); running any other version is not (no `npx --yes <pkg>@<version>`, `pip install`, global installs).
- A repository tool runs through its entry script in `scripts/`, which checks that the locked version is installed and otherwise stops naming the install command (e.g. `scripts/lint-docs.sh`).

## Upgrades

- An upgrade's impact is checked against what the code relies on, not only the APIs and defaults it calls: list the guarantees taken from the library (e.g. which concurrent writes conflict) and check each against the release's changes, those announced as performance work or fixes included.
- A guarantee the code relies on has a test of its observable outcome (a learning test), which provokes the case that would break it, not the library's current mechanism: the suite then checks it at every upgrade.

## Out of scope

Code under `spikes/` is throwaway and does not follow this rule.
