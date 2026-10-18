# Project ideas summary

Status: exploratory. Nothing here is approved; these are ideas to feed future tasks, ADRs and designs.

## 1. Overall architecture

- Three zones, each able to move to the cloud independently:
  1. **Collect**: raw data arrives through three paths (see §2).
  2. **Process** (local for now): bronze → silver → gold.
  3. **Serve** (local): visualization reads only from gold.
- Pattern: **decoupled landing zone**. Collection only drops raw files; it knows nothing about processing. Allows full reprocessing when silver/gold logic changes.
- Timing per path:
  - Cloud capture is real time, but processed in **batch** when downloaded from R2 (hours or days later).
  - Local capture is processed in **micro-batches** as it arrives (near real time).

## 2. Data sources

| Path | Systems | Run by | When | Raw format | Feeds |
|---|---|---|---|---|---|
| A. Cloud capture | AMBici, Bicing | Cloudflare Worker → R2 | Always on, automatic | API JSON | Historical view |
| B. Local capture | AMBici, Bicing | Local machine → local disk | A few minutes, on demand | API JSON | Live view (disposable) |
| C. Monthly published history | Bicing only | Owner, manual download | Monthly | `.7z` | Historical view (deferred) |

- C could backfill gaps in Bicing data. Deferred: adds complexity.

## 3. Collector

- The Worker runs the capture code; R2 only stores the output.
- A and B do the same job (call the APIs, store the raw response) in two places. They share an **output contract**: same raw payload, UTC capture timestamp (ADR-0005) and file naming, so the pipeline cannot tell them apart.
- C is not a collector: it is a manual operational action with its own format. The contract does not apply to it.
- TODO: decide whether the collector code lives in this repo or a separate one.

## 4. Processing

- Kappa-style: **one pipeline**, written once (bronze → silver → gold), run in two modes:
  - Process what has arrived and stop — for A (candidate: Spark Structured Streaming `Trigger.AvailableNow`).
  - Keep listening, micro-batches — for B (candidate: `processingTime` trigger).
- Rejected alternative: Lambda (two separate pipelines, duplicated transformation logic).
- Each path gets its own bronze step; C needs its own extraction because of its format. From silver on, everything is shared.
- Silver records the source of every row, so C can be added later without rework.
- Deduplication in silver (station + observation time), within each source.
- Precedence for Bicing (when C is added): **A wins over C**, because A comes in the latest schema version; C only fills gaps.

## 5. Storage and configuration

- The pipeline does not know where data physically lives: storage roots come from configuration (local path today, object storage later).
- Two **configuration profiles**, each with its own storage root and the same layer layout.
- Landing is split by source, named by origin rather than technology (so changing cloud provider does not rename folders):

```
data/                  historical profile (kept)
├── landing/
│   ├── realtime/      path A, downloaded from R2, as is
│   └── history/       path C, .7z files, as is
├── bronze/            .7z extracted here, not in landing
├── silver/
└── gold/

data-live/             live profile (disposable)
├── landing/
│   └── realtime/      path B, written by the local collector
├── bronze/
├── silver/
└── gold/
```

- Live data never mixes with historical data, so A and B never overlap.
- Both roots are Git-ignored (ADR-0009). An occasional local capture can be copied by hand as a test fixture.
- Folder names are provisional.

## 6. Gold and visualization

- Two views:
  1. **Historical**: time series (e.g. occupancy by hour, by station). Fed by A (and C later).
  2. **Live**: append-only records from B; the visualization decides whether to show the latest value per station or a time window. Map area filtering is done in the app, not in the pipeline.
- Visualization is a **separate consumer of gold**; its stack (BI tool, local web app…) can be chosen later without touching the pipeline.
- Gold shape will be driven by the questions to answer (dimensional modelling, Kimball).
- TODO: brainstorm the questions and visualizations; this defines gold.

## 7. Repository layout

- Candidate: **monorepo organized by deployable unit**, with the PyPA `src` layout for Python code.

```
.
├── collector/          paths A and B (not C: manual)
├── src/bikesharing/    Python/Spark pipeline (bronze, silver, gold)
├── apps/               gold consumers: dashboards, local web app
├── infra/              cloud config / IaC
├── tests/  docs/  spikes/
```

- Rejected so far: single Python package for everything (mixes runtimes); separate repos per component (too much friction for a portfolio project).
- `collector/` content, two options:
  1. **One collector, two entry points** (Cloudflare Worker and local loop) sharing the capture logic. Requires the same language in both.
  2. **Two implementations of one contract** (e.g. `collector/cloud/` and `collector/local/`), linked by a shared contract document.
- The Worker can be written in Python; option 1 depends on whether a Python Worker fits the CPU time limit per invocation. To be answered by the spike.
- C needs at most a helper script or a documented manual procedure.
- Spikes follow the existing convention: throwaway code in `spikes/<name>/`, report in `docs/spikes/<name>.md`. Spike code never goes to production; the final code goes through a design doc.
- The cloud capture (A) is still a candidate with open questions: it starts as a spike.
- TODO: record the chosen layout as an ADR and update CLAUDE.md "Project structure" in the same commit.

## 8. Parked

- Gold brainstorming (questions and visualizations).
- Bicing monthly history (C) as a backfill source.
- Repo layout decision (ADR).
- Collector option 1 or 2 (depends on the spike).
- Collector code location (this repo or separate).
- Visualization / BI stack.
- Internal organization of the pipeline (by medallion layer or by domain).
- Orchestration and storage format (Delta, Iceberg, Parquet).
