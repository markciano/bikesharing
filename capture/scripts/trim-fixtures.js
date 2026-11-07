// Builds capture's test fixtures from live responses: for each source, its index
// and every feed the index lists, each trimmed to a few entries, plus a manifest
// of where and when each one was fetched (d004, Fixtures; ADR-0037, Test fixtures
// per component). Run with `npm run fixtures`; Node built-in modules and `fetch` only.

import { mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { SOURCES, requiredFeeds } from "../src/sources.js";
import { parseIndex } from "../src/adapters/gbfs.js";

const FIXTURES_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "test", "fixtures");

/** Entries kept from each feed's entry list; shorter lists stay whole. */
const KEEP = 3;

/** The index's own fixture name; the index is the only response kept whole. */
const INDEX_FEED = "gbfs";

/**
 * Keys to follow from `data` to each feed's list of entries: one key when the
 * list sits right under `data`, two for `geofencing_zones`, a GeoJSON
 * FeatureCollection whose entries are in `features`, none when the feed has no
 * list. Other arrays, such as `languages` in `system_information`, are not
 * entries and stay whole.
 * @type {Readonly<Record<string, readonly string[]>>}
 */
const ENTRY_LISTS = Object.freeze({
  station_information: ["stations"],
  station_status: ["stations"],
  free_bike_status: ["bikes"],
  vehicle_status: ["vehicles"],
  system_regions: ["regions"],
  system_pricing_plans: ["plans"],
  vehicle_types: ["vehicle_types"],
  geofencing_zones: ["geofencing_zones", "features"],
  system_hours: ["rental_hours"],
  system_alerts: ["alerts"],
  gbfs_versions: ["versions"],
  system_information: [],
});

/**
 * Attribution stored with each fixture of a source, from its source card.
 * @type {Readonly<Record<string, string>>}
 */
const ATTRIBUTION = Object.freeze({
  bicing:
    "Bicing GBFS feed (system_id bike_barcelona), Barcelona. The feed has no licence " +
    "fields (CC0 by the GBFS 3.0 default); attributed as good practice.",
});

/**
 * @typedef {object} ManifestEntry
 * @property {string} source       Source ID, as in `SOURCES`
 * @property {string} feed         Feed name; `gbfs` for the index
 * @property {string} url          URL the response was fetched from
 * @property {string} captured_at  Fetch time, ISO 8601 UTC
 * @property {string} [attribution]
 */

/**
 * Fetches a URL and parses its body as JSON; `fetch` decompresses gzip itself.
 * @param {string} url
 * @returns {Promise<{ body: any, capturedAt: string }>}
 */
async function fetchJson(url) {
  const capturedAt = new Date().toISOString();
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return { body: await response.json(), capturedAt };
}

/**
 * Lists every feed of a GBFS index, 3.0 (`data.feeds`) or 2.x (`data.en.feeds`).
 * @param {any} index
 * @returns {{ name: string, url: string }[]}
 */
function listFeeds(index) {
  return index.data.feeds ?? index.data.en.feeds;
}

/**
 * Keeps the first entries of a feed's entry list; everything else as received.
 * @param {string} feed
 * @param {any} body
 * @returns {any}
 */
function trim(feed, body) {
  const path = ENTRY_LISTS[feed];
  if (path === undefined) {
    throw new Error(`feed ${feed} has no entry list in ENTRY_LISTS: add it before trimming`);
  }
  if (path.length === 0) return body;

  const trimmed = structuredClone(body);
  const parent = path.slice(0, -1).reduce((node, key) => node[key], trimmed.data);
  const last = path[path.length - 1];
  if (!Array.isArray(parent[last])) throw new Error(`feed ${feed}: data.${path.join(".")} is not a list`);
  parent[last] = parent[last].slice(0, KEEP);
  return trimmed;
}

/**
 * Writes one fixture as pretty-printed JSON and returns its manifest entry.
 * @param {string} source
 * @param {string} feed
 * @param {string} url
 * @param {any} body
 * @param {string} capturedAt
 * @returns {Promise<ManifestEntry>}
 */
async function writeFixture(source, feed, url, body, capturedAt) {
  await writeFile(join(FIXTURES_DIR, source, `${feed}.json`), JSON.stringify(body, null, 2) + "\n");
  const entry = { source, feed, url, captured_at: capturedAt };
  if (ATTRIBUTION[source]) entry.attribution = ATTRIBUTION[source];
  return entry;
}

/** @returns {Promise<void>} */
async function main() {
  /** @type {ManifestEntry[]} */
  const manifest = [];

  for (const source of SOURCES) {
    // A feed the source no longer lists must not leave a stale fixture behind.
    await rm(join(FIXTURES_DIR, source.id), { recursive: true, force: true });
    await mkdir(join(FIXTURES_DIR, source.id), { recursive: true });

    const index = await fetchJson(source.indexUrl);
    const result = parseIndex(JSON.stringify(index.body), requiredFeeds(source));
    if (!result.ok) throw new Error(`${source.id} index: ${result.error}`);
    manifest.push(await writeFixture(source.id, INDEX_FEED, source.indexUrl, index.body, index.capturedAt));

    for (const { name, url } of listFeeds(index.body)) {
      if (name === INDEX_FEED) continue;
      const feed = await fetchJson(url);
      manifest.push(await writeFixture(source.id, name, url, trim(name, feed.body), feed.capturedAt));
    }
  }

  manifest.sort((a, b) => a.source.localeCompare(b.source) || a.feed.localeCompare(b.feed));
  await writeFile(join(FIXTURES_DIR, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
  console.log(`${manifest.length} fixtures written to test/fixtures/`);
}

await main();
