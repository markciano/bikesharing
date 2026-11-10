// Unit tests of the heartbeat signal: a GET to the Healthchecks.io URL comes back as
// a result, never a throw, and no failed result carries the URL, which is a secret.
// The endpoint is simulated in vitest.config.js; limits are the tests' own.
import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it, vi } from "vitest";
import { USER_AGENT } from "../../src/fetch.js";
import { sendHeartbeat } from "../../src/heartbeat.js";

const LIMITS = env.TEST_LIMITS;
const SIM = "https://sim.test";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("sendHeartbeat", () => {
  it("returns ok with the status and a latency when the endpoint answers 200", async () => {
    const result = await sendHeartbeat(`${SIM}/heartbeat/ok`, LIMITS);

    expect(result).toMatchObject({ ok: true, status: 200 });
    expect(result.latencyMs).toBeGreaterThanOrEqual(0);
  });

  it("fails as http with the status when the endpoint answers 500", async () => {
    const result = await sendHeartbeat(`${SIM}/http-500`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "http", status: 500 });
    expect(result.error).toEqual(expect.any(String));
  });

  it("fails as timeout when the response body never ends", async () => {
    const result = await sendHeartbeat(`${SIM}/stall-body`, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "timeout" });
  });

  // Verifies d004 R23
  it("returns an error without the URL when the network error's message contains it", async () => {
    const url = `${SIM}/heartbeat/secret-check-uuid`;
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError(`connect failed: ${url} (${url})`));

    const result = await sendHeartbeat(url, LIMITS);

    expect(result).toMatchObject({ ok: false, errorType: "network", status: null, latencyMs: null });
    expect(result.error).not.toContain(url);
    expect(result.error).toContain("TypeError");
  });

  // Verifies d006 R8
  it("does not send the capture User-Agent with the heartbeat", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 200 }));

    await sendHeartbeat(`${SIM}/heartbeat/ok`, LIMITS);

    expect(spy).toHaveBeenCalledTimes(1);
    const [, init] = spy.mock.calls[0];
    expect(new Headers(init?.headers).get("User-Agent")).not.toBe(USER_AGENT);
  });
});
