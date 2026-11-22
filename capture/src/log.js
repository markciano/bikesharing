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
 * @param {'info' | 'warn' | 'error'} level
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
 * Each event's JSON line, without its newline. The pass serializes its events once and
 * both the R2 log and the copy to Grafana are built from these same lines (d009, Sending
 * the copy). Pure.
 * @param {Record<string, unknown>[]} events
 * @returns {string[]}
 */
export function toLines(events) {
  return events.map((e) => JSON.stringify(e));
}

/**
 * JSON Lines, one event per line, ending in a newline. Pure.
 * @param {Record<string, unknown>[]} events
 * @returns {string}
 */
export function toJsonl(events) {
  return toLines(events).map((line) => line + "\n").join("");
}

/**
 * `putOnce` to `logKey(runId)`. If it still fails, writes each line with `console.log`
 * and the write error with `console.error`, which reach Workers Logs. Never throws.
 * @param {R2Bucket} bucket
 * @param {string} runId
 * @param {string[]} lines The pass's JSON lines, from `toLines`
 * @param {{ retryDelayMs: number }} limits
 * @returns {Promise<void>}
 */
export async function writeLog(bucket, runId, lines, limits) {
  const key = logKey(runId);
  const result = await putOnce(bucket, key, lines.map((line) => line + "\n").join(""), limits);
  if (result.ok) return;
  // The log explains the pass's failures; if R2 cannot keep it, Workers Logs still can.
  for (const line of lines) console.log(line);
  console.error(`log write failed for ${key} after ${result.attempts} attempts: ${result.error}`);
}
