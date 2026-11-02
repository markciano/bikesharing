# Memory probe of spike s012: does Modal's Starter plan accept a 4 GiB function
# and let it occupy at least 3 GB?
# Inputs: none. Output: progress lines and one JSON line with the peak memory, in
# the run's logs. Run with: uv run modal run memory_probe.py::probe

import json
import resource
import time
from pathlib import Path

import modal

ALLOCATED_BYTES = 3_758_096_384  # 3.5 GiB
PAGE_BYTES = 4_096
HOLD_S = 60

app = modal.App("memory-probe")
image = modal.Image.debian_slim(python_version="3.13")


@app.function(image=image, memory=4096, timeout=300)
def probe() -> None:
    start = time.monotonic()

    print(f"Allocating {ALLOCATED_BYTES:,} bytes", flush=True)
    buffer = bytearray(ALLOCATED_BYTES)
    # A fresh bytearray is only reserved: the kernel assigns a page on its first
    # write, so one write per page is what really occupies the memory.
    for offset in range(0, ALLOCATED_BYTES, PAGE_BYTES):
        buffer[offset] = 1

    print(f"Holding the memory for {HOLD_S} s", flush=True)
    time.sleep(HOLD_S)

    # Printed as they are, since the container's /proc may not expose every field.
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("Vm"):
            print(line, flush=True)

    # ru_maxrss is in KiB on Linux. A sandbox that does not track it returns 0, which
    # means "not measured": it must not read as a peak under the Gate's 3 GB.
    peak_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    result = {
        "allocated_bytes": len(buffer),
        "peak_gb": round(peak_kib * 1_024 / 10**9, 3) if peak_kib else None,
        "duration_s": round(time.monotonic() - start, 1),
    }
    print(json.dumps(result), flush=True)
