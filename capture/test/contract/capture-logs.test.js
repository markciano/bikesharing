// Contract tests of the capture log lines: the producer side builds every valid case of
// the shared vectors in contracts/capture-logs.json.
import { describe, expect, it } from "vitest";
import vectors from "../../../contracts/capture-logs.json";
import { buildEvent, toJsonl } from "../../src/log.js";

describe("capture logs contract", () => {
  // Verifies d004 R15
  it.each(vectors.valid.map((v) => [v.name, v]))("builds the JSON Lines of the valid case: %s", (_name, v) => {
    const events = v.inputs.map((i) =>
      buildEvent({ runId: i.run_id, version: i.version }, new Date(i.ts), i.level, i.event, i.fields),
    );

    expect(toJsonl(events)).toBe(v.jsonl);
  });
});
