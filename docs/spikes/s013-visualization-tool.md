# Spike: Visualization tool

- **Task:** T038
- **ADRs:** `<ADRs this spike must respect, or "none">`
- **Code:** `spikes/visualization-tool/`

## Status

<!-- State: Draft 📝 · Ready 🎬 · Running 🔄 · Concluded ✅.
Phase: the blocks and the review completed.
Started / Finished: UTC dates of the first step executed and of the Conclusion.
Current step: the step being executed, or —. -->

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review · [ ] Conclusion
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

### 1.2 Decided at framing

#### D1. Public access without login

The visualization stays publicly accessible and read-only, without login, as [d002 › R1](../designs/d002-requirements.md#requirements) asks. This is a portfolio project, so the link must open with no friction. The page publishes open station data, so a login would protect nothing confidential. The main risk of public access is therefore cost, not a data leak: bots or heavy traffic drive up cost if each visit triggers work or reads.

- **What would change it:** no publishing option keeps abuse-driven cost under control within the visualization's €2 share ([s011](s011-engine-pipeline-language.md)). Action: reopen this decision and consider a login.
- **Rejected:** login. It removes most abuse, but part of the people who receive the link would not reach the project, and it adds users to manage and one more access to protect. A login can in principle be added in front of the page later without rebuilding it.

#### D2. Gold stays private and the browser does not read it

Visitors' browsers do not read gold from R2, so gold is not made public, as [d002 › R18](../designs/d002-requirements.md#requirements) asks. Reading it directly would turn every visit into Class B operations with no limit on how many anyone can trigger, which is the cost risk of D1. A script at 100 reads/s makes about 8.6 M reads a day: it uses up the free 10 M in just over a day and costs about $90 a month at [$0.36 per million](<https://developers.cloudflare.com/r2/pricing/>), against the visualization's €2 share.

- **Scope:** this rejects public access to gold only. Where any files prepared for the page are published is still open.

#### D3. Static web page with JavaScript

The visualization is a static web page with JavaScript: visitors download prepared files, and no server runs. It scores 9.2 out of 10 in the weighted matrix, against 7.0 for Streamlit on Community Cloud. It leads on look and own identity, the heaviest criterion, and on upkeep, because nothing keeps running. Its cost is build effort: JavaScript and web tools are new to the project.

TODO(T041): choose between a hand-written page and Observable Framework. Both are static pages with JavaScript and publish the same way, so the choice does not change this decision. Observable's look and capability scores are inferred, because its documentation could not be fetched; if it confirmed 5 on both, it would score 9.0 against 9.2.

- **What would change it:** build effort weighing about 30 instead of 10, where Streamlit on Community Cloud ties. If T041 finds the page out of reach for its effort, it reopens this decision with Streamlit on Community Cloud as the fallback.
- **Rejected:**
  - Streamlit on Community Cloud: the structure reveals the tool, a process keeps running, and it has no custom domain. It passes N5 only through a manual reboot, so it needs an alert that tells the owner.
  - Streamlit on Oracle Cloud: same look, plus a machine to administer.
  - Evidence: its theme covers colours and fonts, and refreshing without a rebuild in the open-source version is not confirmed.
  - Grafana Cloud: public dashboards on the free plan are not confirmed (N1), and it stays at 4.4 even with generous scores on everything else.
- **Robustness:** the winner holds with equal weights (8.0 against 7.5), with look at weight 0 (8.7 against 7.7), and with one point less on look and on capability (7.8 against 7.0). The figures compare it with Streamlit on Community Cloud.

Needs, each traced to its origin:

| # | Need | Origin |
|---|---|---|
| N1 | Public and read-only, without login | [d002 › R1](../designs/d002-requirements.md#requirements), D1 |
| N2 | Shows the attribution each source's licence requires | [d002 › R2](../designs/d002-requirements.md#requirements) |
| N3 | Shows current station status within the freshness of R3 | [d002 › R3](../designs/d002-requirements.md#requirements) |
| N4 | Shows the age of the latest data if a feed stops updating | [d002 › R7](../designs/d002-requirements.md#requirements) |
| N5 | Costs at most €2 per month, including under abuse | [d002 › R4](../designs/d002-requirements.md#requirements), [s011](s011-engine-pipeline-language.md), D1 |
| N6 | Gold and all other stored data stay private | [d002 › R18](../designs/d002-requirements.md#requirements), D2 |
| N7 | Can present the guiding questions with a map, charts and filters | [d002 › Guiding questions](../designs/d002-requirements.md#guiding-questions) |
| N8 | Polished look with its own identity | [d002 › Context](../designs/d002-requirements.md#context) |
| N9 | One person can maintain it with little work | [architecture › Owner](../architecture.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md) |
| N10 | Adapts to any screen, from phone to desktop | [d002 › R29](../designs/d002-requirements.md#requirements) |

Hard cuts: an option that fails N1–N6 or N10 is out, unscored. N5 is applied as follows: abuse cannot bill more than €2 per month, and the page works again at most 1 day after the abuse ends. An outage during abuse is accepted because the expected cost is close to zero.

Criteria, with weights adding up to 100:

| Criterion | Weight | Need |
|---|---|---|
| Look and own identity | 40 | N8 |
| Capability to present the guiding questions | 30 | N7 |
| Upkeep | 20 | N9 |
| Build effort | 10 | Largest difference between a Python app and a web page |

Anchors:

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| Look and own identity | Generic template: only colours change | Own colours and good maps and charts, but the structure reveals the tool, and going beyond it needs workarounds | Full control of structure, typography, map and interaction: nothing reveals the tool |
| Capability to present the guiding questions | Does not handle the map with about 780 stations well, or leaves out a Must question | Covers the Must questions with map and filters, but a Should or Could question is limited | Covers all guiding questions with interactive map, charts and filters, and loads each station's detail on click |
| Upkeep | A machine to administer: system, patches and restarts | Managed service, but with a running process or limits that need attention from time to time | Nothing running: only dependency updates |
| Build effort | New language and tools, and almost everything is written by hand | Specific tool with little code in a new language | Python only, with ready-made components |

Scores:

| Option | Look (40) | Capability (30) | Upkeep (20) | Effort (10) | Out of 10 |
|---|---|---|---|---|---|
| Hand-written web page | 5 | 5 | 5 | 1 | **9.2** |
| Observable Framework | 4 | 4 | 4 | 2 | 7.6 |
| Streamlit on Community Cloud | 3 | 4 | 3 | 5 | 7.0 |
| Streamlit on Oracle Cloud | 3 | 4 | 1 | 4 | 6.0 |
| Evidence | 2 | 3 | 4 | 4 | 5.8 |

Facts behind the scores:

- **Hand-written web page:** full control of the page; [static assets are free and unlimited](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/); nothing keeps running; needs JavaScript. Map rendering of about 780 stations is not measured.
- **Observable Framework:** Markdown plus JavaScript, generated statically; [one release in the last 11 months](https://github.com/observablehq/framework/releases). Look and capability are inferred.
- **Streamlit on Community Cloud:** [theming and CSS](https://docs.streamlit.io/develop/concepts/configuration/theming); a `streamlit.app` subdomain only; [maps with click selection, where each click reruns on the server](https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart); [past its limits an app may slow down or stop, and the owner can reboot it](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app); Python only.
- **Streamlit on Oracle Cloud:** as above for look and capability; [Always Free compute with an idle reclaim policy](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm); the operator administers the machine.
- **Evidence:** [SQL and Markdown](https://docs.evidence.dev/); [theme of colours, palettes and fonts](https://docs.evidence.dev/core-concepts/themes); [point maps](https://docs.evidence.dev/components/maps/point-map/); refresh without a rebuild is documented only for its hosted product.

Sizing for comparing options uses a refresh every 5–10 minutes, that is 4,300–8,600 refreshes per month.

TODO(T040): the visitor sees cadence plus run time (about 2 minutes, not measured), so a 5–10 minute cadence gives an age of about 7–12 minutes, above R3's 5 minutes. Choose the cadence and review R3 and the freshness of d002's Q1, Q2 and Q5 together.

#### D4. Data published by redeploying on Workers Static Assets

The pipeline publishes the page's data by deploying a new version on Cloudflare Workers Static Assets at each refresh. [Requests for static assets are free and unlimited](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/), so abuse has no quota to use up and cannot bill, which meets N5. It needs no domain, and page and data always match because they are published together. Cloudflare publishes [no limit on deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/), but does not confirm that 4,300–8,600 a month are acceptable, so this depends on Q1. If its Gate fails, the fallback applies.

- **Fallback:** a Worker with the Cache API in front of private R2. [Past 100,000 requests a day it fails until the counter resets at 00:00 UTC](https://developers.cloudflare.com/workers/platform/limits/), within N5, but it adds code to maintain.
- **Rejected:** a separate R2 bucket with a custom domain and CDN cache. It needs a domain, and requests for keys that do not exist miss the cache and bill Class B operations, with only one free rate-limiting rule to stop them.

TODO(T041): decide whether to buy a custom domain; without one, the page uses a free `workers.dev` address.

#### D5. No separate operations panel

The pipeline's health is viewed through the public section for feed health (d002's Q2), the existing email alerts and ad hoc SQL. A separate panel would add a login, which [d002 › R1](../designs/d002-requirements.md#requirements) does not contemplate for the page, and one more component to protect and maintain, and the cost of Modal's OpenTelemetry integration is not checked. It can be added later if needed.

TODO(T040): write a script with the common health queries for the owner to run, and decide whether it can run from a phone.

- **Rejected:** a private panel with login, for the reasons above.

#### D6. Visualization security

Five new requirements, R30–R34, and the other threats documented without a requirement. Threats are listed with STRIDE and controls follow least privilege, as in [s012 › D3](s012-execution-target.md#d3-pipeline-security). The scope is the page, the files it publishes, the credential that deploys it and what runs in the visitor's browser.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| TH1 | The credential the pipeline deploys the page with leaks (Tampering) | Someone publishes other content at the page's address and, depending on the credential's scope, could change capture | Its own credential, limited to publishing, kept in the secret store (R25) | R30 |
| TH2 | Someone takes over the Cloudflare account (Spoofing) | Reaches the page, capture and R2; R24 covers only the pipeline's accounts | Two-factor authentication also on the accounts that publish the page | R31 |
| TH3 | More than intended is published (Information disclosure) | Low for open data, but logs or internal state could go out | Only files on an explicit list are published, never the contents of a bucket | R32 |
| TH4 | A compromised JavaScript library runs in the visitor's browser (Tampering) | Third-party code on the page of whoever visits it | Pinned libraries served from the page's own address, with no third-party scripts | R33 |
| TH5 | Text in a feed, such as a station name, contains code (Tampering) | It would run in the visitor's browser; unlikely, since the feeds come from the operators | Data is always shown as text, never as HTML | R34 |
| TH6 | A flood of visits or bots (Denial of service) | Slow or unavailable page while it lasts, with no bill | Accepted: D1, D4 and the N5 cut in D3 | None |
| TH7 | The base map provider stops the service (Denial of service) | Map with no background; free providers give no guarantees | Accepted: T041 chooses a provider and an alternative | None |
| TH8 | The base map provider sees visitors' IP addresses (Information disclosure) | Low | Accepted, with no cookies or analytics; reviewed if T041 wants analytics | None |
| TH9 | No record of who published each version (Repudiation) | Low: there is one operator | Accepted | None |

Requirements transferred to [d002 › Requirements](../designs/d002-requirements.md#requirements): R30 (TH1), R31 (TH2), R32 (TH3), R33 (TH4), R34 (TH5).

### 1.3 Questions

Main question: `<one sentence>`

- **Q1.** Can the pipeline deploy a new version on Workers Static Assets every 5–10 minutes on the free plan? Unblocks D4.
- **Observe only:** `<item>`

### 1.4 Exit criteria

- **Standard:** `<standard or pattern applied>`
- **Timebox:** `<window, and what ends it>`
- `<criterion>` — `<threshold>` — hard cut | guide

### 1.5 Out of scope

- `<item>` — TNNN

### 1.6 Open questions

| Question | Notes |
|---|---|
| | |

## 2. Method — how we find out

### 2.1 Approach

<!-- The variants, options or probes compared, and what each one tells that the others do not. -->

| Variant | What it is | What it tells |
|---|---|---|
| | | |

#### 2.1.1 Shared behaviour

<!-- Optional. Rules every variant follows (schedules, formats, key layouts, logs), stated once so the steps can cite them. -->

-

#### `<A>`. `<Title of variant, option or probe A>`

<!-- Detailed description -->

### 2.3 Decision log

<!-- It logs decisions about the method, before and during the run, including changes of course. Oldest first.
Entries follow .claude/rules/docs/decision-log.md (log only, change links).
- Column Applies to: anchor link(s) to the section where the decision is applied, named in one or two words (e.g. Q1, Probe A, File layout).
- Column Decided at: the Status phase where it was decided (Method, Steps), `<phase> review` when decided while reviewing that phase, or `Running step N` when decided during the run.
-->

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| `<N>` |  |  |  |  |

### 2.4 File layout

<!-- Every file and folder the spike creates, as a tree with its purpose in one line. Captured data and outputs are marked as ignored by Git (ADR-0009). The README is always included. -->

```text
spikes/visualization-tool/
├── README.md        Question, setup and commands, what each script does, link to the report
└── <file>           <purpose>
```

## 3. Steps

<!-- Each step is one reviewable result, touching at most 2–3 files.
- Status: where the step is: 💤 todo · 🎬 ready · 🔄 in progress · ⛔ blocked · ✅ done
- Who: Owner (manual actions: dashboards, accounts, deploys, runs, checks) or Claude (code and documents).
- Commit: only in a step that changes committed files: the proposed message, following the Git conventions in CLAUDE.md.
- Model: the model and effort the step's session runs with (e.g. sonnet · medium), or — when Who is Owner.
- Gate: optional. <condition> → <consequence if it fails: variants or steps dropped or re-decided>. -->

### 3.1 Prerequisites

<!-- Owner actions outside the repo, each with its exact version or value and how to verify it. Write "None" when empty. -->

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **Model:** `<model · effort>` (or —)
- **Gate:** `<condition>` → `<consequence>`

#### Scope

<!-- The result of the step. List the components and the files created or changed (code, tests, docs). A reviewer should know what the diff will contain from this section alone. -->

#### Reads

<!-- List of reads containing what to read (be specific with paragraph or line), what contains the read, and why it is interesting here.  -->

#### Do

<!-- Numbered actions in execution order, one verb each (write, implement, update, run). Every file named here must appear in Scope; add nothing Scope does not list. -->

#### Check

<!-- command/s or verification with a yes/no result. -->

## 4. Findings

<!-- Filled during the run, in the step that produces the evidence. One fact per finding: what was observed, the evidence (figures, tables) and its consequence for the spike. Numbering is never reused. An earlier finding is not rewritten to fit a later result; the later one says which finding it corrects. -->

### F1. `<one-line statement>`

Step N · YYYY-MM-DD · `<source of evidence>`

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

## 5. Conclusion

<!-- Filled after the last step. Covers only the observed window. -->

Observed window: `<from–to, UTC; what it does not cover>`

### 5.1 Answers

- **Q1. Title** `<answer>` (FN)

### 5.2 Exit criteria

<!-- One result per criterion and variant. -->

| Criterion | Kind | Result | Findings |
|---|---|---|---|

### 5.3 Verdict

<!-- The answer to the main question in 2–3 sentences. -->

### 5.4 Not verified

<!-- What the evidence does not cover, each with its risk and mitigation. "None" is valid. -->

- `<item>` — `<risk>` — `<mitigation>`

### 5.5 Production inputs

<!-- Optional. Points worth taking to production, from any part of the spike. Each one has a Destination: a design (with its task) or discarded with a reason. -->

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | `<e.g. D1, #2, F3>` | |

### 5.6 Follow-ups

<!-- ADRs to write, from Decided at framing (each in its own commit), and new tasks agreed with the owner. Production inputs are not repeated here. -->

- `<ADR or task>`

## 6. Sources

<!-- Optional. Earlier spikes, benchmarks and documentation used. -->

-
