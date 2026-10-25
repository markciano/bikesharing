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

T035 decides where the medallion layers (ADR-0018) live, their table format and their retention, and whether capture (ADR-0011) stays as it is. These decisions were taken by analysis while framing the spike (D1–D6, below). The run only provides the evidence that D2 (R2 within quotas and budget) and D4 (Delta Lake works on R2) depend on. T036 (engine), T039 (capture in production) and T042 build on the outcome.

The owner runs capture always on and the pipeline on demand: it can stay off for days, catch up on what is pending before a demo, and run live during it (d002).

### Decided at framing

Decisions taken by analysis while framing the spike, without a run. The ADRs are written at Conclusion unless decided otherwise per case.

- **D1. Own lakehouse on object storage** (2026-10-25). Every medallion layer (ADR-0018) is stored as files in open formats in an object store, and compute runs separately from storage. Rejected: silver and gold in a managed analytics platform (warehouse), because it ties storage to that platform's engine and free quotas, and merges this decision with the engine choice (T036).
- **D2. Cloudflare R2 is the object store for every layer, subject to the volume and operations calculation** (2026-10-25).
  - Capture already lands in R2 (ADR-0011), so bronze needs no move and capture stays as it is.
  - R2 charges no egress, so the pipeline can run anywhere (T036) without paying to read its data.
  - Storage above the free 10 GB-month costs about $0.015/GB-month: even 50 GB stays well under the project's €10/month (d002 R4).
  - The open risk is operations, not storage: the pipeline's listings, reads and writes add to capture's ~220k Class A per month (s005) against the free 1M. A Q verifies it; R2 is compared with another store only if it fails a hard constraint.
  - Rejected: comparing another store (e.g. Backblaze B2) from the start, because no constraint currently argues against R2.
- **D3. Bronze is the captured `json.gz` objects as they are** (2026-10-25). No bronze table is built from them.

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
- **D4. Delta Lake is the table format for silver and gold, subject to the probe on R2** (2026-10-25). Chosen with a weighted decision matrix: hard cut first, then scores against anchors fixed before scoring. Facts gathered by the `web-researcher` on 2026-10-25 (Sources).
  - Hard cut: reads and writes from Python without JVM or cluster, and adds no paid service whose cost breaks the project's €10/month (d002 R4). All three candidates pass; Iceberg only conditionally, because its catalog options are Cloudflare Basin Catalog (formerly R2 Data Catalog; GA 2026-10-01; paid above 1M catalog operations per month) or a SQLite catalog the PyIceberg docs mark as test-only.
  - Anchors (2 and 4 are in between):

  | Criterion (weight) | 1 | 3 | 5 |
  |---|---|---|---|
  | Portfolio value (5) | Not a table format | Recognised, but tied to one vendor's ecosystem | Standard backed by several major vendors |
  | Python single-node maturity (4) | No MERGE/upsert, no atomic commits | Append, overwrite and upsert stable; maintenance (compaction, expiry) missing or experimental | All stable, maintenance included, in a release ≥ 1.0 |
  | R2 fit (4) | Needs a service outside R2 that is unsupported or unaffordable | Works on R2 with an extra component (catalog, lock) or a method not documented for R2 | Works on R2 alone, with documented safe commits |
  | Single-node engine support (3) | Neither Polars nor DuckDB reads it | Both read it; writing is missing in one or limited | Both read and write it natively and stably |
  | Operational simplicity (3) | Needs a service to keep running | Needs a managed service or credentials beyond the bucket | Only the bucket and its credentials |
  | Learning value (2) | No concept beyond files | One core concept (e.g. transaction log) | Several: log or snapshots, catalog, concurrency, maintenance |

  - Scores (total = Σ score × weight, maximum 105, normalised to 0–10):

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
- **D5. Bronze is kept indefinitely, reviewed only above a cost threshold** (2026-10-25).
  - Silver and gold are rebuilt from bronze (d002 R13), so whatever is deleted from bronze can never be rebuilt.
  - The longest gold windows are 12 months (Q3, Q4, Q6, Q7), and Q8 covers changes since the earliest archive loaded.
  - Raw grows about 0.7–1.4 GB per month (s005), 8–17 GB per year; above the free 10 GB it costs about $0.015/GB-month, cents per year.
  - Rejected: a rolling window of 12 months plus a margin, because no rule change could then be applied to older data, and Q8 would depend on what silver kept.
- **D6. Silver keeps a rolling 12 months, gold is kept indefinitely, and Delta keeps 7 days of history** (2026-10-25).
  - Silver holds bronze's observations as a table: parsed, deduplicated, typed, in UTC and on the common model (ADR-0008); gold holds hourly and daily aggregates.
  - Both are rebuildable from bronze (D5), so their retention trades storage against rebuild cost, with no data at risk.
  - Silver covers the longest gold window (12 months), so gold is recomputed without re-parsing bronze; older silver is rebuilt from bronze if ever needed.
  - Gold is small and is what the public sees.
  - Seven days of Delta history (old file versions removed by vacuum) is Delta's default and is enough to undo a recent error.
  - This is the usual decreasing retention: bronze longest, silver shorter, gold by its use.
  - Rejected: keeping every layer indefinitely; simpler, since no silver partitions are deleted, but silver grows without bound alongside bronze. It is reconsidered if the calculation shows it equally cheap.

### Questions

Main question: does the own lakehouse on R2 with Delta Lake (D1–D6) hold within the project's €10/month budget (d002 R4) and R2's quotas?

- **Q1. Rough calculation.** What storage per layer and how many Class A and Class B operations per month do capture and pipeline need, with a pessimistic figure for Delta's operations per commit, in each cadence scenario; do they fit R2's free quotas, and if not, what do they cost against €10/month? Gate for D2.
  - Scenarios, all with capture always on:
    - pipeline running 24/7 with a commit every 1, 5, 10, 30 and 60 minutes, and every 6 hours;
    - on-demand mode: a weekly catch-up plus a few hours of live demo per month.
  - Cadences above 5 minutes do not meet the 5-minute freshness of d002 Q1. They show how cost falls as freshness is relaxed, an input for T039.
  - In a catch-up, listing and reading the pending objects costs the same as processing them minute by minute; what falls is the number of commits.
  - Capture volume is measured, not estimated: objects, bytes and records per feed and day from the production bucket and capture's log, about 10 days of real capture so far. s005's estimates are used only where nothing is measured.
- **Q2. Delta on R2.** Against a real R2 bucket with `deltalake`:
  - Does it write?
  - Does it MERGE?
  - Does it keep concurrent commits safe?
  - Do optimize and vacuum work?
  - Do Polars and DuckDB read the table?
  - Gate for D4.
- **Q3. Final calculation.** With the operations per commit measured in Q2 in place of the pessimistic figure, what is the monthly cost at 12 months out, in each Q1 scenario, with the retention of D5 and D6?
- **Observe only:** the latency of a commit on R2, which counts against the 5-minute freshness of d002 Q1.

### Exit criteria

- **Standard:** hard constraints first, then a gate per question that confirms or reopens its decision (D2, D4). The choice between options was already made with a weighted decision matrix (D4) and is not repeated in the run.
- **Timebox:** one day of run. It ends when Q1–Q3 are answered or the day runs out; then the decision is taken on the evidence gathered and the gaps go to Not verified. If the D4 gate fails, half a day is added for the Iceberg probe, recorded in the Decision log.
- **Storage cost** — R2 storage and operations cost at most €1/month at 12 months in the on-demand mode (Q1, confirmed in Q3) — hard cut. Expected is about €0.15/month; €1 means the estimate is wrong by an order of magnitude. The 24/7 scenarios are reported, not judged. The same €1 is the review threshold of D5. The remaining €9 of d002 R4 is left to the other components; T036 or T038 may ask to rebalance it.
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

## 2. Method — how we find out

### Approach

| Variant | What it is | What it tells |
|---|---|---|
| | | |

### Shared behaviour

-

### Decision log

| Date | Decision | Reason |
|---|---|---|
| | | |

### File layout

```text
spikes/storage-table-format/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
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
