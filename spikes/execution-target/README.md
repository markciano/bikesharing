# Execution target spike

**Question:** does Modal's Starter plan accept a function that requests 4 GiB, and let it occupy that memory? See the report: [s012](../../docs/spikes/s012-execution-target.md).

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

- `memory_probe.py`: one Modal function that requests 4 GiB, allocates and writes 3.5 GiB, holds it for 60 s and prints one JSON line with `allocated_bytes`, `peak_gb` and `duration_s`.
