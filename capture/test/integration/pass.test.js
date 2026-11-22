// Integration tests of a normal capture pass: with each source's index in state/, a
// pass stores every dynamic feed, the extra fetch of its minute, and one log object;
// at the heartbeat minute it signals Healthchecks.io. R2 is Miniflare's in-memory
// bucket and the sources are the simulated ones in vitest.config.js.
import { createExecutionContext, createScheduledController, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { describe, expect, it, vi } from "vitest";
import { parseIndex } from "../../src/adapters/gbfs.js";
import { readIndex, writeIndex } from "../../src/index-state.js";
import { runPass } from "../../src/pass.js";
import { extraFetch } from "../../src/schedule.js";
import { SOURCES, requiredFeeds } from "../../src/sources.js";
import { logKey, rawKey, runIdOf } from "../../src/storage.js";
import worker from "../../src/worker.js";
import { expectRegistered } from "../registry.js";

const LIMITS = env.TEST_LIMITS;
const SIM = "https://sim.test";
const VERSION = "test-version";
const DAY = Date.UTC(2026, 10, 6);
const OTLP_TOKEN = "test-credential";

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
    const text = await gunzip(fixtureBytes(source.id, "gbfs"));
    const parsed = parseIndex(text, requiredFeeds(source));
    if (!parsed.ok) throw new Error(`fixture index of ${source.id} is invalid: ${parsed.error}`);
    const feeds = { ...parsed.feeds };
    for (const [name, url] of Object.entries(moved)) {
      const [sourceId, feed] = name.split("/");
      if (sourceId === source.id) feeds[feed] = url;
    }
    const written = await writeIndex(env.BUCKET, source.id, { refreshed_at: "2026-11-06T00:07:00Z", feeds }, LIMITS);
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

/**
 * Runs a pass scheduled at `scheduledTime` that starts `second` seconds later, so each
 * test has a run ID of its own.
 * @param {number} scheduledTime
 * @param {number} second
 * @param {string} [heartbeatUrl]
 */
async function runAt(scheduledTime, second, heartbeatUrl = `${SIM}/heartbeat/default`, copy = {}) {
  const start = new Date(scheduledTime + second * 1000);
  /** @type {Promise<unknown>[]} */
  const pending = [];
  await runPass(scheduledTime, {
    bucket: copy.bucket ?? env.BUCKET,
    heartbeatUrl,
    otlpEndpoint: copy.endpoint ?? `${SIM}/otlp/default`,
    otlpToken: OTLP_TOKEN,
    waitUntil: (promise) => {
      copy.onWaitUntil?.();
      pending.push(promise);
    },
    version: VERSION,
    limits: LIMITS,
    now: () => start,
  });
  await Promise.all(pending);
  return { runId: runIdOf(start), start };
}

/** What the simulated Grafana received on `otlp/<path>`. @param {string} path */
async function otlpSeen(path) {
  return (await fetch(`${SIM}/otlp-seen/${path}`)).json();
}

/** The line of every record of an OTLP request, in order. @param {{ body: string }} request */
function recordLines(request) {
  return JSON.parse(request.body).resourceLogs.flatMap((r) =>
    r.scopeLogs.flatMap((s) => s.logRecords.map((record) => record.body.stringValue)),
  );
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
  const keys = await listKeys("raw/");
  return keys
    .filter((k) => k.endsWith(`/${runId}.json.gz`))
    .map((k) => k.split("/").slice(1, 3).join("/"))
    .sort();
}

/**
 * The events of a run's log object. Every line read must be an event of the registry
 * (d009, Observability catalog).
 * @param {string} runId
 */
async function readLog(runId) {
  const object = await env.BUCKET.get(logKey(runId));
  if (!object) throw new Error(`no log object for ${runId}`);
  const lines = (await object.text()).split("\n").filter(Boolean);
  expectRegistered(lines);
  return lines.map((line) => JSON.parse(line));
}

/** @param {string} path */
async function requestCount(path) {
  return Number(await (await fetch(`${SIM}/count/${path}`)).text());
}

const dynamicFeeds = () => SOURCES.flatMap((s) => s.dynamic.map((f) => `${s.id}/${f}`)).sort();
const PLAIN_MINUTE = minuteWhere((extra) => extra === null);

describe("a capture pass", () => {
  // Verifies d004 R1
  it("stores each dynamic feed with the fixture's bytes when the scheduled handler runs", async () => {
    await seedIndexes();
    const before = new Map();
    for (const name of dynamicFeeds()) before.set(name, new Set(await listKeys(`raw/${name}/`)));
    const controller = createScheduledController({ scheduledTime: PLAIN_MINUTE, cron: "* * * * *" });
    const ctx = createExecutionContext();
    const testEnv = { ...env, OTLP_ENDPOINT: `${SIM}/otlp/handler`, OTLP_TOKEN };

    await worker.scheduled(controller, testEnv, ctx);
    await waitOnExecutionContext(ctx);

    for (const name of dynamicFeeds()) {
      const added = (await listKeys(`raw/${name}/`)).filter((k) => !before.get(name).has(k));
      expect(added, name).toHaveLength(1);
      const stored = await env.BUCKET.get(added[0]);
      const [source, feed] = name.split("/");
      expect(new Uint8Array(await stored.arrayBuffer())).toEqual(fixtureBytes(source, feed));
    }
  });

  // Verifies d004 R4
  it("stores the dynamic feeds and only that static feed at a static feed's minute", async () => {
    await seedIndexes();
    const scheduledTime = minuteWhere((extra) => extra?.type === "feed");
    const { source, feed } = extraFetch(scheduledTime);

    const { runId } = await runAt(scheduledTime, 1);

    expect(await capturedFeeds(runId)).toEqual([...dynamicFeeds(), `${source}/${feed}`].sort());
    const stored = await env.BUCKET.get(rawKey(source, feed, runId));
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(fixtureBytes(source, feed));
  });

  // Verifies d004 R6
  it("fetches a feed at the new URL its index in state/ points to, and stores it", async () => {
    const movedPath = "moved/bicing/station_status/r6";
    await seedIndexes({ "bicing/station_status": `${SIM}/${movedPath}` });

    const { runId } = await runAt(PLAIN_MINUTE, 2);

    expect(await requestCount(movedPath)).toBe(1);
    const stored = await env.BUCKET.get(rawKey("bicing", "station_status", runId));
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(fixtureBytes("bicing", "station_status"));
  });

  // Verifies d004 R10
  it("leaves an object already at its key unchanged and logs feed_captured", async () => {
    await seedIndexes();
    const start = new Date(PLAIN_MINUTE + 3_000);
    const key = rawKey("ambici", "station_status", runIdOf(start));
    await env.BUCKET.put(key, "existing");

    const { runId } = await runAt(PLAIN_MINUTE, 3);

    expect(await (await env.BUCKET.get(key)).text()).toBe("existing");
    const events = await readLog(runId);
    expect(events).toContainEqual(
      expect.objectContaining({ event: "feed_captured", system: "ambici", feed: "station_status" }),
    );
  });

  // Verifies d004 R15
  it("writes one log object whose lines carry the common fields", async () => {
    await seedIndexes();

    const { runId } = await runAt(PLAIN_MINUTE, 4);

    expect(await listKeys(logKey(runId))).toEqual([logKey(runId)]);
    const events = await readLog(runId);
    expect(events.length).toBeGreaterThan(0);
    for (const event of events) {
      expect(Object.keys(event).slice(0, 6)).toEqual(["ts", "level", "component", "version", "run_id", "event"]);
      expect(event).toMatchObject({ component: "capture", version: VERSION, run_id: runId });
    }
    const captured = events.filter((e) => e.event === "feed_captured").map((e) => `${e.system}/${e.feed}`);
    expect(captured.sort()).toEqual(dynamicFeeds());
  });

  // Verifies d004 R17
  it("sends one heartbeat and logs heartbeat_sent at the heartbeat minute with every dynamic feed stored", async () => {
    await seedIndexes();
    // Minute 5: the first heartbeat minute of an hour that is not the hour's own start
    // (d009, Capture silence).
    const scheduledTime = DAY + 5 * 60_000;

    const { runId } = await runAt(scheduledTime, 5, `${SIM}/heartbeat/r17`);

    expect(await requestCount("heartbeat/r17")).toBe(1);
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "heartbeat_sent", level: "info", status: 200 }),
    );
  });

  // Verifies d004 R16
  it("stores the index, adopts it in state/ and logs index_refreshed at the source's index minute", async () => {
    await seedIndexes();
    const scheduledTime = minuteWhere((extra) => extra?.type === "index");
    const { source } = extraFetch(scheduledTime);

    const { runId, start } = await runAt(scheduledTime, 6);

    const stored = await env.BUCKET.get(rawKey(source, "gbfs", runId));
    expect(new Uint8Array(await stored.arrayBuffer())).toEqual(fixtureBytes(source, "gbfs"));
    expect((await readIndex(env.BUCKET, source)).refreshed_at).toBe(start.toISOString().replace(".000Z", "Z"));
    expect(await readLog(runId)).toContainEqual(
      expect.objectContaining({ event: "index_refreshed", system: source, unknown_feeds: [] }),
    );
  });
});

describe("a capture pass's copy to Grafana", () => {
  // Verifies d009 R1
  it("sends one request with one record per line written to R2, of every level, in order", async () => {
    await seedIndexes();
    const scheduledTime = minuteWhere((extra) => extra?.type === "feed");

    const { runId } = await runAt(scheduledTime, 10, `${SIM}/heartbeat/d009-r1`, { endpoint: `${SIM}/otlp/r1` });

    const written = (await (await env.BUCKET.get(logKey(runId))).text()).split("\n").filter(Boolean);
    const seen = await otlpSeen("r1");
    expect(seen).toHaveLength(1);
    expect(seen[0].authorization).toBe(`Basic ${OTLP_TOKEN}`);
    expect(recordLines(seen[0])).toEqual(written);
  });

  // Verifies d009 R1
  it("copies the warn and error lines of a failing pass as well as the info ones", async () => {
    await seedIndexes({ "bicing/station_status": `${SIM}/http-500/r1` });

    const { runId } = await runAt(PLAIN_MINUTE, 11, undefined, { endpoint: `${SIM}/otlp/r1-levels` });

    const levels = new Set((await readLog(runId)).map((e) => e.level));
    expect(levels).toContain("error");
    const copied = recordLines((await otlpSeen("r1-levels"))[0]).map((line) => JSON.parse(line).level);
    expect(new Set(copied)).toEqual(levels);
  });

  // Verifies d009 R3
  it.each([
    ["http-500", "http"],
    ["stall-body", "timeout"],
    ["network-error", "network"],
  ])("changes neither the log nor the heartbeat when Grafana answers %s, and writes otlp_send_failed", async (route, errorType) => {
    await seedIndexes();
    const scheduledTime = DAY + 5 * 60_000;
    const log = vi.spyOn(console, "log").mockImplementation(() => {});

    const { runId } = await runAt(scheduledTime, 12, `${SIM}/heartbeat/r3-${route}`, { endpoint: `${SIM}/${route}/r3` });

    expect(await requestCount(`heartbeat/r3-${route}`)).toBe(1);
    expect(await readLog(runId)).toContainEqual(expect.objectContaining({ event: "heartbeat_sent" }));
    const failed = log.mock.calls.map(([line]) => String(line)).filter((line) => line.includes('"otlp_send_failed"'));
    expect(failed).toHaveLength(1);
    expectRegistered(failed);
    expect(JSON.parse(failed[0])).toMatchObject({ level: "warn", component: "capture", error_type: errorType });
    log.mockRestore();
  });

  // Verifies d009 R4
  it("writes the same R2 log whether the copy succeeds or fails", async () => {
    await seedIndexes();
    vi.spyOn(console, "log").mockImplementation(() => {});
    // The run ID, the start and the measured latencies are the only lines' content that differ between runs.
    const normalized = async ({ runId, start }) =>
      (await (await env.BUCKET.get(logKey(runId))).text())
        .replaceAll(runId, "RUN")
        .replaceAll(start.toISOString(), "TS")
        .replace(/"latency_ms":\d+/g, '"latency_ms":0');

    const ok = await runAt(PLAIN_MINUTE, 13, undefined, { endpoint: `${SIM}/otlp/r4` });
    const failed = await runAt(PLAIN_MINUTE, 14, undefined, { endpoint: `${SIM}/http-500/r4` });

    expect(await normalized(failed)).toBe(await normalized(ok));
    vi.restoreAllMocks();
  });

  // Verifies d009 R3
  it("keeps the log and does not throw when waitUntil throws", async () => {
    await seedIndexes();
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const start = new Date(PLAIN_MINUTE + 16_000);

    await expect(
      runPass(PLAIN_MINUTE, {
        bucket: env.BUCKET,
        heartbeatUrl: `${SIM}/heartbeat/default`,
        otlpEndpoint: `${SIM}/otlp/waituntil-throws`,
        otlpToken: OTLP_TOKEN,
        waitUntil: () => {
          throw new Error("waitUntil rejected");
        },
        version: VERSION,
        limits: LIMITS,
        now: () => start,
      }),
    ).resolves.toBeUndefined();

    expect(await readLog(runIdOf(start))).not.toHaveLength(0);
    expect(String(error.mock.calls[0])).toContain("waitUntil rejected");
    vi.restoreAllMocks();
  });

  // Verifies d009 R3
  it("sends the copy after the log is written, through waitUntil", async () => {
    await seedIndexes();
    const order = [];
    const bucket = {
      get: (...args) => env.BUCKET.get(...args),
      head: (...args) => env.BUCKET.head(...args),
      put: async (key, ...rest) => {
        const result = await env.BUCKET.put(key, ...rest);
        if (key.startsWith("logs/")) order.push("log");
        return result;
      },
    };

    await runAt(PLAIN_MINUTE, 15, undefined, {
      bucket,
      endpoint: `${SIM}/otlp/order`,
      onWaitUntil: () => order.push("copy"),
    });

    expect(order).toEqual(["log", "copy"]);
  });
});
