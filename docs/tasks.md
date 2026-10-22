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
| T007 | GBFS ingestion spec and plan | 5 | ⬜ | T006, T011 | Inputs: [s008 P1–P4](spikes/s008-testing-conventions.md#production-inputs) |
| T008 | Portfolio presentation | 3 | ✅ | — | [ADR-0007](decisions/0007-repository-presentation-to-externals.md) |
| T009 | Review previous project Claude docs | 3 | ✅ | — | — |
| T010 | Write README | 3 | ⬜ | T006 | — |
| T011 | Testing conventions | 2 | ✅ | — | [t011-testing-conventions](designs/t011-testing-conventions.md) |
| T012 | Real-time capture without the Mac | 8 | ✅ | T006 | [s005-benchmark-data-capture.md](spikes/s005-benchmark-data-capture.md), [s006-cloudflare-capture.md](spikes/s006-cloudflare-capture.md) |
| T013 | Workflow v2 | 5 | ✅ | — | [t013-workflow-v2](designs/t013-workflow-v2.md) |
| T014 | Workflow v3 – Align design template with SDD | 3 | ✅ | — | [t014-workflow-v3](designs/t014-workflow-v3.md) |
| T015 | Match Bicing October archive against real-time capture | 2 | ⛔ | T005 | [bicing-historical-data](spikes/s004-bicing-historical-data.md) |
| T016 | Track active time per phase in the design template | 1 | ✅ | — | [design-doc.md](docs/templates/design-doc.md) |
| T017 | Workflow v4 | 5 | ✅ | — | [settings.json](../.claude/settings.json) |
| T018 | Git branches and CI/CD flow | 5 | ✅ | T019 | [git-branching-cicd](spikes/s007-git-branching-cicd.md) |
| T018.1 | Git and CI conventions as invariants in CLAUDE.md | 1 | ✅ | T018 | — |
| T019 | Review repo contents and history before making it public | 2 | ✅ | — |  |
| T020 | Testing conventions and place in claude files | 5 | ✅ | — | [testing-conventions](spikes/s008-testing-conventions.md) |
| T021 | Production stack versions (Python, Spark, Java) and dependency tooling (ADR; `uv` + `pyproject.toml` vs pip) | 1 | 🔄 | T020 | [d001-production-stack-versions](designs/d001-production-stack-versions.md) |
| T022 | Supersede ADR-0003: deployment target (Fabric dropped) | 1 | ⬜ | — |  |
| T023 | Include `.claude/*/*.md` and `spikes/*/*.md` in `.claude/rules/docs.md` | 1 | ⬜ | — |  |
| T024 | Hooks: Code conventions for Python, JS, Spark and SQL | 1 | ⬜ | — |  |
| T025 | Data processing pipeline spec and plan | 5 | ⬜ | T007, T021, T022 |  |
| T026 | Include `model` in the steps of skills/{design,spike}/template.md | 1 | ⬜ |  |  |
| T027 | Automated dependency and runtime updates (Dependabot vs Renovate); covers the security-patch risk of exact pins in ADR-0016 | 2 | ⬜ | T021 |  |
| T028 | Design skill: rule documents and prerequisites written in the design (lessons from d001; done on the T021 branch) | 1 | ✅ | — | [SKILL.md](../.claude/skills/design/SKILL.md) |
