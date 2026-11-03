---
status: Proposed
date: 2026-11-03
---

# Static web page for the visualization

## Context and problem statement

The platform must present the guiding questions to anyone who opens its link, and no tool or access path is chosen for it yet. The choice sets what the project has to build, keep running and pay for.

- Access is public and read-only, without login ([d002 › R1](../designs/d002-requirements.md#requirements), [s013 › D1](../spikes/s013-visualization-tool.md#d1-public-access-without-login)), so the data is not confidential and the main risk is cost: bots or heavy traffic can drive up whatever each visit consumes.
- The visualization's share of the budget is €2 per month ([ADR-0026](0026-budget-shares-per-component.md)). Abuse cannot bill more than that, and the page must work again at most 1 day after the abuse ends.
- Gold and all other stored data stay private ([d002 › R18](../designs/d002-requirements.md#requirements)).
- This is a portfolio project, so a polished look with its own identity weighs most.
- The page presents the guiding questions with a map of about 780 stations, charts and filters, on any screen from phone to desktop ([d002 › R29](../designs/d002-requirements.md#requirements)).
- One person maintains the solution, with little work.

## Considered Options

Each option first has to pass the hard cuts above: public access, cost under abuse, private data and any screen. Those that pass are compared on look and own identity, capability to present the guiding questions, upkeep and build effort. The other options evaluated are in [s013 › D3](../spikes/s013-visualization-tool.md#d3-static-web-page-with-javascript).

### 1. Static web page with prepared files

Visitors download files prepared for the page and their browser renders them. No server runs and no visit reaches the stored data.

- Pros:
  - full control of structure, typography, map and interaction, so nothing reveals the tool;
  - covers all guiding questions, loading each station's detail on click;
  - nothing keeps running, so upkeep is dependency updates.
- Cons:
  - highest build effort: browser JavaScript and front-end tools are new to the project;
  - the files have to be prepared and published;
  - map rendering of about 780 stations is not measured.

### 2. Streamlit on Community Cloud

A Python app on Streamlit's managed hosting.

- Pros:
  - lowest build effort: Python only, with ready-made components;
  - no machine to administer.
- Cons:
  - theming and CSS change its look, but the structure reveals the tool;
  - a process keeps running, and each map click reruns on the server;
  - past its limits an app may slow down or stop until the owner reboots it, so it needs an alert to the owner;
  - it offers only a `streamlit.app` subdomain.

### 3. Browser reading gold directly

The page's JavaScript reads the gold tables from R2, with no prepared files.

- Pros:
  - no files to prepare or publish.
- Cons:
  - it fails the private data cut, because gold would have to be public;
  - it fails the cost cut, because every visit becomes billed read operations with no limit: a script at 100 reads/s costs about $90 a month.

## Decision Outcome

**Chosen option:** 1. Static web page with prepared files.

It passes the hard cuts and leads on look and own identity, the heaviest force in the Context, and on upkeep, which matters for a single maintainer. Written by hand, it scores 9.2 out of 10 against 7.0 for Streamlit on Community Cloud, and it stays ahead with equal weights, with look at weight 0 and with one point less on look and on capability. Built with Observable Framework, it scores 7.6 on inferred figures. Its cost is build effort, the lightest criterion.

Why not the others:

- Streamlit on Community Cloud: its structure reveals the tool, which is the heaviest criterion, and it keeps a process that needs attention. It remains the fallback.
- Browser reading gold directly: public gold and unbounded read costs break two hard cuts.

**Scope:** What the visualization is and how the browser gets its data. It does not choose between a hand-written page and Observable Framework, or decide on a custom domain, both in T041. It does not decide where the prepared files are published, which belongs to the publishing decision ([s013 › D4](../spikes/s013-visualization-tool.md#d4-data-published-by-redeploying-on-workers-static-assets)).

### Consequences

#### Positive

- **Nothing to keep running:** one operator has no process or machine to look after.
- **Stored data stays private:** visitors reach only the prepared files, never a bucket.
- **Visits consume nothing in the lakehouse:** the cost of abuse depends only on where the files are published.
- **Own identity:** the page controls its structure and look, instead of inheriting a dashboard tool's.

#### Negative

- **New stack to learn and maintain:** the page adds front-end tools, with their own pinned runtimes, locked dependencies and CI job ([s013 › P6](../spikes/s013-visualization-tool.md#55-production-inputs)). If T041 finds the page out of reach for its effort, it reopens this decision with Streamlit on Community Cloud as the fallback.
- **Data only as fresh as the last publication:** visitors see the refresh cadence plus the run time, so the pipeline has to prepare the files and publish them at each refresh.
- **File sizes shape the page:** the hourly history is too large to download whole, so it is split per station and loaded on click.
- **Performance is estimated:** rendering and file sizes are not measured until T041 ([s013 › Not verified](../spikes/s013-visualization-tool.md#54-not-verified)).

## More information

- Full matrix, with needs, weights, anchors, scores, robustness and all options evaluated: [s013 › D3](../spikes/s013-visualization-tool.md#d3-static-web-page-with-javascript).
- Why the browser does not read gold, with the cost arithmetic: [s013 › D2](../spikes/s013-visualization-tool.md#d2-gold-stays-private-and-the-browser-does-not-read-it).
