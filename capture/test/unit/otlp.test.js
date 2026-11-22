// Unit tests of capture's OTLP sender: the request built from a pass's JSON lines, and its
// single send to Grafana Cloud, which comes back as a result and never throws. The
// endpoint is simulated in vitest.config.js; limits are the tests' own.
import { env } from "cloudflare:workers";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SEVERITY_NUMBER, buildLogsRequest, sendLogs } from "../../src/otlp.js";

const LIMITS = env.TEST_LIMITS;
const SIM = "https://sim.test";
const VERSION = "7f3c2a9e-1b4d-4c6a-8e2f-5d9b0a1c3e47";
const RUN_ID = "20261018T120003Z";

/** A JSON line as capture writes it: the common fields first, then the event's own. */
const line = (fields = {}, common = {}) =>
  JSON.stringify({
    ts: "2026-01-01T00:00:00.871Z",
    level: "info",
    component: "capture",
    version: VERSION,
    run_id: RUN_ID,
    event: "feed_captured",
    ...common,
    ...fields,
  });

/** The attributes of a record as `{ key: value }` pairs in order, for readable expectations. */
const attrs = (record) => record.attributes.map((a) => [a.key, a.value]);

/** The requests `otlp/<id>/v1/logs` received. @param {string} id */
async function seen(id) {
  return (await fetch(`${SIM}/otlp-seen/${id}/v1/logs`)).json();
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SEVERITY_NUMBER", () => {
  it("gives each level its OpenTelemetry severity number", () => {
    expect(SEVERITY_NUMBER).toEqual({ info: 9, warn: 13, error: 17 });
  });
});

describe("buildLogsRequest", () => {
  it("builds one resource per component and version, in order of first appearance, with one scope each", () => {
    const lines = [
      line({}, { version: "v2" }),
      line({}, { version: "v1" }),
      line({}, { version: "v2" }),
      line({}, { component: "pipeline", version: "v1" }),
    ];

    const { resourceLogs } = buildLogsRequest(lines);

    expect(resourceLogs.map((r) => r.resource.attributes)).toEqual([
      [
        { key: "service.name", value: { stringValue: "capture" } },
        { key: "service.version", value: { stringValue: "v2" } },
      ],
      [
        { key: "service.name", value: { stringValue: "capture" } },
        { key: "service.version", value: { stringValue: "v1" } },
      ],
      [
        { key: "service.name", value: { stringValue: "pipeline" } },
        { key: "service.version", value: { stringValue: "v1" } },
      ],
    ]);
    expect(resourceLogs.map((r) => r.scopeLogs.map((s) => s.scope.name))).toEqual([["capture"], ["capture"], ["pipeline"]]);
    expect(resourceLogs.map((r) => r.scopeLogs[0].logRecords.length)).toEqual([2, 1, 1]);
  });

  it("builds one record per line, in order, with the time in nanoseconds as a decimal string", () => {
    const lines = [
      line({ system: "bicing" }),
      line({ system: "ambici" }, { ts: "2026-01-01T00:00:01.002Z" }),
    ];

    const [{ scopeLogs }] = buildLogsRequest(lines).resourceLogs;
    const records = scopeLogs[0].logRecords;

    expect(records.map((r) => r.timeUnixNano)).toEqual(["1767225600871000000", "1767225601002000000"]);
    expect(records.map((r) => attrs(r).find(([k]) => k === "system")[1])).toEqual([
      { stringValue: "bicing" },
      { stringValue: "ambici" },
    ]);
  });

  it("gives each record its level as severityText and its severity number", () => {
    const lines = ["info", "warn", "error"].map((level) => line({}, { level }));

    const records = buildLogsRequest(lines).resourceLogs[0].scopeLogs[0].logRecords;

    expect(records.map((r) => [r.severityText, r.severityNumber])).toEqual([
      ["info", 9],
      ["warn", 13],
      ["error", 17],
    ]);
  });

  it("maps every field but ts, level, component and version to an attribute, typed, in the line's order", () => {
    const l = line({
      system: "bicing",
      status: 200,
      latency_ms: 412,
      recompressed: false,
      ratio: 0.5,
      unknown_feeds: ["a", "b"],
      headers: { server: "nginx" },
    });

    const [record] = buildLogsRequest([l]).resourceLogs[0].scopeLogs[0].logRecords;

    expect(attrs(record)).toEqual([
      ["run_id", { stringValue: RUN_ID }],
      ["event", { stringValue: "feed_captured" }],
      ["system", { stringValue: "bicing" }],
      ["status", { intValue: "200" }],
      ["latency_ms", { intValue: "412" }],
      ["recompressed", { boolValue: false }],
      ["ratio", { doubleValue: 0.5 }],
      ["unknown_feeds", { stringValue: '["a","b"]' }],
      ["headers", { stringValue: '{"server":"nginx"}' }],
    ]);
  });

  it("leaves out a null field", () => {
    const l = line({ system: "bicing", feed: null, status: null });

    const [record] = buildLogsRequest([l]).resourceLogs[0].scopeLogs[0].logRecords;

    expect(attrs(record).map(([key]) => key)).toEqual(["run_id", "event", "system"]);
  });

  // Verifies d009 R2
  it("builds a record for an event and a system the code has never seen", () => {
    const l = line({ system: "zzz-bikes", brand_new_field: 7 }, { event: "never_seen_event" });

    const [record] = buildLogsRequest([l]).resourceLogs[0].scopeLogs[0].logRecords;

    expect(attrs(record)).toEqual([
      ["run_id", { stringValue: RUN_ID }],
      ["event", { stringValue: "never_seen_event" }],
      ["system", { stringValue: "zzz-bikes" }],
      ["brand_new_field", { intValue: "7" }],
    ]);
  });

  // Verifies d009 R6
  it("sets each record's body to its line as written, never serialized again", () => {
    // Spaces and key order that JSON.stringify would not produce, and a redacted secret.
    const odd = `{"ts": "2026-01-01T00:00:00.871Z", "level":"error","component":"capture","version":"${VERSION}","run_id":"${RUN_ID}","event":"heartbeat_failed","error":"Error: failed to reach [redacted]"}`;
    const lines = [line({ system: "bicing" }), odd];

    const records = buildLogsRequest(lines).resourceLogs[0].scopeLogs[0].logRecords;

    expect(records.map((r) => r.body)).toEqual(lines.map((stringValue) => ({ stringValue })));
  });

  it("builds a request with no resources when there are no lines", () => {
    expect(buildLogsRequest([])).toEqual({ resourceLogs: [] });
  });
});

describe("sendLogs", () => {
  it("returns null when Grafana answers 200, after one POST of the request with the Basic credential", async () => {
    const lines = [line({ system: "bicing" }), line({ system: "ambici" })];
    const target = { endpoint: `${SIM}/otlp/auth-1/v1/logs`, token: "dXNlcjp0b2tlbg==" };

    const result = await sendLogs(target, lines, LIMITS);

    expect(result).toBeNull();
    const requests = await seen("auth-1");
    expect(requests).toHaveLength(1);
    expect(requests[0].authorization).toBe("Basic dXNlcjp0b2tlbg==");
    expect(JSON.parse(requests[0].body)).toEqual(buildLogsRequest(lines));
  });

  it("sends the request as JSON", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 200 }));

    await sendLogs({ endpoint: `${SIM}/otlp/json-1/v1/logs`, token: "t" }, [line()], LIMITS);

    const [, init] = spy.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });

  it("sends no request and returns null when there are no lines", async () => {
    const spy = vi.spyOn(globalThis, "fetch");

    const result = await sendLogs({ endpoint: `${SIM}/otlp/empty-1/v1/logs`, token: "t" }, [], LIMITS);

    expect(result).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("fails as http with the status when Grafana answers 500", async () => {
    const result = await sendLogs({ endpoint: `${SIM}/http-500/otlp`, token: "t" }, [line()], LIMITS);

    expect(result).toMatchObject({ errorType: "http", status: 500 });
    expect(result.error).toEqual(expect.any(String));
  });

  // Verifies d009 R5
  it("fails as timeout when the response body never ends", async () => {
    const result = await sendLogs({ endpoint: `${SIM}/stall-body/otlp`, token: "t" }, [line()], LIMITS);

    expect(result).toMatchObject({ errorType: "timeout" });
  });

  it("fails as network with no status when the request gets no response", async () => {
    const result = await sendLogs({ endpoint: `${SIM}/network-error/otlp`, token: "t" }, [line()], LIMITS);

    expect(result).toMatchObject({ errorType: "network", status: null });
    expect(result.error).toEqual(expect.any(String));
  });

  it("returns a failure instead of throwing when fetch throws", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("connect failed"));

    const result = await sendLogs({ endpoint: `${SIM}/otlp/x/v1/logs`, token: "t" }, [line()], LIMITS);

    expect(result).toMatchObject({ errorType: "network", status: null });
    expect(result.error).toContain("TypeError");
  });
});
