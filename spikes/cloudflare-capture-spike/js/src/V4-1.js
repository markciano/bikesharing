/**
 * Smoke test (spike plan step 2.7): does `encodeResponseBody: 'manual'` make
 * the Worker `fetch` hand over the origin's gzip bytes undecoded (F8)?
 *
 * Requests one feed per source with `Accept-Encoding: gzip` and
 * `encodeResponseBody: 'manual'`, then:
 *   - Test A: streams the unread body to R2 under `V4-1/<source>/<feed>/passthrough.gz`.
 *   - Test B, only if A fails: reads the body into memory and stores those bytes
 *     under `V4-1/<source>/<feed>/buffered.gz`.
 * It reports status, headers and the outcome of each test per feed.
 */

// Feed URLs are resolved from each index, as the source cards require.
const FEEDS = [
  {
    source: "ambici",
    feed: "free_bike_status",
    index: "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_bs/gbfs.json",
  },
  {
    source: "bicing",
    feed: "station_status",
    index: "https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json",
  },
];

/** Returns the URL of `feed` listed in a GBFS index (2.x or 3.0). */
async function resolveFeedUrl(index, feed) {
  const response = await fetch(index);
  if (!response.ok) {
    throw new Error(`index returned ${response.status}`);
  }
  const { data } = await response.json();
  // GBFS 3.0 lists the feeds directly; 2.x nests them per language.
  const feeds = data.feeds ?? data.en.feeds;
  const entry = feeds.find((f) => f.name === feed);
  if (!entry) {
    throw new Error(`${feed} not in index`);
  }
  return entry.url;
}

/** Requests the feed asking for gzip and leaving the body encoded. */
function fetchGzip(url) {
  return fetch(url, {
    headers: { "Accept-Encoding": "gzip" },
    encodeResponseBody: "manual",
  });
}

/** Runs tests A and B for one feed and returns the report. */
async function capture(env, { source, feed, index }) {
  const prefix = `V4-1/${source}/${feed}`;
  const report = { source, feed };
  try {
    report.url = await resolveFeedUrl(index, feed);
    const response = await fetchGzip(report.url);
    report.status = response.status;
    report["content-encoding"] = response.headers.get("content-encoding");
    report["content-length"] = response.headers.get("content-length");

    // Test A: the body is handed over unread.
    try {
      const object = await env.BUCKET.put(`${prefix}/passthrough.gz`, response.body);
      report.A = { key: `${prefix}/passthrough.gz`, size: object.size, etag: object.etag };
      return report;
    } catch (error) {
      report.A = { error: String(error) };
    }

    // Test B: A consumed the first body, so the feed is requested again.
    try {
      const retry = await fetchGzip(report.url);
      const bytes = await retry.arrayBuffer();
      const object = await env.BUCKET.put(`${prefix}/buffered.gz`, bytes);
      report.B = {
        key: `${prefix}/buffered.gz`,
        status: retry.status,
        "content-encoding": retry.headers.get("content-encoding"),
        byteLength: bytes.byteLength,
        size: object.size,
        etag: object.etag,
      };
    } catch (error) {
      report.B = { error: String(error) };
    }
  } catch (error) {
    report.error = String(error);
  }
  return report;
}

export default {
  async fetch(request, env) {
    // Browsers also ask for /favicon.ico; capture only once per visit.
    if (new URL(request.url).pathname !== "/") {
      return new Response(null, { status: 404 });
    }
    const results = await Promise.all(FEEDS.map((f) => capture(env, f)));
    return Response.json(results);
  },
};
