---
status: Accepted
date: 2026-11-16
---

# Deployments tagged with their commit by a deploy script per component

## Context and problem statement

The project's components run on different platforms, and each is deployed on its own. To investigate a fault, someone must know which code each component was running at a given moment.

Deployments are made by hand from a local copy of `main`, right after a change reaches it ([ADR-0013](0013-github-flow-with-rebase-merge.md)); that copy can be out of date or hold uncommitted changes. Each platform keeps a history of its deployments. Each component already reports its own version in what it produces: capture in its log events ([ADR-0036](0036-log-convention-across-components.md)), the pipeline in its rows and logs ([ADR-0043](0043-lineage-at-four-levels.md)). Nothing links a deployment to its commit, and nothing stops a deployment from a working tree with changes that were never committed.

## Considered Options

### 1. A deploy script per component that tags each deployment

Each component deploys through a script of its own, run instead of the platform's command. It deploys only when the working tree is clean and its commit is the latest of `main`, and passes the commit's SHA as the deployment's tag on the platform.

- Pros:
  - The commit behind any deployment is read directly in the platform's history.
  - No deployment carries uncommitted code or an old commit by mistake.
  - The same script can later run from CI, unchanged.
- Cons:
  - One script per component to build and keep.

### 2. Find a deployment's commit by its time

Nothing is built: the commit behind a deployment is the last merge to `main` before the deployment's time on its platform.

- Pros:
  - Nothing to build or keep.
- Cons:
  - A lookup matches two histories by hand.
  - It gives the wrong commit for a deployment from an out-of-date or modified local copy.

### 3. Tag each deployment and read every version in one health query

As option 1, plus one query that reads the running version of every component.

- Pros:
  - All running versions read in one place.
- Cons:
  - A query to build and keep, for an occasional lookup each platform's history already answers.

## Decision Outcome

**Chosen option:** 1. A deploy script per component that tags each deployment

Rationale: a deployment's commit cannot be reliably derived from its time while a local copy can differ from `main`, so it is recorded where the deployment happens; the checks that make the tag true also keep uncommitted code out of production. This follows Twelve-Factor's build, release, run, where every release carries a unique ID.

Why not the others:

- Option 2 fails exactly in the case that most needs investigating, a deployment of code that is not on `main`.
- Option 3 adds a query for what the platforms' histories already show.

**Scope:** every production deployment of every component. A deployment made by a component in its own runs, such as the pipeline redeploying the page ([ADR-0033](0033-data-published-by-redeploying-static-assets.md)), is tagged with that component's code version. It does not decide who or what runs the script: by hand today, possibly CI later.

### Consequences

#### Positive

- **Direct lookup:** each deployment names its commit on its platform.
- **Guarded deployments:** only committed code on the latest `main` reaches production.
- **Ready for CI:** a CI job can run the same script with its token from the environment.

#### Negative

- **One script per component:** each new component needs its own.
- **Platform dependence:** the tag relies on each platform's CLI offering one; a platform without it needs another record.
- **No quick local deploy:** testing a change in production first requires it on `main`.

## More information

- [d007 › D6](../designs/d007-pipeline-design.md#d6-deployments-tagged-with-their-commit), [#8](../designs/d007-pipeline-design.md#22-decision-summary).
- At writing: `wrangler deploy --tag` and `modal deploy --tag`.
