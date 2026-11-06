import { describe, expect, it } from "vitest";
import { SOURCES, requiredFeeds } from "../../src/sources.js";

describe("requiredFeeds", () => {
  it.each(SOURCES.map((s) => [s.id, s]))("of %s is its dynamic, hourly and daily feeds", (_id, source) => {
    expect(requiredFeeds(source)).toEqual([...source.dynamic, ...source.hourly, ...source.daily]);
  });

  it.each(SOURCES.map((s) => [s.id, s]))("of %s does not include the index gbfs", (_id, source) => {
    expect(requiredFeeds(source)).not.toContain("gbfs");
  });
});

describe("SOURCES", () => {
  it("lists ambici and bicing, both read by the gbfs adapter", () => {
    expect(SOURCES.map((s) => [s.id, s.kind])).toEqual([
      ["ambici", "gbfs"],
      ["bicing", "gbfs"],
    ]);
  });

  it("holds 3 dynamic feeds across sources", () => {
    expect(SOURCES.flatMap((s) => s.dynamic)).toHaveLength(3);
  });

  it("holds 12 daily feeds across sources", () => {
    expect(SOURCES.flatMap((s) => s.daily)).toHaveLength(12);
  });
});
