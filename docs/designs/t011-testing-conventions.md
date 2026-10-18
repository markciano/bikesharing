# Design: Testing conventions

- **Task:** T011
- **ADRs:** ADR-0005 (UTC), ADR-0009 (recorded fixtures), ADR-0010 (logic separated from platform)

## Status

- State: Complete
- Current step: —
- Next: —

### Implemented

- ADR-0009 (trimmed source samples as test fixtures) and ADR-0010 (ingestion logic separated from platform).
- CLAUDE.md › Code › Testing with the general conventions; Project structure with `src/` and `tests/`; Raw data rule links ADR-0009.

### Known gaps at close

- Test conventions for the platform layer (scheduler, storage) — T012.
- Test conventions for Spark and dashboards — no task yet; defined when their technology is chosen.

### Decisions taken during implementation

- Location revised: no Common › Testing section; feature-specific decisions stay in this design and ADR-0010, general conventions go to Code › Testing — owner's request, to keep CLAUDE.md free of feature-specific rules.

## Context

CLAUDE.md sets testing principles but not concrete conventions; T007 needs them before its first test. Scope is ingestion in Python, with its logic separated from the platform that runs it (T012 is still open). Spark and dashboards get their own conventions when their technology is chosen.

TODO: T012 must choose a platform that runs Python.

## Done when

- CLAUDE.md › Code › Testing states the general conventions in the Decision summary, and the T011 TODO is removed.
- CLAUDE.md › Project structure shows `src/` and `tests/`.
- ADR-0009 (recorded fixtures exception) and ADR-0010 (logic separated from platform) exist and are linked from this design.

## Decision summary

| Concern | Decision |
|---|---|
| Scope | Ingestion (T007), in Python. Logic (parsing, validation, file naming) is separated from platform code (scheduler, storage); tests target the logic, platform code gets a manual smoke check. Spark and dashboards are out of scope: their conventions are defined when their technology is chosen. |
| Location | General conventions in CLAUDE.md › Code › Testing; the design template's Test plan already points there. Folder layout in CLAUDE.md › Project structure. Run command and coverage settings in `pyproject.toml` and the README. Feature-specific decisions (Scope) stay in this design and ADR-0010. |
| Layout | src layout (PyPA): code in `src/bikesharing/`; tests in `tests/unit/` (mirrors `src/`) and `tests/integration/`; recorded fixtures in `tests/fixtures/`. |
| Tool | pytest + pytest-cov. |
| Naming | Test files `test_<module>.py`; test functions `test_<behaviour>_<condition>`. |
| Shared fixtures | `conftest.py` in `tests/`, plus one per level when needed. |
| Recorded fixtures | Real GBFS responses from the spike captures, trimmed to a few stations by a committed script and stored in `tests/fixtures/` with source and capture date; edge cases are written by hand. Both sources are CC0 (see source cards), so samples may be committed; Bicing samples carry attribution as good practice. Exception to "Raw data never committed" recorded in ADR-0009. |
| Coverage | pytest-cov report only, no threshold; reviewed in Review to spot untested cases. |
| Determinism | No test touches the network (recorded fixtures instead); code that uses the current time receives it as a parameter, and tests pass a fixed UTC time (ADR-0005); `pytest` runs everything, integration tests carry the `integration` marker. |
| Spike and analysis code | Exempt from these conventions: throwaway code; conclusions are checked by the owner against the evidence. |

## Open questions

| Question | Notes |
|---|---|
| | |

## Implementation steps

| Step | Scope | Reads | Check | Commit | Done |
|---|---|---|---|---|---|
| 1 | Write ADR-0009 (recorded fixtures exception to "Raw data never committed"); link it from CLAUDE.md › Conventions › Raw data | This design › Decision summary | ADR exists in MADR format and CLAUDE.md › Raw data links to it | `docs(T011): add ADR-0009 recorded fixtures` | ✓ |
| 2 | Write ADR-0010 (ingestion logic separated from platform code) | This design › Decision summary | ADR exists in MADR format and is linked from this design | `docs(T011): add ADR-0010 logic separated from platform` | ✓ |
| 3 | Update CLAUDE.md: Code › Testing (general conventions), Project structure (`src/`, `tests/`); remove the T011 TODO | This design › Decision summary; CLAUDE.md | Every general Decision summary row is reflected in CLAUDE.md and the T011 TODO is gone | `docs(T011): add testing conventions to CLAUDE.md` | ✓ |
