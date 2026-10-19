// P4 producer test: objectKey returns the expected key for every valid vector of the collector contract.
import { describe, expect, it } from "vitest";
import vectors from "../../../contract/collector-contract.json";
import { objectKey } from "../../src/contract.js";

describe("objectKey", () => {
  it.each(vectors.valid)("$name", ({ source, feed, captured_at, key }) => {
    expect(objectKey(source, feed, new Date(captured_at))).toBe(key);
  });
});
