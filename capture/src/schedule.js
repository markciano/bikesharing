// The pass schedule: decides the extra fetch, if any, of the pass scheduled at a given
// time, from two explicit tables of the calendar (d004, Pass schedule).

/**
 * @typedef {{ type: 'index', source: string }
 *         | { type: 'feed', source: string, feed: string }
 *         | { type: 'heartbeat' }} ExtraFetch
 */

/**
 * Extra fetch of every hour, by UTC minute. Each source's index refresh comes 5 minutes
 * before its `station_information`, so that feed uses the refreshed URLs.
 * @type {Readonly<Record<number, ExtraFetch>>}
 */
const HOURLY = Object.freeze({
  7: Object.freeze({ type: "index", source: "bicing" }),
  12: Object.freeze({ type: "feed", source: "bicing", feed: "station_information" }),
  22: Object.freeze({ type: "heartbeat" }),
  37: Object.freeze({ type: "index", source: "ambici" }),
  42: Object.freeze({ type: "feed", source: "ambici", feed: "station_information" }),
});

/** UTC minute at which the daily feeds run, in the even hours of {@link DAILY}. */
const DAILY_MINUTE = 52;

/**
 * Daily feed by UTC hour, one every 2 hours alternating sources, so an outage of one hour
 * costs at most one daily feed (d004 D4, Static feeds spread across passes).
 * @type {Readonly<Record<number, ExtraFetch>>}
 */
const DAILY = Object.freeze({
  0: Object.freeze({ type: "feed", source: "bicing", feed: "system_information" }),
  2: Object.freeze({ type: "feed", source: "ambici", feed: "system_information" }),
  4: Object.freeze({ type: "feed", source: "bicing", feed: "system_pricing_plans" }),
  6: Object.freeze({ type: "feed", source: "ambici", feed: "system_pricing_plans" }),
  8: Object.freeze({ type: "feed", source: "bicing", feed: "system_regions" }),
  10: Object.freeze({ type: "feed", source: "ambici", feed: "system_regions" }),
  12: Object.freeze({ type: "feed", source: "bicing", feed: "vehicle_types" }),
  14: Object.freeze({ type: "feed", source: "ambici", feed: "vehicle_types" }),
  16: Object.freeze({ type: "feed", source: "bicing", feed: "geofencing_zones" }),
  18: Object.freeze({ type: "feed", source: "ambici", feed: "geofencing_zones" }),
  20: Object.freeze({ type: "feed", source: "bicing", feed: "gbfs_versions" }),
  22: Object.freeze({ type: "feed", source: "ambici", feed: "system_hours" }),
});

/**
 * Reads the minute and hour in UTC of `scheduledTime`, never the clock, and looks
 * them up in the tables of the pass schedule.
 * @param {number} scheduledTime The event's `scheduledTime`, in ms since the epoch
 * @returns {ExtraFetch | null}  `null` when the minute carries no extra fetch
 */
export function extraFetch(scheduledTime) {
  // The event's time, not the clock, so a pass that starts late still makes its extra fetch.
  const at = new Date(scheduledTime);
  const minute = at.getUTCMinutes();
  if (minute === DAILY_MINUTE) return DAILY[at.getUTCHours()] ?? null;
  return HOURLY[minute] ?? null;
}
