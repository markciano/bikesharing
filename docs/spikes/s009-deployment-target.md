# Spike: Deployment target

- **Task:** T022
- **ADRs:** ADR-0003 (to be superseded)
- **Code:** none (desk research)

## Status

- State: Ready 🎬
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### Context

ADR-0003 chose to build locally first and port to Microsoft Fabric later; Fabric is dropped, and "local first" stays. This spike decides where the processing pipeline and the visualization run once built, which the pipeline design (T025) waits on. Fixed inputs: capture lands in Cloudflare R2 (ADR-0011), code runs in Python (ADR-0010), and the real-time path is compared against a batch baseline (ADR-0004). The budget is $0, so the answer depends on free-tier limits that need evidence.

### Questions

Main question: where do the processing pipeline and the visualization run, and with which visualization runtime model (static, server app or managed BI), at $0?

- **Q1.** Which platforms, local and cloud free tiers, run a Python Spark + Delta Lake pipeline at $0, and with what limits (compute, storage, run time, expiry)?
- **Q2.** Where can each visualization runtime model be hosted publicly at $0, and with what limits (sleep, refresh, data size)?
- **Q3.** Which top pairs (pipeline platform, visualization host) support the three operating modes, each started on demand and in how long: static by default (the visualization shows the last processed data, nothing running), catch-up (one pipeline run processes what R2 holds and the pipeline does not), and live for demos (1-minute deltas from R2 through to the visualization, switched off afterwards)?
- **Q4.** How does each pipeline platform and each visualization host score on the weighted criteria, and which of the top pairs pass the junction check?
- **Observe only:** R2 free-tier operation limits (listing counts as Class A, shared with the Worker's writes) when polled every minute during a demo.

### Exit criteria

- **Standard:** hard constraints first, then a weighted scoring matrix over the surviving candidates and a junction check of the top pairs, recorded in MADR style for the ADR that supersedes ADR-0003.
- **Timebox:** half a day of desk research; the run ends when every P1 and P2 survivor is scored and the top pairs are junction-checked, or when the timebox runs out, in which case the decision is taken on the evidence gathered and the gaps go to Not verified. One candidate meeting the criteria is not enough, because the ADR needs the ranked alternatives.
- **Cost:** expected cost is $0, on always-free tiers or on trials lasting 3 months or more; each candidate records when it expires — hard cut.
- **Payment card:** passes if the official documentation shows at least one of: no card required; no charges without an explicit plan upgrade; a spending cap; budget alerts. Budget alerts are enough because an accidental overage of up to €10 is an accepted risk — hard cut.
- **Spark + Delta Lake:** the platform runs PySpark with open-source Delta Lake as it runs locally, either as a managed service or on a self-installed VM or container — hard cut.
- **Cloud pipeline:** the pipeline is deployed on a cloud platform; local stays the development environment and the reference in P1, not a target — hard cut.
- **Weighted criteria** — guide. Each P1 and P2 survivor scores 1–5 per criterion (Public availability applies to visualization hosts only); the total is the sum of score × weight, shown on a 0–10 scale as total ÷ maximum possible × 10:

| Criterion | What it measures | Weight |
|---|---|---|
| Public availability | A URL anyone can open at any time | 5 |
| Portfolio impact | Stack recognised in the job market, visual quality, what it conveys | 5 |
| Live mode | 1-minute data from R2 through to the visualization | 4 |
| Operational effort | Setup and upkeep (managed vs self-installed) | 3 |
| Portability | The same code runs locally and on the target (ADR-0010) | 3 |
| Durability | How long the free tier lasts before it expires | 2 |
| Learning curve | Effort to learn it starting from no web background | 1 |

### Out of scope

- Live data path: live mode reads from R2 (ADR-0011); a local collector is not considered.
- The concrete visualization tool: chosen within the winning runtime model in T033.
- The pipeline design (T025): this spike only requires Spark + Delta Lake.

## 2. Method — how we find out

### Approach

A funnel of three probes: the first two screen candidates cheaply against the hard cuts, the third works only on survivors.

| Probe | What it is | What it tells |
|---|---|---|
| P1. Pipeline platforms | Local (Mac), managed Spark free tiers and free VMs or containers, screened against the hard cuts | Q1: which run Spark + Delta Lake at $0, and their limits |
| P2. Visualization hosting | For each runtime model (static, server app, managed BI), where it is published for free, screened against the hard cuts | Q2: where each model can live, and its limits |
| P3. Scores and junction | P1 and P2 survivors scored separately on the weighted matrix; the top 3 of each side checked in pairs for the junction | Q3, Q4 and the Verdict |

Seed list (unverified until P1 and P2 run):

| Probe | Kind | Candidate | Note |
|---|---|---|---|
| P1 | Reference | Local (Mac) | Known to work |
| P1 | Managed Spark | Databricks Free Edition | Delta Lake native |
| P1 | Self-installed VM | Oracle Cloud Always Free ARM VM | |
| P1 | On-demand job | GitHub Actions on a public repository | Fits catch-up runs; nothing always on |
| P1 | Self-installed VM | Google Cloud free tier e2-micro VM | Likely too small; discarded on evidence |
| P2 | Static | GitHub Pages | |
| P2 | Static | Cloudflare Pages | |
| P2 | Static | Vercel | Hobby plan is non-commercial |
| P2 | Server app | Streamlit Community Cloud | |
| P2 | Server app | Hugging Face Spaces | |
| P2 | Server app | Render | Free plan |
| P2 | Managed BI | Looker Studio | |
| P2 | Managed BI | Power BI | Publish to web |
| P2 | Managed BI | Tableau Public | |

### Shared behaviour

- **Status at every stop.** Each step sets Current step when it starts, and Status is updated before the session stops.
- **Junction check.** A pair (pipeline platform, visualization host) passes if the visualization reads the pipeline's output at $0 (directly, or through an intermediate store such as R2) and the live mode works end to end, from pipeline start to visualization refresh. Pairs are ranked by the sum of their two 0–10 totals; the Verdict is the best-ranked pair that passes. The pair's expiry is the earlier of the two.
- **Scoring anchors.** Every score in P3 uses these anchors; 2 and 4 are for cases in between.

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| Public availability | No public URL (demo only) | Public URL with cold start or sleep | Public URL always reachable, no wait |
| Portfolio impact | Little-known tool, basic visuals | Recognised tool or polished visuals | Stack in demand for data engineering and rich visuals (maps, animation) |
| Live mode | Not possible | Possible with manual steps or more than 1 minute of lag | Starts on demand, 1-minute deltas end to end |
| Operational effort | Self-managed VM with several services kept by hand (install, schedule, logs, patches) | Some setup and occasional upkeep | Managed, near-zero upkeep |
| Portability | Logic lives in the platform: configured in the UI rather than code, or calls provider-only APIs | Platform layer changes and some platform APIs leak into the logic | Same code; only the platform layer changes (ADR-0010) |
| Durability | Trial of 3–6 months | Trial of 12 months or more | Always free |
| Learning curve | New language or paradigm on top of the platform | New platform, known language | Python tools the owner already uses |

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-23 | Candidates come from a seed list plus at most 3 additions per probe (P1, P2) found by the web researcher | Long list → short list: bounds the timebox without missing recent free-tier offers |
| 2026-10-23 | A free-tier limit counts as evidence only from the provider's official pricing page or documentation, with URL and access date; blogs and forums are leads, not evidence; anything without an official source goes to Not verified | Primary sources keep the matrix and the ADR traceable; free tiers change often |
| 2026-10-23 | Claude proposes each score with a one-line justification citing its source or finding, against fixed anchors (Shared behaviour); the owner validates or corrects in an Owner step | Fixed anchors make a weighted matrix reproducible; the owner's correction records the decision-maker's call |
| 2026-10-23 | Pipeline platforms and visualization hosts are scored separately; only the top 3 of each side are checked in pairs (junction check), instead of scoring every P1 × P2 combination | The parts do different jobs and meet only where one reads the other; up to 9 junction checks fit the timebox, about 36 scored combinations do not (Steps review, finding 4) |
| 2026-10-23 | The run is executed in the spike session, not through `/implement` | Desk research with no code: `/implement` would add a session without adding a review of code |

## 3. Steps

### Step 1 — P1: pipeline platforms against the hard cuts

- **Status:** 💤 todo
- **Who:** Claude (web researcher)
- **Commit:** `docs: add s009 pipeline platform findings`
- **R:** —
- **Gate:** no cloud platform passes every hard cut → the spike stops and the owner decides which hard cut to relax before Step 2.

#### Scope

Findings for every P1 candidate in this doc: the result of each hard cut (cost, payment card, Spark + Delta Lake, cloud pipeline) and the limits (compute, storage, run time, expiry), each with its official URL and access date. Candidates the researcher adds (at most 3) are appended to the seed list table, marked "added in Step 1". Status in this doc is set to Running 🔄 with today's UTC date as Started.

#### Reads

- This doc, Exit criteria: the hard cuts every candidate is checked against.
- This doc, Approach › seed list: the P1 candidates.
- This doc, Decision log: the evidence rule and the cap on additions.

#### Check

Every P1 candidate has a pass or fail for each hard cut, backed by an official URL and access date, or is listed as Not verified: yes/no.

#### Do

1. Update Status: State to Running 🔄, Started to today's UTC date, Current step to 1.
2. Run the web researcher with the P1 seed list, the hard cuts, the evidence rule and the cap of 3 additions.
3. Append the researcher's additions to the seed list table.
4. Write the P1 findings, one per candidate, with the hard-cut results and the limits.
5. Add a Production input for any limit the pipeline design (T025) must respect.
6. Apply the Gate.

### Step 2 — P2: visualization hosting against the hard cuts

- **Status:** 💤 todo
- **Who:** Claude (web researcher)
- **Commit:** `docs: add s009 visualization hosting findings`
- **R:** —
- **Gate:** a runtime model with no host passing every hard cut → that model leaves P3; no model with a passing host → the spike stops and the owner decides which hard cut to relax before Step 3.

#### Scope

Findings for every P2 candidate in this doc: the result of each applicable hard cut (cost, payment card) and the limits (sleep or cold start, refresh, data size, expiry, terms of use such as non-commercial plans), each with its official URL and access date. Additions (at most 3) are appended to the seed list table, marked "added in Step 2".

#### Reads

- This doc, Exit criteria: the hard cuts.
- This doc, Approach › seed list: the P2 candidates.
- This doc, Decision log: the evidence rule and the cap on additions.

#### Check

Every P2 candidate has a pass or fail for each applicable hard cut, backed by an official URL and access date, or is listed as Not verified: yes/no.

#### Do

1. Run the web researcher with the P2 seed list, the hard cuts, the evidence rule and the cap of 3 additions.
2. Append the researcher's additions to the seed list table.
3. Write the P2 findings, one per candidate, with the hard-cut results and the limits.
4. Add a Production input for any limit the visualization tool choice (T033) must respect.
5. Apply the Gate.

### Step 3 — Validate P1 and P2

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** none, unless corrections are written (then `docs: correct s009 platform findings`)
- **R:** —

#### Scope

The owner's validation of the P1 and P2 findings. Corrections are written by Claude as new findings that name the finding they correct.

#### Reads

- This doc, Findings from Steps 1 and 2, and the official URLs they cite.

#### Check

The owner reports "OK" or a list of corrections, and every correction is written as a new finding: yes/no.

#### Do

1. Open the official URL of every discarded candidate and of every survivor.
2. Report back "OK" or, per finding, what is wrong and the source that shows it.

### Step 4 — P3: proposed scores and junction check

- **Status:** 💤 todo
- **Who:** Claude (web researcher for gaps)
- **Commit:** `docs: add s009 scores and junction check`
- **R:** —

#### Scope

Findings in this doc: a proposed score per weighted criterion for every P1 and P2 survivor, with a one-line justification against the anchors in Shared behaviour, plus the weighted total on a 0–10 scale; the junction check (Shared behaviour) for the pairs of the top 3 of each side, each pair with its expiry and its three operating modes (static, catch-up, live: possible or not, and start-up time); the ranked pairs; and the R2 Class A operation count for one hour of live mode as a percentage of the official free-tier limit, including the Worker's writes (Observe only).

#### Reads

- This doc, Findings from Steps 1–3: the survivors and their limits.
- This doc, Exit criteria › weighted criteria and Shared behaviour › junction check and scoring anchors.
- This doc, Questions › Q3: the three operating modes.
- ADR-0011: the Worker's capture rate, which sets its R2 writes.

#### Check

Every survivor has a score with justification for each applicable criterion and a total equal to (sum of score × weight) ÷ maximum possible × 10; every top pair has a junction result, its expiry and its three modes assessed: yes/no.

#### Do

1. Write the proposed score matrix for P1 and P2 survivors, with justifications and 0–10 totals.
2. List the pairs of the top 3 of each side; candidates tied at third place are all included.
3. Run the web researcher only for junction or operating-mode gaps the earlier findings do not cover, under the same evidence rule.
4. Write the junction findings per pair and the ranked pairs.
5. Run the web researcher for the official R2 free-tier Class A limit, and write, as percentages of that monthly limit, the Worker's Class A operations per month and the Class A operations per hour of live mode, plus the demo hours that fit in the remaining quota, stating the assumptions: one LIST per source per poll (each listing returns fewer than 1000 objects) and the Worker's write rate from ADR-0011.

### Step 5 — Validate or correct the scores

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** none, unless corrections are written (then `docs: correct s009 scores and junction check`)
- **R:** —

#### Scope

The owner's validation of the Step 4 findings: proposed scores, junction checks with their operating modes, and the R2 count. Corrections are written by Claude as new findings; corrected scores are marked as the owner's.

#### Reads

- This doc, the score matrix, the junction findings and the R2 count from Step 4.

#### Check

The owner reports "OK" or a list of corrections, the R2 count matches the owner's own arithmetic, and the totals are recomputed after any correction: yes/no.

#### Do

1. Check each junction and operating-mode finding against the source it cites.
2. Recompute the R2 count by hand from the limit, the live polling rate and the Worker's writes.
3. Review each score against its anchor and justification.
4. Report back "OK" or, per item, the corrected value and why.

### Step 6 — Conclusion

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: conclude spike s009`
- **R:** —

#### Scope

1. Conclusion in this doc: Observed window, Answers, Exit criteria, Verdict, Not verified, Follow-ups.
2. The destination of every Production input in this doc.
3. No README and no tear-down: the spike has no code and creates no accounts.
4. Sources in this doc: the official URLs cited in Findings, or the section removed if Findings already carry them all.
5. Status in this doc and the T022 row in `docs/tasks.md`.

#### Reads

1. This doc, Questions.
2. This doc, Method › Decision log.
3. This doc, Findings.

#### Check

Every Q is answered, every exit criterion has a result, and every Production input has a destination: yes/no.

#### Do

1. Write the Conclusion.
2. Set the destination of every Production input.
3. List in Follow-ups the ADR that supersedes ADR-0003, in MADR style (the ranked pairs as Considered Options), written in its own commit.
4. Fill or remove Sources.
5. Update Status in this doc and the T022 row in `docs/tasks.md`.

## 4. Findings

TODO: filled during the run.

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| | | | |

## 5. Conclusion

TODO: filled in the last step.

## Sources

- TODO: write during the run, or remove.
