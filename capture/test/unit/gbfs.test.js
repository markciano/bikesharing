// Unit tests of parseIndex: valid GBFS 2.x and 3.0 indexes, and each reason to reject one.
import { describe, expect, it } from "vitest";
import { parseIndex } from "../../src/adapters/gbfs.js";

const REQUIRED = ["station_status", "station_information"];
const url = (name) => `https://example.test/gbfs/${name}.json`;
const entries = (...names) => names.map((name) => ({ name, url: url(name) }));

/** GBFS 3.0 lists the feeds in `data.feeds` (Bicing). */
const v3 = (feeds) => JSON.stringify({ version: "3.0", data: { feeds } });
/** GBFS 2.x nests them per language, in `data.en.feeds` (AMBici). */
const v2 = (feeds) => JSON.stringify({ version: "2.3", data: { en: { feeds } } });

describe("parseIndex", () => {
  it.each([
    ["GBFS 3.0", v3],
    ["GBFS 2.x", v2],
  ])("returns the URLs of the required feeds of a valid %s index", (_shape, build) => {
    const result = parseIndex(build(entries("gbfs", "station_information", "station_status")), REQUIRED);

    expect(result).toEqual({
      ok: true,
      feeds: { station_status: url("station_status"), station_information: url("station_information") },
      unknownFeeds: [],
    });
  });

  it("returns the feeds that are not required as unknownFeeds, sorted, without gbfs", () => {
    const text = v3(entries("vehicle_availability", "station_status", "gbfs", "station_information", "alerts"));

    const result = parseIndex(text, REQUIRED);

    expect(result.ok).toBe(true);
    expect(result.unknownFeeds).toEqual(["alerts", "vehicle_availability"]);
    expect(Object.keys(result.feeds).sort()).toEqual([...REQUIRED].sort());
  });

  // Verifies d004 R12
  it("rejects text that is not JSON", () => {
    const result = parseIndex("<html>Bad gateway</html>", REQUIRED);

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/JSON/);
  });

  // Verifies d004 R12
  it("rejects JSON with no feed list", () => {
    const result = parseIndex(JSON.stringify({ data: {} }), REQUIRED);

    expect(result.ok).toBe(false);
    expect(result.error).toEqual(expect.any(String));
  });

  // Verifies d004 R12
  it("rejects an index with an entry without name", () => {
    const text = v3([...entries(...REQUIRED), { url: url("alerts") }]);

    const result = parseIndex(text, REQUIRED);

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/name/);
  });

  // Verifies d004 R12
  it("rejects an index with an entry without url", () => {
    const text = v3([...entries("station_information"), { name: "station_status" }]);

    const result = parseIndex(text, REQUIRED);

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/url/);
  });

  // Verifies d004 R12
  it("rejects an index missing a required feed, naming it", () => {
    const result = parseIndex(v3(entries("gbfs", "station_information")), REQUIRED);

    expect(result).toEqual({ ok: false, error: "required feed station_status is missing" });
  });
});
