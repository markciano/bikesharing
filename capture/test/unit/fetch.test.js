// Unit tests of the source fetch: a response comes back as the gzip bytes to store,
// compressed by capture when the source sent plain JSON, or as its failure with the
// status and latency to log; an index body decompresses within a size limit.
// Sources are the simulated ones in vitest.config.js; limits are the tests' own.
import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";
import { USER_AGENT, fetchFeed, gunzipText, retryWait } from "../../src/fetch.js";

const LIMITS = env.TEST_LIMITS;
const SIM = "https://sim.test";

/** @param {string} b64 */
const fromBase64 = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));

/** @param {Uint8Array} bytes */
async function gunzip(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).text();
}

/** @param {string} text */
async function gzip(text) {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

describe("fetchFeed", () => {
  it("returns a gzip fixture's bytes unchanged, not recompressed", async () => {
    const { url, gzipB64 } = env.FIXTURES["bicing/station_status"];

    const result = await fetchFeed(url, LIMITS);

    expect(result).toMatchObject({ ok: true, status: 200, recompressed: false });
    expect(result.body).toEqual(fromBase64(gzipB64));
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
  });

  // Verifies d006 R8
  it("sends the capture User-Agent to a source", async () => {
    const result = await fetchFeed(`${SIM}/user-agent`, LIMITS);

    expect(result.ok).toBe(true);
    expect(await gunzip(result.body)).toBe(USER_AGENT);
  });

  it("compresses a plain JSON body and marks it recompressed", async () => {
    const expected = await gunzip(fromBase64(env.FIXTURES["bicing/station_status"].gzipB64));

    const result = await fetchFeed(`${SIM}/plain-json`, LIMITS);

    expect(result).toMatchObject({ ok: true, status: 200, recompressed: true });
    expect([...result.body.slice(0, 2)]).toEqual([0x1f, 0x8b]);
    expect(await gunzip(result.body)).toBe(expected);
  });

  it("fails as http with the status and a latency when the source answers 500", async () => {
    const result = await fetchFeed(`${SIM}/http-500`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "http", status: 500 });
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
    expect(result.error).toEqual(expect.any(String));
  });

  it("fails as timeout with the status and a latency when the body never ends", async () => {
    const result = await fetchFeed(`${SIM}/stall-body`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "timeout", status: 200 });
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
  });

  it("fails as network with null status and latency when the request throws", async () => {
    const result = await fetchFeed(`${SIM}/network-error`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "network", status: null, latencyMs: null });
    expect(result.error).toEqual(expect.any(String));
  });

  it("fails as too_large with the status and a latency when the body exceeds maxBytes", async () => {
    const result = await fetchFeed(`${SIM}/oversized`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "too_large", status: 200 });
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
  });
});

describe("retryWait", () => {
  // Verifies d006 R3
  it("waits the minimum when random is 0", () => {
    expect(retryWait(LIMITS, () => 0)).toBe(LIMITS.retry403MinMs);
  });

  // Verifies d006 R3
  it("waits the midpoint when random is 0.5", () => {
    expect(retryWait(LIMITS, () => 0.5)).toBe((LIMITS.retry403MinMs + LIMITS.retry403MaxMs) / 2);
  });

  // Verifies d006 R3
  it("waits less than the maximum when random is just below 1", () => {
    const wait = retryWait(LIMITS, () => 1 - Number.EPSILON);

    expect(wait).toBeLessThan(LIMITS.retry403MaxMs);
    expect(wait).toBeGreaterThan(LIMITS.retry403MinMs);
  });
});

describe("gunzipText", () => {
  it("returns the text of a gzip body within maxBytes", async () => {
    const { gzipB64 } = env.FIXTURES["bicing/gbfs"];
    const bytes = fromBase64(gzipB64);

    const result = await gunzipText(bytes, LIMITS.maxBytes);

    expect(result).toEqual({ ok: true, text: await gunzip(bytes) });
  });

  it("rejects a body larger than maxBytes once decompressed as too_large", async () => {
    const bytes = await gzip(" ".repeat(LIMITS.maxBytes + 1));

    const result = await gunzipText(bytes, LIMITS.maxBytes);

    expect(result).toEqual({ ok: false, errorType: "too_large", error: expect.any(String) });
  });

  it("rejects a body that is not gzip as invalid_index", async () => {
    const result = await gunzipText(new TextEncoder().encode("{}"), LIMITS.maxBytes);

    expect(result).toEqual({ ok: false, errorType: "invalid_index", error: expect.any(String) });
  });
});
