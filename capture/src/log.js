// The pass log: builds the events of a pass and writes them as one JSON Lines object,
// with the console as a fallback when the bucket keeps failing (d004 D9, Capture logs).
import { logKey, putOnce } from "./storage.js";

/** Value of `component` in every event of this Worker (ADR-0036, One log convention for every component). */
const COMPONENT = "capture";

/**
 * @typedef {object} LogContext
 * @property {string} runId   Run ID of the pass, `YYYYMMDDTHHMMSSZ`
 * @property {string} version `CF_VERSION_METADATA.id`
 */

/**
 * One event: `ts`, `level`, `component` (`capture`), `version`, `run_id` and `event`,
 * in that order, then `fields`. Pure.
 * @param {LogContext} ctx
 * @param {Date} ts
 * @param {'info' | 'warning' | 'error'} level
 * @param {string} event  One of the events of the capture log
 * @param {Record<string, unknown>} fields Its own fields, in snake_case
 * @returns {Record<string, unknown>}
 */
export function buildEvent(ctx, ts, level, event, fields) {
  return {
    ts: ts.toISOString(),
    level,
    component: COMPONENT,
    version: ctx.version,
    run_id: ctx.runId,
    event,
    ...fields,
  };
}

/**
 * JSON Lines, one event per line, ending in a newline. Pure.
 * @param {Record<string, unknown>[]} events
 * @returns {string}
 */
export function toJsonl(events) {
  return events.map((e) => JSON.stringify(e) + "\n").join("");
}

/**
 * `putOnce` to `logKey(runId)`. If it still fails, writes each line with `console.log`
 * and the write error with `console.error`, which reach Workers Logs. Never throws.
 * @param {R2Bucket} bucket
 * @param {string} runId
 * @param {Record<string, unknown>[]} events
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<void>}
 */
export async function writeLog(bucket, runId, events, limits) {
  const key = logKey(runId);
  const result = await putOnce(bucket, key, toJsonl(events), limits);
  if (result.ok) return;
  // The log explains the pass's failures; if R2 cannot keep it, Workers Logs still can.
  for (const event of events) console.log(JSON.stringify(event));
  console.error(`log write failed for ${key} after ${result.attempts} attempts: ${result.error}`);
}
