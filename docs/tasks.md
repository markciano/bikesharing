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
| T007 | GBFS ingestion spec and plan | 5 | ⬜ | T006, T011 | — |
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
| T018 | Git branches and CI/CD flow | 5 | 📝 | T019 | [git-branching-cicd](spikes/s007-git-branching-cicd.md) |
| T019 | Review repo contents and history before making it public | 2 | ⬜ | — |  |