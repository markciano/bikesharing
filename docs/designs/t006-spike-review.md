# Design: T006 spike review

- **Task:** T006.1
- **ADRs:** none

## Status

- State: Draft
- Current step: —
- Next: owner approves this design, then step 1

## Context

Exceptional design: a review checklist, not a build. Some statements in the T006 reports and source cards rest on Claude's judgement rather than direct evidence. The owner reviews each one before T006 closes.

## Done when

- Every point below is confirmed, corrected or removed by the owner
- Corrections are applied in the affected documents
- The owner has committed the changes

## Decision summary

| Concern | Decision |
|---|---|
| Method | The owner reviews each point against the evidence; Chat applies the corrections the owner approves |

## Points to review

`docs/spikes/s002-bicing-realtime-capture.md`

1. Table 2a as a whole: the piece with most judgement, especially the AMBici "Transform" rows and `description`, derived from `_description`.
2. 3b: "last_reported is not reliable to detect changes".
3. 8j: "its meaning in Bicing cannot be derived from this evidence", left as an open question.
4. Conclusion › T007: treat station 309 as a late-arriving dimension, and choose languages at ingestion.

`docs/spikes/s001-ambici-realtime-capture.md`

1. 5d: the "provider" classification of minute 18:42 is doubtful.
2. 9a, bike_id: "consistent with ID rotation (not confirmed)".
3. 8j: "an empty station is not flagged as not renting".
4. Conclusion › For T007: the six design recommendations.
5. Last line of Conclusion: it points to a hosting task that did not exist yet; it is now T012.

`docs/sources/ambici.md`

1. Known characteristics: `last_updated` is not strictly monotonic.
2. Data quality: "An empty station is not flagged as not renting".

`docs/sources/bicing.md`

1. "Detect changes by content": advice inside a fact about the source.
2. `is_renting`: "Its meaning is unknown", and adding it to Open questions.
3. "Meaning of the four vehicle types" left open: the data gives hints (`form_factor`, `propulsion_type`) that were not interpreted.
4. The three historical questions tagged "(T005)" to re-point them.

## Implementation steps

| Step | Scope | Reads | Check | Commit | Done |
|---|---|---|---|---|---|
| 1 | Review Bicing report points 1–4 | s002-bicing-realtime-capture.md; its evidence in `spikes/bicing-spike/analysis/` | Each point confirmed, corrected or removed | `docs(T006.1): review Bicing capture report` | |
| 2 | Review AMBici report points 1–5 | s001-ambici-realtime-capture.md; its evidence in `spikes/ambici-spike/analysis/` | Each point confirmed, corrected or removed | `docs(T006.1): review AMBici capture report` | |
| 3 | Review AMBici source card points 1–2 | `docs/sources/ambici.md` | Each point confirmed, corrected or removed | `docs(T006.1): review AMBici source card` | |
| 4 | Review Bicing source card points 1–4 | `docs/sources/bicing.md` | Each point confirmed, corrected or removed | `docs(T006.1): review Bicing source card` | |
