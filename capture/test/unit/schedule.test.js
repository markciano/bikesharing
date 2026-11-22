// Unit tests of the pass schedule: which extra fetch each minute of a UTC day carries.
import { describe, expect, it } from "vitest";
import { extraFetch } from "../../src/schedule.js";
import { SOURCES } from "../../src/sources.js";

const DAY_START = Date.UTC(2026, 0, 1);
const MINUTE_MS = 60_000;

/** Every minute of one UTC day with its extra fetch, as `{ hour, minute, fetch }`. */
function day() {
  return Array.from({ length: 1440 }, (_, i) => ({
    hour: Math.floor(i / 60),
    minute: i % 60,
    fetch: extraFetch(DAY_START + i * MINUTE_MS),
  }));
}

/** The minutes of the day whose extra fetch equals `expected`. */
function minutesOf(expected) {
  return day().filter(({ fetch }) => fetch !== null && JSON.stringify(fetch) === JSON.stringify(expected));
}

describe("extraFetch over one UTC day", () => {
  // Verifies d004 R5
  it.each([
    ["bicing", 7],
    ["ambici", 37],
  ])("returns the index of %s 24 times, at minute %i of every hour", (source, minute) => {
    const hits = minutesOf({ type: "index", source });

    expect(hits).toHaveLength(24);
    expect(hits.every((h) => h.minute === minute)).toBe(true);
  });

  // Verifies d004 R2
  it.each([
    ["bicing", 12],
    ["ambici", 42],
  ])("returns station_information of %s 24 times, at minute %i of every hour", (source, minute) => {
    const hits = minutesOf({ type: "feed", source, feed: "station_information" });

    expect(hits).toHaveLength(24);
    expect(hits.every((h) => h.minute === minute)).toBe(true);
  });

  // Verifies d009 R43
  it("returns the heartbeat 288 times, at every minute that is a multiple of 5 and at no other", () => {
    const hits = minutesOf({ type: "heartbeat" });

    expect(hits).toHaveLength(288);
    expect(hits.every((h) => h.minute % 5 === 0)).toBe(true);
  });

  // Verifies d004 R3
  it.each([
    [0, "bicing", "system_information"],
    [2, "ambici", "system_information"],
    [4, "bicing", "system_pricing_plans"],
    [6, "ambici", "system_pricing_plans"],
    [8, "bicing", "system_regions"],
    [10, "ambici", "system_regions"],
    [12, "bicing", "vehicle_types"],
    [14, "ambici", "vehicle_types"],
    [16, "bicing", "geofencing_zones"],
    [18, "ambici", "geofencing_zones"],
    [20, "bicing", "gbfs_versions"],
    [22, "ambici", "system_hours"],
  ])("returns the daily feed at %i:52 once: %s %s", (hour, source, feed) => {
    const hits = minutesOf({ type: "feed", source, feed });

    expect(hits).toHaveLength(1);
    expect(hits[0]).toMatchObject({ hour, minute: 52 });
  });

  // Verifies d004 R4
  // Each minute has one extra fetch at most, so 396 = 288 heartbeats + 108 others
  // proves that no heartbeat minute is also an index or feed minute.
  it("returns an extra fetch at exactly 396 minutes", () => {
    expect(day().filter(({ fetch }) => fetch !== null)).toHaveLength(396);
  });

  // Verifies d004 R4
  it("schedules every hourly and daily feed of SOURCES", () => {
    const scheduled = new Set(
      day()
        .map(({ fetch }) => fetch)
        .filter((f) => f?.type === "feed")
        .map((f) => `${f.source}/${f.feed}`),
    );
    const expected = SOURCES.flatMap((s) => [...s.hourly, ...s.daily].map((feed) => `${s.id}/${feed}`));

    expect([...scheduled].sort()).toEqual([...expected].sort());
  });

  it("returns only the heartbeat at minute 0", () => {
    const fetches = day().filter(({ minute }) => minute === 0).map(({ fetch }) => fetch);

    expect(fetches).toEqual(Array(24).fill({ type: "heartbeat" }));
  });
});

describe("extraFetch for a scheduledTime within its minute", () => {
  it("returns that minute's extra fetch when scheduledTime is some seconds into the minute", () => {
    const late = Date.UTC(2026, 0, 1, 3, 7, 41, 250);

    expect(extraFetch(late)).toEqual({ type: "index", source: "bicing" });
  });
});
