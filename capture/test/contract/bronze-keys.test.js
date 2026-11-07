// Contract tests of the bronze object keys: the producer side builds every valid key of
// the shared vectors in contracts/bronze-keys.json.
import { describe, expect, it } from "vitest";
import vectors from "../../../contracts/bronze-keys.json";
import { logKey, rawKey, runIdOf } from "../../src/storage.js";

describe("bronze keys contract", () => {
  // Verifies d004 R1
  it.each(vectors.valid.map((v) => [v.name, v]))("builds the run ID of the valid case: %s", (_name, v) => {
    expect(runIdOf(new Date(v.captured_at))).toBe(v.run_id);
  });

  // Verifies d004 R1
  it.each(vectors.valid.map((v) => [v.name, v]))("builds the key of the valid case: %s", (_name, v) => {
    const runId = runIdOf(new Date(v.captured_at));

    const key = v.kind === "raw" ? rawKey(v.source, v.feed, runId) : logKey(runId);

    expect(key).toBe(v.key);
  });
});
