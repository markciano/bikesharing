# Spike: Storage and table format

- **Task:** T035
- **ADRs:** ADR-0005, ADR-0009, ADR-0011
- **Code:** `spikes/storage-table-format/`

## Status

- State: Draft 📝
- Phase: [x] Questions · [x] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: Steps written; next: Steps approval, then `/spike s010 review-steps` in a new session

## 1. Questions — what we need to know

### Context

T035 decides where the medallion layers (ADR-0018) live, their table format, their retention and their security baseline, and whether capture (ADR-0011) stays as it is. These decisions were taken by analysis while framing the spike (D1–D7, below). The run only provides the evidence that D2 (R2 within quotas and budget) and D4 (Delta Lake works on R2) depend on. T036 (engine), T039 (capture in production) and T042 build on the outcome.

The owner runs capture always on and the pipeline on demand: it can stay off for days, catch up on what is pending before a demo, and run live during it (d002).

### Decided at framing

Decisions taken by analysis while framing the spike, without a run. The ADRs are written at Conclusion unless decided otherwise per case.

#### D1. Own lakehouse on object storage

Every medallion layer (ADR-0018) is stored as files in open formats in an object store, and compute runs separately from storage.

- Rejected: silver and gold in a managed analytics platform (warehouse), because it ties storage to that platform's engine and free quotas, and merges this decision with the engine choice (T036).

#### D2. Cloudflare R2 is the object store for every layer, subject to the volume and operations calculation

- Capture already lands in R2 (ADR-0011), so bronze needs no move and capture stays as it is.
- R2 charges no egress, so the pipeline can run anywhere (T036) without paying to read its data.
- Storage above the free 10 GB-month costs about $0.015/GB-month: even 50 GB stays well under the project's €10/month (d002 R4).
- The open risk is operations, not storage: the pipeline's listings, reads and writes add to capture's ~270–300k Class A per month (`raw/`, `logs/`, `state/`; estimate, measured by [probe B](#b-measured-volume)) against the free 1M. A Q verifies it; R2 is compared with another store only if it fails a hard constraint.
- Rejected: comparing another store (e.g. Backblaze B2) from the start, because no constraint currently argues against R2.

#### D3. Bronze is the captured `json.gz` objects as they are

No bronze table is built from them. The Bicing history archives (d002 R5) are bronze too: stored once, as downloaded (`.7z`), in the bronze bucket ([D7](#d7-storage-security-baseline)); their prefix and load procedure are set in the archive-load design.

| | Objects as captured (chosen) | Landing objects + bronze table |
|---|---|---|
| Storage | One copy of raw | Two copies, each with its retention |
| Fidelity (ADR-0006) | The origin's bytes | Payload kept, in another container |
| SQL over raw | Yes, slower: engines such as DuckDB read `json.gz` from R2 directly | Yes, fast |
| What has been processed | Watermark in silver over time-ordered keys | Given by the table |
| Capture metadata (feed, time, HTTP status) | Already in capture's own log (s005, s006) | Table columns |
| Pipeline steps | raw → silver | raw → bronze → silver |

- What the chosen option gives up is fast SQL over raw and built-in tracking of what has been processed; both have cheap substitutes.
- The deciding argument is reversibility: the `json.gz` objects are kept, so a bronze table can be built from them later at no loss if the pipeline design (T039) finds a reason. The bronze table pays a second copy and an extra step from day one. For a reversible decision, the simpler option is taken and complexity is deferred until needed (YAGNI).
- Rejected: landing zone plus a bronze table (the Databricks Auto Loader pattern), for the reasons above.

#### D4. Delta Lake is the table format for silver and gold, subject to the probe on R2

Chosen with a weighted decision matrix: hard cut first, then scores against anchors fixed before scoring. Facts gathered by the `web-researcher` on 2026-10-25 (Sources).

Hard cut: reads and writes from Python without JVM or cluster, and adds no paid service whose cost breaks the project's €10/month (d002 R4). All three candidates pass; Iceberg only conditionally, because its catalog options are Cloudflare Basin Catalog (formerly R2 Data Catalog; GA 2026-10-01; paid above 1M catalog operations per month) or a SQLite catalog the PyIceberg docs mark as test-only.

Anchors (2 and 4 are in between):

| Criterion (weight) | 1 | 3 | 5 |
|---|---|---|---|
| Portfolio value (5) | Not a table format | Recognised, but tied to one vendor's ecosystem | Standard backed by several major vendors |
| Python single-node maturity (4) | No MERGE/upsert, no atomic commits | Append, overwrite and upsert stable; maintenance (compaction, expiry) missing or experimental | All stable, maintenance included, in a release ≥ 1.0 |
| R2 fit (4) | Needs a service outside R2 that is unsupported or unaffordable | Works on R2 with an extra component (catalog, lock) or a method not documented for R2 | Works on R2 alone, with documented safe commits |
| Single-node engine support (3) | Neither Polars nor DuckDB reads it | Both read it; writing is missing in one or limited | Both read and write it natively and stably |
| Operational simplicity (3) | Needs a service to keep running | Needs a managed service or credentials beyond the bucket | Only the bucket and its credentials |
| Learning value (2) | No concept beyond files | One core concept (e.g. transaction log) | Several: log or snapshots, catalog, concurrency, maintenance |

Scores (total = Σ score × weight, maximum 105, normalised to 0–10):

| Criterion (weight) | Delta Lake (`deltalake`) | Apache Iceberg (`pyiceberg`) | Hive-partitioned Parquet |
|---|---|---|---|
| Portfolio value (5) | 4: widely adopted; born at Databricks, now in the Linux Foundation | 5: backed by Databricks, Snowflake, AWS S3 Tables and Cloudflare | 1: not a table format |
| Python maturity (4) | 5: 1.x with MERGE, optimize and vacuum | 3: upsert since 0.9; compaction documented as planned; below 1.0 | 1: no MERGE, no atomic commits |
| R2 fit (4) | 4: no extra component; R2 and the `object_store` crate document conditional put, but delta-rs does not document R2 | 3: needs a catalog (Basin, paid above quota, or test-only SQLite); direct metadata scanning reads without a catalog but cannot commit | 4: R2 alone, but no atomic commits |
| Engine support (3) | 4: Polars reads and writes; DuckDB writes INSERT only (no MERGE) | 3: Polars writing marked unstable; DuckDB writes only through a REST catalog | 5: native in both |
| Operational simplicity (3) | 5: only the bucket | 3: managed catalog and tokens | 5: only the bucket |
| Learning value (2) | 4: transaction log, optimistic concurrency, maintenance | 5: snapshots, manifests, catalog, REST spec | 2: partitioning only |
| **Total** | **91 → 8.7** | **77 → 7.3** | **59 → 5.6** |

- Reading: Delta wins on maturity and simplicity. Iceberg leads on portfolio value but loses on three criteria through its dependence on a catalog. Parquet is the baseline that shows what a table format adds.
- Delta on R2 is not confirmed end to end: no official delta-rs document covers R2, and an old issue reported a write error. A probe verifies it before the decision is final; only the winner is probed.
- Gate: if Delta fails to write, MERGE or keep concurrent commits safe on R2, Iceberg becomes the candidate, it is probed in turn, and the Basin Catalog cost enters the R2 calculation. Failures in maintenance or engine reads do not reject Delta; they are recorded as limitations.
- Rejected: Iceberg (second, see above) and Hive-partitioned Parquet (no MERGE or atomic rebuild, which silver deduplication and d002 R13 need).

#### D5. Bronze is kept indefinitely, reviewed only above a cost threshold

- Silver and gold are rebuilt from bronze (d002 R13), so whatever is deleted from bronze can never be rebuilt.
- The longest gold windows are 12 months (Q3, Q4, Q6, Q7), and Q8 covers changes since the earliest archive loaded.
- Raw grows about 2.7 GB per month, about 33 GB per year (measured 2026-10-14 to 2026-10-24, `architecture.md` §3); above the free 10 GB it costs about $0.015/GB-month, under $0.40/month at month 12.
- Review trigger: the total monthly R2 bill above €2 ([Exit criteria](#exit-criteria)), watched by the owner with a Cloudflare billing alert. The review covers the retention of D5 and D6 and the operations, not bronze alone, since the excess can come from any of them.
- TODO (production design): recalibrate the Cloudflare alerts (budget, Class A, storage) with Q1's figures; consider managing them through the API and updating them monthly, alerting on growth rate or projected cost rather than fixed values.
- Rejected: a rolling window of 12 months plus a margin, because no rule change could then be applied to older data, and Q8 would depend on what silver kept.

#### D6. Silver keeps a rolling 12 months, gold is kept indefinitely, and Delta keeps 7 days of history

- Silver holds bronze's observations as a table: parsed, deduplicated, typed, in UTC and on the common model (ADR-0008); gold holds hourly and daily aggregates.
- Both are rebuildable from bronze (D5), so their retention trades storage against rebuild cost, with no data at risk.
- Silver covers the longest gold window (12 months), so gold is recomputed without re-parsing bronze; older silver is rebuilt from bronze if ever needed.
- Gold is small and is what the public sees.
- Seven days of Delta history is enough to undo a recent error. It is Delta's default retention for vacuum, which removes old file versions only when the pipeline runs it (delta-rs does not run it on its own); the transaction log is kept 30 days by default.
- This is the usual decreasing retention: bronze longest, silver shorter, gold by its use.
- Rejected: keeping every layer indefinitely; simpler, since no silver partitions are deleted, but silver grows without bound alongside bronze. It is reconsidered if the calculation shows it equally cheap.

#### D7. Storage security baseline

Security is treated explicitly, not left implicit: R2 holds the only copy of bronze, and its credentials give access to both the data and the bill. Threats are listed with STRIDE, and each control follows least privilege (NIST SP 800-53, AC-6).

| Threat | Impact | Control |
|---|---|---|
| Leaked credentials | An attacker deletes or overwrites data, or drives up cost with requests (denial of wallet) | One token per component, with only the access it needs; secrets in `.env`, never in code; bronze protected by a bucket lock |
| A pipeline bug writes to bronze | Bronze cannot be rebuilt (D5), so the damage is permanent | The pipeline has read-only access to the bronze bucket; only capture writes it, plus the one-off history upload |
| A bucket is made public by mistake | Anyone can list and read all data, and every read costs | Buckets stay private, which is R2's default; public access to gold only as T038 decides |

Two buckets, because R2 API tokens scope to whole buckets, not key prefixes ([R2 source card](../sources/r2-storage.md)), so a read-only bronze needs its own bucket:

- **bronze**: capture's existing bucket, with an indefinite bucket lock on the `raw/`, `logs/` and history archive prefixes that blocks deletes and overwrites. All three only receive new objects and none can be rebuilt; the logs attribute gaps to capture or provider (QS5). `state/` holds capture's working index, rewritten on every pass and rebuildable from `raw/`, so it stays unlocked;
- **lakehouse**: silver and gold together, since both have the same access pattern.

Access per component:

| Component | Bronze bucket | Lakehouse bucket |
|---|---|---|
| Capture | Read and write (R2 has no write-only token; capture reads `state/`) | None |
| Owner (one-off history upload) | Read and write | None |
| Pipeline | Read | Read and write |
| Visualization (T038) | None | Read |
| Spike probes | None | None; a separate test bucket only |

- R2 has no object versioning, so the bucket lock is the only guard against losing bronze. Only an Admin token can remove a lock rule; the owner keeps that token and uses it only for D5's cost review.
- TODO (T039): before the lock is enabled, confirm that capture writes each key under `raw/` and `logs/` once (ADR-0012 key layout); the lock would also block a capture retry that rewrites a key.
- TODO (production design): capture's existing bucket is named `bikesharing-capture-spike`; R2 cannot rename buckets, so a production name means copying `raw/` and `logs/` to a new bucket before the lock is enabled.
- [Probe A](#a-delta-on-r2) checks that its test token cannot read or write `bikesharing-capture-spike`, the only production bucket that exists yet, and whether a bucket lock blocks a delete made with an Object Read & Write token (the docs do not say).
- Rejected: one token with read and write on everything. It is simpler, but a single leak or pipeline bug puts bronze at risk.
- Rejected: one bucket per layer. It would let the visualization read gold alone, but T038 has not decided how gold is served; gold moves to its own bucket then if needed.

### Questions

Main question: does the own lakehouse on R2 with Delta Lake (D1–D7) hold within the project's €10/month budget (d002 R4) and R2's quotas?

#### Q1. Cost calculation

What storage per layer and how many Class A and Class B operations per month do capture and pipeline need in each scenario, with Delta's operations per commit measured in Q2 and the retention of D5 and D6; do they fit R2's free quotas, and what do they cost per month and accumulated at months 1, 2, 4, 6 and 12? Gate for D2.

- Scenarios, all with capture always on:
  - pipeline running 24/7 with a commit every 1, 5, 10, 30 and 60 minutes, and every 6 hours;
  - on-demand mode: a grid of catch-ups per month (4, 6, 8, 10) by hours of live use per month (0.5, 1, 2, 3), with live commits every minute, each cell adding both; the cell judged is 10 catch-ups + 2 h live.
- Cadences above 5 minutes do not meet the 5-minute freshness of d002 Q1. They show how cost falls as freshness is relaxed, an input for T039.
- In a catch-up, listing and reading the pending objects costs the same as processing them minute by minute; what falls is the number of commits.
- Month 1 includes the initial load: the history archives (d002 R5) and capture's backlog in `raw/` since capture started. Silver starts with the history inside its 12-month window.
- Capture volume is measured, not estimated, on a local copy of the production bucket (about 10 days of real capture): `raw/`, `logs/` and `state/`, each counted separately. s005's estimates are used only where nothing is measured.

#### Q2. Delta on R2

Against a real R2 bucket with `deltalake`:

- Does it write?
- Does it MERGE?
- Does it keep concurrent commits safe?
- Do optimize and vacuum work?
- Do Polars and DuckDB read the table?
- Gate for D4.

**Observe only:** the latency of a commit on R2, which counts against the 5-minute freshness of d002 Q1.

### Exit criteria

- **Standard:** hard constraints first, then a gate per question that confirms or reopens its decision (D2, D4). The choice between options was already made with a weighted decision matrix (D4) and is not repeated in the run.
- **Timebox:** one day of run. It ends when Q1–Q2 are answered or the day runs out; then the decision is taken on the evidence gathered and the gaps go to Not verified. If the D4 gate fails, half a day is added for the Iceberg probe, recorded in the Decision log.
- **Storage cost** — no month within 12 months costs more than €2 in R2 storage and operations, in the on-demand cell of 10 catch-ups + 2 h live (Q1) — hard cut. The 24/7 scenarios and the other cells are reported, not judged. €2 is 20% of d002 R4's €10/month, leaving the rest for engine, execution and visualization (T036–T038). The same €2, as the total monthly R2 bill, is the review trigger of D5.
- **D2 gate (Q1)** — a scenario fits when its total R2 cost (storage and operations) is at most €2 in every month up to 12; fitting R2's free quotas is reported, not judged. If the worst case (1-minute commits 24/7) fits, D2 holds without conditions; if only the on-demand mode fits, D2 holds with an operating constraint, recorded as a Production input; if neither fits, D2 is reopened — hard cut.
- **D4 gate (Q2)** — `deltalake` on R2 writes, MERGEs and keeps concurrent commits safe; if any fails, Iceberg becomes the candidate and is probed in turn — hard cut.
- **Maintenance and engine reads (Q2)** — optimize and vacuum work on R2, and Polars and DuckDB read the table; a failure is recorded as a limitation for T036 or a Production input, not a rejection of Delta — guide.
- One variant meeting the criteria is enough: D4 already ranked the alternatives.

### Out of scope

- The processing engine and where it runs (T036). The probe uses Polars and DuckDB only to check that they read the table, not to choose between them.
- The pipeline design, its cadence and how it tracks what has been processed, such as D3's watermark (T039). Q1 reports the cost of each cadence; it does not choose one.
- Table structure: partitioning, keys and schemas of silver and gold, set in each slice's design.
- Performance at scale: the probe uses a sample.
- A bronze table over the `json.gz` objects: rejected by D3, reversible if T039 finds a reason.
- Managed analytics platforms (warehouses): rejected by D1.
- Reads of gold by the visualization: each read that reaches R2 is a Class B operation, and how gold is served is decided in T038. Input for T038: a public page lets anyone trigger reads, so cost can be driven up on purpose (denial of wallet); security is a vector T038 must treat explicitly.
- R2 Infrequent Access storage class for old bronze: cheaper storage, but a 30-day minimum and a per-GB retrieval fee that every rebuild would pay. A possible later optimisation.

## 2. Method — how we find out

### Approach

Three probes run in order A, B, C. A goes first because it tests the riskiest assumption (D4) and its result changes C: if Delta fails on R2, Iceberg is probed in turn and Basin Catalog's cost enters the model.

| Probe | Answers | Feeds |
|---|---|---|
| A. Delta on R2 | Q2 (D4 gate); commit latency (observed) | Measured operations per commit, Parquet bytes per row, `_delta_log` and rewritten bytes → C |
| B. Measured volume | Inputs for Q1 | Storage and capture operations → C |
| C. Cost model | Q1 (D2 gate) | — |

#### A. Delta on R2

- **What:** `deltalake` against a test R2 bucket with a small data sample.
- **Data:** real `station_status` responses from both providers, a few hours from the local capture copy (`spikes/cloudflare-capture-spike/data/V4/raw/`), flattened to rows (station, time, bikes, docks). Commits mimic 1-minute runs, partitioned by day, so each commit touches one partition; MERGE runs on real keys (station + time).
- **Checks,** in the order of the D4 gate: write, MERGE, two concurrent commits (hard cut); optimize, vacuum, reads from Polars and DuckDB (guide). Commits are kept safe by R2's conditional put, with no external lock; the delta-rs option that enables it is checked in the step.
- **Measures:** the R2 operations per commit, by class (A, B); the latency of each commit; Parquet bytes per row in the written table, so C can size silver and gold; `_delta_log` bytes per commit and bytes rewritten by MERGE and optimize, so C can size Delta's overhead.
- **Security ([D7](#d7-storage-security-baseline)):** uses a token scoped to the test bucket and checks that it cannot read or write `bikesharing-capture-spike`, the only production bucket that exists yet; tries to delete and overwrite an object under a locked prefix of the test bucket with the Object Read & Write token.
- **Where it runs:** on the owner's Mac, against a test bucket in the production Cloudflare account, with an Object Read & Write token scoped to it. The owner creates the test bucket, the token and the lock rule in the console before the probe; the script only runs the checks.
- **Counting:** a local HTTPS-inspecting proxy (mitmproxy) between `deltalake` and R2 logs every request and classifies it by the [R2 source card](../sources/r2-storage.md); the test bucket's R2 metrics give a second, independent count. `deltalake` gets the proxy address and its certificate through `storage_options`, so requests reach R2 unchanged and their signatures stay valid; only the probe process trusts that certificate. The proxy covers the whole counted run, reads and token and lock checks included; C takes only the commit and maintenance checks from the logs, and requests to other buckets are filtered out ([#22](#decision-log)).
- **Evidence:**
  - the proxy logs one JSON line per request: UTC time, method, path, status, bytes, duration;
  - the probe logs each check's start, end, result (ok or error message) and commit latency;
  - an analysis script joins both logs by time window (checks run one after another) into operations per check, step and class;
  - logs and results go to an `output/` folder ignored by Git (ADR-0009); summary tables are copied into Findings.
- **Analysis checks:**
  - known arithmetic: an append of one file gives one data PUT and one log PUT;
  - independent count: the proxy's total for the test bucket against the bucket's R2 metrics for the day of the counted run, a dashboard day on which nothing else touches the bucket;
  - fault injection: one of two concurrent commits must conflict and retry.
- **Clean-up:** the owner removes the test lock rule, then deletes the bucket and the token; a locked bucket cannot be emptied, so the lock rule goes first.
- An Iceberg probe is not planned; it is built only if the D4 gate fails (Exit criteria).

#### B. Measured volume

- Runs on the owner's local copies, not the production bucket, so it spends no R2 operations:
  - `spikes/cloudflare-capture-spike/data/V4/`: about 10 days of the production bucket, with the same layout (`raw/`, `logs/`, `state/`);
  - `spikes/bicing-spike/historical-data/raw/`: the Bicing history archives (`.7z`, December 2025–September 2026, d002 R5).
- Measures:
  - `raw/`: objects, bytes and records per feed and day; for `station_status`, also distinct (`station_id`, `last_reported`) records, silver's dedup basis; the first and last days are dropped as incomplete;
  - `logs/` and `state/`: objects, bytes and writes per day, as capture's own Class A operations and storage;
  - history, per archive and type: size as `.7z` and uncompressed, and raw rows (an upper bound); for ESTACIONS (`station_status`), distinct (`station_id`, `last_reported`) rows and snapshots per day; for INFORMACIO (`station_information`), rows at one snapshot per day, the basis of C's daily static commits ([#21](#decision-log));
  - archives are read as a stream, not extracted to disk.
- Capture's operations are also checked against R2 metrics: the owner reads the daily Class A and Class B of `bikesharing-capture-spike` in the Cloudflare dashboard over days when only capture ran (PutObject alone if the dashboard breaks operations down). Manual downloads of the whole bucket show as Class B peaks and those days are excluded. The daily average × 30 checks the derived `state/` writes and D2's ~270–300k Class A per month; if they disagree, the metric prevails and the gap goes to Findings ([#24](#decision-log)).
- Writes one volumes file that C reads.
- s005's estimates are used only where nothing is measured.

#### C. Cost model

- **What:** a script that computes, for each scenario in Q1 (24/7 cadences and the on-demand grid) and for months 1, 2, 4, 6 and 12, storage per layer and Class A and Class B operations per month, and their monthly and accumulated cost against R2's free quotas and prices.
- **Inputs:** A's measured operations per commit, Parquet bytes per row, `_delta_log` bytes per commit and bytes rewritten by MERGE and optimize, B's volumes, the commit model below, and the retention of D5 and D6.
- **Commit model:**
  - silver has one table per feed type on the common model (9: 2 dynamic, 7 static); gold has one table per guiding question (8);
  - a table commits at most once per run, and only when it has new data;
  - in live and 24/7 runs, a gold table commits no more often than its question's freshness (`architecture.md` §1.1): Q1, Q2, Q5 every run; Q3, Q4, Q7 hourly; Q6, Q8 daily;
  - so in a 1-minute run only 5 tables commit: the 2 dynamic silver tables and gold Q1, Q2, Q5; static silver tables commit once a day, when their feed is captured (`architecture.md` §1.1);
  - a catch-up commits once per table and pending day;
  - the pipeline's LISTs on bronze are derived from ADR-0012's key layout: the provider, feed and day prefixes each run lists, at 1,000 keys per LIST page ([#23](#decision-log));
  - month 1 adds the initial load as one catch-up of the history archives and capture's backlog since capture started; the production start date is a parameter;
  - table counts and cadences are parameters.
- **Sizing:**
  - bronze: B's `raw/` and `logs/` growth plus the history archives as `.7z`;
  - silver: B's deduplicated records per day (raw records for feeds without a dedup basis) times A's Parquet bytes per row, so no compression ratio is assumed; raw records give an upper bound; it starts in month 1 with the history inside its 12-month window;
  - gold: stations (B) × time buckets (hours or days) × tables (parameter) × A's bytes per row, an upper bound by cardinality;
  - Delta overhead in silver and gold: A's `_delta_log` bytes per commit × 30 days of commits, plus the bytes rewritten by MERGE and optimize in 7 days ([D6](#d6-silver-keeps-a-rolling-12-months-gold-is-kept-indefinitely-and-delta-keeps-7-days-of-history)).
- **Output:** cost per layer as well as the total; capture's `logs/` and `state/` writes are reported apart from `raw/`, so their share of the quota is visible.
- **Runs** once, after A and B; parameters are kept apart from the logic so the model can be re-run with new inputs.
- **Prices, quotas and operation classes** come from the [R2 source card](../sources/r2-storage.md). Assumptions where the pricing page is silent:
  - the free tier is shared by every bucket in the account (pessimistic);
  - a conditional PutObject is Class A, ListObjectsV2 is Class A as ListObjects, and DeleteObjects is free as DeleteObject; A confirms them on the test bucket's metrics;
  - deletes (silver retention, vacuum) are free, so they add no cost.

### Decision log

| # | Applies to | Decision | Reason | Decided at |
|---|---|---|---|---|
| 1 | [Q1](#q1-cost-calculation) | On-demand mode is a grid of catch-ups by live hours; the hard cut is judged at 10 catch-ups + 2 h live | Catch-ups and live use vary independently; the judged cell is the owner's pessimistic expected use | Method |
| 2 | [Q1](#q1-cost-calculation) | The 24/7 scenarios are calculated and reported, not judged | The calculation is free; the cost curve as freshness is relaxed is an input for T039 | Method |
| 3 | [Cost model](#c-cost-model) | Commit model: tables commit only with new data, gold at its question's freshness | An incremental pipeline writes only tables with new data; table counts stay pessimistic | Method |
| 4 | [Cost model](#c-cost-model) | The cost model runs once, with measured operations per commit; the former Q3 is merged into Q1 | Measured data prevails over estimates; the pessimism lives in the scenarios | Method |
| 5 | [Probe A](#a-delta-on-r2) | Probe A counts operations with a local proxy, cross-checked against R2 metrics → #19 | Exact counts per commit and step; two independent counts check each other | Method |
| 6 | [Probe A](#a-delta-on-r2) | Probe A runs on the owner's Mac against a scoped test bucket in the production account → #20 | About 1,000 operations per run, under 1% of the quota; the scoped token isolates production ([D7](#d7-storage-security-baseline)) | Method |
| 7 | [Probe A](#a-delta-on-r2) | Probe A evidence is logged to files and checked by an analysis script | Evidence must be reproducible and checked, not read off the console | Method |
| 8 | [Probe A](#a-delta-on-r2) | Probe A writes real `station_status` data from the local capture copy | File sizes and MERGE keys match the real pipeline; synthetic data would invent both | Method |
| 9 | [Probe B](#b-measured-volume) | Probe B measures `raw/`, `logs/` and `state/` separately on the local copy, plus the Bicing history → #21 | The local copy mirrors the bucket and spends no operations; `logs/` and `state/` are capture writes too | Method |
| 10 | [Cost model](#c-cost-model) | Silver is sized from B's records and A's Parquet bytes per row → #16 | Two measurements replace an assumed compression ratio | Method |
| 11 | [D7](#d7-storage-security-baseline) | The bronze bucket lock covers `raw/` and `logs/`, not `state/` → #13 | `state/` is rewritten on every pass, so a lock would break capture | Method |
| 12 | [Q1](#q1-cost-calculation), [Exit criteria](#exit-criteria) | Q1 reports cost at months 2, 4, 6 and 12; the hard cut is €2 in any month, raised from €1 → #17 | €2 is 20% of d002 R4's €10/month for R2 storage and operations; the rest is left for T036–T038 | Method |
| 13 | [D3](#d3-bronze-is-the-captured-jsongz-objects-as-they-are), [D7](#d7-storage-security-baseline) | The Bicing history archives are bronze, kept as downloaded in the bronze bucket under the lock; extends #11 | Same principle as D3 and D5: the origin's bytes are kept, and what cannot be rebuilt is not deleted; Open Data BCN does not guarantee the archives stay published. SQL over the raw archives is given up: they are loaded once and queried in silver, and the `.7z` is about 40 times smaller than its contents | Method review |
| 14 | [D5](#d5-bronze-is-kept-indefinitely-reviewed-only-above-a-cost-threshold) | D5's review is triggered by the total monthly R2 bill above €2 and covers every retention and the operations | Bronze storage alone would take about 10 years to reach €2; the bill is what Cloudflare charges, and an alert can watch it | Method review |
| 15 | [Exit criteria](#exit-criteria) | A scenario fits the D2 gate when its total R2 cost is at most €2 in every month up to 12; free quotas are reported, not judged | One threshold for the gate and the cost cut; leaving the free tier is acceptable within budget | Method review |
| 16 | [Cost model](#c-cost-model) | C sizes gold by cardinality and adds Delta's overhead (log and rewritten files) from A's measures; extends #10 | Total storage leaves no layer out; measured data prevails over an assumed margin (#10) | Method review |
| 17 | [Q1](#q1-cost-calculation), [Cost model](#c-cost-model) | Month 1 includes the initial load (history and capture's backlog) and is judged like any other month; extends #12 | It is the most expensive month, and the bill does not separate one-off from recurring cost | Method review |
| 18 | [Probe A](#a-delta-on-r2) | Probe A keeps concurrent commits safe with R2's conditional put, with no external lock | It is what D4 scored (only the bucket); a DynamoDB lock adds an AWS service and would reopen D4 | Method review |
| 19 | [Probe A](#a-delta-on-r2) | The proxy is mitmproxy with HTTPS inspection, trusted by the probe process only; refines #5 → #22 | Requests are signed (SigV4) for R2's host, so a plain reverse proxy breaks them; mitmproxy is the standard HTTP inspection tool and needs no signing code | Method review |
| 20 | [Probe A](#a-delta-on-r2) | The owner creates and removes the test bucket, token and lock rule in the console; the script only runs the checks; refines #6 | Operational actions are the owner's (CLAUDE.md), and the script never holds an admin credential | Method review |
| 21 | [Probe B](#b-measured-volume) | B counts history rows per archive type, with the same dedup basis as capture's `station_status` (`station_id`, `last_reported`); INFORMACIO at one snapshot per day; raw rows kept as an upper bound; extends #9 | C sizes silver in rows (#10) and month 1 holds the history (#17); deduplicated rows are what silver stores, and both sources are counted on the same basis | Steps |
| 22 | [Probe A](#a-delta-on-r2) | The proxy covers the whole counted run, `extra` included; the independent count compares totals for the test bucket on a dashboard day that only step 5 uses; C takes only the commit and maintenance checks, and requests to other buckets are filtered out; refines #5, #19 | The test bucket receives only the probe's requests, so a daily total needs no narrower window | Steps |
| 23 | [Cost model](#c-cost-model) | The pipeline's LISTs on bronze are derived from ADR-0012's key layout (prefixes per provider, feed and day per run; 1,000 keys per page), not set by hand | They are probably the largest Class A item (about 430k a month for 10 prefixes every minute), so they are derived, not guessed | Steps |
| 24 | [Probe B](#b-measured-volume) | Capture's daily Class A and B from the dashboard, on capture-only days, check B's derived `state/` writes and D2's ~270–300k Class A; the metric prevails | Measured data prevails over derived counts | Steps |
| 25 | [File layout](#file-layout) | `output/` is ignored by a `.gitignore` in the spike folder | The spike stays self-contained and the root file is not touched | Steps |

### File layout

```text
spikes/storage-table-format/
├── README.md          Question, setup, commands, what each script does; link to s010; How we got here (written at Conclusion)
├── .gitignore         Ignores output/ (ADR-0009)
├── pyproject.toml     Pinned Python and locked dependencies (ADR-0016, ADR-0017)
├── uv.lock
├── .env.example       Test bucket endpoint and scoped token, empty values
├── r2_proxy.py        A: mitmproxy addon that logs each deltalake request to R2, one JSON line per request
├── delta_probe.py     A: write, MERGE, concurrency, optimize, vacuum, reads, token and lock checks
├── analyse_ops.py     A: joins proxy and probe logs; operations per check, step and class; the three checks
├── measure_volume.py  B: raw/, logs/, state/ and history volumes
├── cost_model.py      C: scenarios × months, cost per layer and total
├── params.toml        C: every parameter (tables, cadences, retention, prices), apart from the logic
└── output/            Ignored by Git (ADR-0009): logs, volumes, operation and cost tables
```

## 3. Steps

The cheapest test of the riskiest assumption runs first: steps 2–3 check the D4 gate on R2 without instrumentation, before counting is built on it (steps 4–5). Paths in the steps are relative to `spikes/storage-table-format/` unless they start at the repository root.

| # | Title | Who | Gate | Files |
|---|---|---|---|---|
| 1 | Scaffold the spike folder | Claude | — | `README.md`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore` |
| 2 | Write the Delta gate checks | Claude | — | `delta_probe.py` (write, MERGE, concurrent commits) |
| 3 | Set up the test bucket and run the gate checks | Owner | D4 hard cut | `.env` (local) |
| 4 | Add counting and the remaining checks | Claude | — | `r2_proxy.py`, `delta_probe.py`, `analyse_ops.py` |
| 5 | Run probe A and verify the analysis | Owner | Analysis checks | `output/` |
| 6 | Write the volume measurement | Claude | — | `measure_volume.py` |
| 7 | Run probe B and verify volumes | Owner | — | `output/` |
| 8 | Write the cost model | Claude | — | `cost_model.py`, `params.toml` |
| 9 | Run probe C and verify the model | Owner | D2 gate | `output/` |
| 10 | Write the ADRs | Claude | — | `docs/decisions/` |
| 11 | Conclusion | Claude, Owner (teardown) | — | this document, `README.md`; test lock rule, bucket and token |

### Step 1 — Scaffold the spike folder

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: scaffold storage and table format spike`
- **Model:** sonnet · medium
- **Gate:** —

#### Scope

- `README.md`: the question (s010 Main question), a link to this document, setup (`uv sync --locked`, `.env` from `.env.example`) and a Commands section that later steps fill.
- `pyproject.toml` and `uv.lock`: Python pinned in `requires-python`; dependencies `deltalake` (≥ 1.0), `polars`, `duckdb`, `boto3`, `mitmproxy`, `python-dotenv`.
- `.env.example`, empty values: `R2_ACCOUNT_ID`, `R2_TEST_BUCKET`, `R2_TEST_ACCESS_KEY_ID`, `R2_TEST_SECRET_ACCESS_KEY`, `R2_PROD_BUCKET`, `R2_LOCKED_PREFIX`.
- `.gitignore`: ignores `output/` (ADR-0009, #25).
- Not touched: anything outside these files.

#### Reads

- This document, §2 File layout: the folder's files and their purpose.
- `.claude/rules/code/spikes.md`: what a spike README holds.

#### Do

1. Create `pyproject.toml` with `uv init --bare` and add the dependencies with `uv add`, which writes `uv.lock`.
2. Write `.env.example`.
3. Write `README.md`.
4. Write `.gitignore`.
5. Update this step's Status.

#### Check

- `uv sync --locked` succeeds and `uv run python -c "import deltalake, polars, duckdb, boto3; print(deltalake.__version__)"` prints a version ≥ 1.0.
- `git check-ignore spikes/storage-table-format/output/x` prints the path.

### Step 2 — Write the Delta gate checks

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: add delta gate checks to storage spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

`delta_probe.py`, subcommand `gate`, with a `--local` option that runs against a temporary local table instead of R2:

- **Sample:** `station_status` objects of both providers from `spikes/cloudflare-capture-spike/data/V4/raw/<provider>/station_status/<day>/<UTC time>.json.gz`, for a window given by parameters (default: the first 15 captured minutes of a full day). Each object becomes rows `source`, `station_id`, `last_reported` (UTC), `captured_at` (UTC, from the key), `bikes_available`, `docks_available`, `capture_date` (partition column). The two providers may use different GBFS versions; the field mapping handles both.
- **Table:** `s3://<R2_TEST_BUCKET>/<run_id>/station_status`, with `run_id` the run's UTC start time, so each run writes a fresh table.
- **Storage options:** endpoint from `R2_ACCOUNT_ID`, region `auto`, the test token, and the option that enables conditional put for safe commits with no external lock (decision log #18).
- **Checks,** each logged as one JSON line in `output/probe-<run_id>.jsonl` (UTC start and end, check, result `ok` or the error message, table version, commit latency in ms):
  - `write`: creates the table and appends one commit per captured minute (10 by default). Ok when the version count equals the commits and the row count equals the rows written.
  - `merge`: 3 MERGE commits with the following minutes, keyed on `source`, `station_id`, `last_reported` (update when matched, insert otherwise). Ok when no key is duplicated and the row count equals the distinct keys.
  - `concurrent`: fault injection by stale writers. Two handles are opened at the same version; one commits, then the other commits on its stale snapshot. For two appends, both land on consecutive versions with no row lost (compatible commits are retried). For two MERGEs that touch the same partition, the second fails with a commit conflict and the table holds the first one's result. Ok when both behave like this.
- The run stops at the first failed check and prints a summary table.

#### Reads

- This document, Q2, D4 (gate paragraph) and §2 A: what the gate requires and how it is checked.
- delta-rs documentation on writing to S3-compatible stores and concurrent writes, through the `web-researcher`: the option that enables conditional put on R2, and the exception raised on a commit conflict.
- One `station_status` sample per provider in the local copy: the field names of each GBFS version.

#### Do

1. Write the sample loader and the row mapping.
2. Write the three checks and the JSON-lines log.
3. Run `uv run python delta_probe.py gate --local`.
4. Update the README Commands section and this step's Status.

#### Check

`uv run python delta_probe.py gate --local` reports `ok` for `write`, `merge` and `concurrent`, and makes no request to R2.

### Step 3 — Set up the test bucket and run the gate checks

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: record delta gate result in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** write, MERGE and concurrent commits pass (D4 hard cut) → otherwise the run stops, and probe A and the cost model are re-planned for Iceberg

#### Scope

The test bucket, its lock rule and its token in the production Cloudflare account (decision log #20); the local `.env` (ignored by Git); the first findings.

#### Reads

- `README.md`: setup and the `gate` command.

#### Do

1. In the Cloudflare console, create the private R2 bucket `bikesharing-s010-test`.
2. Add a bucket lock rule on the prefix `locked/`, with indefinite retention.
3. Create an R2 API token with Object Read & Write, scoped to `bikesharing-s010-test` only.
4. Copy `.env.example` to `.env` and fill it: account ID, bucket, the token's access key ID and secret, `R2_PROD_BUCKET=bikesharing-capture-spike`, `R2_LOCKED_PREFIX=locked/`.
5. Run `uv run python delta_probe.py gate`.
6. Report the summary table and the `run_id`.

#### Check

The summary shows `ok` for `write`, `merge` and `concurrent` → the D4 gate holds. Claude records the result and commit latencies as findings.

### Step 4 — Add counting and the remaining checks

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: add request counting and remaining checks to storage spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

- `r2_proxy.py`: mitmproxy addon (decision log #19). Logs every request to `output/proxy-<UTC start>.jsonl`, one JSON line each: UTC time, bucket, method, path, query, status, request and response bytes, duration, and the operation and its class (A, B or free) as classified by the [R2 source card](../sources/r2-storage.md).
- `delta_probe.py`:
  - subcommand `full`, through the proxy: `write` (60 commits, one hour), `merge` (10 commits), `concurrent`, `optimize` (compaction), `vacuum` (a dry run with the 7-day default, then a run with zero retention and the retention check disabled, so the probe sees files deleted). Every client (`deltalake`, Polars, DuckDB, `boto3`) reaches the proxy through its own settings (proxy URL and the mitmproxy CA certificate), so only the probe process trusts it;
  - per check it also logs Parquet bytes per row, `_delta_log` bytes per commit, and bytes rewritten by MERGE and optimize;
  - subcommand `extra`, run after `full`, also through the proxy (#22): Polars and DuckDB read the table and match its row count (guide); the test token cannot list, read or write `R2_PROD_BUCKET` (a write attempt uses the key `s010-token-check/canary.txt`, so a wrongful success is harmless and easy to remove); under `R2_LOCKED_PREFIX`, a new object is written and then an overwrite and a delete of it are attempted with the test token.
- `analyse_ops.py`: joins the proxy log and the probe log by time window; writes operations per check, per commit and per class to `output/`, for the test bucket only (requests to other buckets are filtered out by bucket); marks the `full` checks as the ones C takes; flags any check with no proxied request, as its client bypassed the proxy; runs the three analysis checks of §2 A:
  - known arithmetic: one append of one file gives one data PUT and one log PUT;
  - independent count: the proxy's totals per class for the whole run equal the test bucket's R2 metrics for that day, passed as arguments;
  - fault injection: the `concurrent` check shows a rejected log PUT (HTTP 412) followed by a successful retry.
- Not touched: the `gate` subcommand's behaviour.

#### Reads

- This document, §2 A (Measures, Security, Counting, Evidence, Analysis checks).
- [R2 source card](../sources/r2-storage.md): operation classes, for the classifier.
- mitmproxy addon API, and the proxy and CA certificate settings of each client (`object_store` for `deltalake` and Polars, DuckDB's delta extension, `boto3`), through the `web-researcher`. A client with no such setting is reported before step 5; its check then runs on another day, uncounted.

#### Do

1. Write `r2_proxy.py`.
2. Extend `delta_probe.py` with `full` and `extra`.
3. Write `analyse_ops.py`, with a small synthetic pair of logs to check its counts.
4. Run `uv run python delta_probe.py full --local` and `analyse_ops.py` on the synthetic logs.
5. Update the README Commands section and this step's Status.

#### Check

- `uv run python delta_probe.py full --local` reports `ok` for every counted check.
- `analyse_ops.py` on the synthetic logs gives the expected counts per check and class.

### Step 5 — Run probe A and verify the analysis

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: record probe a results in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** the three analysis checks pass → otherwise the scripts are fixed and the probe is run again

#### Scope

A counted run of probe A on the test bucket; operation, size and latency tables in `output/`; findings for Q2 and for the cost model's inputs.

#### Reads

- `README.md`: the `full`, `extra` and `analyse_ops.py` commands.

#### Do

1. Pick a day of the Cloudflare dashboard on which only this step touches the test bucket: not step 3's day, and no other run that day.
2. Start the proxy in one terminal: `uv run mitmdump -s r2_proxy.py --listen-port 8080`.
3. In another terminal, run `uv run python delta_probe.py full`, then `uv run python delta_probe.py extra`.
4. Stop the proxy.
5. Once the day is over, read the test bucket's Class A and Class B operations for that day in the Cloudflare dashboard.
6. Run `uv run python analyse_ops.py --r2-class-a <A> --r2-class-b <B>`.
7. Report both probe summaries, the analysis summary and the R2 figures.

#### Check

The three analysis checks pass and no check is flagged as bypassing the proxy. Claude records as findings: operations per commit by class, commit latency, Parquet bytes per row, `_delta_log` bytes per commit, rewritten bytes, the maintenance and read results (guide) and the token and lock results.

### Step 6 — Write the volume measurement

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: add volume measurement to storage spike`
- **Model:** sonnet · high
- **Gate:** —

#### Scope

`measure_volume.py`, which writes `output/volumes.json` (the file C reads) and prints a summary:

- **`raw/`** (`spikes/cloudflare-capture-spike/data/V4/raw/`), per provider, feed and day: objects, bytes and records (entries in the payload's main list; 1 for feeds without one). For `station_status`, also distinct (`station_id`, `last_reported`) records. The first and last days are dropped as incomplete.
- **`logs/` and `state/`**, per day: objects, bytes and writes. `logs/` writes are its objects. `state/` keeps only its latest version locally, so its writes per day are derived: capture passes per day (from `logs/`) times the `state/` objects one pass writes (from capture's code).
- **History** (`spikes/bicing-spike/historical-data/raw/*.7z`), per archive: type (ESTACIONS or INFORMACIO, from the file name), month, `.7z` bytes, uncompressed bytes and raw rows. For ESTACIONS, also distinct (`station_id`, `last_reported`) rows and snapshots per day. For INFORMACIO, rows at one snapshot per day (#21).
- Archives are streamed with macOS's built-in `tar -xOf <archive>` (libarchive reads 7z), never extracted to disk. Rows are counted with a CSV parser on that stream, not by lines (header, quoted newlines).
- Not touched: the local copies, which are only read.

#### Reads

- This document, §2 B and decision log #21: what is measured and on which basis.
- Capture's code in `spikes/cloudflare-capture-spike/js/`, the part that writes `state/` and `logs/`: objects written per pass.
- The header of one extracted CSV per archive type (the July–September 2026 CSVs under `spikes/bicing-spike/historical-data/`; find them by listing): the column names for the station, `last_reported` and the snapshot time.

#### Do

1. Write the `raw/`, `logs/` and `state/` measurements.
2. Write the history measurement.
3. Write a targeted check of the counting: a small hand-made sample with known raw and distinct counts, including a quoted newline.
4. Run the targeted check and the 2026-09 ESTACIONS archive alone.
5. Update the README Commands section and this step's Status.

#### Check

- The targeted check gives the expected raw and distinct counts.
- The 2026-09 ESTACIONS archive gives the same raw rows as its extracted `.csv` parsed the same way (reference: 4,528,266 lines including the header, 290,689,605 bytes uncompressed).

### Step 7 — Run probe B and verify volumes

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: record probe b volumes in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** —

#### Scope

A full run of `measure_volume.py`; `output/volumes.json`; findings for the cost model's inputs.

#### Reads

- `README.md`: the `measure_volume.py` command.

#### Do

1. Run `uv run python measure_volume.py`.
2. Spot-check one provider, feed and day: `find <day folder> -type f | wc -l` and `du -sk <day folder>` against the summary's objects and bytes.
3. In the Cloudflare dashboard, read the daily Class A and Class B operations of `bikesharing-capture-spike` (PutObject alone if the dashboard breaks operations down) over the longest span of days on which only capture ran; days of manual bucket downloads show as Class B peaks and are excluded (#24).
4. Report the summary, the spot check and the daily figures with their dates.

#### Check

- The spot check matches the summary.
- Claude compares the dashboard's daily average × 30 with B's capture writes (`raw/`, `logs/` and the derived `state/` writes) and with D2's ~270–300k Class A per month; if they disagree, the metric prevails and the gap goes to Findings.
- `raw/` growth per day is consistent with the ~2.7 GB per month measured in `architecture.md` §3; a large gap is explained before C runs.
- Claude records as findings: volumes per feed and day, `logs/` and `state/` writes per day, history rows per type, and the dedup ratio of both sources.

### Step 8 — Write the cost model

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `chore: add cost model to storage spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

- `params.toml`, every parameter apart from the logic:
  - tables (9 silver: 2 dynamic, 7 static; 8 gold) and each gold question's freshness (§2 C commit model);
  - scenarios: 24/7 commits every 1, 5, 10, 30 and 60 minutes and every 6 hours; the on-demand grid of 4, 6, 8 and 10 catch-ups by 0.5, 1, 2 and 3 live hours; the judged cell (10 catch-ups + 2 h);
  - months reported (1, 2, 4, 6, 12), capture start date and production start date;
  - retention (D5, D6): bronze and gold indefinite, silver 12 months, 7 days of Delta history, 30 days of log;
  - maintenance: optimize and vacuum runs per table and pipeline day;
  - an optional override of capture's monthly Class A and B with step 7's dashboard figures (#24);
  - prices and free quotas from the [R2 source card](../sources/r2-storage.md), and the USD→EUR rate with its date, since prices are in USD and the threshold in EUR;
  - paths to A's operation tables and B's `volumes.json`.
- `cost_model.py`: for each scenario and month, storage per layer (bronze, silver, gold, Delta overhead) and Class A and B operations, split into capture `raw/`, capture `logs/` and `state/`, and pipeline. It computes monthly and accumulated cost against the shared free quotas, with month 1 including the initial load (#17). It writes `output/cost_*.csv` and a summary, and marks per scenario whether it fits the D2 gate (at most €2 in every month up to 12).
- The pipeline's LISTs on bronze are derived from ADR-0012's key layout: the provider, feed and day prefixes each run lists, at 1,000 keys per LIST page (#23).
- Silver and gold commits are costed with A's measured MERGE commit (the more expensive one measured), so the model stays pessimistic.
- Not touched: A's and B's outputs, which are only read.

#### Reads

- This document, Q1, Exit criteria and §2 C: scenarios, commit model, sizing and assumptions.
- [R2 source card](../sources/r2-storage.md): prices, free quotas and operation classes.
- `architecture.md` §1.1: each guiding question's freshness and the static feeds' daily capture.
- ADR-0012 (`docs/decisions/`), the key layout: the prefixes a pipeline run lists.

#### Do

1. Write `params.toml`.
2. Write `cost_model.py`.
3. Write a targeted check: a minimal parameter set and inputs for which one scenario and month are computed by hand.
4. Run the targeted check.
5. Update the README Commands section and this step's Status.

#### Check

The targeted check matches the hand computation for storage, Class A (bronze LISTs included), Class B and cost.

### Step 9 — Run probe C and verify the model

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: record cost model results in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** the judged on-demand cell (10 catch-ups + 2 h live) costs at most €2 in every month up to 12 (D2 gate, hard cut) → otherwise D2 is reopened. If 1-minute commits 24/7 also fit, D2 holds without conditions; if not, it holds with an operating constraint, recorded as a Production input.

#### Scope

A full run of the cost model on A's and B's outputs; `output/cost_*.csv`; the findings that answer Q1.

#### Reads

- `README.md`: the `cost_model.py` command.

#### Do

1. Check that `params.toml` points to the outputs of steps 5 and 7, set the production start date and the USD→EUR rate, and set the capture override if step 7 found a gap.
2. Run `uv run python cost_model.py`.
3. Recompute by hand, from the CSV and `params.toml`, the Class A operations of the judged cell in month 1.
4. Report the summary and the hand recomputation.

#### Check

- The hand recomputation matches the CSV.
- Claude records as findings: cost per layer and total per scenario and month, the free quota usage, the judged cell and the 1-minute 24/7 case, and applies the gate.

### Step 10 — Write the ADRs

- **Status:** 💤 todo
- **Who:** Claude
- **Commit:** `docs: record storage and table format decisions as adrs`
- **Model:** opus · high
- **Gate:** —

#### Scope

- The ADRs for the decisions D1–D7 that hold after the gates, in `docs/decisions/` (§1 Decided at framing), each with its reason and the findings that confirm it. Whether they go in one step or two is decided at the Steps review.
- Not touched: the Conclusion, written in step 11.

#### Reads

1. This document, §1 Decided at framing: D1–D7.
2. This document, §4 Findings: the evidence for D2 and D4.
3. One existing ADR in `docs/decisions/`: format and numbering.

#### Do

1. Write one ADR per decision that holds.
2. Update this step's Status.

#### Check

Every decision D1–D7 that holds has an ADR, and the D2 and D4 ADRs cite their findings.

### Step 11 — Conclusion

- **Status:** 💤 todo
- **Who:** Claude, Owner (teardown)
- **Commit:** `docs: conclude spike s010`
- **Model:** opus · high
- **Gate:** —

#### Scope

- This document: Conclusion (Answers, Exit criteria, Verdict, Not verified, Follow-ups), the destination of every Production input, and Status.
- `README.md`: How we got here.
- Teardown by the owner: the test lock rule, the bucket `bikesharing-s010-test` and its token; the canary `s010-token-check/canary.txt` in `bikesharing-capture-spike` if the token check created it.

#### Reads

1. This document, §1 Questions and Exit criteria.
2. This document, §2 Decision log.
3. This document, §4 Findings and Production inputs.

#### Do

1. Write the Conclusion.
2. Set the destination of every Production input: a design with its task, or discarded with a reason.
3. Write How we got here in `README.md`.
4. Owner: remove the test lock rule, then empty and delete the test bucket, delete the token, and delete the canary if it exists.
5. Set Status to finished with the UTC date.

#### Check

- Every Q is answered, every exit criterion has a result and every Production input has a destination.
- The Cloudflare console lists neither the test bucket nor its token.

## 4. Findings

**F1. `<one-line statement>`** (step N, YYYY-MM-DD, `<source of evidence>`)

- `<evidence>`
- Consequence: `<for variants, steps or questions>`

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | | Step N · FN | |

## 5. Conclusion

Observed window: `<from–to, UTC; what it does not cover>`

### Answers

- **Q1.** `<answer>` (FN)

### Exit criteria

| Criterion | `<Variant A>` | `<Variant B>` |
|---|---|---|
| | | |

### Verdict

### Not verified

- `<item>` — `<risk>` — `<mitigation>`

### Follow-ups

- `<ADR or task>`

## Sources

R2 prices, quotas and operation classes: [R2 source card](../sources/r2-storage.md) (`web-researcher`, 2026-10-26).

Gathered by the `web-researcher` on 2026-10-25 for D4:

- delta-rs releases: <https://github.com/delta-io/delta-rs/releases>
- delta-rs on S3, commit safety: <https://raw.githubusercontent.com/delta-io/delta-rs/main/docs/integrations/object-storage/s3.md>
- `object_store` conditional put: <https://docs.tvix.dev/rust/object_store/aws/enum.S3ConditionalPut.html>
- PyIceberg docs and releases: <https://py.iceberg.apache.org/>, <https://py.iceberg.apache.org/api/>, <https://github.com/apache/iceberg-python/releases>
- Cloudflare Basin Catalog changelog and pricing: <https://developers.cloudflare.com/changelog/product/basin/>, <https://developers.cloudflare.com/basin-catalog/platform/pricing/>
- R2 S3 API (conditional PutObject): <https://developers.cloudflare.com/r2/api/s3/api/>
- Polars Delta and Iceberg support: <https://pola.rs/posts/polars-in-aggregate-apr26>, <https://docs.pola.rs/api/python/stable/reference/api/polars.LazyFrame.sink_iceberg.html>
- DuckDB Delta and Iceberg: <https://duckdb.org/2026/05/07/delta-uc-updates>, <https://duckdb.org/docs/2.0/core_extensions/iceberg/overview.html>, <https://duckdb.org/2025/11/28/iceberg-writes-in-duckdb>
- Format adoption trend (vendor blog, directional): <https://risingwave.com/blog/apache-iceberg-vs-delta-lake-vs-hudi-2026/>
