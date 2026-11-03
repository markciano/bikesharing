---
status: Proposed
date: 2026-11-03
---

# Data published by redeploying on Workers Static Assets

## Context and problem statement

The visualization is a static web page whose browser downloads prepared files ([ADR-0032](0032-static-web-page-for-visualization.md)). Those files need a public place to live, and the pipeline has to replace them at each refresh.

- Access is public, so anyone can make as many requests as they like. Abuse cannot bill more than the visualization's €2 monthly share ([ADR-0026](0026-budget-shares-per-component.md)), and the page must work again at most 1 day after the abuse ends.
- Gold and all other stored data stay private ([d002 › R18](../designs/d002-requirements.md#requirements)).
- The cadence is not chosen yet. A refresh every 5–10 minutes is 4,300–8,600 publications a month.
- One person maintains the solution, so every piece of code to keep is a cost.
- The project owns no domain.

## Considered Options

Each option is compared on what abuse can cost, whether it needs a domain and what it adds to maintain.

### 1. Redeploying on Workers Static Assets

At each refresh, the pipeline deploys a new version of a Worker that holds the page and its prepared files.

- Pros:
  - requests for static assets are free and unlimited, so abuse has no quota to use up and cannot bill;
  - it needs no domain;
  - page and data always match, because they are published together;
  - no code runs to serve the files.
- Cons:
  - no Cloudflare page confirms that this rate of deployments is accepted;
  - the pipeline holds a credential that can publish at the page's address;
  - every refresh depends on a deployment succeeding.

### 2. Worker with the Cache API in front of private R2

A Worker reads the files from a private bucket and caches them.

- Pros:
  - abuse cannot bill: past 100,000 requests a day it fails until the counter resets at 00:00 UTC;
  - publishing a refresh needs no deployment.
- Cons:
  - it adds code to maintain;
  - abuse takes the page down until the reset.

### 3. Separate R2 bucket with a custom domain and CDN cache

The files go to a public bucket of their own, served through the CDN.

- Pros:
  - no code to maintain;
  - publishing a refresh needs no deployment.
- Cons:
  - it needs a domain;
  - requests for keys that do not exist miss the cache and bill Class B operations, with only one free rate-limiting rule to stop them.

## Decision Outcome

**Chosen option:** 1. Redeploying on Workers Static Assets.

It is the only option where abuse has nothing to use up, which meets the budget force in the Context with an expected cost of €0. It needs no domain and adds no code to serve the files. Its open point is that Cloudflare's acceptance of this use is not confirmed: its limits page lists no cap on deployments or versions, and 4,300–8,600 a month stay far below the 1,200 API requests per 5 minutes.

Why not the others:

- Worker with the Cache API: it meets the budget force, but with code to maintain and an outage under abuse. It remains the fallback.
- Separate R2 bucket: it needs a domain and leaves a path for abuse to bill.

**Scope:** Where the page's files are published and how a refresh reaches them. It does not choose the cadence or define the list of files, both in T040, and it does not decide on a custom domain, in T041.

### Consequences

#### Positive

- **Abuse cannot bill:** a flood of visits can make the page slow or unavailable while it lasts, with no bill.
- **Consistent versions:** each version holds a page and data published together. A visitor with the page open during a refresh is handled by keeping file names fixed ([s013 › P1](../spikes/s013-visualization-tool.md#55-production-inputs)).
- **Stored data stays private:** the buckets are not involved in serving the page.

#### Negative

- **Acceptance not confirmed:** if Cloudflare rejects or limits the deployments, the page stays up with its last data, shows its age ([d002 › R7](../designs/d002-requirements.md#requirements)), and publishing moves to the fallback.
- **One more credential in the pipeline:** a leak lets someone publish other content at the page's address, so the token is limited to this Worker ([d002 › R30](../designs/d002-requirements.md#requirements)). That a token so limited can upload assets is not confirmed; the fallback is a separate Cloudflare account for the page.
- **A new step in each run:** the pipeline depends on Cloudflare to publish, so a failed deployment must not fail the run's data.
- **Not measured:** errors while deploying, and how soon a same-named file refreshes ([s013 › Not verified](../spikes/s013-visualization-tool.md#54-not-verified)).

## More information

- Decision, sources and fallback: [s013 › D4](../spikes/s013-visualization-tool.md#d4-data-published-by-redeploying-on-workers-static-assets).
- What the pipeline and the page must do with this: [s013 › P1, P2, P3, P8](../spikes/s013-visualization-tool.md#55-production-inputs).
- Facts on static assets and limits: [Cloudflare source card](../sources/cloudflare.md).
