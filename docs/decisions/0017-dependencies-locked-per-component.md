---
status: Accepted
date: 2026-10-22
---

# Dependencies locked per component, one manager per ecosystem

## Context and problem statement

Each component depends on third-party libraries and tools, and each of those brings its own transitive dependencies. Unless something records the resolved tree, an install resolves it again at install time, so two installs of the same component can end with different versions.

Today dependencies are recorded in different ways: a snapshot of an installed environment that does not separate what was asked for from what was resolved, and a repository-wide tool fetched on demand at a version kept equal by hand in two files. Nothing verifies that what runs matches what was declared.

The forces are: every install must be deterministic, locally and in CI; an upgrade must be a deliberate, reviewable change; a mismatch between declared and installed versions must be detected, not discovered; and each ecosystem should need as few tools as possible.

## Considered Options

### 1. Manifest and lockfile, with one integrated locking manager per ecosystem

Each component declares its direct dependencies in a manifest and commits a lockfile written by a single tool that also creates the environment and runs commands (`uv` for Python, `npm` for JavaScript). Pros: deterministic installs; the tool can refuse a lockfile out of sync with its manifest; one tool per ecosystem; `uv` also installs the Python runtime. Cons: `uv` is a third-party tool.

### 2. Manifest and lockfile, with separate tools

The same manifest and lockfile, produced and consumed by separate tools (for Python, a compiler of pinned requirements, an installer and a virtual environment tool). Pros: each tool is a community standard. Cons: three tools where option 1 needs one; the runtime is managed by yet another tool; slower.

### 3. Keep the current state

Environment snapshots and on-demand installs. Pros: no change. Cons: declared and resolved versions are not separated, so a lockfile cannot be checked against its manifest; on-demand installs bypass any lock.

## Decision Outcome

**Chosen option:** 1. Manifest and lockfile, with one integrated locking manager per ecosystem.

Rationale: it is the only option that makes every install deterministic and detects drift between declared and installed versions with one tool per ecosystem, as the Context requires.
Why not the others: separate tools meet the same guarantees with three tools and an extra one for the runtime; the current state cannot detect drift at all.
For JavaScript, `npm` ships with the runtime and meets every force, so no alternative was weighed.

Rules:

- Each component MUST declare its direct dependencies in its ecosystem's manifest as compatible ranges, because ranges record intent and leave resolution to the lockfile.
- Each component MUST commit a lockfile with the full resolved tree at exact versions, because it makes every install reproduce the same tree.
- Python components MUST use `uv` (`pyproject.toml`, `uv.lock`) and JavaScript components MUST use `npm` (`package.json`, `package-lock.json`), because one tool per ecosystem keeps setup, CI and documentation uniform.
- Development-only dependencies SHOULD be declared apart from runtime ones, because a deployment then installs only what runs.
- Tools that act on the whole repository MUST form one more component at the root, with its own manifest and lockfile and with each tool pinned exactly in the manifest, because a directly invoked tool then has one readable version that its entry point can check before running.
- CI MUST install only from the lockfile, in the mode that fails when the lockfile does not match its manifest, because a stale lockfile must block the merge, not pass silently.
- Commands MUST run the locked versions and MUST NOT fetch another version on the fly, because that bypasses the lock.

**Scope:** the library and tool dependencies of every component and of the repository-wide tooling, in every environment. It does not cover runtime versions (ADR-0016), nor which libraries each component uses, which its design decides; throwaway spike code is outside it.

### Consequences

#### Positive

- **Deterministic installs:** the same tree locally and in CI.
- **Reviewable upgrades:** every version change is a diff to a manifest and its lockfile.
- **Drift is caught:** an out-of-sync lockfile fails CI.

#### Negative

- **Third-party dependency:** Python tooling relies on `uv`; its export to the standard `pylock.toml` (PEP 751) limits the lock-in.
- **Noisy diffs:** regenerated lockfiles are large to review.
- **Install before run:** every clone needs one install step before any tool runs.

## More information

- How to apply it: `.claude/rules/code/dependencies.md`; CI recipe: `.claude/rules/code/ci.md`.
- Related: ADR-0016 (runtime versions pinned per component).
