/**
 * Capturer V2 (spike plan step 3.1): one capture pass over the GBFS feeds of
 * AMBici and Bicing, compressing each body with `CompressionStream`.
 *
 * `runPass` fetches both `gbfs.json` indexes, then every feed they list:
 * the dynamic feeds when `includeDynamic`, the rest when `includeStatic`.
 * Each feed is gzipped, stored in R2 under the V2 prefix and logged. The pass
 * ends by writing one JSONL log object with one line per request.
 *
 * The `scheduled` handler (step 3.3) runs one pass per trigger: dynamic feeds
 * every minute, static feeds at minute 17, and no dynamic feeds at minute 17
 * of odd UTC hours.
 *
 * Run a pass by hand with `npx wrangler dev --remote src/V2.js`.
 */

const VARIANT = "V2";

// Feed URLs are resolved from these indexes, never hardcoded.
const SOURCES = [
  {
    source: "ambici",
    index: "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json",
    dynamic: ["station_status", "free_bike_status"],
  },
  {
    source: "bicing",
    index: "https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json",
    dynamic: ["station_status"],
  },
];

// Feed lists per source, kept across passes while the isolate lives.
const heldFeeds = new Map();

/** Formats epoch ms as UTC `YYYYMMDDTHHMMSSZ` (ADR 0005). */
function formatTimestamp(now) {
  return new Date(now).toISOString().replace(/\.\d+Z$/, "Z").replace(/[-:]/g, "");
}

/** Formats epoch ms as the UTC date `YYYY-MM-DD`. */
function formatDate(now) {
  return new Date(now).toISOString().slice(0, 10);
}

/** Returns the `{ name, url }` entries of a GBFS index (2.x or 3.0). */
function listFeeds(index) {
  // GBFS 3.0 lists the feeds directly; 2.x nests them per language.
  return index.data.feeds ?? index.data.en.feeds;
}

/** Gzips a readable stream and returns the compressed bytes. */
function gzip(stream) {
  // R2 needs a known length, so the compressed output is buffered.
  return new Response(stream.pipeThrough(new CompressionStream("gzip"))).arrayBuffer();
}

/**
 * Fetches `url`, gzips the body and stores it at `key`.
 * Never throws: the outcome is returned as one log entry.
 */
async function captureFeed(env, { source, feed, url, key }) {
  const entry = { source, feed, url, key, status: null, latency_ms: null, bytes: null, error: null };
  const started = Date.now();
  try {
    const response = await fetch(url);
    entry.status = response.status;
    if (!response.ok) {
      throw new Error(`feed returned ${response.status}`);
    }
    // Latency spans the request until the body is fully read, so the body is
    // read before compressing to keep compression time out of it.
    const raw = await response.arrayBuffer();
    entry.latency_ms = Date.now() - started;
    const bytes = await gzip(new Blob([raw]).stream());
    await env.BUCKET.put(key, bytes);
    entry.bytes = bytes.byteLength;
  } catch (error) {
    entry.error = String(error);
  }
  return entry;
}

/**
 * Fetches a source's index and returns its log entry, parsed feed list and
 * raw body (null on failure).
 */
async function fetchIndex({ source, index }) {
  const entry = { source, feed: "gbfs", url: index, key: null, status: null, latency_ms: null, bytes: null, error: null };
  const started = Date.now();
  try {
    const response = await fetch(index);
    entry.status = response.status;
    if (!response.ok) {
      throw new Error(`index returned ${response.status}`);
    }
    const body = await response.text();
    entry.latency_ms = Date.now() - started;
    entry.bytes = body.length;
    return { entry, feeds: listFeeds(JSON.parse(body)), body };
  } catch (error) {
    entry.error = String(error);
    return { entry, feeds: [], body: null };
  }
}

/** Reads a source's persisted index from `<variant>/state/`; null if absent or unreadable. */
async function loadPersistedFeeds(env, source) {
  try {
    const object = await env.BUCKET.get(`${VARIANT}/state/${source}_index.json`);
    return object ? listFeeds(JSON.parse(await object.text())) : null;
  } catch {
    return null;
  }
}

/**
 * Resolves a source's feed list under the index refresh policy.
 *
 * The index is fetched when `refresh` is set or when none is known (memory,
 * then `<variant>/state/`); a fetched index is held in memory and persisted. A failed
 * fetch keeps the last known index. `entry` is the `gbfs` log line, or null
 * when no fetch was made.
 */
async function resolveIndex(env, source, refresh) {
  let feeds = heldFeeds.get(source.source) ?? (await loadPersistedFeeds(env, source.source));
  if (feeds && !refresh) {
    heldFeeds.set(source.source, feeds);
    return { entry: null, feeds };
  }
  const fetched = await fetchIndex(source);
  if (fetched.body !== null) {
    feeds = fetched.feeds;
    heldFeeds.set(source.source, feeds);
    try {
      await env.BUCKET.put(`${VARIANT}/state/${source.source}_index.json`, fetched.body);
    } catch (error) {
      fetched.entry.error = String(error);
    }
  } else if (feeds) {
    heldFeeds.set(source.source, feeds);
  }
  return { entry: fetched.entry, feeds: feeds ?? [] };
}

/**
 * Runs one capture pass at `now` (epoch ms) and returns the log entries.
 *
 * Indexes are refreshed when `includeStatic` is set and otherwise reused
 * (see `resolveIndex`). A failure in one feed or one index does not stop the
 * others.
 */
export async function runPass(env, { now, includeStatic, includeDynamic }) {
  const date = formatDate(now);
  const ts = formatTimestamp(now);

  const indexes = await Promise.all(SOURCES.map((s) => resolveIndex(env, s, includeStatic)));
  const entries = indexes.map((i) => i.entry).filter((e) => e !== null);

  const jobs = [];
  SOURCES.forEach((s, i) => {
    for (const { name, url } of indexes[i].feeds) {
      const isDynamic = s.dynamic.includes(name);
      if (isDynamic ? !includeDynamic : !includeStatic) {
        continue;
      }
      const key = `${VARIANT}/raw/${s.source}/${name}/${date}/${ts}.json.gz`;
      jobs.push(captureFeed(env, { source: s.source, feed: name, url, key }));
    }
  });
  entries.push(...(await Promise.all(jobs)));

  const logKey = `${VARIANT}/logs/${date}/${ts}.jsonl`;
  // Explicit field list: the log format is fixed, in this order.
  const lines = entries.map(({ source, feed, status, latency_ms, bytes, error }) =>
    JSON.stringify({ ts, source, feed, status, latency_ms, bytes, error }),
  );
  await env.BUCKET.put(logKey, lines.join("\n") + "\n");
  return { logKey, entries };
}

export default {
  async scheduled(controller, env) {
    const time = new Date(controller.scheduledTime);
    const atStaticMinute = time.getUTCMinutes() === 17;
    // Dynamic feeds are skipped only in the minute-17 pass of odd UTC hours.
    const skipDynamic = atStaticMinute && time.getUTCHours() % 2 === 1;
    await runPass(env, {
      now: controller.scheduledTime,
      includeStatic: atStaticMinute,
      includeDynamic: !skipDynamic,
    });
  },

  async fetch(request, env) {
    // Browsers also ask for /favicon.ico; capture only once per visit.
    if (new URL(request.url).pathname !== "/") {
      return new Response(null, { status: 404 });
    }
    // Both flags on: the worst case for the CPU budget.
    const { logKey, entries } = await runPass(env, {
      now: Date.now(),
      includeStatic: true,
      includeDynamic: true,
    });
    const feeds = entries.map(({ source, feed, status, latency_ms, bytes, error }) => ({
      source,
      feed,
      status,
      latency_ms,
      bytes,
      error,
    }));
    return Response.json({ logKey, feeds });
  },
};
