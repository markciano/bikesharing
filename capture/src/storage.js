// Object keys and writes to the bronze bucket: write-once for raw data and logs, plain
// overwrite for state, with retries. The only module that calls the R2 binding
// (d004, Write-once).

/** Write attempts per object: the first one and up to 2 retries (d004 D8, Capture failure behaviour). */
const MAX_ATTEMPTS = 3;

/**
 * @typedef {{ ok: true, attempts: number }
 *         | { ok: false, attempts: number, error: string }} PutResult
 * `attempts`: write attempts made, 1 to 3.
 */

/**
 * The pass's start, truncated to the second, in the key format of ADR-0012.
 * @param {Date} start
 * @returns {string} `YYYYMMDDTHHMMSSZ`
 */
export function runIdOf(start) {
  // toISOString is always UTC; slicing drops the milliseconds, so they are truncated, not rounded.
  return start.toISOString().slice(0, 19).replace(/[-:]/g, "") + "Z";
}

/**
 * The UTC date of a run ID, as the date folder of its keys.
 * @param {string} runId `YYYYMMDDTHHMMSSZ`
 * @returns {string} `YYYY-MM-DD`
 */
function dateOf(runId) {
  return `${runId.slice(0, 4)}-${runId.slice(4, 6)}-${runId.slice(6, 8)}`;
}

/**
 * Key of a raw response (d004 D1, Bronze bucket and key convention).
 * @param {string} source Source ID, such as `bicing`
 * @param {string} feed   Feed name; the index is stored as `gbfs`
 * @param {string} runId  Run ID from {@link runIdOf}
 * @returns {string} `raw/<source>/<feed>/<YYYY-MM-DD>/<runId>.json.gz`
 */
export function rawKey(source, feed, runId) {
  return `raw/${source}/${feed}/${dateOf(runId)}/${runId}.json.gz`;
}

/**
 * Key of a pass's log (d004 D9, Capture logs).
 * @param {string} runId Run ID from {@link runIdOf}
 * @returns {string} `logs/date=<YYYY-MM-DD>/<runId>.jsonl`
 */
export function logKey(runId) {
  return `logs/date=${dateOf(runId)}/${runId}.jsonl`;
}

/**
 * Key of a source's last valid index (d004, Index state).
 * @param {string} source Source ID
 * @returns {string} `state/index/<source>.json`
 */
export function stateKey(source) {
  return `state/index/${source}.json`;
}

/**
 * Runs `attempt` up to {@link MAX_ATTEMPTS} times, `retryDelayMs` apart, until one
 * resolves; an attempt that throws counts as failed. Never throws.
 * @param {() => Promise<void>} attempt
 * @param {number} retryDelayMs
 * @returns {Promise<PutResult>}
 */
async function withRetries(attempt, retryDelayMs) {
  let error = "";
  for (let n = 1; n <= MAX_ATTEMPTS; n++) {
    if (n > 1) await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
    try {
      await attempt();
      return { ok: true, attempts: n };
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }
  return { ok: false, attempts: MAX_ATTEMPTS, error };
}

/**
 * Conditional put, `onlyIf` with `If-None-Match: *`, for keys under `raw/` and `logs/`.
 * A `null` answer counts as written: the key already holds an object. If the put throws,
 * `head(key)` decides: an object there counts as written; otherwise the attempt failed.
 * Up to 2 retries, `retryDelayMs` apart. Never throws.
 * @param {R2Bucket} bucket
 * @param {string} key
 * @param {Uint8Array | string} body
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<PutResult>}
 */
export async function putOnce(bucket, key, body, limits) {
  return withRetries(async () => {
    try {
      await bucket.put(key, body, { onlyIf: new Headers({ "If-None-Match": "*" }) });
    } catch (putError) {
      // Under the bucket lock an existing key throws instead of answering null, and a write
      // can be stored with its answer lost; head tells both apart from a real failure
      // without reading the error message.
      let found = null;
      try {
        found = await bucket.head(key);
      } catch {
        // A failed head proves nothing: the put's error is the one reported.
      }
      if (!found) throw putError;
    }
  }, limits.retryDelayMs);
}

/**
 * Plain put, for keys under `state/`, which each refresh overwrites; same retries as
 * {@link putOnce}. Never throws.
 * @param {R2Bucket} bucket
 * @param {string} key
 * @param {string} text
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<PutResult>}
 */
export async function putState(bucket, key, text, limits) {
  return withRetries(async () => {
    await bucket.put(key, text);
  }, limits.retryDelayMs);
}

/**
 * Reads a state object as text.
 * @param {R2Bucket} bucket
 * @param {string} key
 * @returns {Promise<string | null>} null when the object is missing or the read fails
 */
export async function getState(bucket, key) {
  try {
    const object = await bucket.get(key);
    return object ? await object.text() : null;
  } catch {
    return null;
  }
}
