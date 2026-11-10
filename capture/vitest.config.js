// Tests run inside workerd, the Workers runtime, through @cloudflare/vitest-plugin.
// Every request the Worker sends is answered here by Miniflare's outboundService:
// the fixtures at their real URLs, and the fixed routes on https://sim.test/ below,
// the catalogue of simulated responses. Any other URL fails (d004, Tests and contracts).
// Fixtures are gzipped once here and served without Content-Encoding, so their bytes
// reach capture unchanged whatever the runtime does with `encodeResponseBody`; the
// same bytes are passed to the tests as a binding (d004, Fixtures).
import { readFileSync } from "node:fs";
import { Readable } from "node:stream";
import { gzipSync } from "node:zlib";
import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

import { SOURCES, requiredFeeds } from "./src/sources.js";

const FIXTURES_DIR = new URL("./test/fixtures/", import.meta.url);

/** Limits the tests pass instead of `LIMITS`: milliseconds and bytes, larger than any fixture. */
const TEST_LIMITS = Object.freeze({
  timeoutMs: 100,
  maxBytes: 64_000,
  retryDelayMs: 0,
  heartbeatTimeoutMs: 100,
  retry403MinMs: 1,
  retry403MaxMs: 2,
});

const SIM_ORIGIN = "https://sim.test";

/** What a route returns when the request must fail with no response at all. */
const NETWORK_ERROR = Symbol("network error");

/** @type {{ source: string, feed: string, url: string }[]} */
const manifest = JSON.parse(readFileSync(new URL("manifest.json", FIXTURES_DIR), "utf8"));

/** `<source>/<feed>` → the fixture's uncompressed text and its gzip bytes. */
const fixtures = new Map(
  manifest.map(({ source, feed, url }) => {
    const text = readFileSync(new URL(`${source}/${feed}.json`, FIXTURES_DIR), "utf8");
    return [`${source}/${feed}`, { url, text, gzip: gzipSync(text) }];
  }),
);

/** Fixture URL → its gzip bytes. */
const byUrl = new Map([...fixtures.values()].map(({ url, gzip }) => [url, gzip]));

/** @param {string} source @param {string} feed */
function fixture(source, feed) {
  const found = fixtures.get(`${source}/${feed}`);
  if (!found) throw new Error(`no fixture ${source}/${feed}`);
  return found;
}

/** A gzip body as a source serves it: no Content-Encoding, so nothing decodes it. */
const gzipResponse = (bytes) => new Response(bytes, { headers: { "Content-Type": "application/json" } });

/**
 * The source's fixture index with its feed lists changed by `edit`, in the GBFS shape
 * of that source: 3.0 lists feeds in `data.feeds`, 2.x once per language.
 * @param {string} source
 * @param {(feeds: object[]) => object[]} edit
 */
function editedIndex(source, edit) {
  const index = JSON.parse(fixture(source, "gbfs").text);
  if (Array.isArray(index.data.feeds)) index.data.feeds = edit(index.data.feeds);
  else for (const lang of Object.values(index.data)) lang.feeds = edit(lang.feeds);
  return index;
}

/** @param {string} source */
const sourceOf = (source) => {
  const found = SOURCES.find((s) => s.id === source);
  if (!found) throw new Error(`no source ${source}`);
  return found;
};

/** A body that never ends: one chunk, then nothing, so only the timeout stops the read. */
function stallingBody() {
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("{"));
    },
  });
}

/** A stream of `bytes` repeated past `limit`, with no length known in advance. */
function streamPast(bytes, limit) {
  let sent = 0;
  return new ReadableStream({
    pull(controller) {
      if (sent > limit) return controller.close();
      controller.enqueue(bytes);
      sent += bytes.length;
    },
  });
}

/**
 * The simulated routes on https://sim.test/, by first path segment. Each handler gets
 * the segments that follow; a trailing `/<id>` of the test's own is ignored by the
 * handler and only keeps the request counts of one test apart from another's.
 * @type {Record<string, (args: string[], url: string, headers: import("node:http").IncomingHttpHeaders)
 *   => Response | typeof NETWORK_ERROR>}
 */
const ROUTES = {
  // HTTP 500 with a short body: a source that answers with an error (errorType `http`).
  "http-500": () => new Response("internal error", { status: 500 }),
  // Headers, then a body that never ends: the timeout covers the body too (R7).
  "stall-body": () => new Response(stallingBody(), { headers: { "Content-Type": "application/json" } }),
  // The request throws: no response at all (errorType `network`, status and latency null).
  "network-error": () => NETWORK_ERROR,
  // A fixture served uncompressed: capture compresses it and logs `recompressed`.
  "plain-json": () =>
    new Response(fixture("bicing", "station_status").text, { headers: { "Content-Type": "application/json" } }),
  // A body larger than the tests' maxBytes, with no content-length (R22, `too_large`).
  oversized: () => new Response(streamPast(fixture("bicing", "station_status").gzip, TEST_LIMITS.maxBytes)),
  // The source's index without its first required feed: rejected by its adapter.
  "invalid-index": ([source]) => {
    const missing = requiredFeeds(sourceOf(source))[0];
    return gzipResponse(gzipSync(JSON.stringify(editedIndex(source, (f) => f.filter((e) => e.name !== missing)))));
  },
  // The source's index with one feed not in requiredFeeds: logged as unknown.
  "index-extra-feed": ([source]) =>
    gzipResponse(
      gzipSync(JSON.stringify(editedIndex(source, (f) => [...f, { name: "extra_feed", url: `${SIM_ORIGIN}/extra-feed` }]))),
    ),
  // Gzip bytes that decompress beyond the tests' maxBytes: the index's decompressed size limit.
  "index-oversized": ([source]) =>
    gzipResponse(gzipSync(fixture(source, "gbfs").text + " ".repeat(TEST_LIMITS.maxBytes))),
  // A fixture's gzip bytes at a URL other than its own: a feed the index moved (R6).
  moved: ([source, feed]) => gzipResponse(fixture(source, feed).gzip),
  // 200 with the request's User-Agent as its body: what capture sends to identify
  // the project (d006 D5, Every source request identifies the project).
  "user-agent": (_args, _url, headers) => new Response(String(headers["user-agent"] ?? "")),
  // The heartbeat endpoint answering OK.
  heartbeat: () => new Response("OK"),
  // The heartbeat request throws: no response at all.
  "heartbeat-network-error": () => NETWORK_ERROR,
};

/** Requests received by path, for the `count/<path>` route. */
const counts = new Map();

/**
 * The simulated response to a URL: a fixture at its own URL, or a route on sim.test.
 * @param {string} href
 * @param {import("node:http").IncomingHttpHeaders} headers The request's headers
 * @returns {Response | typeof NETWORK_ERROR}
 */
function simulate(href, headers) {
  const fixtureBytes = byUrl.get(href);
  if (fixtureBytes) return gzipResponse(fixtureBytes);

  const url = new URL(href);
  if (url.origin === SIM_ORIGIN) {
    const [route, ...args] = url.pathname.split("/").filter(Boolean);
    // How many requests a path has received, as plain text; not counted itself.
    if (route === "count") return new Response(String(counts.get(`/${args.join("/")}`) ?? 0));
    const handler = ROUTES[route];
    if (handler) {
      counts.set(url.pathname, (counts.get(url.pathname) ?? 0) + 1);
      return handler(args, href, headers);
    }
  }
  throw new Error(`request outside the simulated sources: ${href}`);
}

/**
 * The outbound service in Miniflare's Node handler form. Its other form, a function
 * returning a Response, turns any thrown error into an HTTP 500, so it cannot make
 * the Worker's fetch throw; closing the socket unanswered can. Workers only reach
 * sources over HTTPS, and the handler sees the path and the Host header.
 * @param {import("node:http").IncomingMessage} req
 * @param {import("node:http").ServerResponse} res
 */
async function outboundService(req, res) {
  const response = simulate(`https://${req.headers.host}${req.url}`, req.headers);
  if (response === NETWORK_ERROR) {
    req.socket.destroy();
    return;
  }
  res.writeHead(response.status, Object.fromEntries(response.headers));
  if (!response.body) return void res.end();
  // A body that never ends, like `stall-body`, keeps this pipe open; it is not awaited.
  Readable.fromWeb(response.body).pipe(res);
}

/** Each fixture's URL and gzip bytes (base64), by `<source>/<feed>`, for the tests to compare with. */
const FIXTURES = Object.fromEntries(
  [...fixtures].map(([name, { url, gzip }]) => [name, { url, gzipB64: gzip.toString("base64") }]),
);

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: {
          FIXTURES,
          TEST_LIMITS,
          HEARTBEAT_URL: `${SIM_ORIGIN}/heartbeat/default`,
        },
        outboundService: { node: outboundService },
      },
    }),
  ],
});
