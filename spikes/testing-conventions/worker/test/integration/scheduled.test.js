// P3 integration test (Q3): the scheduled handler runs in workerd with the source served by Miniflare's
// outboundService (vitest.config.js) and writes the gzip bytes, unchanged, to the in-memory R2 binding at the contract key.
// The expected bytes come from the config's in-memory gzip fixture (binding SERVED_GZIP_B64), not from a fetch.
import { createExecutionContext, createScheduledController, waitOnExecutionContext } from "cloudflare:test";
import { env } from "cloudflare:workers";
import { expect, it } from "vitest";
import vectors from "../../../contract/collector-contract.json";
import worker from "../../src/index.js";

it("stores the served gzip bytes unchanged at the contract key", async () => {
  const served = Uint8Array.from(atob(env.SERVED_GZIP_B64), (c) => c.charCodeAt(0));
  const vector = vectors.valid[0]; // bicing / station_status at 2026-10-18T12:00:00Z

  const controller = createScheduledController({ scheduledTime: new Date(vector.captured_at) });
  const ctx = createExecutionContext();
  await worker.scheduled(controller, env, ctx);
  await waitOnExecutionContext(ctx);

  const listed = await env.RAW_BUCKET.list();
  expect(listed.objects.map((o) => o.key)).toEqual([vector.key]);
  const stored = new Uint8Array(await (await env.RAW_BUCKET.get(vector.key)).arrayBuffer());
  expect(stored.slice(0, 2)).toEqual(Uint8Array.of(0x1f, 0x8b)); // still gzip, not decoded
  expect(stored).toEqual(served);
});
