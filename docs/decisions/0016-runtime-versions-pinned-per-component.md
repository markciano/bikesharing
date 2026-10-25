---
status: Accepted
date: 2026-10-22
---

# Runtime versions pinned per component in native version files

## Context and problem statement

The project is made of components in different ecosystems, each needing one or more runtimes (an interpreter, a virtual machine, a serverless platform). Every component runs in at least two environments, a developer machine and CI, and later in its deployment target.

Today a runtime version is written wherever someone needs it: inside CI job definitions, in setup notes, and in some cases kept equal by hand across two files. Nothing makes those copies agree, so a component can pass in one environment and fail in another, and a version change can miss one of its copies.

The forces are: every environment must run the same runtime; an upgrade must happen in one place; each ecosystem's tools already look for a version in their own conventional location; and no extra tool should be mandatory on every machine and runner.

## Considered Options

### 1. Native version file per runtime, inside each component

Each runtime is pinned in the file its ecosystem's tools read by convention, in the component's directory. Pros: read with no configuration, one value per file, no extra tool. Cons: one small file per runtime; a few runtimes have no such file.

### 2. One universal version file per component

All runtimes of a component in one file read by a polyglot version manager (e.g. asdf or mise). Pros: one file per component. Cons: several ecosystem tools ignore it and read only their native file, so versions are declared twice; the manager becomes mandatory on every machine and runner.

### 3. Keep the current state

Versions stay where each environment uses them. Pros: no change. Cons: no single source of truth; copies drift unnoticed.

## Decision Outcome

**Chosen option:** 1. Native version file per runtime, inside each component.

Rationale: it is the only option that gives one source per runtime that every environment, including CI, reads without extra tooling, which the Context requires.
Why not the others: the universal file still needs the native files for the tools that ignore it, so it adds a second source instead of removing one; the current state is the drift the Context describes.

Rules:

- Each runtime a component needs MUST be pinned in its ecosystem's native version file, inside the component (e.g. `.python-version`), because the ecosystem's tools then use it with no configuration and the component carries its own runtime.
- The pin MUST be an exact version in the full format of that runtime's tooling, never a major version or a range, because a partial version resolves to different releases over time and across machines.
- A runtime with no native version file MUST be pinned in the component's own configuration where its platform reads it (e.g. a serverless compatibility date), because that is then its single source.
- CI MUST take each runtime version from the component's pin and MUST NOT state a version in a workflow, because a second copy drifts from the first.
- A compatibility range declared for consumers MAY coexist with the pin, because it states what the component supports while the pin states what runs.

**Scope:** every component and the repository-wide tooling at the root, in every environment where they run. It does not choose concrete versions, which each component's design sets against its deployment runtime; it does not cover library dependencies (ADR-0017); throwaway spike code is outside it.

### Consequences

#### Positive

- **One source per runtime:** an upgrade is a one-line change, visible in review.
- **Same runtime everywhere:** local, CI and deployment read the same pin.

#### Negative

- **More small files:** one per runtime, per component.
- **Patches are deliberate:** exact pins do not pick up security releases on their own; someone must bump them.
- **Version switching on each machine:** developers need a tool that honours each native file.

## More information

- How to apply it: `.claude/rules/code/dependencies.md`; CI recipe: `.claude/rules/code/ci.md`.
- Related: ADR-0017 (dependencies locked per component).
