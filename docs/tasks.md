# Tasks

| ID | Task | Effort | Status | Depends on | Doc |
|---|---|---|---|---|---|
| T001 | Define workflow | 2 | ✅ | — | — |
| T002 | Create repo | 1 | ✅ | — | — |
| T003 | Capture Bicing real time | 3 | ✅ | — | [bicing-realtime-capture](spikes/s002-bicing-realtime-capture.md) |
| T004 | Check AMBici history availability | 1 | ✅ | — | [ambici-historical-data](spikes/s003-ambici-historical-data.md) |
| T005 | Profile Bicing historical data | 5 | ✅ | — | [bicing-historical-data](spikes/s004-bicing-historical-data.md) |
| T006 | Close AMBici and Bicing capture spikes | 5 | ✅ | T006.1 | [ambici](spikes/s001-ambici-realtime-capture.md), [bicing](spikes/s002-bicing-realtime-capture.md) |
| T006.1 | Review the points written with Claude's judgement in T006 docs | 2 | ✅ | — | [t006-spike-review](designs/t006-spike-review.md) |
| T008 | Portfolio presentation | 3 | ✅ | — | [ADR-0007](decisions/0007-repository-presentation-to-externals.md) |
| T009 | Review previous project Claude docs | 3 | ✅ | — | — |
| T011 | Testing conventions | 2 | ✅ | — | [t011-testing-conventions](designs/t011-testing-conventions.md) |
| T012 | Real-time capture without the Mac | 8 | ✅ | T006 | [s005-benchmark-data-capture.md](spikes/s005-benchmark-data-capture.md), [s006-cloudflare-capture.md](spikes/s006-cloudflare-capture.md) |
| T013 | Workflow v2 | 5 | ✅ | — | [t013-workflow-v2](designs/t013-workflow-v2.md) |
| T014 | Workflow v3 – Align design template with SDD | 3 | ✅ | — | [t014-workflow-v3](designs/t014-workflow-v3.md) |
| T016 | Track active time per phase in the design template | 1 | ✅ | — | [design-doc.md](docs/templates/design-doc.md) |
| T017 | Workflow v4 | 5 | ✅ | — | [settings.json](../.claude/settings.json) |
| T018 | Git branches and CI/CD flow | 5 | ✅ | T019 | [git-branching-cicd](spikes/s007-git-branching-cicd.md) |
| T018.1 | Git and CI conventions as invariants in CLAUDE.md | 1 | ✅ | T018 | — |
| T019 | Review repo contents and history before making it public | 2 | ✅ | — |  |
| T020 | Testing conventions and place in claude files | 5 | ✅ | — | [testing-conventions](spikes/s008-testing-conventions.md) |
| T030 | Process changes made on the T021 branch: ADR rule and template, implement and spike skills, task status rule (`.claude/rules/tasks.md`) | 1 | ✅ | — | — |
| T021 | Production stack versions (Python, Spark, Java) and dependency tooling (ADR; `uv` + `pyproject.toml` vs pip) | 1 | ✅ | T020 | [d001-production-stack-versions](designs/d001-production-stack-versions.md) |
| T028 | Design skill: rule documents and prerequisites written in the design (lessons from d001; done on the T021 branch) | 1 | ✅ | — | [SKILL.md](../.claude/skills/design/SKILL.md) |
| T029 | Upgrade `markdownlint-cli2` 0.23.2 → 0.23.3 (11 → 10 `npm audit` advisories, js-yaml cleared); no release clears all on 2026-10-22: braces has no fixed version and katex is held back by `micromark-extension-math`; 0.24.0 deferred until it matures; upstream fixes picked up by T027 | 1 | ✅ | T021 |  |
| T031 | Add a dated amendment note to ADR-0013 for the commit format change (`type(TNNN)` → `type: description`), edited in place on the T021 branch | 1 | ✅ | — |  |
| T032 | Move web-research delegation from Claude's memory to a project subagent (`.claude/agents/web-researcher.md`) | 1 | ✅ | — |  |
| T022 | Order the project's decisions by dependency (requirements and volume → storage and format → engine → execution target → visualization) and review the affected ADRs and tasks | 3 | ✅ | — | [architecture](architecture.md) |
| T023 | Markdown lint scope and hook: scope and rules in `.markdownlint-cli2.yaml` as single source (root `*.md`, `docs/`, `.claude/`, `spikes/`; default rules except MD013 and MD060), mirrored in `.claude/rules/docs.md`; `--fix` for cosmetic rules; PostToolUse hook that fixes and lints on every edit; existing violations fixed; run instructions moved to `docs/testing-strategy.md` | 2 | ✅ | — | [testing-strategy](testing-strategy.md) |
| T026 | Include `model` in the steps of skills/{design,spike}/template.md | 1 | ✅ |  |  |
| T034 | Requirements: consumers, questions the data answers, freshness, public or not, whether Bicing history enters | 2 | 📝 | T022 | [requirements](designs/d002-requirements.md) |
| T035 | Storage and table format: where raw data and tables live, retention, table format; confirms or replaces capture (ADR-0011) | 3 | ⬜ | T034 |  |
| T036 | Processing engine (single node) and pipeline language | 3 | ⬜ | T035 |  |
| T037 | Execution target: where the pipeline runs and what schedules it | 3 | ⬜ | T036 |  |
| T038 | Visualization: tool and where it is published | 2 | ⬜ | T034, T035, T037 |  |
| T039 | Capture in production (parent; split into TNNN.M in its design) | 5 | ⬜ | T035 |  |
| T040 | Processing pipeline (parent; split into TNNN.M in its design) | 8 | ⬜ | T036, T037 |  |
| T041 | Visualization (parent; split into TNNN.M in its design) | 5 | ⬜ | T038, T040 |  |
| T024 | Hooks: code conventions for the project's languages | 1 | 🔄 | — |  |
| T027 | Automated dependency and runtime updates (Dependabot vs Renovate); covers the security-patch risk of exact pins in ADR-0016 | 2 | ⬜ | T021 |  |
| T010 | Write README | 3 | ⬜ | T034, T035, T036, T037, T038 | — |
| T015 | Match Bicing October archive against real-time capture | 2 | ⛔ | T034 | [bicing-historical-data](spikes/s004-bicing-historical-data.md) |
