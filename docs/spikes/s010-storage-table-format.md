# Spike: Storage and table format

- **Task:** T035
- **ADRs:** ADR-0005, ADR-0009, ADR-0011
- **Code:** `spikes/storage-table-format/`

## Status

- State: Running 🔄
- Phase: [x] Questions · [x] Method · [x] Steps · [x] Steps review
- Started: 2026-10-27 · Finished: —
- Current step: step 9 (Owner): run and hand check done (#48); sensitivity on 24/7 10 min and charts (#49), then findings and gate, pending

## 1. Questions — what we need to know

### Context

T035 decides where the medallion layers (ADR-0018) live, their table format, their retention and their security baseline, and whether capture (ADR-0011) stays as it is. These decisions were taken by analysis while framing the spike (D1–D7, below). The run only provides the evidence that D2 (R2 within quotas and budget) and D4 (Delta Lake works on R2) depend on. T036 (engine), T039 (capture in production) and T042 build on the outcome.

The owner runs capture always on and the pipeline on demand: it can stay off for days, catch up on what is pending before a demo, and run live during it (d002).

### Decided at framing

Decisions taken by analysis while framing the spike, without a run. The ADRs and the matching `architecture.md` changes are written after the spike closes, in a fresh session, from the Conclusion's Decisions to record ([#26](#decision-log)).

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

What storage per layer and how many Class A and Class B operations per month do capture and pipeline need in each scenario, with Delta's operations per commit measured in Q2 and the retention of D5 and D6; do they fit R2's free quotas, and what do they cost per month and accumulated, computed for every month 1–12 and reported at months 1, 2, 4, 6 and 12? Gate for D2.

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
- **Timebox:** one day of run, counted as effort; waiting for step 5's counted dashboard day to end does not count. It ends when Q1–Q2 are answered or the day runs out; then the decision is taken on the evidence gathered and the gaps go to Not verified. If the D4 gate fails, half a day is added for the Iceberg probe, recorded in the Decision log.
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
- **Data:** real `station_status` responses from both providers, a few hours from the local capture copy (`spikes/cloudflare-capture-spike/data/V4/raw/`), flattened to rows (station, time, bikes, docks). Commits mimic 1-minute runs, partitioned by day, so each commit touches one partition; MERGE runs on real keys (station + time). Appended rows are deduplicated at load on silver's basis (`station_id`, `last_reported`; §2 B, [#21](#decision-log)), so the table holds unique keys; MERGE takes each minute's full rows ([#32](#decision-log)).
- **Checks,** in the order of the D4 gate: write, MERGE, two concurrent commits (hard cut); optimize, vacuum, reads from Polars and DuckDB (guide). Commits are kept safe by R2's conditional put, with no external lock; the delta-rs option that enables it is checked in the step.
- **Measures:** the R2 operations per commit, by class (A, B); the latency of each commit; Parquet bytes per row in the written table, so C can size silver and gold; `_delta_log` bytes per commit and bytes rewritten by MERGE and optimize, so C can size Delta's overhead. Each commit opens a fresh table handle, as a separate pipeline run would, so its operations include loading the table. The test table sets `delta.checkpointInterval = 10`, so checkpoints occur within the run. Per commit, the probe logs the JSON commits read since the last checkpoint, whether it wrote a checkpoint and, for MERGE, the files in the target partition ([#27](#decision-log)).
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
  - independent count: the proxy's total requests for the test bucket, failed ones included, within ±0.5% of the bucket's R2 metrics total over the counted run's UTC window, from the GraphQL Analytics API, with nothing else touching the bucket during the run ([#37, #39](#decision-log)); R2's metrics are sampled, so only the total is compared and the per-class counts come from the proxy ([F14](#4-findings));
  - fault injection: of two concurrent commits, the stale one is rejected and then retried or raises a conflict, with no key duplicated or row lost; and in each round of two clients racing a put-if-absent on one new key, R2 accepts exactly one and rejects the other, keeping the winner's body ([#40](#decision-log)).
- **Security outcome:** a failed token or lock check reopens D7 with the owner before the Conclusion.
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
- Capture's operations are also checked against R2 metrics: the owner queries the GraphQL Analytics API (`r2OperationsAdaptiveGroups`) for `bikesharing-capture-spike`, per UTC day, operation and status. PutObject is capture's writes; ListObjects and GetObject, which also come from the owner's downloads of the bucket, are reported apart ([#36](#decision-log)). The daily PutObject average × 30 checks the derived `state/` writes and D2's ~270–300k Class A per month; within ±10%, B's values are kept; beyond it, the metric prevails and the gap goes to Findings ([#24, #29](#decision-log)).
- Writes one volumes file that C reads.
- s005's estimates are used only where nothing is measured.

#### C. Cost model

- **What:** a script that computes, for each scenario in Q1 (24/7 cadences and the on-demand grid) and for every month from 1 to 12 (months 1, 2, 4, 6 and 12 reported; the gate judges each one, [#29](#decision-log)), storage per layer and Class A and Class B operations per month, and their monthly and accumulated cost against R2's free quotas and prices.
- **Inputs:** A's measured operations per commit, Parquet bytes per row, `_delta_log` bytes per commit and bytes rewritten by MERGE and optimize, B's volumes, the commit model below, and the retention of D5 and D6.
- **Commit model:**
  - silver has one table per feed type on the common model (9: 2 dynamic, 7 static); gold has one table per guiding question (8);
  - a table commits at most once per run, and only when it has new data;
  - in live and 24/7 runs, a gold table commits no more often than its question's freshness (`architecture.md` §1.1): Q1, Q2, Q5 every run; Q3, Q4, Q7 hourly; Q6, Q8 daily;
  - so in a 1-minute run only 5 tables commit: the 2 dynamic silver tables and gold Q1, Q2, Q5; static silver tables commit once a day, when their feed is captured (`architecture.md` §1.1);
  - a catch-up commits once per table and pending day;
  - a commit's operations are modelled from A's measures as table-load reads (per JSON commit since the last checkpoint), plus MERGE reads per file in the target partition (files accumulate until the next optimize), plus a checkpoint every N commits; N (delta-rs's default) is a parameter ([#27](#decision-log)); a checkpoint commit adds 3 Class A and 33 × N / 10 Class B ([#42](#decision-log));
  - optimize runs once per table at the end of each catch-up and each live session, and daily in the 24/7 scenarios; vacuum runs right after each optimize, with D6's 7-day retention; for 1-minute 24/7, a sensitivity row compares hourly with daily optimize ([#30](#decision-log)); in the on-demand grid, each catch-up is followed by one live session ([#41](#decision-log));
  - the pipeline's LISTs on bronze are derived from ADR-0012's key layout, at 1,000 keys per LIST page ([#23](#decision-log)): each run lists in full the current day prefix of the 3 dynamic feeds, static feeds' day prefixes are listed once a day, and a catch-up lists every pending day prefix of the 17 feeds ([#43](#decision-log)); each new bronze object is read once (one GET, Class B);
  - month 1 adds the initial load as one catch-up of the history archives and capture's backlog since capture started; the production start date is a parameter, set to the latest date the owner considers plausible, which gives the most pending days in month 1 (pessimistic, [#31](#decision-log));
  - table counts and cadences are parameters.
- **Sizing:**
  - bronze: B's `raw/` and `logs/` growth plus the history archives as `.7z`;
  - silver: B's deduplicated records per day (raw records for feeds without a dedup basis) times the larger of A's Parquet bytes per row before and after optimize ([#29](#decision-log)), weighted by rows with an estimate for vehicles, which A did not write: 22.0 bytes per row ([#46](#decision-log)), so no compression ratio is assumed; raw records give an upper bound; it starts in month 1 with the history inside its 12-month window;
  - gold: an upper bound by cardinality, each table's rows × the same bytes per row: one row per station for the snapshot questions (Q1, Q5), feeds × minutes for Q2, and stations (B) × hours or days by grain for the others, accumulated over every loaded day ([#44](#decision-log));
  - Delta overhead in silver and gold: A's `_delta_log` bytes per commit × 30 days of commits, plus the bytes rewritten by MERGE and optimize in 7 days ([D6](#d6-silver-keeps-a-rolling-12-months-gold-is-kept-indefinitely-and-delta-keeps-7-days-of-history)).
- **Output:** cost per layer as well as the total; capture's `logs/` and `state/` writes are reported apart from `raw/`, so their share of the quota is visible.
- **Runs** once, after A and B; parameters are kept apart from the logic so the model can be re-run with new inputs.
- **Hand check** ([#48](#decision-log)): `cost_model_handcheck.py` recomputes month 1's Class A and Class B, and their cost after the free quotas, for the judged cell and 24/7 at 10 minutes, without importing the model, and compares each component with `output/cost_months.csv`. It follows this section and these rules, which the model applies and the bullets above leave implicit:
  - A's measures: a table load is 14 Class B plus 2 per JSON commit since the last checkpoint ((N − 1) / 2 on average), fitted on the appends after the first checkpoint; MERGE and optimize read 3 Class B per data file; optimize and vacuum each load the table at N like a commit, plus their fixed extra over A's measured load (3 and 15 Class B);
  - initial load: one commit per table and day with data on a new table, reading no file, and one optimize per table over all of them; silver tables without history archives load the backlog only, and gold loads history and backlog; bronze adds the backlog's day prefixes, one LIST of the history prefix, the archives' upload (one PUT each) and a GET of every backlog object and archive;
  - the backlog is counted at production's capture cadence (static feeds once a day), not the current worker's hourly one, since static feeds rarely change;
  - catch-ups: each one redoes the previous session's day, so a month has days + catch-ups day partitions per table; each commit finds the day's compacted file, and the catch-up's optimize compacts two files per day;
  - live sessions: `live_hours` are per month, split evenly over the sessions; static silver and daily gold commit only in catch-ups, and an hourly table commits once per started hour of a session;
  - LIST pages: each run lists the day prefix as it stands at that run, at least one page, so pages grow through the day.
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
| 4 | [Cost model](#c-cost-model) | The cost model runs once, with measured operations per commit; the former Q3 is merged into Q1 → #27 | Measured data prevails over estimates; the pessimism lives in the scenarios | Method |
| 5 | [Probe A](#a-delta-on-r2) | Probe A counts operations with a local proxy, cross-checked against R2 metrics → #19, #22 | Exact counts per commit and step; two independent counts check each other | Method |
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
| 16 | [Cost model](#c-cost-model) | C sizes gold by cardinality and adds Delta's overhead (log and rewritten files) from A's measures; extends #10 → #44 | Total storage leaves no layer out; measured data prevails over an assumed margin (#10) | Method review |
| 17 | [Q1](#q1-cost-calculation), [Cost model](#c-cost-model) | Month 1 includes the initial load (history and capture's backlog) and is judged like any other month; extends #12 | It is the most expensive month, and the bill does not separate one-off from recurring cost | Method review |
| 18 | [Probe A](#a-delta-on-r2) | Probe A keeps concurrent commits safe with R2's conditional put, with no external lock | It is what D4 scored (only the bucket); a DynamoDB lock adds an AWS service and would reopen D4 | Method review |
| 19 | [Probe A](#a-delta-on-r2) | The proxy is mitmproxy with HTTPS inspection, trusted by the probe process only; refines #5 → #22 | Requests are signed (SigV4) for R2's host, so a plain reverse proxy breaks them; mitmproxy is the standard HTTP inspection tool and needs no signing code | Method review |
| 20 | [Probe A](#a-delta-on-r2) | The owner creates and removes the test bucket, token and lock rule in the console; the script only runs the checks; refines #6 | Operational actions are the owner's (CLAUDE.md), and the script never holds an admin credential | Method review |
| 21 | [Probe B](#b-measured-volume) | B counts history rows per archive type, with the same dedup basis as capture's `station_status` (`station_id`, `last_reported`); INFORMACIO at one snapshot per day; raw rows kept as an upper bound; extends #9 | C sizes silver in rows (#10) and month 1 holds the history (#17); deduplicated rows are what silver stores, and both sources are counted on the same basis | Steps |
| 22 | [Probe A](#a-delta-on-r2) | The proxy covers the whole counted run, `extra` included; the independent count compares totals for the test bucket on a dashboard day that only step 5 uses; C takes only the commit and maintenance checks, and requests to other buckets are filtered out; refines #5, #19 → #37, #39 | The test bucket receives only the probe's requests, so a daily total needs no narrower window | Steps |
| 23 | [Cost model](#c-cost-model) | The pipeline's LISTs on bronze are derived from ADR-0012's key layout (prefixes per provider, feed and day per run; 1,000 keys per page), not set by hand → #43 | They are probably the largest Class A item (about 430k a month for 10 prefixes every minute), so they are derived, not guessed | Steps |
| 24 | [Probe B](#b-measured-volume) | Capture's daily Class A and B from the dashboard, on capture-only days, check B's derived `state/` writes and D2's ~270–300k Class A; the metric prevails → #36 | Measured data prevails over derived counts | Steps |
| 25 | [File layout](#file-layout) | `output/` is ignored by a `.gitignore` in the spike folder | The spike stays self-contained and the root file is not touched | Steps |
| 26 | [Decided at framing](#decided-at-framing), [Step 10](#step-10--conclusion) | The spike writes no ADR. Its Conclusion adds Decisions to record (outcome, findings, ADR grouping, affected sections per decision); the ADRs, `architecture.md` and the R2 source card are written after the spike closes, in a fresh session, as T035's post-spike work | `architecture.md` and the ADRs are the project's most valuable documents and are written with full, clean context, not during a run; the closed spike holds everything they need | Steps review |
| 27 | [Probe A](#a-delta-on-r2), [Cost model](#c-cost-model) | A opens a fresh table before each commit, on a test table with `delta.checkpointInterval = 10`, and logs table-load reads, checkpoints and files per MERGE; C models a commit as table load + per-file MERGE reads + a checkpoint every N commits, with N and the optimize cadence as parameters; refines #4 → #30, #42 | A real run loads the table from scratch and its MERGE scans the files written since the last optimize, so a constant from a long-lived process can understate cost by orders of magnitude; a small interval shows several checkpoints in a short run, and each component is measured once and scaled in C | Steps review |
| 28 | [Probe A](#a-delta-on-r2), [D7](#d7-storage-security-baseline) | The concurrency check is judged as a safety property (no duplicate key or lost row versus a serial run; the stale commit retries or raises a conflict); the independent count accepts the proxy's total with or without failed requests; a failed token or lock check reopens D7 before the Conclusion → #39, #40 | The D4 gate asks for safe commits, not for one mechanism; R2's billing of failed requests is undocumented, so a billing rule must not loop step 5; D7 had no rule for a failed security check | Steps review |
| 29 | [Probe B](#b-measured-volume), [Cost model](#c-cost-model), [Exit criteria](#exit-criteria) | B's history counter is checked against s004's parquet row counts; capture's dashboard figures override B beyond ±10%; C computes every month 1–12, adds one GET per new bronze object, and sizes tables with the larger bytes per row of A (before or after optimize); the timebox counts effort, not waiting days → #31, #36, #46 | The extracted CSVs no longer exist; each check needs a yes/no threshold; the gate judges every month; Class B was missing bronze reads; the larger value keeps the model pessimistic | Steps review |
| 30 | [Cost model](#c-cost-model) | Optimize runs once per table at the end of each catch-up and each live session, and daily in the 24/7 scenarios; vacuum runs right after each optimize, with D6's 7-day retention; C adds a sensitivity row for 1-minute 24/7 with hourly versus daily optimize; refines #27 → #41 | Each MERGE reads every file in its target partition, so the optimize cadence drives Class B; a fixed value makes the model executable, and the sensitivity row shows how much the unconditional D2 verdict depends on it | Steps review |
| 31 | [Q1](#q1-cost-calculation), [Exit criteria](#exit-criteria), [Probe B](#b-measured-volume), [Cost model](#c-cost-model) | The production start date is the latest the owner considers plausible; the timebox excludes only the wait for step 5's counted day; Q1, §2 B and §2 C state #29's ±10% threshold, months 1–12 and larger bytes per row; refines #29 | A later start leaves more pending days in month 1, which keeps it pessimistic; step 7 reads past days and waits for nothing; thresholds belong in the Method, not only in the steps | Steps review |
| 32 | [Probe A](#a-delta-on-r2), [Step 2](#step-2--write-the-delta-gate-checks), [Step 4](#step-4--add-counting-and-the-remaining-checks) | Appends write only keys not yet seen in the data window, deduplicated on silver's basis (`station_id`, `last_reported`); the second minute of the concurrent append pair is also deduplicated against the first; MERGEs take each minute's full rows, and the concurrent MERGE pair keeps overlapping new keys. The window grows to 17 captured minutes in `gate` (10 write, 3 merge, 2 + 2 concurrent) and to 74 in `full` (60, 10, 2 + 2); step criteria unchanged | Bicing repeats keys across minutes when a station has not reported (2026-10-15, minutes 1–10: Bicing 5,430 rows / 2,153 distinct keys; AMBici 2,370 / 2,370), so raw appends leave duplicate keys and the `merge` check would fail with Delta correct; overlapping new keys in the MERGE pair are the insert race that matters for safety | Running step 2 |
| 33 | [Step 10](#step-10--conclusion) | The spike transfers its security requirements to d002 Requirements; the spike of each other component does the same | The spike holds the threat model and the evidence; d002 stays the single list read before each spike | T045 |
| 34 | [Step 5](#step-5--run-probe-a-and-verify-the-analysis) | Step 5 waits for a clean dashboard day; steps 6–8 run before it; step 9 still needs step 5's operation tables → #37 | Opening the test bucket in the dashboard on 2026-10-28 added operations that cannot be subtracted, so that day fails #22's independent count; steps 6–8 do not read probe A's outputs | Running step 6 |
| 35 | [Step 7](#step-7--run-probe-b-and-verify-volumes) | The spot check sums the day's file sizes with `stat` instead of `du -sk` | B sums object bytes; `du` rounds each file up (to 4 KB blocks, or to 512 bytes with `-A`) and adds the directory itself, so on ~1,400 small objects it never matches; the exact sum needs no tolerance | Running step 7 |
| 36 | [Probe B](#b-measured-volume), [Step 7](#step-7--run-probe-b-and-verify-volumes) | Capture's R2 operations come from the GraphQL Analytics API (`r2OperationsAdaptiveGroups`) per UTC day, operation and status, not from the dashboard; the check uses PutObject alone, and ListObjects and GetObject are reported apart; refines #24, #29 | The dashboard's summary and charts disagree, and neither its day boundary nor an operation breakdown is documented; the owner downloaded the bucket almost daily, so no day is capture-only, and PutObject alone excludes those downloads ([R2 metrics](https://developers.cloudflare.com/r2/platform/metrics-analytics/)) | Running step 7 |
| 37 | [Probe A](#a-delta-on-r2), [Step 5](#step-5--run-probe-a-and-verify-the-analysis) | Step 5's independent count uses the test bucket's R2 metrics over the run's UTC window (proxy's first to last request, one minute of margin each side) from the GraphQL Analytics API, not a clean dashboard day; refines #22, #34 → #38, #39 | The API accepts `datetime` range filters; for 2026-10-27 23:00 UTC it returned exactly the owner's 13 operations (7 Class A, 6 Class B), so a window isolates the run without a day free of other activity | After step 7 |
| 38 | [Step 5](#step-5--run-probe-a-and-verify-the-analysis) | The uncounted DuckDB read runs on the same day as the counted run, after Do 7's R2 metrics query has returned; refines #37 | The run window, not the day, isolates the counted run, so a later read outside the window does not change it | Running step 5 |
| 39 | [Probe A](#a-delta-on-r2), [Step 5](#step-5--run-probe-a-and-verify-the-analysis) | The independent count compares the proxy's total requests for the test bucket, failed ones included, with R2's total over the run window, within ±0.5%; per-class counts come from the proxy; refines #22, #28, #37 | R2's operation metrics are sampled ([F14](#4-findings)): per-object counts scatter around the proxy's exact ones, while the totals differ by 0.02%; ±0.5% (about 30 requests in a 6,000-request run) still exposes a client that bypasses the proxy for part of a check; the query returns failed requests as `userError`, so both totals include them | Running step 5 |
| 40 | [Probe A](#a-delta-on-r2), [Step 5](#step-5--run-probe-a-and-verify-the-analysis) | Fault injection judges the `concurrent` pairs on their safety outcome (stale MERGE conflicts, stale append retried, no duplicate key, same rows as a serial run) and adds an `extra` check `race`: 10 rounds of two clients PUTting one new key at once with `If-None-Match: *`, outside the table; each round needs one success, one rejection and the winner's body stored. The re-run is `extra --only race` through the proxy in its own window; `analyse_ops.py` takes both proxy logs and the sum of both windows' R2 totals; refines #28 | delta-rs found the winner's commit before its own log PUT, so no 412 occurred ([F15](#4-findings)); the race exercises R2's put-if-absent, the only guard of commits with no external lock (#18, F1), without depending on delta-rs timing | Running step 5 |
| 41 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | In the on-demand grid, each catch-up is followed by one live session, so a cell has as many live sessions as catch-ups (10 in the judged cell); each session ends with an optimize per table; extends #30 | Q1 set the live hours but not the sessions; opening the dashboard catches up and then runs live | Running step 8 |
| 42 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | A commit that writes a checkpoint adds 3 Class A and 33 × N / 10 Class B, scaling A's measure at N = 10 to the model's N; extends #27 | Writing a checkpoint rereads the commits since the previous one, so it grows with N but occurs N times less often: about 3.3 reads per commit, against about 100 to load the table at N = 100 ([F5, F16](#4-findings)) | Running step 8 |
| 43 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | Each pipeline run lists in full the current day prefix of the 3 dynamic feeds, at 1,000 keys per page; static feeds' day prefixes are listed once a day; a catch-up lists every pending day prefix of the 17 feeds; refines #23 | Listing static feeds every minute would cost about 770k Class A a month (77% of the free quota) for data captured once a day; a full listing assumes no watermark, which is T039's; listing after the last processed key would save about 5% | Running step 8 |
| 44 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | C sizes gold snapshot tables (Q1, Q5) at one row per station, Q2 at feeds × minutes, and the other tables at stations × hours or days by their grain, accumulated over every loaded day; extends #16 | The sizing in §2 C covered only hour and day grains; Q2 measures the feeds, not the stations, and by station it would add about 0.6 GB a month that the question never holds | Running step 8 |
| 45 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model), [Step 9](#step-9--run-probe-c-and-verify-the-model) | Step 8 adds, in a new session, a sensitivity analysis and charts. Sensitivity: A's four extrapolated measures (reads per file, checkpoint interval N, Parquet bytes per row, bytes rewritten per MERGE), one at a time at ×0.5 and ×2, on the judged cell and 1-minute 24/7, giving each case's worst month; reported, not judged. Charts, with matplotlib in `output/cost-model/`: monthly cost against the €2 gate, the on-demand grid as a heat map, the worst month by 24/7 cadence, cost per layer by month for the judged cell, and the sensitivity as a tornado chart | A measured these four on one small `station_status` table at N = 10, so they are the model's least certain inputs; the analysis shows whether any could push the judged cell over €2 and which to watch in production. Capture volume and prices are measured or published, so they are not varied. The charts make the gate and the cost curve for T039 readable | After step 8 |
| 46 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | Silver and gold are sized at 22.0 Parquet bytes per row: the mean of `station_status` (17.34, A's larger value) and vehicles (22.85, estimated) weighted by silver rows (16% and 84%). Vehicles are estimated as A's value × their gzip bytes per record in bronze over `station_status`'s (24.07 / 18.26, step 7's `volumes.json`); extends #29 | A wrote only `station_status`, but vehicles are 84% of silver's rows and carry more columns; the bronze ratio estimates them without a new measurement, and #45's ×0.5 and ×2 cover its error | After step 8 |
| 47 | [Cost model](#c-cost-model), [Step 8](#step-8--write-the-cost-model) | The sensitivity adds a break-even per measure: the factor above 1 at which the judged cell's worst month reaches the €2 gate, searched up to ×1,000. Sensitivity outputs (CSVs and tornado chart) go in `output/cost-model/sensitivity/`; extends #45 | ×0.5 and ×2 rank the measures but do not show the margin to the gate, which is what Q1 judges; a subfolder keeps the sensitivity apart from the model's charts | Running step 8 |
| 48 | [Cost model](#c-cost-model), [Step 9](#step-9--run-probe-c-and-verify-the-model) | Step 9's hand recomputation is a script, `cost_model_handcheck.py`, covering month 1's Class A and Class B of the judged cell and 24/7 at 10 minutes; §2 C gets a Hand check bullet with the rules the model applies and §2 C left implicit, the backlog counted at production's daily static capture included | The spec is the source of truth, so rules found only in the code are written into it; a script makes the check repeatable after a re-run; 24/7 at 10 minutes uses 89% of the free Class B in month 1, so Class B is where it can break the gate | Running step 9 |

### File layout

```text
spikes/storage-table-format/
├── README.md          Question, setup, commands, what each script does; link to s010; How we got here (written at Conclusion)
├── .gitignore         Ignores output/ (ADR-0009)
├── pyproject.toml     Pinned Python and locked dependencies (ADR-0016, ADR-0017)
├── uv.lock
├── .python-version    Exact Python version (ADR-0016)
├── .env.example       Test bucket endpoint, scoped token and proxy settings, empty values
├── r2_proxy.py        A: mitmproxy addon that logs each deltalake request to R2, one JSON line per request
├── delta_probe.py     A: write, MERGE, concurrency, optimize, vacuum, reads, token and lock checks
├── analyse_ops.py     A: joins proxy and probe logs; operations per check, step and class; the three checks
├── measure_volume.py  B: raw/, logs/, state/ and history volumes
├── cost_model.py      C: scenarios × months, cost per layer and total; sensitivity and charts (#45)
├── params.toml        C: every parameter (tables, cadences, retention, prices), apart from the logic
├── cost_model_handcheck.py  C: month 1's Class A and B of two cells, recomputed without the model (#48)
└── output/            Ignored by Git (ADR-0009): logs, volumes, operation and cost tables; cost-model/ charts
```

## 3. Steps

The cheapest test of the riskiest assumption runs first: steps 2–3 check the D4 gate on R2 without instrumentation, before counting is built on it (steps 4–5). Paths in the steps are relative to `spikes/storage-table-format/` unless they start at the repository root.

| # | Title | Who | Gate | Files |
|---|---|---|---|---|
| 1 | Scaffold the spike folder | Claude | — | `README.md`, `pyproject.toml`, `uv.lock`, `.python-version`, `.env.example`, `.gitignore` |
| 2 | Write the Delta gate checks | Claude | — | `delta_probe.py` (write, MERGE, concurrent commits), `README.md` |
| 3 | Set up the test bucket and run the gate checks | Owner | D4 hard cut | `.env` (local) |
| 4 | Add counting and the remaining checks | Claude | — | `r2_proxy.py`, `delta_probe.py`, `analyse_ops.py`, `README.md` |
| 5 | Run probe A and verify the analysis | Owner | Analysis checks | `output/` |
| 6 | Write the volume measurement | Claude | — | `measure_volume.py`, `README.md` |
| 7 | Run probe B and verify volumes | Owner | — | `output/` |
| 8 | Write the cost model | Claude | — | `cost_model.py`, `params.toml`, `README.md`, `pyproject.toml`, `uv.lock` |
| 9 | Run probe C and verify the model | Owner | D2 gate | `cost_model_handcheck.py`, `README.md`, `output/` |
| 10 | Conclusion | Claude, Owner (teardown) | — | this document, `README.md`; test lock rule, bucket and token |

### Step 1 — Scaffold the spike folder

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 1 - scaffold storage and table format spike`
- **Model:** sonnet · medium
- **Gate:** —

#### Scope

- `README.md`: the question (s010 Main question), a link to this document, setup (`uv sync --locked`, `.env` from `.env.example`) and a Commands section that later steps fill.
- `pyproject.toml` and `uv.lock`: `requires-python` as a compatibility range; dependencies `deltalake` (≥ 1.0), `polars`, `duckdb`, `boto3`, `mitmproxy`, `python-dotenv`.
- `.python-version`: the exact Python version that runs (ADR-0016).
- `.env.example`, empty values: `R2_ACCOUNT_ID`, `R2_TEST_BUCKET`, `R2_TEST_ACCESS_KEY_ID`, `R2_TEST_SECRET_ACCESS_KEY`, `R2_PROD_BUCKET`, `R2_LOCKED_PREFIX`, `PROXY_URL`, `PROXY_CA_CERT` (path to the mitmproxy CA certificate); the README gives their usual local values.
- `.gitignore`: ignores `output/` (ADR-0009, #25).
- Not touched: anything outside these files.

#### Reads

- This document, §2 File layout: the folder's files and their purpose.
- `.claude/rules/code/spikes.md`: what a spike README holds.

#### Do

1. Create `pyproject.toml` with `uv init --bare`, pin Python with `uv python pin`, and add the dependencies with `uv add`, which writes `uv.lock`.
2. Write `.env.example`.
3. Write `README.md`.
4. Write `.gitignore`.
5. Update this step's Status.

#### Check

- `uv sync --locked` succeeds and `uv run python -c "import deltalake, polars, duckdb, boto3; print(deltalake.__version__)"` prints a version ≥ 1.0.
- `git check-ignore spikes/storage-table-format/output/x` prints the path.

### Step 2 — Write the Delta gate checks

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 2 - add delta gate checks to storage spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

`delta_probe.py`, subcommand `gate`, with a `--local` option that runs against a temporary local table instead of R2:

- **Sample:** `station_status` objects of both providers from `spikes/cloudflare-capture-spike/data/V4/raw/<provider>/station_status/<day>/<UTC time>.json.gz`, for a window given by parameters (default: the first 17 captured minutes of a full day; #32). Each object becomes rows `source`, `station_id`, `last_reported` (UTC), `captured_at` (UTC, from the key), `bikes_available`, `docks_available`, `capture_date` (partition column). The two providers may use different GBFS versions; the field mapping handles both.
- **Table:** `s3://<R2_TEST_BUCKET>/<run_id>/station_status`, with `run_id` the run's UTC start time, so each run writes a fresh table.
- **Storage options:** endpoint from `R2_ACCOUNT_ID`, region `auto`, the test token, and the option that enables conditional put for safe commits with no external lock (decision log #18).
- **Table handle:** a fresh `DeltaTable` is opened before each commit (#27), so each commit's latency includes the table load. `gate` sends its requests directly to R2 and ignores the proxy settings.
- **Checks,** each logged as one JSON line in `output/probe-<run_id>.jsonl`, or under `output/local/` with `--local` (UTC start and end, check, result `ok` or the error message, table version, commit latency in ms):
  - `write`: creates the table and appends one commit per captured minute (10 by default). Ok when the version count equals the commits and the row count equals the rows written.
  - `merge`: 3 MERGE commits with the following minutes, keyed on `source`, `station_id`, `last_reported` (update when matched, insert otherwise). Ok when no key is duplicated and the row count equals the distinct keys.
  - `concurrent`: fault injection by stale writers. Two handles are opened at the same version; one commits, then the other commits on its stale snapshot. For two appends, both land on consecutive versions with no row lost (compatible commits are retried). For two MERGEs that touch the same partition, the second either lands on its own new version after a correct retry or raises a commit conflict. Ok when, in both cases, the table has no duplicate key and no lost row compared with a serial run of the same two commits (#28). Which of the two outcomes occurred is logged.
- The run stops at the first failed check and prints a summary table.
- Also: `README.md` (Commands) and this step's Status in this document.

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

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: step 3 - record delta gate result in s010` (Claude writes the findings and Status from the owner's report)
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

The summary shows `ok` for `write`, `merge` and `concurrent` → the D4 gate holds. Claude records as findings the result, the outcome of the stale MERGE (retried or conflict), and the commit latencies; taken without the proxy and with the table load included (#27), they are Q2's observed latency.

### Step 4 — Add counting and the remaining checks

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 4 - add request counting and remaining checks to storage spike`
- **Model:** opus · high
- **Gate:** —

#### Scope

- `r2_proxy.py`: mitmproxy addon (decision log #19). Logs every request to `output/proxy-<UTC start>.jsonl`, one JSON line each: UTC time, bucket, method, path, query, status, request and response bytes, duration, and the operation and its class (A, B or free) as classified by the [R2 source card](../sources/r2-storage.md).
- `delta_probe.py`:
  - subcommand `full`, through the proxy, on a table created with `delta.checkpointInterval = 10` and with a fresh `DeltaTable` opened before each commit (#27): `write` (60 commits, one hour), `merge` (10 commits), on a data window of 74 captured minutes of a full day set by parameters (#32), `concurrent`, `optimize` (compaction), `vacuum` (a dry run with the 7-day default, then a run with zero retention and the retention check disabled, so the probe sees files deleted). Every client (`deltalake`, Polars, DuckDB, `boto3`) reaches the proxy through its own settings (proxy URL and the mitmproxy CA certificate), so only the probe process trusts it; `full` prints its `run_id`;
  - per check it also logs Parquet bytes per row, `_delta_log` bytes per commit, and bytes rewritten by MERGE and optimize; per commit, the JSON commits read since the last checkpoint, whether it wrote a checkpoint and, for MERGE, the files in the target partition;
  - subcommand `extra --run-id <id>`, run after `full` on the table it wrote, also through the proxy (#22), with `--skip <check>` to leave a check out and `--only <check>` to run one alone: Polars and DuckDB read the table and match its row count (guide); the test token cannot list, read or write `R2_PROD_BUCKET` (a write attempt uses the key `s010-token-check/canary.txt`, so a wrongful success is harmless and easy to remove); under `R2_LOCKED_PREFIX`, a new object is written and then an overwrite and a delete of it are attempted with the test token;
  - `extra` appends its lines to `full`'s `output/probe-<run_id>.jsonl`;
  - `full` and `extra` abort before their first request if `PROXY_URL` or `PROXY_CA_CERT` is empty, so no request bypasses the proxy; the only exception is `extra --only <check> --no-proxy`, the uncounted run of a check whose client cannot use the proxy.
- `analyse_ops.py --run-id <id> --proxy-log <file>`: joins that proxy log and the run's probe logs by time window; writes operations per check, per commit and per class to `output/`, for the test bucket only (requests to other buckets are filtered out by bucket); marks the `full` checks as the ones C takes; flags any check with no proxied request, as its client bypassed the proxy; runs the three analysis checks of §2 A:
  - known arithmetic: one append of one file, on a commit that writes no checkpoint, gives one data PUT and one log PUT;
  - independent count: the proxy's totals per class for the whole run, computed both with and without failed (non-2xx) requests, and one of them equals the test bucket's R2 metrics for that day, passed as arguments (#28);
  - fault injection: the `concurrent` check shows a rejected log PUT (HTTP 412) followed by a successful retry or a raised conflict; refined by #40: the pairs are judged on their safety outcome, and the 412 comes from `extra`'s `race` check.
- Synthetic and `--local` logs go under `output/local/`, apart from the counted run's.
- Also: `README.md` (Commands); in this document, a finding with delta-rs's default checkpoint interval N and its source (C's N), and this step's Status.
- Not touched: the `gate` subcommand's behaviour; `.env.example`, which step 1 wrote.

#### Reads

- This document, §2 A (Measures, Security, Counting, Evidence, Analysis checks).
- [R2 source card](../sources/r2-storage.md): operation classes, for the classifier.
- delta-rs documentation, through the `web-researcher`: the default checkpoint interval, which C takes as N.
- mitmproxy addon API, and the proxy and CA certificate settings of each client (`object_store` for `deltalake` and Polars, DuckDB's delta extension, `boto3`), through the `web-researcher`. A client with no such setting is reported before step 5; its check then runs on another day, uncounted.

#### Do

1. Write `r2_proxy.py`.
2. Extend `delta_probe.py` with `full` and `extra`.
3. Write `analyse_ops.py`, with a small synthetic pair of logs to check its counts.
4. Run `uv run python delta_probe.py full --local` and `analyse_ops.py` on the synthetic logs.
5. Record N with its source as a finding.
6. Update the README Commands section and this step's Status.

#### Check

- `uv run python delta_probe.py full --local` reports `ok` for every counted check.
- `analyse_ops.py` on the synthetic logs gives the expected counts per check and class.
- `full` with `PROXY_URL` empty aborts before any request.
- `extra --no-proxy` without `--only` is rejected before any request.
- N is recorded as a finding with its source.

### Step 5 — Run probe A and verify the analysis

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: step 5 - record probe a results in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** the three analysis checks pass → otherwise the scripts are fixed and the probe is run again in a new run window

#### Scope

A counted run of probe A on the test bucket; operation and size tables in `output/`; findings for Q2 and for the cost model's inputs.

#### Reads

- `README.md`: the `full`, `extra` and `analyse_ops.py` commands.

#### Do

1. During the run, nothing else touches the test bucket: no other run and no dashboard view of the bucket (#37).
2. Start the proxy in one terminal: `uv run mitmdump -s r2_proxy.py --listen-port 8080`. On its first start, mitmdump creates its CA certificate.
3. In `.env`, set `PROXY_URL=http://localhost:8080` and `PROXY_CA_CERT` to the absolute path of `~/.mitmproxy/mitmproxy-ca-cert.pem`.
4. In another terminal, run `uv run python delta_probe.py full` and note the `run_id` it prints.
5. Run `uv run python delta_probe.py extra --run-id <id>`, adding `--skip <check>` for a check whose client step 4 reported as unable to use the proxy.
6. Stop the proxy.
7. About 20 minutes after the run, so that every operation's metrics are in (F14), query the test bucket's R2 operations over the run's window: from one minute before the proxy's first request to one minute after its last (#37). Claude sums the output into the total of requests, failed ones included (#39).

   ```bash
   set -a; source .env; set +a
   LOG=$(ls output/proxy-*.jsonl | tail -1); echo $LOG
   START=$(jq -rs 'map(.ts) | min - 60 | floor | todate' $LOG)
   END=$(jq -rs 'map(.ts) | max + 60 | ceil | todate' $LOG)
   echo "$START .. $END"
   curl -s https://api.cloudflare.com/client/v4/graphql \
     -H "Authorization: Bearer $CF_ANALYTICS_API_TOKEN" -H "Content-Type: application/json" \
     --data "$(jq -n --arg acc "$R2_ACCOUNT_ID" --arg b "$R2_TEST_BUCKET" --arg s "$START" --arg e "$END" '{variables: {acc: $acc, b: $b, s: $s, e: $e}, query: "query($acc: String!, $b: String!, $s: Time!, $e: Time!) { viewer { accounts(filter: {accountTag: $acc}) { r2OperationsAdaptiveGroups(limit: 10000, filter: {bucketName: $b, datetime_geq: $s, datetime_lt: $e}) { sum { requests } dimensions { actionType actionStatus } } } } }"}')" \
     | jq -r '.errors // (.data.viewer.accounts[0].r2OperationsAdaptiveGroups | sort_by(.dimensions.actionType) | .[] | [.dimensions.actionType, .dimensions.actionStatus, .sum.requests] | @tsv)'
   ```

8. Only if a check was skipped, and after Do 7's query has returned: run `uv run python delta_probe.py extra --run-id <id> --only <check> --no-proxy`, the same day (#38).
9. In the same shell as Do 7, run `uv run python analyse_ops.py --run-id <id> --proxy-log $LOG --r2-total <N>`, with Claude's sum from Do 7.
10. Report the probe summaries, the analysis summary and the R2 figures.

#### Check

- The three analysis checks pass, and no check is flagged as bypassing the proxy apart from one skipped in Do 5. The gap between the proxy's and R2's totals is recorded as a finding.
- If the token check or the lock check fails, it is recorded as a finding and D7 is reopened with the owner before step 10; Decisions to record marks D7 as reopened (#28).
- Claude records as findings: operations per commit by class, Parquet bytes per row, `_delta_log` bytes per commit, rewritten bytes, the maintenance and read results (guide) and the token and lock results.

### Step 6 — Write the volume measurement

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 6 - add volume measurement to storage spike`
- **Model:** sonnet · high
- **Gate:** —

#### Scope

`measure_volume.py`, which writes `output/volumes.json` (the file C reads) and prints a summary:

- **`raw/`** (`spikes/cloudflare-capture-spike/data/V4/raw/`), per provider, feed and day: objects, bytes and records (entries in the payload's main list; 1 for feeds without one). For `station_status`, also distinct (`station_id`, `last_reported`) records. The first and last days are dropped as incomplete.
- **`logs/` and `state/`**, per day: objects, bytes and writes. `logs/` writes are its objects. `state/` keeps only its latest version locally, so its writes per day are derived: capture passes per day (from `logs/`) times the `state/` objects one pass writes (from capture's code).
- **History** (`spikes/bicing-spike/historical-data/raw/*.7z`), per archive: type (ESTACIONS or INFORMACIO, from the file name), month, `.7z` bytes, uncompressed bytes and raw rows. For ESTACIONS, also distinct (`station_id`, `last_reported`) rows and snapshots per day. For INFORMACIO, rows at one snapshot per day (#21).
- Archives are streamed with macOS's built-in `tar -xOf <archive>` (libarchive reads 7z), never extracted to disk. Rows are counted with a CSV parser on that stream, not by lines (header, quoted newlines); the parser also reports the quoted newlines it finds.
- Also: `README.md` (Commands) and this step's Status in this document.
- Not touched: the local copies, which are only read.

#### Reads

- This document, §2 B and decision log #21: what is measured and on which basis.
- Capture's code in `spikes/cloudflare-capture-spike/js/`, the part that writes `state/` and `logs/`: objects written per pass.
- The header and first row of one archive per type, read from the stream (`tar -xOf <archive> | head -n 2`): the column names for the station, `last_reported` and the snapshot time.
- The s004 code that wrote `spikes/bicing-spike/historical-data/work/*.parquet`: confirm that it keeps every CSV row, so the parquet row counts are an independent reference.

#### Do

1. Write the `raw/`, `logs/` and `state/` measurements.
2. Write the history measurement.
3. Write a targeted check of the counting: a small hand-made sample with known raw and distinct counts, including a quoted newline.
4. Run the targeted check, then the 2026-09 and 2026-08 ESTACIONS archives alone.
5. Update the README Commands section and this step's Status.

#### Check

- The targeted check gives the expected raw and distinct counts.
- The 2026-09 ESTACIONS stream gives 290,689,605 bytes uncompressed, and its raw rows plus the quoted newlines the parser reports equal 4,528,265 (4,528,266 lines minus the header).
- The 2026-08 ESTACIONS raw rows equal the row count of its parquet in `work/` (#29); if the s004 code drops rows, they equal instead the row count of DuckDB's `read_csv` on the same stream.

### Step 7 — Run probe B and verify volumes

- **Status:** ✅ done
- **Who:** Owner
- **Commit:** `docs: step 7 - record probe b volumes in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** —

#### Scope

A full run of `measure_volume.py`; `output/volumes.json`; findings for the cost model's inputs.

#### Reads

- `README.md`: the `measure_volume.py` command.

#### Do

1. Run `uv run python measure_volume.py`.
2. Spot-check one provider, feed and day: `find <day folder> -type f | wc -l` and `find <day folder> -type f -exec stat -f %z {} + | awk '{s+=$1} END {print s}'` ([#35](#decision-log)) against that day's objects and bytes in `output/volumes.json`.
3. From `spikes/storage-table-format/`, query the R2 metrics of `bikesharing-capture-spike` per UTC day, operation and status (#24, #36):

   ```bash
   set -a; source .env; set +a
   curl -s https://api.cloudflare.com/client/v4/graphql \
     -H "Authorization: Bearer $CF_ANALYTICS_API_TOKEN" -H "Content-Type: application/json" \
     --data "$(jq -n --arg acc "$R2_ACCOUNT_ID" '{variables: {acc: $acc}, query: "query($acc: String!) { viewer { accounts(filter: {accountTag: $acc}) { r2OperationsAdaptiveGroups(limit: 10000, filter: {bucketName: \"bikesharing-capture-spike\", date_geq: \"2026-10-14\", date_leq: \"2026-10-27\"}) { sum { requests } dimensions { date actionType actionStatus } } } } }"}')" \
     | jq -r '.errors // (.data.viewer.accounts[0].r2OperationsAdaptiveGroups | sort_by(.dimensions.date, .dimensions.actionType) | .[] | [.dimensions.date, .dimensions.actionType, .dimensions.actionStatus, .sum.requests] | @tsv)'
   ```

4. Report the summary, the spot check and the query's output.

#### Check

- The spot check matches the summary.
- Claude compares the metrics' daily PutObject average × 30, over B's complete days, with B's capture writes (`raw/`, `logs/` and the derived `state/` writes): within ±10%, B's values are kept; outside it, the metrics' figures override capture's operations in `params.toml` (step 9) and the gap is recorded as a finding (#29). D2's ~270–300k Class A per month is compared the same way, and the result is a finding.
- `raw/` growth per day is within ±10% of the ~2.7 GB per month measured in `architecture.md` §3; otherwise the gap is recorded as a finding before step 8, and C uses B's measured volumes.
- Claude records as findings: volumes per feed and day, `logs/` and `state/` writes per day, history rows per type, and the dedup ratio of both sources.

### Step 8 — Write the cost model

- **Status:** ✅ done
- **Who:** Claude
- **Commit:** `chore: step 8 - add cost model to storage spike`; then `chore: step 8 - add sensitivity, break-even and charts to cost model` (#45, #47)
- **Model:** opus · high
- **Gate:** —

#### Scope

- `params.toml`, every parameter apart from the logic:
  - tables (9 silver: 2 dynamic, 7 static; 8 gold) and each gold question's freshness (§2 C commit model);
  - scenarios: 24/7 commits every 1, 5, 10, 30 and 60 minutes and every 6 hours; the on-demand grid of 4, 6, 8 and 10 catch-ups by 0.5, 1, 2 and 3 live hours; the judged cell (10 catch-ups + 2 h);
  - months reported (1, 2, 4, 6, 12), capture start date and production start date; every month from 1 to 12 is computed, since the gate judges each one;
  - retention (D5, D6): bronze and gold indefinite, silver 12 months, 7 days of Delta history, 30 days of log;
  - maintenance: optimize once per table at the end of each catch-up and each live session, and daily in the 24/7 scenarios; vacuum right after each optimize, with D6's 7-day retention (#30); one live session per catch-up (#41);
  - the checkpoint interval N, delta-rs's default as confirmed in step 4;
  - an optional override of capture's monthly Class A and B with step 7's R2 metrics figures (#24, #36);
  - prices and free quotas from the [R2 source card](../sources/r2-storage.md), and the USD→EUR rate with its date, since prices are in USD and the threshold in EUR;
  - paths to A's operation tables and B's `volumes.json`.
- `cost_model.py`: for each scenario and month, storage per layer (bronze, silver, gold, Delta overhead) and Class A and B operations, split into capture `raw/`, capture `logs/` and `state/`, and pipeline. It computes monthly and accumulated cost against the shared free quotas, with month 1 including the initial load (#17). It writes `output/cost_*.csv` and a summary, and marks per scenario whether it fits the D2 gate (at most €2 in every month up to 12).
- The pipeline's LISTs on bronze are derived from ADR-0012's key layout, at 1,000 keys per LIST page (#23): each run lists in full the current day prefix of the 3 dynamic feeds, static feeds once a day, and a catch-up every pending day of the 17 feeds (#43). Each new bronze object costs one GET (Class B).
- Silver and gold commits are costed as MERGE commits from A's measures (#27): table-load reads for the JSON commits since the last checkpoint, plus reads per file in the target partition, which grows with each commit until the next optimize, plus a checkpoint every N commits, which adds 3 Class A and 33 × N / 10 Class B (#42).
- A sensitivity row for 1-minute 24/7 compares hourly with daily optimize (#30); it is reported, not judged.
- Gold is sized by cardinality: one row per station for Q1 and Q5, feeds × minutes for Q2, stations × hours or days for the others (#44).
- Tables are sized with the larger of A's two Parquet bytes per row, before and after optimize (#29); `params.toml` sets 22.0, weighted by rows with the vehicles' estimate (#46).
- Sensitivity (#45): reads per file, N, Parquet bytes per row and bytes rewritten per MERGE, each at ×0.5 and ×2 with the rest unchanged, on the judged cell and 1-minute 24/7; `output/cost-model/sensitivity/sensitivity.csv` holds each case's worst month; reported, not judged.
- Break-even (#47): for each of those measures, the factor above 1 at which the judged cell's worst month reaches €2, up to ×1,000, in `output/cost-model/sensitivity/break_even.csv`; reported, not judged.
- Charts (#45), PNG with matplotlib: in `output/cost-model/`, monthly cost against the €2 gate (judged cell and 24/7 cadences), the on-demand grid as a heat map with the judged cell marked, the worst month by 24/7 cadence and cost per layer by month for the judged cell; in `output/cost-model/sensitivity/`, the sensitivity as a tornado chart with each measure's break-even (#47).
- Also: `README.md` (Commands), `pyproject.toml` and `uv.lock` (matplotlib), and this step's Status in this document.
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
6. Set bytes per row to 22.0 in `params.toml` (#46); add matplotlib, the sensitivity analysis and the charts (#45).
7. Extend the targeted check with one sensitivity case and one break-even computed by hand: reads per file × 2, and the reads per file factor that reaches the gate, on the synthetic case.
8. Run the targeted check and generate the charts from it; update the README Commands section and this step's Status.

#### Check

- The targeted check matches the hand computation for storage, Class A (bronze LISTs and checkpoints included), Class B (bronze GETs, table loads and per-file MERGE reads included) and cost.
- The sensitivity case and the break-even match their hand computation, and the five charts are written to `output/local/cost-model/` (the tornado to its `sensitivity/` subfolder).

### Step 9 — Run probe C and verify the model

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** `docs: step 9 - record cost model results in s010` (Claude writes the findings and Status from the owner's report)
- **Model:** —
- **Gate:** the judged on-demand cell (10 catch-ups + 2 h live) costs at most €2 in every month up to 12 (D2 gate, hard cut) → otherwise D2 is reopened. If 1-minute commits 24/7 also fit, D2 holds without conditions; if not, it holds with an operating constraint, recorded as a Production input.

#### Scope

- A full run of the cost model on A's and B's outputs; 
- `output/cost_*.csv` and `output/cost-model/`;
- `cost_model_handcheck.py` and its `README.md` entry (#48); 
- the findings that answer Q1.

#### Reads

- `README.md`: the `cost_model.py` command.

#### Do

1. Check that `params.toml` points to the outputs of steps 5 and 7. Set the production start date (the latest you consider plausible, #31), the USD→EUR rate, the capture start date (the earliest day under `raw/` in `bikesharing-capture-spike`, read in the Cloudflare console), and the capture override if step 7 found a gap beyond ±10%.
2. Run `uv run python cost_model.py`.
3. Run `uv run python cost_model_handcheck.py`: month 1's Class A and Class B of the judged cell and 24/7 at 10 minutes, recomputed without the model (#48).
4. Report the summary and the hand recomputation.

#### Check

- The hand check prints `all rows match`.
- Claude records as findings: cost per layer and total per scenario and month, the free quota usage, the judged cell and the 1-minute 24/7 case with its optimize sensitivity row, the sensitivity of A's measures (#45), and applies the gate.

### Step 10 — Conclusion

- **Status:** 💤 todo
- **Who:** Claude, Owner (teardown)
- **Commit:** `docs: step 10 - conclude spike s010`
- **Model:** opus · high
- **Gate:** —

#### Scope

- This document: Conclusion (Answers, Exit criteria, Verdict, Decisions to record, Not verified, Follow-ups), the destination of every Production input, and Status.
- Decisions to record: for each of D1–D7, whether it holds, changes or is reopened; the findings that support it; its grouping into ADRs; and the sections of `architecture.md` and of the [R2 source card](../sources/r2-storage.md) it affects. It is enough to write the ADRs from the closed spike (#26).
- Security requirements: from D7 and the security checks of probe A, the requirements the system needs, transferred to d002 Requirements after R14.
- Follow-ups: the post-spike documentation work of T035 (ADRs, `architecture.md`, R2 source card), in a fresh session from the closed spike (#26).
- `README.md`: How we got here.
- Not touched: `docs/decisions/`, `architecture.md` and the R2 source card, which the post-spike work writes.
- Teardown by the owner: the test lock rule, the bucket `bikesharing-s010-test` and its token; the canary `s010-token-check/canary.txt` in `bikesharing-capture-spike` if the token check created it.

#### Reads

1. This document, §1 Questions and Exit criteria.
2. This document, §2 Decision log.
3. This document, §4 Findings and Production inputs.

#### Do

1. Write the Conclusion, Decisions to record included.
2. Transfer the security requirements to d002 Requirements in its EARS form, numbered from R15; leave out any the evidence does not support, and mark D7 as reopened if probe A's token or lock check failed.
3. Set the destination of every Production input: a design with its task, or discarded with a reason.
4. Write How we got here in `README.md`.
5. Owner: remove the test lock rule, then empty and delete the test bucket, delete the token, and delete the canary if it exists.
6. Set Status to finished with the UTC date.

#### Check

- Every Q is answered, every exit criterion has a result and every Production input has a destination.
- Every decision D1–D7 has an entry in Decisions to record, with its findings and affected sections.
- d002 lists the security requirements, each traceable to a D7 threat or control.
- The Cloudflare console lists neither the test bucket nor its token.

## 4. Findings

**F1. delta-rs documents safe commits on R2 with `aws_conditional_put: "etag"`, enforced by R2 with no external lock** (step 2, 2026-10-27, `web-researcher`: delta-rs docs and source, `object_store` source, R2 S3 API; Sources)

- The delta-rs S3 docs list R2 among the stores that support `aws_conditional_put`. The default log store commits as put-if-absent; `object_store` sends PutObject with `If-None-Match: *`, and R2 evaluates it atomically, returning 412 to the loser.
- The DynamoDB locking provider (`AWS_S3_LOCKING_PROVIDER`) is no longer supported by delta-rs; `AWS_S3_ALLOW_UNSAFE_RENAME` is documented as unsafe. Neither is set.
- Consequence: D4 scored R2 fit 4 because delta-rs did not document R2; that premise no longer holds. Step 3 confirms the behaviour on R2.

**F2. The D4 gate holds on R2: write, MERGE and concurrent commits pass** (step 3, 2026-10-27, run `20261027T192323Z`, `output/probe-20261027T192323Z.jsonl`)

- Window: 2026-10-15 from 00:00, 17 minutes of `station_status` from both providers; table `s3://bikesharing-s010-test/20261027T192323Z/station_status`.
- `write`: 10 commits, version 9, 4,523 rows. `merge`: 3 commits, version 12, no duplicate key. `concurrent`: 5 commits, version 16, no duplicate key and the same result as a serial run of the same commits.

**F3. A stale MERGE on the same partition fails with a commit conflict; a stale append is retried** (step 3, 2026-10-27, run `20261027T192323Z`)

- Stale MERGE (base version 12): `CommitFailedError`, "a concurrent transactions added new data", with advice to rerun the query. The table stayed at version 14 with no duplicate key and no lost row.
- Stale append (base version 14): retried and landed on version 16 with no row lost.
- This confirms P1: the MERGE is not auto-resolved.

**F4. Commit latency on R2, direct (no proxy) and with the table load included (#27)** (step 3, 2026-10-27, run `20261027T192323Z`)

| Check | Commits | Median ms | Max ms |
|---|---|---|---|
| write | 10 | 2250 | 2560 |
| merge | 3 | 5528 | 7223 |
| concurrent | 5 | 3636 | 5432 |

- These are Q2's observed latency. A MERGE takes about 2.5 times the median of an append.

**F5. delta-rs's default checkpoint interval is 100 commits; C takes it as N** (step 4, 2026-10-27, `web-researcher`: delta-rs source; `delta_probe.py full --local`)

- `delta.checkpointInterval` defaults to 100 when unset (`crates/core/src/table/config.rs`). The post-commit hook, on by default in Python, writes a checkpoint and `_last_checkpoint` when `(version + 1)` is a multiple of the interval (`crates/core/src/kernel/transaction/mod.rs`).
- Observed locally with the test table's interval of 10: checkpoints at versions 9, 19, …, 69, and a fresh handle loads 0–9 JSON commits after the last checkpoint.

**F6. DuckDB's delta extension cannot send its log reads through the proxy; `deltalake`, Polars and `boto3` can** (step 4, 2026-10-27, `web-researcher`: duckdb-delta `delta_multi_file_list.cpp`; local routing test, `output/local/proxy-routing-test.jsonl`)

- The extension builds the delta-kernel engine from the secret's credentials, endpoint and region only; DuckDB's `http_proxy` and `ca_cert_file` do not reach it.
- Local test, a mitmproxy on a fake `.invalid` endpoint (no request to R2): `deltalake` (log reads), Polars (log and its own Parquet reads) and `boto3` went through the proxy and trusted its CA. DuckDB's kernel request did not; only its `httpfs` extension download did.
- Consequence: step 5 runs `extra --skip duckdb` in the counted run and `extra --only duckdb --no-proxy` on another day, uncounted.

**F7. Capture's `raw/` grows 95 MB a day, 2.85 GB a month, within ±10% of `architecture.md`'s 2.7 GB** (step 7, 2026-10-28, `measure_volume.py`, `output/volumes.json`; 11 complete days, 2026-10-15 to 2026-10-25)

- Means per day: AMBici `free_bike_status` 73.2 MB (77%), Bicing `station_status` 17.0 MB, AMBici `station_status` 3.2 MB, all static feeds together 1.5 MB.
- Objects per day: about 1,425 per dynamic feed (3 feeds) and 24 per static feed (14 feeds), 4,620 in all.
- +5.5% against the 2.7 GB per month of `architecture.md` §3, so C uses B's measured volumes either way.
- Spot check, Bicing `station_status` on 2026-10-15: 1,431 objects and 16,944,054 bytes, on disk and in `volumes.json` (#35).

**F8. Capture writes 1,440 `logs/` objects and 48 `state/` objects a day** (step 7, 2026-10-28, `measure_volume.py`)

- `logs/`: one object per pass, 1,440 a day (0.58 MB).
- `state/`: 48 writes a day, from 24 static passes that each write both indexes (4 KB in all; only the latest version is kept).
- Capture's writes: 6,094 a day on average (`raw/` 4,620, `logs/` 1,440, `state/` 48).

**F9. R2's PutObject count matches B's capture writes within 0.1% (4.05% with 2026-10-15)** (step 7, 2026-10-28, GraphQL Analytics API, `r2OperationsAdaptiveGroups`, `bikesharing-capture-spike`, #36)

- Daily PutObject `success` over B's 11 days: 6,343.8 on average, against B's 6,096.7 (+4.05%, within ±10%); B's values are kept (#29).
- Without 2026-10-15: 6,098.8 against 6,094.4 (+0.07%); the other days differ by −9 to +29.
- 2026-10-15 has 8,794 PutObject, 2,674 over B: 2,671 are under `V2/` (an earlier capture variant still running that day, outside B's `V4/` copy) and `V4/` has 6,123 against B's 6,120 (GraphQL `objectName` grouped by prefix).
- Failed PutObject (`internalError`): 42 on 2026-10-16, when B also counts fewer objects (5,980), and 1 on 2026-10-18.

**F10. Capture's Class A is about 183k a month, below D2's ~270–300k estimate** (step 7, 2026-10-28, F8, F9)

- B's 6,097 writes a day × 30 = 182,902 a month (190,315 with R2's mean including 2026-10-15); capture makes no LIST.
- D2's ~270–300k is 32–39% higher than measured; C uses the measured value.

**F11. Capture's own Class B is about 10 GetObject a day** (step 7, 2026-10-28, GraphQL Analytics API)

- On days with no download of the bucket (2026-10-17, 18, 20 and 22): 7 to 17 GetObject and at most 1 HeadObject a day; on download days, thousands of GetObject and HeadObject and hundreds of ListObjects.
- They match capture's code: a fresh Worker isolate reads `state/` once per source (`loadPersistedFeeds` in `V4.js`).

**F12. The Bicing history has 44.3M rows per type over 10 months, and INFORMACIO is a snapshot every few minutes, not daily** (step 7, 2026-10-28, `measure_volume.py`; 20 archives, 2025-12 to 2026-09)

- ESTACIONS: 202.6 MB as `.7z`, 2.88 GB uncompressed, 44,307,568 raw rows, 43,658,302 distinct (`station_id`, `last_reported`).
- INFORMACIO: 81.0 MB as `.7z`, 9.13 GB uncompressed, 44,306,142 raw rows; at one snapshot per day (#21), 165,131 rows.
- Both types have 238 to 278 snapshots per day on monthly average, about 541–557 stations each; no quoted newline in any archive.
- 2026-08 ESTACIONS raw rows equal its s004 parquet (3,987,120, #29); 2026-09 matches its bytes and lines.

**F13. Deduplication keeps 33% of Bicing's live `station_status` rows, but 98.5% of its history rows** (step 7, 2026-10-28, F7, F12)

- Live capture, distinct over raw records: Bicing 0.331, AMBici 0.987.
- History ESTACIONS: 0.985 (0.939–0.997 per month).
- Capture polls every minute and Bicing repeats a station until it reports again (#32); the history samples every few minutes, so fewer repeats remain.

**F14. R2's operation metrics are sampled: the total matches the proxy, per-object counts do not** (step 5, 2026-10-28, GraphQL Analytics API, `r2OperationsAdaptiveGroups`, run `20261028T132108Z`, window 13:20:09–13:40:41 UTC, #39)

- Total requests to the test bucket, failed ones included: proxy 6,048, R2 6,049 (+0.02%).
- With the `race` re-run's window (30 requests, matched exactly), the independent count is proxy 6,078 against R2 6,079 (−0.016%), within #39's ±0.5%.
- Per class: Class A proxy 514, R2 527 (+2.5%); Class B proxy 5,532, R2 5,519 (−0.2%); DeleteObjects proxy 1, R2 2.
- Per object: data files written once show 0, 2 or 6 PutObject in R2; data files the proxy saw read 54 times each show 38 to 78 GetObject.
- Failed requests appear in R2 as `userError` and match the proxy: 13 GetObject 404, 1 PutObject 409 and 1 DeleteObject 409 (the lock check).
- A query about 10 minutes after the run returned only DeleteObject, DeleteObjects and GetObject; a later one returned every operation.
- Not confirmed by the API: the dataset exposes neither `count` nor `avg { sampleInterval }` ("unknown field"), so the sampling is inferred from the per-object pattern.
- Consequence: the independent count compares totals (#39), and C takes per-class counts from the proxy.

**F15. delta-rs resolves a stale commit before its log PUT, so the `concurrent` pairs got no 412** (step 5, 2026-10-28, run `20261028T132108Z`, proxy log, #40)

- MERGE pair (base v69): the stale writer PUT its data file, then raised "a concurrent transactions added new data" with no log PUT; v70 is the other writer's.
- Append pair (base v71): the stale writer PUT v73 with `If-None-Match: *` (200) after the other writer's v72; no failed log PUT.
- Both pairs: 0 duplicate keys and the same rows as a serial run.
- Consequence: R2's put-if-absent was not exercised by delta-rs; the `race` check exercises it directly (#40).

**F16. Operations per commit: an append costs 6 Class A and 14 Class B plus 2 per JSON commit since the last checkpoint** (step 5, 2026-10-28, run `20261028T132108Z`, `analyse_ops.py` operation windows, proxy counts)

| Operation | Commits | Class A | Class B |
|---|---|---|---|
| Append, no checkpoint | 54 | 6 (5–6) | 14 + 2 per JSON commit loaded (5–30) |
| Append, writing a checkpoint | 6 | 9 | 61 (43–65) |
| MERGE, no checkpoint | 9 | 6 | 194 (187–201) |
| MERGE, writing a checkpoint | 1 | 9 | 236 |
| Stale append, retried (`concurrent`) | 2 | 5.5 (5–6) | 3.5 (2–5) |
| Optimize | 1 | 8 | 202 |
| Vacuum dry run (7-day retention) | 1 | 1 | 35 |
| Vacuum (zero retention) | 1 | 9, plus 1 DeleteObjects | 39 |

- An append's Class A is 2 PutObject (data and log) and 4 ListObjectsV2 (3 on the table's first commit); a checkpoint commit adds 2 PutObject and 1 ListObjectsV2. Its Class B grows from 14 to 28 as JSON commits accumulate after a checkpoint (`delta.checkpointInterval = 10`).
- A MERGE reads each data file of the target partition 3 times: 57 files × 3 = 171 of its about 190 GetObject.
- Median commit latency through the proxy: append 3.7 s, MERGE 24.8 s, concurrent 23.9 s, optimize 28.2 s, vacuum 5.9 s.

**F17. Parquet costs 17.3 bytes per row in per-minute files and 3.7 after optimize; a log commit is 1.2–2.1 KB** (step 5, 2026-10-28, run `20261028T132108Z`, measure windows)

- Parquet bytes per row: 17.34 after 60 appends (60 files), 15.04 after 10 MERGEs, 14.85 after `concurrent`, 3.72 after optimize (1 file); 30,858 rows at the end.
- `_delta_log` bytes per commit: append 1,218, MERGE 2,076, `concurrent` 1,601, optimize 16,596, vacuum 292.
- Checkpoints: 6 during the appends (211,211 bytes, about 35 KB each), 1 during the MERGEs (50,739 bytes).
- Bytes rewritten: 309,728 over 10 MERGEs (about 31 KB each), 85,469 in `concurrent`; optimize writes 114,738 bytes and removes 458,258.

**F18. Optimize, vacuum and both readers work on R2** (step 5, 2026-10-28, run `20261028T132108Z`)

- Optimize compacts 59 files into 1 in one partition, keeping 30,858 rows.
- Vacuum's dry run with the 7-day default finds no file; with zero retention it deletes 74 files.
- Polars reads 30,858 rows through the proxy; DuckDB's delta extension reads 30,858 rows, uncounted (F6, #38).

**F19. The test token is isolated from production, the bucket lock holds against an Object Read & Write token, and R2 enforces put-if-absent under a race** (step 5, 2026-10-28, run `20261028T132108Z`, `extra`)

- Token: list, read and write on `bikesharing-capture-spike` each return 403 `AccessDenied`; the canary was not created.
- Lock: under `locked/`, a new object is created (200); its overwrite and delete return 409 `ObjectLockedByBucketPolicy`, and its body is unchanged.
- Race: in 10 of 10 rounds both PUTs were in flight at once; R2 accepted one (200) and rejected the other (412 `PreconditionFailed`), and the winner's body was stored; each writer won 5 rounds.
- D7 is not reopened.

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|
| P1 | A MERGE that conflicts with a concurrent commit on the same partition raises `CommitFailedError` and is not auto-resolved; the pipeline retries it on a fresh table handle | Step 2 · `web-researcher` (delta-rs conflict checker) | |
| P2 | Tables are created before any concurrent writer (version-0 race on R2, delta-rs #3505), and concurrent writers do not use `schema_mode="merge"` (metadata changes are never retried, #3829 on R2) | Step 2 · `web-researcher` (delta-rs issues) | |
| P3 | The checkpoint interval N is tuned per table: it sets how many JSON commits each table load reads (2 Class B each) against how often a checkpoint is written | Step 8 · owner (#42) | |
| P4 | The cost model is recalibrated once the pipeline runs: R2's GraphQL Analytics metrics per bucket (#36) give the actual Class A, Class B and storage, which are compared with the model's prediction to adjust `params.toml` and re-run it | Step 8 · owner | |

## 5. Conclusion

Observed window: `<from–to, UTC; what it does not cover>`

### Answers

- **Q1.** `<answer>` (FN)

### Exit criteria

| Criterion | `<Variant A>` | `<Variant B>` |
|---|---|---|
| | | |

### Verdict

### Decisions to record

| D | Outcome | Findings | ADR | Sections affected |
|---|---|---|---|---|
| D1 | `<holds, changes or reopened>` | | | |

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

Gathered by the `web-researcher` on 2026-10-27 for step 2 (delta-rs `main`; `deltalake` 1.6.6):

- delta-rs on S3-compatible stores: <https://raw.githubusercontent.com/delta-io/delta-rs/main/docs/integrations/object-storage/s3-like.md>
- delta-rs AWS storage options and locking provider: <https://raw.githubusercontent.com/delta-io/delta-rs/main/crates/aws/src/storage.rs>
- delta-rs commit loop and retries: <https://raw.githubusercontent.com/delta-io/delta-rs/main/crates/core/src/kernel/transaction/mod.rs>
- delta-rs conflict checker: <https://raw.githubusercontent.com/delta-io/delta-rs/main/crates/core/src/kernel/transaction/conflict_checker.rs>
- delta-rs Python exceptions: <https://raw.githubusercontent.com/delta-io/delta-rs/main/python/deltalake/exceptions.py>
- `object_store` conditional put on S3: <https://raw.githubusercontent.com/apache/arrow-rs-object-store/main/src/aws/mod.rs>
- delta-rs issues on R2: <https://github.com/delta-io/delta-rs/issues/3505>, <https://github.com/delta-io/delta-rs/issues/3829>
