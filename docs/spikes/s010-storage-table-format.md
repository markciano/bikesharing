# Spike: Storage and table format

- **Task:** T035
- **ADRs:** ADR-0005, ADR-0009, ADR-0011
- **Code:** `spikes/storage-table-format/`

## Status

- State: Draft 📝
- Phase: [x] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### Context

T035 decides where the medallion layers (ADR-0018) live, their table format, their retention and their security baseline, and whether capture (ADR-0011) stays as it is. These decisions were taken by analysis while framing the spike (D1–D7, below). The run only provides the evidence that D2 (R2 within quotas and budget) and D4 (Delta Lake works on R2) depend on. T036 (engine), T039 (capture in production) and T042 build on the outcome.

The owner runs capture always on and the pipeline on demand: it can stay off for days, catch up on what is pending before a demo, and run live during it (d002).

### Decided at framing

Decisions taken by analysis while framing the spike, without a run. The ADRs are written at Conclusion unless decided otherwise per case.

#### D1. Own lakehouse on object storage

Decided 2026-10-25. Every medallion layer (ADR-0018) is stored as files in open formats in an object store, and compute runs separately from storage.

- Rejected: silver and gold in a managed analytics platform (warehouse), because it ties storage to that platform's engine and free quotas, and merges this decision with the engine choice (T036).

#### D2. Cloudflare R2 is the object store for every layer, subject to the volume and operations calculation

Decided 2026-10-25.

- Capture already lands in R2 (ADR-0011), so bronze needs no move and capture stays as it is.
- R2 charges no egress, so the pipeline can run anywhere (T036) without paying to read its data.
- Storage above the free 10 GB-month costs about $0.015/GB-month: even 50 GB stays well under the project's €10/month (d002 R4).
- The open risk is operations, not storage: the pipeline's listings, reads and writes add to capture's ~270–300k Class A per month (`raw/`, `logs/`, `state/`; estimate, measured by probe A) against the free 1M. A Q verifies it; R2 is compared with another store only if it fails a hard constraint.
- Rejected: comparing another store (e.g. Backblaze B2) from the start, because no constraint currently argues against R2.

#### D3. Bronze is the captured `json.gz` objects as they are

Decided 2026-10-25. No bronze table is built from them.

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

Decided 2026-10-25. Chosen with a weighted decision matrix: hard cut first, then scores against anchors fixed before scoring. Facts gathered by the `web-researcher` on 2026-10-25 (Sources).

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

Decided 2026-10-25.

- Silver and gold are rebuilt from bronze (d002 R13), so whatever is deleted from bronze can never be rebuilt.
- The longest gold windows are 12 months (Q3, Q4, Q6, Q7), and Q8 covers changes since the earliest archive loaded.
- Raw grows about 2.7 GB per month, about 33 GB per year (measured 2026-10-14 to 2026-10-24, `architecture.md` §3); above the free 10 GB it costs about $0.015/GB-month, under $0.40/month at month 12.
- Rejected: a rolling window of 12 months plus a margin, because no rule change could then be applied to older data, and Q8 would depend on what silver kept.

#### D6. Silver keeps a rolling 12 months, gold is kept indefinitely, and Delta keeps 7 days of history

Decided 2026-10-25.

- Silver holds bronze's observations as a table: parsed, deduplicated, typed, in UTC and on the common model (ADR-0008); gold holds hourly and daily aggregates.
- Both are rebuildable from bronze (D5), so their retention trades storage against rebuild cost, with no data at risk.
- Silver covers the longest gold window (12 months), so gold is recomputed without re-parsing bronze; older silver is rebuilt from bronze if ever needed.
- Gold is small and is what the public sees.
- Seven days of Delta history (old file versions removed by vacuum) is Delta's default and is enough to undo a recent error.
- This is the usual decreasing retention: bronze longest, silver shorter, gold by its use.
- Rejected: keeping every layer indefinitely; simpler, since no silver partitions are deleted, but silver grows without bound alongside bronze. It is reconsidered if the calculation shows it equally cheap.

#### D7. Storage security baseline

Decided 2026-10-26. Security is treated explicitly, not left implicit: R2 holds the only copy of bronze, and its credentials give access to both the data and the bill. Threats are listed with STRIDE, and each control follows least privilege (NIST SP 800-53, AC-6).

| Threat | Impact | Control |
|---|---|---|
| Leaked credentials | An attacker deletes or overwrites data, or drives up cost with requests (denial of wallet) | One token per component, with only the access it needs; secrets in `.env`, never in code; bronze protected by a bucket lock |
| A pipeline bug writes to bronze | Bronze cannot be rebuilt (D5), so the damage is permanent | The pipeline has read-only access to the bronze bucket; only capture writes it |
| A bucket is made public by mistake | Anyone can list and read all data, and every read costs | Buckets stay private, which is R2's default; public access to gold only as T038 decides |

Two buckets, because R2 API tokens scope to whole buckets, not key prefixes ([R2 source card](../sources/r2-storage.md)), so a read-only bronze needs its own bucket:

- **bronze**: capture's existing bucket, with an indefinite bucket lock on the `raw/` and `logs/` prefixes that blocks deletes and overwrites. Both only receive new objects and neither can be rebuilt; the logs attribute gaps to capture or provider (QS5). `state/` holds capture's working index, rewritten on every pass and rebuildable from `raw/`, so it stays unlocked;
- **lakehouse**: silver and gold together, since both have the same access pattern.

Access per component:

| Component | Bronze bucket | Lakehouse bucket |
|---|---|---|
| Capture | Write | None |
| Pipeline | Read | Read and write |
| Visualization (T038) | None | Read |
| Spike probes | None | None; a separate test bucket only |

- R2 has no object versioning, so the bucket lock is the only guard against losing bronze. Only an Admin token can remove a lock rule; the owner keeps that token and uses it only for D5's cost review.
- TODO: before the lock is enabled, confirm that capture writes each key under `raw/` and `logs/` once (ADR-0012 key layout); the lock would also block a capture retry that rewrites a key.
- Probe C checks that its test token cannot read or write the production buckets, and whether a bucket lock blocks a delete made with an Object Read & Write token (the docs do not say).
- Rejected: one token with read and write on everything. It is simpler, but a single leak or pipeline bug puts bronze at risk.
- Rejected: one bucket per layer. It would let the visualization read gold alone, but T038 has not decided how gold is served; gold moves to its own bucket then if needed.

### Questions

Main question: does the own lakehouse on R2 with Delta Lake (D1–D7) hold within the project's €10/month budget (d002 R4) and R2's quotas?

#### Q1. Cost calculation

What storage per layer and how many Class A and Class B operations per month do capture and pipeline need in each scenario, with Delta's operations per commit measured in Q2 and the retention of D5 and D6; do they fit R2's free quotas, and what do they cost per month and accumulated at months 2, 4, 6 and 12? Gate for D2.

- Scenarios, all with capture always on:
  - pipeline running 24/7 with a commit every 1, 5, 10, 30 and 60 minutes, and every 6 hours;
  - on-demand mode: a grid of catch-ups per month (4, 6, 8, 10) by hours of live use per month (0.5, 1, 2, 3), with live commits every minute, each cell adding both; the cell judged is 10 catch-ups + 2 h live.
- Cadences above 5 minutes do not meet the 5-minute freshness of d002 Q1. They show how cost falls as freshness is relaxed, an input for T039.
- In a catch-up, listing and reading the pending objects costs the same as processing them minute by minute; what falls is the number of commits.
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
- **Storage cost** — no month within 12 months costs more than €2 in R2 storage and operations, in the on-demand cell of 10 catch-ups + 2 h live (Q1) — hard cut. The 24/7 scenarios and the other cells are reported, not judged. The same €2 is the review threshold of D5.
- **D2 gate (Q1)** — if the worst case (1-minute commits 24/7) fits, D2 holds without conditions; if only the on-demand mode fits, D2 holds with an operating constraint, recorded as a Production input; if neither fits, D2 is reopened — hard cut.
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

Three probes run in this order. C goes first because it tests the riskiest assumption (D4) and its result changes B: if Delta fails on R2, Iceberg is probed in turn and Basin Catalog's cost enters the model.

| Order | Probe | Answers | Feeds |
|---|---|---|---|
| 1 | C. Delta on R2 | Q2 (D4 gate); commit latency (observed) | Measured operations per commit → B |
| 2 | A. Measured volume | Inputs for Q1 | Storage and capture operations → B |
| 3 | B. Cost model | Q1 (D2 gate) | — |

#### C. Delta on R2

- **What:** `deltalake` against a test R2 bucket with a small data sample.
- **Data:** real `station_status` responses from both providers, a few hours from the local capture copy (`spikes/cloudflare-capture-spike/data/V4/raw/`), flattened to rows (station, time, bikes, docks). Commits mimic 1-minute runs, partitioned by day, so each commit touches one partition; MERGE runs on real keys (station + time).
- **Checks,** in the order of the D4 gate: write, MERGE, two concurrent commits (hard cut); optimize, vacuum, reads from Polars and DuckDB (guide).
- **Measures:** the R2 operations per commit, by class (A, B); the latency of each commit; Parquet bytes per row in the written table, so B can size silver.
- **Security (D7):** uses a token scoped to the test bucket and checks that it cannot read or write the production buckets; sets a bucket lock on a prefix of the test bucket and tries to delete and overwrite an object under it with the Object Read & Write token.
- **Where it runs:** on the owner's Mac, against a test bucket in the production Cloudflare account, with an Object Read & Write token scoped to it.
- **Counting:** a local proxy between `deltalake` and R2 logs every request and classifies it by the [R2 source card](../sources/r2-storage.md); the test bucket's R2 metrics give a second, independent count.
- **Evidence:**
  - the proxy logs one JSON line per request: UTC time, method, path, status, bytes, duration;
  - the probe logs each check's start, end, result (ok or error message) and commit latency;
  - an analysis script joins both logs by time window (checks run one after another) into operations per check, step and class;
  - logs and results go to an `output/` folder ignored by Git (ADR-0009); summary tables are copied into Findings.
- **Analysis checks:**
  - known arithmetic: an append of one file gives one data PUT and one log PUT;
  - independent count: proxy total against R2 metrics;
  - fault injection: one of two concurrent commits must conflict and retry.
- **Clean-up:** a final step removes the test lock rule, then deletes the bucket and the token; a locked bucket cannot be emptied, so the lock rule goes first.
- An Iceberg probe is not planned; it is built only if the D4 gate fails (Exit criteria).

#### A. Measured volume

- Runs on the owner's local copies, not the production bucket, so it spends no R2 operations:
  - `spikes/cloudflare-capture-spike/data/V4/`: about 10 days of the production bucket, with the same layout (`raw/`, `logs/`, `state/`);
  - `spikes/bicing-spike/historical-data/raw/`: the Bicing history archives (`.7z`, January–September 2026, d002 R5).
- Measures:
  - `raw/`: objects, bytes and records per feed and day; the first and last days are dropped as incomplete;
  - `logs/` and `state/`: objects, bytes and writes per day, as capture's own Class A operations and storage;
  - history: size as `.7z` and uncompressed.
- Writes one volumes file that B reads.
- s005's estimates are used only where nothing is measured.

#### B. Cost model

- **What:** a script that computes, for each scenario in Q1 (24/7 cadences and the on-demand grid) and for months 2, 4, 6 and 12, storage per layer and Class A and Class B operations per month, and their monthly and accumulated cost against R2's free quotas and prices.
- **Inputs:** A's volumes, C's measured operations per commit, the commit model below, and the retention of D5 and D6.
- **Commit model:**
  - silver has one table per feed type on the common model (9: 2 dynamic, 7 static); gold has one table per guiding question (8);
  - a table commits at most once per run, and only when it has new data;
  - in live and 24/7 runs, a gold table commits no more often than its question's freshness (`architecture.md` §1.1): Q1, Q2, Q5 every run; Q3, Q4, Q7 hourly; Q6, Q8 daily;
  - so in a 1-minute run only 5 tables commit: the 2 dynamic silver tables and gold Q1, Q2, Q5; static silver tables commit once a day, when their feed is captured (`architecture.md` §1.1);
  - a catch-up commits once per table and pending day;
  - table counts and cadences are parameters.
- **Sizing:** silver size is A's records per day times C's Parquet bytes per row, so no compression ratio is assumed.
- **Output:** cost per layer as well as the total; capture's `logs/` and `state/` writes are reported apart from `raw/`, so their share of the quota is visible.
- **Runs** once, after C and A; parameters are kept apart from the logic so the model can be re-run with new inputs.
- **Prices, quotas and operation classes** come from the [R2 source card](../sources/r2-storage.md). Assumptions where the pricing page is silent:
  - the free tier is shared by every bucket in the account (pessimistic);
  - a conditional PutObject is Class A, ListObjectsV2 is Class A as ListObjects, and DeleteObjects is free as DeleteObject; C confirms them on the test bucket's metrics;
  - deletes (silver retention, vacuum) are free, so they add no cost.

### Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-25 | On-demand mode is a grid of catch-ups by live hours; the hard cut is judged at 10 catch-ups + 2 h live (see Q1) | Catch-ups and live use vary independently; the judged cell is the owner's pessimistic expected use |
| 2026-10-25 | The 24/7 scenarios are calculated and reported, not judged (see Q1) | The calculation is free; the cost curve as freshness is relaxed is an input for T039 |
| 2026-10-25 | Commit model: tables commit only with new data, gold at its question's freshness (see B) | An incremental pipeline writes only tables with new data; table counts stay pessimistic |
| 2026-10-26 | The cost model runs once, with measured operations per commit; the former Q3 is merged into Q1 (see B) | Measured data prevails over estimates; the pessimism lives in the scenarios |
| 2026-10-26 | Probe C counts operations with a local proxy, cross-checked against R2 metrics (see C) | Exact counts per commit and step; two independent counts check each other |
| 2026-10-26 | Probe C runs on the owner's Mac against a scoped test bucket in the production account (see C) | About 1,000 operations per run, under 1% of the quota; the scoped token isolates production (D7) |
| 2026-10-26 | Probe C evidence is logged to files and checked by an analysis script (see C) | Evidence must be reproducible and checked, not read off the console |
| 2026-10-26 | Probe C writes real `station_status` data from the local capture copy (see C) | File sizes and MERGE keys match the real pipeline; synthetic data would invent both |
| 2026-10-26 | Probe A measures `raw/`, `logs/` and `state/` separately on the local copy, plus the Bicing history (see A) | The local copy mirrors the bucket and spends no operations; `logs/` and `state/` are capture writes too |
| 2026-10-26 | Silver is sized from A's records and C's Parquet bytes per row (see B) | Two measurements replace an assumed compression ratio |
| 2026-10-26 | The bronze bucket lock covers `raw/` and `logs/`, not `state/` (see D7) | `state/` is rewritten on every pass, so a lock would break capture |
| 2026-10-26 | Q1 reports cost at months 2, 4, 6 and 12; the hard cut is €2 in any month, raised from €1 (see Q1, Exit criteria) | The measured volume (about 33 GB/year) is 2–4 times s005's estimate, so storage alone could approach €1 at month 12 |

### File layout

```text
spikes/storage-table-format/
├── README.md          Question, setup, commands, what each script does; link to s010; How we got here (written at Conclusion)
├── pyproject.toml     Pinned Python and locked dependencies (ADR-0016, ADR-0017)
├── uv.lock
├── .env.example       Test bucket endpoint and scoped token, empty values
├── r2_proxy.py        C: logging proxy between deltalake and R2, one JSON line per request
├── delta_probe.py     C: write, MERGE, concurrency, optimize, vacuum, reads, token and lock checks
├── analyse_ops.py     C: joins proxy and probe logs; operations per check, step and class; the three checks
├── measure_volume.py  A: raw/, logs/, state/ and history volumes
├── cost_model.py      B: scenarios × months, cost per layer and total
├── params.toml        B: every parameter (tables, cadences, retention, prices), apart from the logic
└── output/            Ignored by Git (ADR-0009): logs, volumes, operation and cost tables
```

## 3. Steps

### Step 1 — `<title>`

- **Status:** 💤 todo
- **Who:** Owner
- **Commit:** following the Git conventions in CLAUDE.md.
- **R:** —
- **Model:** —
- **Gate:** `<condition>` → `<consequence>`

#### Scope

#### Reads

#### Do

#### Check

### Step N — Conclusion

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
