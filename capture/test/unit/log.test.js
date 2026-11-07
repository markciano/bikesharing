// Unit tests of the pass log write: one object per pass, and the fallback to Workers Logs
// through the console when the bucket keeps failing. The bucket is a fake binding.
import { afterEach, describe, expect, it, vi } from "vitest";
import { buildEvent, toJsonl, writeLog } from "../../src/log.js";
import { logKey } from "../../src/storage.js";

const LIMITS = { retryDelayMs: 0 };
const RUN_ID = "20261018T120003Z";
const CTX = { runId: RUN_ID, version: "test-version" };
const EVENTS = [
  buildEvent(CTX, new Date("2026-10-18T12:00:03.871Z"), "info", "heartbeat_sent", { status: 200, latency_ms: 96 }),
  buildEvent(CTX, new Date("2026-10-18T12:00:04.102Z"), "warning", "heartbeat_failed", {
    status: null,
    latency_ms: null,
    error_type: "network",
    error: "Network connection lost.",
  }),
];

/** A fake R2 binding whose put always throws `error`, or always succeeds if `error` is absent. */
function fakeBucket(error) {
  const puts = [];
  return {
    puts,
    async put(key, body, options) {
      puts.push({ key, body, options });
      if (error) throw error;
      return { key };
    },
    async head() {
      return null;
    },
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("writeLog", () => {
  it("writes the events as one JSON Lines object at the pass's log key", async () => {
    const bucket = fakeBucket();

    await writeLog(bucket, RUN_ID, EVENTS, LIMITS);

    expect(bucket.puts).toHaveLength(1);
    expect(bucket.puts[0].key).toBe(logKey(RUN_ID));
    expect(bucket.puts[0].body).toBe(toJsonl(EVENTS));
  });

  it("writes nothing to the console when the log object is stored", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    await writeLog(fakeBucket(), RUN_ID, EVENTS, LIMITS);

    expect(log).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });

  it("writes each line with console.log and the error with console.error when the bucket always fails", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const error = vi.spyOn(console, "error").mockImplementation(() => {});

    await writeLog(fakeBucket(new Error("R2 down")), RUN_ID, EVENTS, LIMITS);

    expect(log.mock.calls).toEqual(EVENTS.map((e) => [JSON.stringify(e)]));
    expect(error).toHaveBeenCalledOnce();
    expect(String(error.mock.calls[0])).toContain("R2 down");
  });

  it("does not throw when the bucket always fails", async () => {
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});

    await expect(writeLog(fakeBucket(new Error("R2 down")), RUN_ID, EVENTS, LIMITS)).resolves.toBeUndefined();
  });
});
