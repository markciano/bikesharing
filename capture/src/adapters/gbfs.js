// Reads a GBFS index (2.x or 3.0) and keeps it only when every feed capture
// takes is listed with a name and a URL (d004 D8, Capture failure behaviour).

/** The index lists itself as a feed; it is neither required nor unknown. */
const INDEX_FEED = "gbfs";

/**
 * @typedef {{ ok: true, feeds: Record<string, string>, unknownFeeds: string[] }
 *         | { ok: false, error: string }} IndexResult
 * `feeds`: feed name → URL, for the required feeds only.
 * `unknownFeeds`: feeds in the index that are not required, sorted; logged so that
 * a feed added by the source is noticed (d004 D9, Capture logs).
 * `error`: why the index is invalid, for the `index_rejected` event.
 */

/**
 * Valid when the text parses as JSON, every feed entry has `name` and `url`,
 * and every required feed is listed. Never throws.
 * @param {string} text                Decompressed body of the index
 * @param {readonly string[]} required From `requiredFeeds(source)`
 * @returns {IndexResult}
 */
export function parseIndex(text, required) {
  let index;
  try {
    index = JSON.parse(text);
  } catch {
    return { ok: false, error: "index is not JSON" };
  }

  const entries = listFeeds(index);
  if (!Array.isArray(entries)) {
    return { ok: false, error: "index has no feed list in data.feeds or data.en.feeds" };
  }

  const listed = {};
  for (const [i, entry] of entries.entries()) {
    if (typeof entry?.name !== "string" || entry.name === "") {
      return { ok: false, error: `feed entry ${i} has no name` };
    }
    if (typeof entry.url !== "string" || entry.url === "") {
      return { ok: false, error: `feed entry ${entry.name} has no url` };
    }
    listed[entry.name] = entry.url;
  }

  const feeds = {};
  for (const name of required) {
    if (!(name in listed)) return { ok: false, error: `required feed ${name} is missing` };
    feeds[name] = listed[name];
  }

  const unknownFeeds = Object.keys(listed)
    .filter((name) => name !== INDEX_FEED && !required.includes(name))
    .sort();
  return { ok: true, feeds, unknownFeeds };
}

/** GBFS 3.0 lists the feeds in `data.feeds`; 2.x nests them per language, in `data.en.feeds`. */
function listFeeds(index) {
  return index?.data?.feeds ?? index?.data?.en?.feeds;
}
