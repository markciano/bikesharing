---
status: accepted
date: 2026-10-05
---

# Repository presentation for external visitors

## Context and Problem Statement

The repository will be shared, so a visitor opens the link once and spends little time on it: about 1 minute to decide whether the project is worth a closer look, and 5–6 minutes at most for that closer look. The project is in its discovery phase, so most of the target system does not exist yet.

How should the repository present itself so that, within that time, a visitor understands what the project is, what it demonstrates and what state it is in?

## Decision Drivers

* 1-minute test: what the project is, what it demonstrates, current status.
* 5–6-minute test: architecture and way of working, mostly without leaving the landing page.
* Honest status: nothing is presented as built unless it is.
* Single source of truth: no content is maintained twice.
* Works during discovery and grows with the project without rework.

## Considered Options

* README as landing page, browsed on GitHub
* Documentation site (MkDocs Material on GitHub Pages)
* Standard README plus an external case study (blog or LinkedIn article)
* Separate visitor-facing documents alongside the working documentation

## Decision Outcome

Chosen option: "README as landing page, browsed on GitHub", because it is where a visitor lands when given the link, it needs no extra tooling (GitHub renders Markdown and Mermaid natively), and it keeps a single set of documents for both daily work and visitors.

### Rules

* The root `README.md` is the only visitor-specific document. All other documents are the working documentation, read by visitors as-is.
* Documents linked from the README must be readable without prior context.
* README sections, in this order:
  1. Title and one-sentence description
  2. What this project demonstrates
  3. Status: what exists and what comes next
  4. Architecture at a glance (diagram)
  5. Reading path (5–6 minutes)
  6. Key decisions: one line per ADR, linked
  7. Data sources and attribution
  8. Tech stack and how to run (added when code exists)
* The architecture diagram shows the target architecture, with each component marked as done, in progress or planned. Components not yet backed by a decision are shown generically or omitted.
* The reading path links 2–3 evidence documents, each showing a different skill (decision-making, investigation with real data, knowledge of the data), with one line saying what the visitor will find. TODO: choose them when the capture spikes close (T006).
* All project diagrams use Mermaid.

### Consequences

* Good, because the visitor's path fits the time budget and needs no tooling.
* Good, because a single set of documents cannot drift apart.
* Bad, because every linked document must be written for an outside reader.
* Bad, because the README must be updated whenever the status or the architecture changes.
* A documentation site was rejected: it adds tooling and deployment, and the visitor leaves GitHub. It can be added later from the same Markdown files.
* An external case study was rejected: two places to keep in sync, and visitors who open the repository directly miss the story.
* Separate visitor documents were rejected: the same content would be maintained twice.
* A standard-readme layout (Background, Install, Usage…) was rejected: it targets users and contributors, not reviewers, and most sections would be empty during discovery.
* A diagram of only what exists was rejected because it hides where the project is going; a target diagram without status was rejected because it implies the system is built.

### Out of scope

* Structure of the architecture documents (arc42, C4, number of files): decided in their own ADR when their first content exists.
* When the README is published: decided by the owner.
* Repository license.