// Contract tests of the log events registry, capture's side: the registry is valid against
// its schema, and it holds exactly the events capture writes. The registry is reference
// data that capture and the pipeline both read, so it has a schema and no vectors.
import { Validator } from "@cfworker/json-schema";
import { describe, expect, it } from "vitest";
import vectors from "../../../contracts/capture-logs.json";
import registry from "../../../contracts/log-events.registry.json";
import schema from "../../../contracts/log-events.schema.json";

const captureEvents = registry.events.filter((e) => e.component === "capture");

describe("log events registry", () => {
  // Verifies d009 R25
  it("is valid against its schema", () => {
    const { valid, errors } = new Validator(schema, "2020-12").validate(registry);

    expect(errors).toEqual([]);
    expect(valid).toBe(true);
  });

  // Verifies d009 R25
  it("lists each pair of component and event once", () => {
    const pairs = registry.events.map((e) => `${e.component}/${e.event}`);

    expect(pairs.filter((p, i) => pairs.indexOf(p) !== i)).toEqual([]);
  });

  // Verifies d009 R25
  it("holds exactly the events of the valid capture log vectors", () => {
    const written = new Set(vectors.valid.flatMap((v) => v.inputs.map((i) => i.event)));

    expect(new Set(captureEvents.map((e) => e.event))).toEqual(written);
  });

  // Verifies d009 R27
  it("registers each valid vector at one of the levels of its event", () => {
    const levels = new Map(captureEvents.map((e) => [e.event, e.levels]));
    const used = vectors.valid.flatMap((v) => v.inputs.map((i) => [i.event, i.level]));

    for (const [event, level] of used) {
      expect(levels.get(event), `levels of ${event}`).toContain(level);
    }
  });
});
