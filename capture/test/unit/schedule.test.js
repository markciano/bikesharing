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
  it.each([
    ["bicing", 7],
    ["ambici", 37],
  ])("returns the index of %s 24 times, at minute %i of every hour", (source, minute) => {
    const hits = minutesOf({ type: "index", source });

    expect(hits).toHaveLength(24);
    expect(hits.every((h) => h.minute === minute)).toBe(true);
  });

  it.each([
    ["bicing", 12],
    ["ambici", 42],
  ])("returns station_information of %s 24 times, at minute %i of every hour", (source, minute) => {
    const hits = minutesOf({ type: "feed", source, feed: "station_information" });

    expect(hits).toHaveLength(24);
    expect(hits.every((h) => h.minute === minute)).toBe(true);
  });

  it("returns the heartbeat 24 times, at minute 22 of every hour", () => {
    const hits = minutesOf({ type: "heartbeat" });

    expect(hits).toHaveLength(24);
    expect(hits.every((h) => h.minute === 22)).toBe(true);
  });

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

  it("returns an extra fetch at exactly 132 minutes", () => {
    expect(day().filter(({ fetch }) => fetch !== null)).toHaveLength(132);
  });

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

  it("returns no extra fetch at minute 0", () => {
    expect(day().filter(({ minute, fetch }) => minute === 0 && fetch !== null)).toEqual([]);
  });
});

describe("extraFetch for a scheduledTime within its minute", () => {
  it("returns that minute's extra fetch when scheduledTime is some seconds into the minute", () => {
    const late = Date.UTC(2026, 0, 1, 3, 7, 41, 250);

    expect(extraFetch(late)).toEqual({ type: "index", source: "bicing" });
  });
});
