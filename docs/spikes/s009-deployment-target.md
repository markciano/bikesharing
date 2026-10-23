# Spike: Deployment target

- **Task:** T022
- **ADRs:** ADR-0003 (to be superseded)
- **Code:** none (desk research)

## Status

- State: Draft 📝
- Phase: [x] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: —

## 1. Questions — what we need to know

### Context

ADR-0003 chose to build locally first and port to Microsoft Fabric later; Fabric is dropped, and "local first" stays. This spike decides where the processing pipeline and the visualization run once built, which the pipeline design (T025) waits on. Fixed inputs: capture lands in Cloudflare R2 (ADR-0011), code runs in Python (ADR-0010), and the real-time path is compared against a batch baseline (ADR-0004). The budget is $0, so the answer depends on free-tier limits that need evidence.

### Questions

Main question: where do the processing pipeline and the visualization run, and with which visualization runtime model (static, server app or managed BI), at $0?

- **Q1.** Which platforms, local and cloud free tiers, run a Python Spark + Delta Lake pipeline at $0, and with what limits (compute, storage, run time, expiry)?
- **Q2.** Where can each visualization runtime model be hosted publicly at $0, and with what limits (sleep, refresh, data size)?
- **Q3.** Which combinations support the three operating modes, each started on demand and in how long: static by default (the visualization shows the last processed data, nothing running), catch-up (one pipeline run processes what R2 holds and the pipeline does not), and live for demos (1-minute deltas from R2 through to the visualization, switched off afterwards)?
- **Q4.** How does each combination score on the weighted criteria?
- **Observe only:** R2 free-tier operation limits (listing counts as Class A, shared with the Worker's writes) when polled every minute during a demo.

### Exit criteria

- **Standard:** hard constraints first, then a weighted scoring matrix over the surviving combinations, recorded in MADR style for the ADR that supersedes ADR-0003.
- **Timebox:** half a day of desk research; the run ends when the matrix is complete for every combination that passes the hard cuts, or when the timebox runs out, in which case the decision is taken on the evidence gathered and the gaps go to Not verified. Every surviving combination is scored: one meeting the criteria is not enough, because the ADR needs the ranked alternatives.
- **Cost:** expected cost is $0, on always-free tiers or on trials lasting 3 months or more; each combination records when it expires — hard cut.
- **Payment card:** accepted only if the provider offers at least budget alerts; the accepted worst case from an accidental overage is €10 — hard cut.
- **Spark + Delta Lake:** the platform runs PySpark with open-source Delta Lake as it runs locally, either as a managed service or on a self-installed VM or container — hard cut.
- **Weighted criteria** — guide. Each surviving combination scores 1–5 per criterion; the total is the sum of score × weight:

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

| Variant | What it is | What it tells |
|---|---|---|
| | | |

### Shared behaviour

- TODO: write during Method, or remove.

### Decision log

| Date | Decision | Reason |
|---|---|---|
| | | |

### File layout

TODO: write during Method, or remove (no code expected).

## 3. Steps

TODO: write during Steps.

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
