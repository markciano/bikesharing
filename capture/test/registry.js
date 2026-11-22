// Test helper: checks capture's log lines against the log events registry, so that an
// event capture writes with no registry entry fails the test that reads it.
import { expect } from "vitest";
import registry from "../../contracts/log-events.registry.json";

/** The registry's capture events by name. @type {Map<string, { levels: string[] }>} */
const CAPTURE_EVENTS = new Map(registry.events.filter((e) => e.component === "capture").map((e) => [e.event, e]));

/**
 * Asserts that each JSON line names a `capture` event of the registry, at one of the
 * levels registered for it.
 * @param {string[]} lines JSON lines of a pass's log
 */
export function expectRegistered(lines) {
  for (const line of lines) {
    const { event, level } = JSON.parse(line);
    const entry = CAPTURE_EVENTS.get(event);
    expect(entry, `event ${event} is not a capture event of the registry`).toBeDefined();
    expect(entry.levels, `level ${level} of ${event} is not registered`).toContain(level);
  }
}
