// The sources capture reads, and the feeds of each one by how often they are
// captured: every pass, hourly or daily (d004 D3, Feed cadence).
// A new GBFS source adds one entry here; a source of another kind also adds an adapter.

/**
 * @typedef {object} Source
 * @property {string} id                 Source ID in object keys and logs: `ambici` or `bicing`
 * @property {string} kind               Adapter that reads its index: `gbfs`
 * @property {string} indexUrl           URL of the source's index (`gbfs` feed)
 * @property {readonly string[]} dynamic Feeds captured every pass
 * @property {readonly string[]} hourly  Feeds captured hourly; the index is not a feed
 *                                       here: `indexUrl` names it and `schedule.js` its refresh
 * @property {readonly string[]} daily   Feeds captured daily
 * @property {boolean} retryOn403        Whether a 403 from this source is retried once
 *   (ADR-0039, Retry a 403 only on sources where it is shown to be transient)
 */

/** @type {readonly Source[]} */
export const SOURCES = Object.freeze([
  Object.freeze({
    id: "ambici",
    kind: "gbfs",
    indexUrl: "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json",
    dynamic: Object.freeze(["station_status", "free_bike_status"]),
    hourly: Object.freeze(["station_information"]),
    daily: Object.freeze([
      "system_information",
      "system_pricing_plans",
      "system_regions",
      "vehicle_types",
      "geofencing_zones",
      "system_hours",
    ]),
    retryOn403: false,
  }),
  Object.freeze({
    id: "bicing",
    kind: "gbfs",
    indexUrl: "https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json",
    dynamic: Object.freeze(["station_status"]),
    hourly: Object.freeze(["station_information"]),
    daily: Object.freeze([
      "system_information",
      "system_pricing_plans",
      "system_regions",
      "vehicle_types",
      "geofencing_zones",
      "gbfs_versions",
    ]),
    retryOn403: true,
  }),
]);

/**
 * Every feed the source's index must list for it to be valid: its dynamic,
 * hourly and daily feeds (d004 D8, Capture failure behaviour).
 * @param {Source} source
 * @returns {string[]}
 */
export function requiredFeeds(source) {
  return [...source.dynamic, ...source.hourly, ...source.daily];
}
