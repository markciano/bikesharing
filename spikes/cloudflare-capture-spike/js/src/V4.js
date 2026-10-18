/**
 * Capturer V4 (spike plan step 4.1): one capture pass over the GBFS feeds of
 * AMBici and Bicing, storing the origin's own gzip bytes with no compression.
 *
 * `runPass` resolves both `gbfs.json` indexes, then fetches every feed they
 * list: the dynamic feeds when `includeDynamic`, the rest when `includeStatic`.
 * Each feed is stored unchanged in R2 under the V4 prefix and logged. The pass
 * ends by writing one JSONL log object with one line per request.
 *
 * The `scheduled` handler (step 4.3) runs one pass per trigger: dynamic feeds
 * every minute, static feeds at minute 17, and no dynamic feeds at minute 17
 * of odd UTC hours.
 *
 * Run a pass by hand with `npx wrangler dev --remote src/V4.js`.
 */

const VARIANT = "V4";

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

/**
 * Fetches `url` and stores the origin's gzip body unchanged at `key`.
 * Never throws: the outcome is returned as one log entry.
 */
async function captureFeed(env, { source, feed, url, key }) {
  const entry = { source, feed, url, key, status: null, latency_ms: null, bytes: null, error: null };
  const started = Date.now();
  try {
    // `encodeResponseBody: 'manual'` keeps the origin's gzip instead of
    // decoding it (F9); it is not in the docs, only in the workers-types.
    const response = await fetch(url, {
      headers: { "Accept-Encoding": "gzip" },
      encodeResponseBody: "manual",
    });
    entry.status = response.status;
    if (!response.ok) {
      throw new Error(`feed returned ${response.status}`);
    }
    // Buffered, not streamed: R2 needs a known length and Bicing sends no
    // `content-length` (F9). Reading compressed bytes costs no compression work.
    const bytes = await response.arrayBuffer();
    entry.latency_ms = Date.now() - started;
    await env.BUCKET.put(key, bytes);
    entry.bytes = bytes.byteLength;
  } catch (error) {
    entry.error = String(error);
  }
  return entry;
}

/**
 * Fetches a source's index (without the option, it is parsed) and returns its
 * log entry, parsed feed list and raw body (null on failure).
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
