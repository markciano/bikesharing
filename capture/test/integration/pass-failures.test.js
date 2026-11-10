// Integration tests of a capture pass under failure: a source that stalls, fails or
// sends an oversized or invalid response, a source with no index yet, R2 failing to
// write, and a failed heartbeat. Each failure is logged and the rest of the pass goes
// on. R2 is Miniflare's in-memory bucket, behind a proxy that fails `put` where a test
// needs it; the sources are the simulated ones in vitest.config.js.
import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";
import { parseIndex } from "../../src/adapters/gbfs.js";
import { readIndex, writeIndex } from "../../src/index-state.js";
import { runPass } from "../../src/pass.js";
import { extraFetch } from "../../src/schedule.js";
import { SOURCES, requiredFeeds } from "../../src/sources.js";
import { logKey, rawKey, runIdOf, stateKey } from "../../src/storage.js";

const LIMITS = env.TEST_LIMITS;
const SIM = "https://sim.test";
const VERSION = "test-version";
const DAY = Date.UTC(2026, 10, 7);
const SEEDED_AT = "2026-11-07T00:07:00Z";

/** The fields every event carries, and the own fields of each event (d004 D9, Capture logs). */
const COMMON_FIELDS = ["ts", "level", "component", "version", "run_id", "event"];
const OWN_FIELDS = {
  feed_captured: ["source", "feed", "status", "latency_ms", "bytes", "attempts", "recompressed"],
  feed_failed: ["source", "feed", "status", "latency_ms", "attempts", "error_type", "error"],
  index_refreshed: ["source", "status", "latency_ms", "bytes", "attempts", "recompressed", "unknown_feeds"],
  index_rejected: ["source", "status", "latency_ms", "attempts", "error_type", "error"],
  heartbeat_sent: ["status", "latency_ms"],
  heartbeat_failed: ["status", "latency_ms", "error_type", "error"],
  fetch_retried: ["source", "feed", "status", "latency_ms", "headers", "body"],
};

/** @param {string} b64 */
const fromBase64 = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));

/** @param {string} source @param {string} feed */
const fixtureBytes = (source, feed) => fromBase64(env.FIXTURES[`${source}/${feed}`].gzipB64);

/** @param {Uint8Array} bytes */
async function gunzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).text();
}

/**
 * Stores each source's fixture index in state/, as a refresh would; `moved` replaces
 * the URL of some `<source>/<feed>` entries.
 * @param {Record<string, string>} [moved]
 */
async function seedIndexes(moved = {}) {
  for (const source of SOURCES) {
    const parsed = parseIndex(await gunzip(fixtureBytes(source.id, "gbfs")), requiredFeeds(source));
    if (!parsed.ok) throw new Error(`fixture index of ${source.id} is invalid: ${parsed.error}`);
    const feeds = { ...parsed.feeds };
    for (const [name, url] of Object.entries(moved)) {
      const [sourceId, feed] = name.split("/");
      if (sourceId === source.id) feeds[feed] = url;
    }
    const written = await writeIndex(env.BUCKET, source.id, { refreshed_at: SEEDED_AT, feeds }, LIMITS);
    if (!written.ok) throw new Error(`seeding state/ failed for ${source.id}`);
  }
}

/**
 * The first scheduled time of the test day whose extra fetch meets `pred`.
 * @param {(extra: ReturnType<typeof extraFetch>) => boolean} pred
 */
function minuteWhere(pred) {
  for (let m = 0; m < 1440; m++) {
    const t = DAY + m * 60_000;
    if (pred(extraFetch(t))) return t;
  }
  throw new Error("no minute of the day meets the condition");
}

/** `SOURCES` with the index URL of `sourceId` replaced. @param {string} sourceId @param {string} indexUrl */
const withIndexUrl = (sourceId, indexUrl) => SOURCES.map((s) => (s.id === sourceId ? { ...s, indexUrl } : s));

/**
 * The test's R2 binding, with `put` throwing for keys under any of `prefixes`, as an R2
 * internal error would; every other call reaches the in-memory bucket.
 * @param {string[]} prefixes
 * @returns {R2Bucket}
 */
function failingPuts(prefixes) {
  const bucket = env.BUCKET;
  return new Proxy(bucket, {
    get(target, prop) {
      if (prop === "put") {
        return async (key, ...rest) => {
          if (prefixes.some((p) => key.startsWith(p))) throw new Error("simulated R2 internal error");
          return target.put(key, ...rest);
        };
      }
      const value = Reflect.get(target, prop, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}

/**
 * Runs a pass scheduled at `scheduledTime` that starts `second` seconds later, so each
 * test has a run ID of its own.
 * @param {number} scheduledTime
 * @param {number} second
 * @param {{ heartbeatUrl?: string, sources?: typeof SOURCES, bucket?: R2Bucket }} [opts]
 */
async function runAt(scheduledTime, second, opts = {}) {
  const { heartbeatUrl = `${SIM}/heartbeat/default`, sources = SOURCES, bucket = env.BUCKET } = opts;
  const start = new Date(scheduledTime + second * 1000);
  await runPass(scheduledTime, { bucket, heartbeatUrl, version: VERSION, sources, limits: LIMITS, now: () => start });
  return runIdOf(start);
}

/** Every key under `prefix`, across listing pages. @param {string} prefix */
async function listKeys(prefix) {
  const keys = [];
  let cursor;
  do {
    const page = await env.BUCKET.list({ prefix, cursor });
    keys.push(...page.objects.map((o) => o.key));
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  return keys;
}

/** `<source>/<feed>` of every raw object of a run, sorted. @param {string} runId */
async function capturedFeeds(runId) {
  return (await listKeys("raw/"))
    .filter((k) => k.endsWith(`/${runId}.json.gz`))
    .map((k) => k.split("/").slice(1, 3).join("/"))
    .sort();
}

/** The raw text of a run's log object. @param {string} runId */
async function readLogText(runId) {
  const object = await env.BUCKET.get(logKey(runId));
  if (!object) throw new Error(`no log object for ${runId}`);
  return object.text();
}

/**
 * The events of a run's log object. Every event read is checked to carry exactly the
 * common fields and its own fields (d004 D9, Capture logs), so every test that reads a
 * log also verifies d004 R16.
 * @param {string} runId
 */
async function readLog(runId) {
  const events = (await readLogText(runId))
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
  for (const event of events) {
    expect(Object.keys(event).sort(), event.event).toEqual([...COMMON_FIELDS, ...OWN_FIELDS[event.event]].sort());
  }
  return events;
}

/** @param {string} path */
async function requestCount(path) {
  return Number(await (await fetch(`${SIM}/count/${path}`)).text());
}

const dynamicFeeds = () => SOURCES.flatMap((s) => s.dynamic.map((f) => `${s.id}/${f}`)).sort();
const PLAIN_MINUTE = minuteWhere((extra) => extra === null);
const HEARTBEAT_MINUTE = minuteWhere((extra) => extra?.type === "heartbeat");
const BICING_INDEX_MINUTE = minuteWhere((extra) => extra?.type === "index" && extra.source === "bicing");

describe("a capture pass with a failing source", () => {
  // Verifies d004 R7
  it("logs a body that stalls beyond timeoutMs as feed_failed timeout and stores the other feeds", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/stall-body/r7` });

    const runId = await runAt(PLAIN_MINUTE, 10);

    expect(await capturedFeeds(runId)).toEqual(dynamicFeeds().filter((f) => f !== "bicing/station_status"));
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "feed_failed", source: "bicing", feed: "station_status", error_type: "timeout" }),
    );
  });

  // Verifies d004 R8
  it("requests a source answering HTTP 500 once and logs feed_failed http with no write attempts", async () => {
    await seedIndexes({ "ambici/station_status": `${SIM}/http-500/r8` });

    const runId = await runAt(PLAIN_MINUTE, 11);

    expect(await requestCount("http-500/r8")).toBe(1);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({
        event: "feed_failed",
        source: "ambici",
        feed: "station_status",
        status: 500,
        error_type: "http",
        attempts: 0,
      }),
    );
  });

  // Verifies d004 R14
  it("logs latency_ms as a number for HTTP 500 and a stalled body, and null for a network failure", async () => {
    const [http500, stalled, network] = dynamicFeeds();
    await seedIndexes({
      [http500]: `${SIM}/http-500/r14`,
      [stalled]: `${SIM}/stall-body/r14`,
      [network]: `${SIM}/network-error/r14`,
    });

    const runId = await runAt(PLAIN_MINUTE, 12);

    const failed = new Map(
      (await readLog(runId)).filter((e) => e.event === "feed_failed").map((e) => [`${e.source}/${e.feed}`, e]),
    );
    expect(failed.get(http500).latency_ms).toEqual(expect.any(Number));
    expect(failed.get(stalled).latency_ms).toEqual(expect.any(Number));
    expect(failed.get(network)).toMatchObject({ error_type: "network", status: null, latency_ms: null });
  });

  // Verifies d004 R22
  it("logs a body over maxBytes with no content-length as feed_failed too_large and stores nothing for it", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/oversized/r22` });

    const runId = await runAt(PLAIN_MINUTE, 13);

    expect(await capturedFeeds(runId)).not.toContain("bicing/station_status");
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "feed_failed", source: "bicing", feed: "station_status", error_type: "too_large" }),
    );
  });

  // Verifies d004 R16
  it("logs feed_captured with recompressed true for a response served without gzip", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/plain-json/r16` });

    const runId = await runAt(PLAIN_MINUTE, 14);

    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "feed_captured", source: "bicing", feed: "station_status", recompressed: true }),
    );
  });
});

describe("a capture pass with a 403", () => {
  /** The position of the first event of a run's log that matches `fields`. */
  const indexOf = (events, fields) => events.findIndex((e) => Object.entries(fields).every(([k, v]) => e[k] === v));

  // Verifies d006 R1, R5, R7
  it("stores a Bicing feed whose first request got a 403 and logs fetch_retried before feed_captured", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/forbidden-once/bicing/station_status/d006r1` });

    const runId = await runAt(PLAIN_MINUTE, 15);

    const stored = await env.BUCKET.get(rawKey("bicing", "station_status", runId));
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(fixtureBytes("bicing", "station_status"));
    const events = await readLog(runId);
    const retried = indexOf(events, { event: "fetch_retried", source: "bicing", feed: "station_status" });
    const captured = indexOf(events, { event: "feed_captured", source: "bicing", feed: "station_status" });
    expect(retried).toBeGreaterThanOrEqual(0);
    expect(captured).toBeGreaterThan(retried);
    expect(events[retried]).toMatchObject({ level: "warning", status: 403, latency_ms: expect.any(Number) });
    expect(Object.keys(events[retried]).slice(-6)).toEqual(OWN_FIELDS.fetch_retried);
    expect(events[captured]).toMatchObject({ status: 200, latency_ms: expect.any(Number) });
  });

  // Verifies d006 R1, R5
  it("adopts a Bicing index whose first request got a 403 and logs fetch_retried with a null feed", async () => {
    await seedIndexes();

    const runId = await runAt(BICING_INDEX_MINUTE, 26, {
      sources: withIndexUrl("bicing", `${SIM}/forbidden-once/bicing/gbfs/d006r1`),
    });

    expect((await readIndex(env.BUCKET, "bicing")).refreshed_at).not.toBe(SEEDED_AT);
    const events = await readLog(runId);
    const retried = indexOf(events, { event: "fetch_retried", source: "bicing", feed: null });
    expect(retried).toBeGreaterThanOrEqual(0);
    expect(indexOf(events, { event: "index_refreshed", source: "bicing" })).toBeGreaterThan(retried);
  });

  // Verifies d006 R2, R7
  it("logs fetch_retried then feed_failed with status 403 when a Bicing feed gets two 403s", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/forbidden/d006r2` });

    const runId = await runAt(PLAIN_MINUTE, 16);

    expect(await requestCount("forbidden/d006r2")).toBe(2);
    const events = await readLog(runId);
    const retried = indexOf(events, { event: "fetch_retried", source: "bicing", feed: "station_status" });
    const failed = indexOf(events, { event: "feed_failed", source: "bicing", feed: "station_status" });
    expect(retried).toBeGreaterThanOrEqual(0);
    expect(failed).toBeGreaterThan(retried);
    expect(events[failed]).toMatchObject({ status: 403, error_type: "http" });
  });

  // Verifies d006 R2
  it("logs feed_failed and no fetch_retried when an AMBici feed gets a 403", async () => {
    await seedIndexes({ "ambici/station_status": `${SIM}/forbidden/d006r2-ambici` });

    const runId = await runAt(PLAIN_MINUTE, 17);

    expect(await requestCount("forbidden/d006r2-ambici")).toBe(1);
    const events = await readLog(runId);
    expect(events.map((e) => e.event)).not.toContain("fetch_retried");
    expect(events).toContainEqual(
      expect.objectContaining({ event: "feed_failed", source: "ambici", feed: "station_status", status: 403 }),
    );
  });
});

describe("an index refresh that fails", () => {
  // Verifies d004 R12
  it("logs an invalid index as index_rejected invalid_index and leaves state/ unchanged", async () => {
    await seedIndexes();
    const before = await readIndex(env.BUCKET, "bicing");

    const runId = await runAt(BICING_INDEX_MINUTE, 20, {
      sources: withIndexUrl("bicing", `${SIM}/invalid-index/bicing/r12`),
    });

    expect(await readIndex(env.BUCKET, "bicing")).toEqual(before);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_rejected", source: "bicing", error_type: "invalid_index" }),
    );
  });

  // Verifies d004 R12
  it("logs a failed write of the index to raw/ as index_rejected write and leaves state/ unchanged", async () => {
    await seedIndexes();
    const before = await readIndex(env.BUCKET, "bicing");

    const runId = await runAt(BICING_INDEX_MINUTE, 21, { bucket: failingPuts(["raw/bicing/gbfs/"]) });

    expect(await readIndex(env.BUCKET, "bicing")).toEqual(before);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_rejected", source: "bicing", error_type: "write" }),
    );
  });

  // Verifies d004 R12
  it("logs a failed write of the index to state/ as index_rejected write and leaves state/ unchanged", async () => {
    await seedIndexes();
    const before = await readIndex(env.BUCKET, "bicing");

    const runId = await runAt(BICING_INDEX_MINUTE, 22, { bucket: failingPuts(["state/"]) });

    expect(await readIndex(env.BUCKET, "bicing")).toEqual(before);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_rejected", source: "bicing", error_type: "write" }),
    );
  });

  // Verifies d004 R24
  it("stores an invalid index under raw/<source>/gbfs/", async () => {
    await seedIndexes();

    const runId = await runAt(BICING_INDEX_MINUTE, 23, {
      sources: withIndexUrl("bicing", `${SIM}/invalid-index/bicing/r24`),
    });

    const stored = await env.BUCKET.get(rawKey("bicing", "gbfs", runId));
    expect(stored).not.toBeNull();
    expect(JSON.parse(await gunzip(new Uint8Array(await stored.arrayBuffer())))).toHaveProperty("data");
  });

  // Verifies d004 R22
  it("rejects an index over maxBytes once decompressed as index_rejected too_large and leaves state/ unchanged", async () => {
    await seedIndexes();
    const before = await readIndex(env.BUCKET, "bicing");

    const runId = await runAt(BICING_INDEX_MINUTE, 24, {
      sources: withIndexUrl("bicing", `${SIM}/index-oversized/bicing/r22`),
    });

    expect(await readIndex(env.BUCKET, "bicing")).toEqual(before);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_rejected", source: "bicing", error_type: "too_large" }),
    );
  });

  // Verifies d004 R16
  it("logs index_refreshed with the feeds not in requiredFeeds as unknown_feeds", async () => {
    await seedIndexes();

    const runId = await runAt(BICING_INDEX_MINUTE, 25, {
      sources: withIndexUrl("bicing", `${SIM}/index-extra-feed/bicing/r16`),
    });

    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_refreshed", source: "bicing", unknown_feeds: ["extra_feed"] }),
    );
  });
});

describe("a source with no valid index", () => {
  // Verifies d004 R13
  it("fetches only that source's index, even at its extra minute, and stores the other source's feeds", async () => {
    await seedIndexes();
    await env.BUCKET.delete(stateKey("bicing"));
    const scheduledTime = minuteWhere((extra) => extra?.type === "feed" && extra.source === "bicing");

    const runId = await runAt(scheduledTime, 30, {
      sources: withIndexUrl("bicing", `${SIM}/moved/bicing/gbfs/r13`),
    });

    expect(await requestCount("moved/bicing/gbfs/r13")).toBe(1);
    const ambiciDynamic = dynamicFeeds().filter((f) => f.startsWith("ambici/"));
    expect(await capturedFeeds(runId)).toEqual([...ambiciDynamic, "bicing/gbfs"].sort());
  });
});

describe("a pass whose data writes fail", () => {
  // Verifies d004 R15
  it("still writes its log object when every data write fails", async () => {
    await seedIndexes();

    const runId = await runAt(PLAIN_MINUTE, 40, { bucket: failingPuts(["raw/"]) });

    const failed = (await readLog(runId)).filter((e) => e.event === "feed_failed" && e.error_type === "write");
    expect(failed.map((e) => `${e.source}/${e.feed}`).sort()).toEqual(dynamicFeeds());
  });
});

describe("the heartbeat of a pass", () => {
  // Verifies d004 R18
  it("sends no request at the heartbeat minute when one dynamic feed failed", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/http-500/r18` });

    const runId = await runAt(HEARTBEAT_MINUTE, 50, { heartbeatUrl: `${SIM}/heartbeat/r18` });

    expect(await requestCount("heartbeat/r18")).toBe(0);
    const events = (await readLog(runId)).map((e) => e.event);
    expect(events).not.toContain("heartbeat_sent");
    expect(events).not.toContain("heartbeat_failed");
  });

  // Verifies d004 R20
  it("logs a heartbeat answering HTTP 500 as heartbeat_failed warning and stores the data and the log", async () => {
    await seedIndexes();

    const runId = await runAt(HEARTBEAT_MINUTE, 51, { heartbeatUrl: `${SIM}/http-500/r20` });

    expect(await capturedFeeds(runId)).toEqual(dynamicFeeds());
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "heartbeat_failed", level: "warning", status: 500 }),
    );
  });

  // Verifies d004 R20
  it("logs a heartbeat failing on the network as heartbeat_failed warning and stores the data and the log", async () => {
    await seedIndexes();

    const runId = await runAt(HEARTBEAT_MINUTE, 52, { heartbeatUrl: `${SIM}/heartbeat-network-error/r20` });

    expect(await capturedFeeds(runId)).toEqual(dynamicFeeds());
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "heartbeat_failed", level: "warning", status: null }),
    );
  });

  // Verifies d004 R23
  it("leaves the heartbeat URL out of the log object after a failed heartbeat", async () => {
    await seedIndexes();
    const secret = "r23-secret-check-id";
    const heartbeatUrl = `${SIM}/heartbeat-network-error/${secret}`;

    const runId = await runAt(HEARTBEAT_MINUTE, 53, { heartbeatUrl });

    const text = await readLogText(runId);
    expect(text).toContain("heartbeat_failed");
    expect(text).not.toContain(secret);
  });

  // Verifies d004 R16
  it("logs heartbeat_sent with exactly its fields", async () => {
    await seedIndexes();

    const runId = await runAt(HEARTBEAT_MINUTE, 54, { heartbeatUrl: `${SIM}/heartbeat/r16` });

    expect(await readLog(runId)).toContainEqual(expect.objectContaining({ event: "heartbeat_sent" }));
  });
});
