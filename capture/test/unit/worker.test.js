// Unit test of the Worker's entry point: it answers the cron trigger only, so it
// exposes no public URL to call.
import { describe, expect, it } from "vitest";
import worker from "../../src/worker.js";

describe("worker entry point", () => {
  it("has a scheduled handler and no fetch handler", () => {
    expect(worker.scheduled).toEqual(expect.any(Function));
    expect(worker).not.toHaveProperty("fetch");
  });
});
