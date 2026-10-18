---
status: accepted
date: 2026-10-04
---

# Documentation architecture

## Context and Problem Statement

In the previous project, design docs (feature decisions, historical) and context docs (current state, living) worked well, but cross-cutting decisions had no home and ended up in `CLAUDE.md` or context docs without their rationale. A first attempt in this project mixed decisions, conventions, source facts and spike methods in one file.

Where should each kind of project content live?

## Considered Options

* One home per kind of content, with one file per cross-cutting decision (MADR)
* One home per kind of content, with all cross-cutting decisions in a single log file
* Design docs + context docs only (previous project)

## Decision Outcome

Chosen option: "One home per kind of content, with one file per cross-cutting decision (MADR)", because it is the industry reference, gives each decision its own Git history, and lets a reader find a decision by its file name without reading the others.

| Content | Home | Lifecycle |
|---|---|---|
| Cross-cutting decisions | `docs/decisions/` (one MADR file per decision, `NNNN-short-title.md`) | Append-only |
| Feature decisions and plan | `docs/designs/` (one per feature) | Closed when implemented |
| Current state of the system | Context docs (architecture, data model, …) | Living, updated with each change |
| Facts about each data source | `docs/sources/` (one card per source) | Living |
| Time-boxed investigations | `docs/spikes/` (one report per spike) | Closed when concluded |
| Conventions and working rules | `CLAUDE.md` | Living |

Folders and files are created when their first document is needed, not upfront.

Industry standards and best practices are the default; deviating from them requires the project owner's explicit OK, recorded as an ADR with the reason.

ADR statuses: `proposed` (suggested, not confirmed), `accepted`, `superseded by ADR-NNNN`. Accepted ADRs are not rewritten: a change of mind is a new ADR that supersedes the old one.

### Consequences

* Documents stay single-purpose.
* `docs/decisions/` only grows with decisions that are expensive to reverse.
* A single log file was rejected because it must be read in full to find one decision.
* Design docs + context docs only was rejected because it leaves no place for cross-cutting decisions.
