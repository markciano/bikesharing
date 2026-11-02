# Memory probe of spike s012: does Modal's Starter plan accept a 4 GiB function
# and let it occupy at least 3 GB?
# Inputs: none. Output: progress lines and one JSON line with the peak memory, in
# the run's logs. Run with: uv run modal run memory_probe.py::probe

import json
import re
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

    status = Path("/proc/self/status").read_text()
    # VmHWM is in KiB, though the kernel labels it kB.
    peak_kib = int(re.search(r"^VmHWM:\s+(\d+) kB$", status, re.MULTILINE).group(1))

    result = {
        "allocated_bytes": len(buffer),
        "peak_gb": round(peak_kib * 1_024 / 10**9, 3),
        "duration_s": round(time.monotonic() - start, 1),
    }
    print(json.dumps(result), flush=True)
