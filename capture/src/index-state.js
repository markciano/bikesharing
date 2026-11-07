// Each source's last valid index, stored under state/ and read on every pass, since the
// Worker keeps nothing in memory between passes (d004, Index state).
import { getState, putState, stateKey } from "./storage.js";

/**
 * @typedef {object} IndexState
 * @property {string} refreshed_at          ISO 8601 UTC, the pass's start
 * @property {Record<string, string>} feeds Feed name → URL, from `parseIndex`
 */

/** @typedef {import("./storage.js").PutResult} PutResult */

/**
 * Whether a parsed value has the shape of an {@link IndexState}.
 * @param {unknown} value
 * @returns {value is IndexState}
 */
function isIndexState(value) {
  if (typeof value !== "object" || value === null) return false;
  const { refreshed_at: refreshedAt, feeds } = /** @type {Record<string, unknown>} */ (value);
  if (typeof refreshedAt !== "string") return false;
  if (typeof feeds !== "object" || feeds === null || Array.isArray(feeds)) return false;
  return Object.values(feeds).every((url) => typeof url === "string");
}

/**
 * Reads a source's last valid index. Anything that is not a valid state means the
 * source has no valid index (d004 D8, Capture failure behaviour).
 * @param {R2Bucket} bucket
 * @param {string} sourceId
 * @returns {Promise<IndexState | null>} null when missing, unreadable or not an IndexState
 */
export async function readIndex(bucket, sourceId) {
  const text = await getState(bucket, stateKey(sourceId));
  if (text === null) return null;
  try {
    const value = JSON.parse(text);
    return isIndexState(value) ? value : null;
  } catch {
    return null;
  }
}

/**
 * Stores a source's index as its last valid one, overwriting the previous state.
 * @param {R2Bucket} bucket
 * @param {string} sourceId
 * @param {IndexState} state
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<PutResult>}
 */
export async function writeIndex(bucket, sourceId, state, limits) {
  return putState(bucket, stateKey(sourceId), JSON.stringify(state), limits);
}
