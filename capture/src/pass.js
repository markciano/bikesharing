// Runs one capture pass: each source's dynamic feeds and the extra fetch of the
// minute, the heartbeat, and the pass's log object, written whatever happened before
// (d004, Architecture).

import * as gbfs from "./adapters/gbfs.js";
import { LIMITS, fetchFeed, gunzipText } from "./fetch.js";
import { sendHeartbeat } from "./heartbeat.js";
import { readIndex, writeIndex } from "./index-state.js";
import { buildEvent, writeLog } from "./log.js";
import { extraFetch } from "./schedule.js";
import { SOURCES, requiredFeeds } from "./sources.js";
import { putOnce, rawKey, runIdOf } from "./storage.js";

/**
 * Each source `kind` → the adapter that validates its index, and the feed name its
 * index is stored under in `raw/`.
 * @type {Readonly<Record<string, { parseIndex: typeof gbfs.parseIndex, indexFeed: string }>>}
 */
const ADAPTERS = Object.freeze({
  gbfs: { parseIndex: gbfs.parseIndex, indexFeed: "gbfs" },
});

/**
 * @typedef {object} PassDeps
 * @property {R2Bucket} bucket
 * @property {string} heartbeatUrl
 * @property {string} version
 * @property {readonly import("./sources.js").Source[]} [sources] Default `SOURCES`
 * @property {typeof LIMITS} [limits]      Default `LIMITS`
 * @property {() => Date} [now]            Default `() => new Date()`
 */

/**
 * The state one pass shares across its sources.
 * @typedef {object} Pass
 * @property {R2Bucket} bucket
 * @property {typeof LIMITS} limits
 * @property {string} runId
 * @property {Date} start
 * @property {(level: 'info' | 'warning' | 'error', event: string, fields: Record<string, unknown>) => void} log
 */

/**
 * `runId` comes from `now()` at the start; the extra fetch from `scheduledTime`.
 * An index refresh adopts a valid index only once stored under `raw/` and `state/`.
 * Sources run in parallel, and so do the fetches within a source. The log is written in
 * `finally`. Never throws.
 * @param {number} scheduledTime
 * @param {PassDeps} deps
 * @returns {Promise<void>}
 */
export async function runPass(scheduledTime, deps) {
  const { bucket, heartbeatUrl, version, sources = SOURCES, limits = LIMITS, now = () => new Date() } = deps;
  const start = now();
  const runId = runIdOf(start);
  /** @type {Record<string, unknown>[]} */
  const events = [];
  const ctx = { runId, version };
  /** @type {Pass} */
  const pass = {
    bucket,
    limits,
    runId,
    start,
    log: (level, event, fields) => events.push(buildEvent(ctx, now(), level, event, fields)),
  };

  try {
    const extra = extraFetch(scheduledTime);
    const stored = await Promise.all(sources.map((source) => runSource(pass, source, extra)));
    if (extra?.type === "heartbeat") {
      // The signal means data is being stored, not only that the Worker ran, so it
      // is sent only when every dynamic feed of every source was stored
      // (d004 D10, Capture heartbeat).
      if (stored.every(Boolean)) await heartbeat(pass, heartbeatUrl);
    }
  } catch (err) {
    // Every step logs its own failures; this only keeps an unexpected error from
    // losing the pass's log (d004 D8, Capture failure behaviour).
    console.error(err);
  } finally {
    await writeLog(bucket, runId, events, limits);
  }
}

/**
 * One source's part of the pass. A source with no valid index fetches only its index,
 * since its feed URLs are unknown (d004 D8, Capture failure behaviour).
 * @param {Pass} pass
 * @param {import("./sources.js").Source} source
 * @param {import("./schedule.js").ExtraFetch | null} extra
 * @returns {Promise<boolean>} Whether every dynamic feed of the source was stored
 */
async function runSource(pass, source, extra) {
  const index = await readIndex(pass.bucket, source.id);
  if (!index) {
    await refreshIndex(pass, source);
    return false;
  }

  const ownExtra = extra && extra.type !== "heartbeat" && extra.source === source.id ? extra : null;
  const [dynamic] = await Promise.all([
    Promise.all(source.dynamic.map((feed) => captureFeed(pass, source, feed, index.feeds[feed]))),
    ownExtra?.type === "index" ? refreshIndex(pass, source) : null,
    ownExtra?.type === "feed" ? captureFeed(pass, source, ownExtra.feed, index.feeds[ownExtra.feed]) : null,
  ]);
  return dynamic.every(Boolean);
}

/**
 * Fetches one feed and stores its response under `raw/`.
 * @param {Pass} pass
 * @param {import("./sources.js").Source} source
 * @param {string} feed
 * @param {string} url From the source's index in `state/`
 * @returns {Promise<boolean>} Whether the response was stored
 */
async function captureFeed(pass, source, feed, url) {
  const fetched = await fetchFeed(url, pass.limits);
  if (!fetched.ok) {
    pass.log("error", "feed_failed", { source: source.id, feed, ...failedFields(fetched, 0) });
    return false;
  }

  const put = await putOnce(pass.bucket, rawKey(source.id, feed, pass.runId), fetched.body, pass.limits);
  if (!put.ok) {
    pass.log("error", "feed_failed", { source: source.id, feed, ...writeFailedFields(fetched, put) });
    return false;
  }
  pass.log("info", "feed_captured", {
    source: source.id,
    feed,
    status: fetched.status,
    latency_ms: fetched.latencyMs,
    bytes: fetched.body.byteLength,
    attempts: put.attempts,
    recompressed: fetched.recompressed,
  });
  return true;
}

/**
 * Fetches the source's index and adopts it only once it is valid and stored under
 * both `raw/` and `state/`, so the index in use is always in bronze; otherwise the
 * last valid index stays in use (d004, Index state).
 * @param {Pass} pass
 * @param {import("./sources.js").Source} source
 * @returns {Promise<void>}
 */
async function refreshIndex(pass, source) {
  const adapter = ADAPTERS[source.kind];
  const reject = (fields) => pass.log("error", "index_rejected", { source: source.id, ...fields });

  const fetched = await fetchFeed(source.indexUrl, pass.limits);
  if (!fetched.ok) return reject(failedFields(fetched, 0));

  const response = { status: fetched.status, latency_ms: fetched.latencyMs, attempts: 0 };
  const text = await gunzipText(fetched.body, pass.limits.maxBytes);
  if (!text.ok) return reject({ ...response, error_type: "invalid_index", error: text.error });
  const parsed = adapter.parseIndex(text.text, requiredFeeds(source));
  if (!parsed.ok) return reject({ ...response, error_type: "invalid_index", error: parsed.error });

  const put = await putOnce(pass.bucket, rawKey(source.id, adapter.indexFeed, pass.runId), fetched.body, pass.limits);
  if (!put.ok) return reject(writeFailedFields(fetched, put));
  const state = await writeIndex(pass.bucket, source.id, { refreshed_at: isoSeconds(pass.start), feeds: parsed.feeds }, pass.limits);
  if (!state.ok) return reject(writeFailedFields(fetched, state));

  pass.log("info", "index_refreshed", {
    source: source.id,
    status: fetched.status,
    latency_ms: fetched.latencyMs,
    bytes: fetched.body.byteLength,
    attempts: put.attempts,
    recompressed: fetched.recompressed,
    unknown_feeds: parsed.unknownFeeds,
  });
}

/**
 * Sends the heartbeat. A failed signal does not affect the data, so it is logged at
 * `warning` (d004 D10, Capture heartbeat).
 * @param {Pass} pass
 * @param {string} url
 * @returns {Promise<void>}
 */
async function heartbeat(pass, url) {
  const result = await sendHeartbeat(url, pass.limits);
  if (result.ok) {
    pass.log("info", "heartbeat_sent", { status: result.status, latency_ms: result.latencyMs });
    return;
  }
  pass.log("warning", "heartbeat_failed", {
    status: result.status,
    latency_ms: result.latencyMs,
    error_type: result.errorType,
    error: result.error,
  });
}

/**
 * The fields of a failed source fetch, in the order of the failure events.
 * @param {import("./fetch.js").FetchFailed} fetched
 * @param {number} attempts
 */
function failedFields(fetched, attempts) {
  return {
    status: fetched.status,
    latency_ms: fetched.latencyMs,
    attempts,
    error_type: fetched.errorType,
    error: fetched.error,
  };
}

/**
 * The fields of a response fetched but not stored.
 * @param {import("./fetch.js").FetchOk} fetched
 * @param {{ attempts: number, error?: string }} put
 */
function writeFailedFields(fetched, put) {
  return {
    status: fetched.status,
    latency_ms: fetched.latencyMs,
    attempts: put.attempts,
    error_type: "write",
    error: put.error ?? "write failed",
  };
}

/** ISO 8601 UTC to the second, as `runId` truncates the start. @param {Date} date */
function isoSeconds(date) {
  return `${date.toISOString().slice(0, 19)}Z`;
}
