# Spike: Git branches and CI/CD flow

- **Task:** T018
- **ADRs:** none
- **Code:** TODO: decide in Method › File layout whether `spikes/git-branching-cicd/` is needed

## Status

- State: Draft 📝
- Phase: [ ] Questions · [ ] Method · [ ] Steps · [ ] Steps review
- Started: — · Finished: —
- Current step: — · Waiting for T019 (repo public before the trial)

## 1. Questions — what we need to know

### Context

The project needs a Git branching model and a CI flow suited to a single owner, who makes every commit while Claude only reads Git (CLAUDE.md › Git). The output is a working procedure for branches and CI that the owner can follow day to day. Today there is no `src/`, no tests and no CI, history is linear on `dev` next to `main`, and the GitHub repo is private, so branch protection rules are not available until it is made public (T019). Choosing the model can be done from published standards; whether the procedure works with the project's rules only shows by running it once.

### Questions

Main question:

- **Q1.**
- **Observe only:**

### Exit criteria

- **Standard:** screening of published branching models (GitHub Flow, trunk-based development, Git Flow) against the project's constraints as pass/fail; the simplest model that passes wins. The procedure is then validated by one trial run of the full cycle in the real repo.
- **Timebox:** TODO: fix with the exit criteria
- TODO: criteria

### Out of scope

- CD (deployment): nothing is deployed yet; the procedure leaves room to add it later.
- Reviewing the repo before making it public: T019.

### Open questions

| Question | Notes |
|---|---|
| | |

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
| 2026-10-18 | Run T018 as a light spike, not a design | A design is too heavy for this choice; no rigorous comparison is needed, only exploring the models and picking the best fit. |
| 2026-10-18 | Trial run in the real repo, after T019 makes it public | Owner's choice; the CI workflow stays as real code, and branch protection can be part of the trial. |

### File layout

```
spikes/git-branching-cicd/
├── README.md        Setup, commands, what each script does; How we got here (written at Conclusion)
└── <file>           <purpose>
```

## 3. Steps

#### Step 1 — <title>

- **Status:** 💤 todo
- **Who:**
- **Scope:**
- **Reads:**
- **Gate:**
- **Check:**
- **Commit:**

#### Step N — Conclusion

- **Status:** 💤 todo
- **Who:** Owner + Claude
- **Scope:** 5. Conclusion and the destination of every Production input in this doc; How we got here in the README; tear-down of what does not outlive the spike.
- **Reads:** 1. Questions, 2. Method › Decision log, 4. Findings
- **Check:** every Q answered; every exit criterion has a result; every P has a destination
- **Commit:** `docs(T018): conclude spike s007`

## 4. Findings

### Production inputs

| P | Input | Origin | Destination |
|---|---|---|---|

## 5. Conclusion

Observed window:

### Answers

### Exit criteria

### Verdict

### Not verified

### Follow-ups

## Sources

-
