# Execution target spike

**Question:** does Modal's Starter plan accept a function that requests 4 GiB, and let it occupy that memory? See the report: [s012](../../docs/spikes/s012-execution-target.md).

## How we got here

Modal led the platform matrix on paper, but one fact stayed out of reach: its documentation enforces a maximum memory without stating the figure, and the pipeline needs 3 GB at worst. A failed answer would have sent us to a VM on Oracle Cloud that the owner has to keep, so the spike came down to one short run.

We wrote a function that requests 4 GiB, occupies 3.5 GiB and reads its own peak. The first run did the hard part and then failed on the last line: the container's `/proc/self/status` has no `VmHWM` ([F2](../../docs/spikes/s012-execution-target.md#f2-procselfstatus-in-modals-container-has-no-vmhwm-line)). We switched the reading to `ru_maxrss` ([#1](../../docs/spikes/s012-execution-target.md#23-decision-log)), which also changes how the pipeline will report its memory.

The second run settled it: 3.822 GB occupied with no failure ([F1](../../docs/spikes/s012-execution-target.md#f1-modals-starter-plan-accepts-a-4-gib-function-and-lets-it-occupy-3822-gb)), and Modal's own graph agrees ([F3](../../docs/spikes/s012-execution-target.md#f3-modals-dashboard-shows-354-gib-used-in-line-with-peak_gb)). Modal stays. Next comes the pipeline itself (T040), which measures real run times and memory.

## Setup

From this folder, with `uv` installed:

```bash
uv sync
uv run modal setup
```

`modal setup` opens a browser to log in and stores the token in `~/.modal.toml`, outside the repository.

## Run

```bash
uv run modal run memory_probe.py::probe
```

It takes about 2 minutes and creates a temporary app that stops when the run ends: nothing is deployed or scheduled.

## Scripts

- `memory_probe.py`: one Modal function that requests 4 GiB, allocates and writes 3.5 GiB, holds it for 60 s, prints the `Vm*` lines of `/proc/self/status` and one JSON line with `allocated_bytes`, `peak_gb` and `duration_s`. `peak_gb` comes from `ru_maxrss`, and is `null` if the container does not track it.
