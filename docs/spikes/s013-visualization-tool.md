# Spike: Visualization tool

- **Task:** T038
- **ADRs:** [ADR-0019](../decisions/0019-own-lakehouse-on-cloudflare-r2.md), [ADR-0023](../decisions/0023-storage-security-baseline.md), [ADR-0026](../decisions/0026-budget-shares-per-component.md), [ADR-0027](../decisions/0027-modal-as-execution-platform.md)
- **Code:** none

## Status

- State: Concluded ✅
- Phase: [x] Questions · [x] Conclusion. Method, Steps and Steps review do not apply: triage left no question that needs a run.
- Started: — · Finished: 2026-11-03
- Current step: —

## 1. Questions — what we need to know

### 1.1 Context

Storage, table format (T035), engine, pipeline language (T036) and execution target (T037) are decided. This spike decides who can see the visualization (D1), how the page gets its data (D2), the tool (D3, the central decision), how its data is published (D4), whether an operations panel is needed (D5), and its threats and new requirements (D6). All of them are decided on documentation and arithmetic: what remains unknown has a written fallback and is checked more reliably on the real page in T041. It builds on the inputs left by [s010](s010-storage-table-format.md), [s011](s011-engine-pipeline-language.md) and [s012](s012-execution-target.md).

### 1.2 Decided at framing

#### D1. Public access without login

The visualization stays publicly accessible and read-only, without login, as [d002 › R1](../designs/d002-requirements.md#requirements) asks. This is a portfolio project, so the link must open with no friction. The page publishes open station data, so a login would protect nothing confidential. The main risk of public access is therefore cost, not a data leak: bots or heavy traffic drive up cost if each visit triggers work or reads.

- **What would change it:** no publishing option keeps abuse-driven cost under control within the visualization's €2 share ([s011](s011-engine-pipeline-language.md)). Action: reopen this decision and consider a login. D4 keeps that cost at zero, so the condition is not met.
- **Rejected:** login. It removes most abuse, but part of the people who receive the link would not reach the project, and it adds users to manage and one more access to protect. A login can in principle be added in front of the page later without rebuilding it.

#### D2. Gold stays private and the browser does not read it

Visitors' browsers do not read gold from R2, so gold is not made public, as [d002 › R18](../designs/d002-requirements.md#requirements) asks. Reading it directly would turn every visit into Class B operations with no limit on how many anyone can trigger, which is the cost risk of D1. A script at 100 reads/s makes about 8.6 M reads a day: it uses up the free 10 M in just over a day and costs about $90 a month at [$0.36 per million](<https://developers.cloudflare.com/r2/pricing/>), against the visualization's €2 share.

- **Scope:** this rejects public access to gold only. D4 decides where the files prepared for the page are published.

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

Sizing, an order of magnitude with no measurement. Rows are stations × points in time, for about 780 stations, at an assumed 3–8 bytes per compressed row and 50 bytes per station in the snapshot:

| Page section | Guiding questions | Rows | Size |
|---|---|---|---|
| Map and current status | d002's Q1, Q5 | 780 | Tens of KB, replaced at each refresh |
| One station's hourly history, loaded on click | d002's Q3, Q7 | 8,760 per station | 25–70 KB per station, 20–55 MB in total |
| Rankings and trips, daily | d002's Q4, Q6 | About 285,000 | 1–2 MB |
| Feed health and network changes | d002's Q2, Q8 | Not calculated | Expected small |

The hourly case cannot be downloaded whole on each visit, but it can be split into one file per station. A refresh every 5–10 minutes is 4,300–8,600 refreshes per month.

#### D4. Data published by redeploying on Workers Static Assets

The pipeline publishes the page's data by deploying a new version on Cloudflare Workers Static Assets at each refresh. [Requests for static assets are free and unlimited](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/), so abuse has no quota to use up and cannot bill, which meets N5 and leaves the visualization's expected cost at €0 against its €2 share. It needs no domain, and page and data always match because they are published together.

- **What would change it:** Cloudflare rejects or limits the deployments. Its [limits page](https://developers.cloudflare.com/workers/platform/limits/) lists no cap on deployments or versions, and 4,300–8,600 a month stay far below the [1,200 API requests per 5 minutes](https://developers.cloudflare.com/fundamentals/api/reference/limits/), but no page confirms that this use is accepted. Action: move to the fallback; the page stays up with its last data, and R7 shows its age.
- **Fallback:** a Worker with the Cache API in front of private R2. [Past 100,000 requests a day it fails until the counter resets at 00:00 UTC](https://developers.cloudflare.com/workers/platform/limits/), within N5, but it adds code to maintain.
- **Rejected:** a separate R2 bucket with a custom domain and CDN cache. It needs a domain, and requests for keys that do not exist miss the cache and bill Class B operations, with only one free rate-limiting rule to stop them.

TODO(T041): decide whether to buy a custom domain, before the link is shared; without one, the page uses a free `workers.dev` address.

#### D5. No separate operations panel

The pipeline's health is viewed through the public section for feed health (d002's Q2), the existing email alerts and ad hoc SQL. A separate panel would add a login, which [d002 › R1](../designs/d002-requirements.md#requirements) does not contemplate for the page, and one more component to protect and maintain, and the cost of Modal's OpenTelemetry integration is not checked. It can be added later if needed. This closes the item left to T038 in [s012 › Out of scope](s012-execution-target.md#15-out-of-scope).

- **Rejected:** a private panel with login, for the reasons above.

#### D6. Visualization security

Five new requirements, R30–R34, and the other threats documented without a requirement. Threats are listed with STRIDE and controls follow least privilege, as in [s012 › D3](s012-execution-target.md#d3-pipeline-security). The scope is the page, the files it publishes, the credential that deploys it and what runs in the visitor's browser.

| # | Threat (STRIDE) | Impact | Control | Requirement |
|---|---|---|---|---|
| TH1 | The credential the pipeline deploys the page with leaks (Tampering) | Someone publishes other content at the page's address | Its own token, with the [Editor role scoped to this Worker](https://developers.cloudflare.com/changelog/post/2026-09-15-granular-worker-permissions/), so it cannot change capture; kept in the secret store (R25). Creating the Worker needs Admin, so the owner creates it once | R30 |
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

Main question: which tool should the visualization use, and where is it published?

No Q: a one-day probe of deployments was considered and dropped. It could not rule out a monthly limit, and what it could measure is measured more reliably on the real page in T041, with its fallbacks already written.

### 1.4 Exit criteria

- **Standard:** weighted decision matrix for the tool; STRIDE with least privilege for the threats.
- **Timebox:** none, since nothing runs.
- N1–N6 and N10 — met by the winner, with N3 open until T040 chooses the cadence — hard cut.

### 1.5 Out of scope

- Design of the page, its base map and its domain — T041
- The refresh cadence and the review of R3 — T040

## 5. Conclusion

Observed window: none. Nothing was run; the evidence is documentation read on 2026-11-03 and arithmetic.

### 5.1 Answers

No Q was raised, so there is nothing to answer; D1–D6 hold the decisions.

### 5.2 Exit criteria

| Criterion | Kind | Result | Findings |
|---|---|---|---|
| N1, N2, N4, N6, N10: public access, attribution, data age, private storage, any screen | Hard cut | Pass by design: a static page has full control of what it shows, and it reads no stored data | D2, D3 |
| N3: freshness of R3 | Hard cut | Open: a 5–10 minute cadence gives about 7–12 minutes of age; T040 reviews it. The tool does not limit it | D3 |
| N5: at most €2, including under abuse, and back within 1 day | Hard cut | Pass on documentation: static asset requests are free and unlimited | D4 |

### 5.3 Verdict

The visualization is a public static web page with JavaScript, without login, which the pipeline publishes by deploying on Cloudflare Workers Static Assets at each refresh. Visitors never reach R2, so abuse cannot bill, and the expected cost is €0 against the €2 share of [ADR-0026](../decisions/0026-budget-shares-per-component.md). Whether to write it by hand or with Observable Framework is left to T041, since both publish the same way.

### 5.4 Not verified

- A token scoped to one Worker uploading static assets: no page states it — the deploy could be rejected — the first real deployment checks it; the fallback is a separate Cloudflare account for the page.
- Whether Cloudflare accepts 4,300–8,600 deployments a month: absence of a stated limit is not a confirmation, and Cloudflare's terms were not read — deployments could be limited — D4's fallback.
- That `wrangler deploy` from the pipeline is outside the limits of Workers Builds and Deploy Hooks: inferred, since no page says so — same risk — D4's fallback.
- Errors while deploying, and how soon the Cloudflare cache serves a new file under the same name: the documents state neither; the default header is `max-age=0, must-revalidate` — visitors could get errors or older data — T041 measures both on the real page.
- Rendering about 780 stations and the file sizes: estimates, not measured — a slower page or larger files — T041 measures them.
- Observable Framework's look and capability: inferred — the choice in T041 could differ from the matrix — T041 reads its documentation.
- Base map providers: licences and limits only partly read — the map could lose its background (TH7) — T041 chooses a provider and an alternative.

### 5.5 Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | Data files keep a fixed name, with no hash, since a file that disappears in a new version [gets a 404](https://developers.cloudflare.com/workers/static-assets/) for whoever has the page open | D4 | T041's design |
| P2 | The owner creates the Worker once (Admin); the first real deployment checks the Editor token scoped to "Specified Workers" with static assets; the fallback is a separate Cloudflare account | TH1 | T041's design |
| P3 | Measure errors while deploying, how soon a same-named file refreshes, rendering of about 780 stations and real file sizes | D3, D4 | T041's design |
| P4 | Group stations when the map is zoomed out, since all of them at once would hide the map, and design the map and charts for phones | D3, R29 | T041's design |
| P5 | Choose a base map provider and an alternative, with its attribution: OSM's tile server needs visible attribution and has no guarantee; Protomaps offers a file to host | TH7, N2 | T041's design |
| P6 | Add the page's stack to the project's conventions: pinned runtimes and locked dependencies (ADR-0016, ADR-0017) and its own CI job (ADR-0013) | R33 | T041's design |
| P7 | No cookies or analytics; reviewed if analytics are wanted | TH8 | T041's design |
| P8 | The pipeline generates the prepared files from an explicit list and deploys them at the end of a run, with the token from the secret store; a failed deployment does not fail the run's data | D4, R25, R32 | T040's design, with T041 |
| P9 | The health script could run from a phone through a manual GitHub Actions run: no server, but its summary is public if the repository is, and GitHub holds one more read-only key. Not verified | D5 | T040's design |

TODO(T041): P1–P7.

TODO(T041): proposal to evaluate in the design: build the riskiest slice first, the map with about 780 stations on a phone, so that a problem shows before much work goes into the page.

### 5.6 Records

| Output | From | Destination | Commit |
|---|---|---|---|
| ADR: static web page with JavaScript | D2, D3 | `docs/decisions/`; [architecture](../architecture.md) › Solution strategy, Building blocks | Done |
| ADR: data published by redeploying on Workers Static Assets | D4 | `docs/decisions/`; [architecture](../architecture.md) › Deployment view (resolves `TODO(T038)`), Runtime view | Done |
| R29–R34 | D3, D6 | [d002 › Requirements](../designs/d002-requirements.md#requirements) | Done |
| Cloudflare facts | D3, D4, D6 | [Cloudflare source card](../sources/cloudflare.md) | Done |
| T053, T054 | Comments in the template; threat IDs | [tasks.md](../tasks.md) | Done |

## 6. Sources

Gathered by the `web-researcher` on 2026-11-03. Its tool summarizes pages, so wording is not guaranteed verbatim.

- Workers Static Assets: <https://developers.cloudflare.com/workers/static-assets/>, [billing and limitations](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/), [headers](https://developers.cloudflare.com/workers/static-assets/headers/), [direct upload](https://developers.cloudflare.com/workers/static-assets/direct-upload/)
- Workers limits, versions and tokens: [limits](https://developers.cloudflare.com/workers/platform/limits/), [versions and deployments](https://developers.cloudflare.com/workers/configuration/versions-and-deployments/), [authorization](https://developers.cloudflare.com/workers/authorization/), [granular Worker permissions](https://developers.cloudflare.com/changelog/post/2026-09-15-granular-worker-permissions/), [API limits](https://developers.cloudflare.com/fundamentals/api/reference/limits/)
- Workers Builds and Deploy Hooks: [deploy hooks](https://developers.cloudflare.com/workers/ci-cd/builds/deploy-hooks/), [limits and pricing](https://developers.cloudflare.com/workers/ci-cd/builds/limits-and-pricing/)
- Cloudflare Pages: [limits](https://developers.cloudflare.com/pages/platform/limits/)
- R2 and cache: [pricing](https://developers.cloudflare.com/r2/pricing/), [public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/), [cache keys](https://developers.cloudflare.com/cache/how-to/cache-keys/), [rate limiting rules](https://developers.cloudflare.com/waf/rate-limiting-rules/), [how charges accrue](https://developers.cloudflare.com/billing/understand/how-charges-accrue/)
- Options scored: see the links in [D3](#d3-static-web-page-with-javascript)
- Grafana: [pricing](https://grafana.com/pricing/), [shared dashboards](https://grafana.com/docs/grafana/latest/dashboards/share-dashboards-panels/shared-dashboards/)
- Base map: [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/), [OpenFreeMap terms](https://openfreemap.org/tos/), [Protomaps basemaps](https://docs.protomaps.com/basemaps/downloads)
