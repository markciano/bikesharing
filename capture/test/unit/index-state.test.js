// Unit tests of the index state: a source's last valid index round-trips through the
// in-memory R2, and anything that is not a valid state reads as no index.
import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";
import { readIndex, writeIndex } from "../../src/index-state.js";
import { stateKey } from "../../src/storage.js";

const LIMITS = { retryDelayMs: 0 };
const STATE = {
  refreshed_at: "2026-11-06T10:07:00Z",
  feeds: {
    station_status: "https://example.test/station_status.json",
    station_information: "https://example.test/station_information.json",
  },
};

describe("writeIndex and readIndex", () => {
  it("reads back a written state unchanged", async () => {
    const result = await writeIndex(env.BUCKET, "roundtrip", STATE, LIMITS);

    expect(result).toEqual({ ok: true, attempts: 1 });
    expect(await readIndex(env.BUCKET, "roundtrip")).toEqual(STATE);
  });

  it("reads the latest state after a second write overwrites the first", async () => {
    const later = { ...STATE, refreshed_at: "2026-11-06T11:07:00Z" };
    await writeIndex(env.BUCKET, "overwrite", STATE, LIMITS);

    await writeIndex(env.BUCKET, "overwrite", later, LIMITS);

    expect(await readIndex(env.BUCKET, "overwrite")).toEqual(later);
  });
});

describe("readIndex", () => {
  it("returns null when the source has no state", async () => {
    expect(await readIndex(env.BUCKET, "missing")).toBeNull();
  });

  it.each([
    ["text that is not JSON", "not json {"],
    ["JSON without refreshed_at", JSON.stringify({ feeds: STATE.feeds })],
    ["JSON without feeds", JSON.stringify({ refreshed_at: STATE.refreshed_at })],
    ["feeds that is not an object", JSON.stringify({ ...STATE, feeds: ["https://example.test"] })],
    ["a feed URL that is not a string", JSON.stringify({ ...STATE, feeds: { station_status: 1 } })],
    ["JSON that is not an object", "null"],
  ])("returns null for %s", async (name, text) => {
    const sourceId = `invalid-${name.replaceAll(" ", "-")}`;
    await env.BUCKET.put(stateKey(sourceId), text);

    expect(await readIndex(env.BUCKET, sourceId)).toBeNull();
  });
});
