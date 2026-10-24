# Decision plan worksheet (provisional)

TODO: delete when T022 closes. Its results live in `docs/architecture.md`, the ADRs and `docs/tasks.md`.

## Status (2026-10-24)

- Done: ADR review; `docs/architecture.md` created; task table reordered (T034–T041); Spark and Java removed from live docs; ADR-0003 and ADR-0004 archived as rejected; archive rule in `.claude/rules/adr.md`; `CLAUDE.md` structure updated.
- Next session: rewrite ADR-0012 in place (and the Python collector `TODO:` in the Worker section of `docs/testing-strategy.md`); point T022 to `docs/architecture.md`; delete this worksheet; close T022.

Worksheet for T022: reviews the existing ADRs and tasks against an ordered decision plan. Nothing here is a decision until it reaches one of those three places.

## Standard

- Decision map ordered by dependencies, each decision taken at the last responsible moment.
- ADR lifecycle (Nygard): accepted, superseded, deprecated.
- Task backlog in topological order.

Decision order: requirements and data characteristics → storage and table format → processing engine → execution target → visualization.

## Inputs

- **Scope:** the plan covers every component, including the existing real-time capture; where capture stores data is reassessed with the storage decision. Both providers are built together: the common model (ADR-0008) exists to unify them, so one provider alone would not test it.
- **Cost:** €0 is the intent; a small cost may be approved once the execution target is evaluated (guide, not hard cut).
- **Measured volume:** about 90 MB/day compressed and about 5,700 objects/day at a 1-minute capture interval (R2 console, 2026-10-14 to 2026-10-24); about 33 GB/year. Which data is kept is left to the storage decision.
- **Capture requirements:** dynamic feeds every minute, static feeds once a day; responses requested gzip-compressed from the origin and stored unchanged; about 3–4 ms of CPU per pass for all feeds. Detail in the Conclusion of [s006](spikes/s006-cloudflare-capture.md). TODO: confirm the figures against s006 before they reach `docs/architecture.md`.
- **Engine:** distributed engines such as Spark are out, oversized for this volume; only single-node engines are compared. Spark and Java removed from the live docs (`docs/testing-strategy.md`, `.claude/rules/python.md`, `dependencies.md`, `ci.md`).

## Decision map

Each decision becomes a task: a spike when it needs measuring, a design when reasoning is enough. Build tasks follow the decision they depend on.

| # | Decision | Sets | Evidence needed | Depends on |
|---|---|---|---|---|
| D1 | Requirements | Consumers, questions answered, freshness (minutes or hours), public or not, whether Bicing history enters | s004; measured volume | — |
| D2 | Storage and table format | Where raw data and tables live, retention, table format (Parquet, Delta, Iceberg); reassesses capture (ADR-0011) | R2 free tier; catalog and format findings | D1 |
| D3 | Processing engine | Single-node engine and pipeline language | Minimal script: read `json.gz`, write and read a table in the D2 format | D2 |
| D4 | Execution target | Where the pipeline runs and what schedules it | Free tiers that run the D3 engine | D3 |
| D5 | Visualization | Tool and where it is published | Where the consumption layer lives (D2, D4); public or not (D1) | D1, D2, D4 |

## ADR review

| ADR | Review | Result | Reason |
|---|---|---|---|
| 0003 build locally first, Fabric later | In depth | Retire | Bundles three plan decisions (table format, engine, execution target) taken before requirements; Spark and Fabric are already out. |
| 0010 ingestion logic separated from platform | In depth | Replace after the architecture is defined | The principle holds for processing (logic separated from what runs it, so it is tested without the platform); collectors are covered by ADR-0012 instead. The "plain Python" constraint goes: languages follow from the plan. |
| 0011 Cloudflare Workers + R2 for capture | In depth | Reassess with the storage decision | Worker and R2 stand or fall together. If the storage decision moves raw data off R2, a new ADR with the chosen capture tool replaces it. What was learned carries over as capture requirements (Inputs). |
| 0012 collectors decoupled by output contract | In depth | Rewrite in place (Proposed) | The landing zone with an output contract holds: key layout, UTC capture time, origin bytes unchanged; the pipeline depends only on the files. Goes: the on-demand local Python collector (one collector only), the amendment to ADR-0010 (the replacement of 0010 scopes itself), and "bronze layer" (layer names belong to the pipeline design). |
| 0016 runtime versions pinned per component | In depth | Hold | Generic rule, independent of the architecture; pins no concrete version. |
| 0017 dependencies locked per component | In depth | Hold | Generic rule, independent of the architecture. d001, the closed design behind 0016 and 0017, is a historical record and is not edited. |
| 0002 data sources AMBici and Bicing | Quick check | Hold | Chooses the sources; independent of the architecture. |
| 0005 UTC for all stored timestamps | Quick check | Hold | UTC in storage, local time only when presenting; independent of the architecture. |
| 0006 raw layer keeps source responses untouched | Quick check | Hold | Reprocessing from raw is bounded by storage capacity: the storage decision sets retention; dropping raw would supersede this ADR. |
| 0008 common model on GBFS 3.0 | Quick check | Hold | Unifies the two sources' schema versions; independent of the architecture. |
| 0009 trimmed source samples as test fixtures | Quick check | Hold | Testing rule; independent of the architecture. |
| 0004 real time against batch baseline | — | Retire | Product decision taken before requirements. |

Only valid ADRs stay in `docs/decisions/`. An ADR that stops holding moves to `docs/decisions/archive/` with its status: `Rejected` if it was never accepted, `Superseded` or `Deprecated` if it was. Numbers are not reused. Links to a moved ADR are updated in the same commit. `.claude/rules/adr.md` gains the `Proposed → Rejected` transition and the move to `archive/`.

## Task reframing

| Task | Today | Result |
|---|---|---|
| T007 | GBFS ingestion spec and plan | Delete; replaced by the decision map tasks |
| T025 | Data processing pipeline spec and plan | Delete; replaced by the decision map tasks |
| T033 | Visualization tool within the s009 runtime model | Delete; replaced by the decision map tasks |
| New | — | T034 D1 Requirements · T035 D2 Storage and table format · T036 D3 Processing engine · T037 D4 Execution target · T038 D5 Visualization. New IDs, not reused: closed docs cite T007 and T025. |
| New | — | Build tasks, created now as parents and split into TNNN.M in their design: T039 Capture in production (depends on T035) · T040 Processing pipeline (T036, T037) · T041 Visualization (T038, T040). |
| T015 | Match Bicing October archive against real-time capture (⛔) | Depends on T034: worth doing only if D1 brings Bicing history in |
| T010 | Write README | Depends on T034–T038: the README tells the architecture |
| T023, T026, T027 | Process tasks | No change: independent of the architecture |
| T024 | Hooks: code conventions for Python, JS, Spark and SQL | Drop the languages, keep the concept: hooks for code conventions of the project's languages |

## Open questions

| Question | Goes to |
|---|---|
| Does Bicing history enter the solution? Answer from [s004](spikes/s004-bicing-historical-data.md); AMBici has no history ([s003](spikes/s003-ambici-historical-data.md)). | Requirements |
| R2 free tier for storage and operations, and whether only part of the history is kept in R2. | Storage |
| Iceberg (native to R2 Data Catalog) as an option next to Delta and plain Parquet. | Storage |
| A minimal script that reads `json.gz` from R2 and writes and reads a table in the chosen format. | Engine |

## Findings with official sources

Accessed 2026-10-23.

- **R2 S3 compatibility:** ListObjectsV2, multipart upload and atomic conditional PutObject (`If-None-Match`) are supported; bucket versioning, policies, ACLs and tagging are not. Region is `auto`. <https://developers.cloudflare.com/r2/api/s3/api/>
- **R2 endpoint:** `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`. <https://developers.cloudflare.com/r2/examples/aws/aws-cli/>
- **R2 Data Catalog:** uses Apache Iceberg; no official Cloudflare example uses Delta Lake. <https://developers.cloudflare.com/r2/data-catalog/config-examples/spark-python/>
- **Delta Lake on S3-compatible storage:** safe with a single writer per table; multi-writer needs DynamoDB (AWS only). <https://docs.delta.io/latest/delta-storage.html>
