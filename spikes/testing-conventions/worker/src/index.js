// Imperative shell: on each cron pass, fetch one GBFS feed and store the body unchanged in R2 (ADR-0011).
// Input: scheduled event (one capture time per pass), env vars SOURCE, FEED, FEED_URL. Output: one R2 object.
import { objectKey } from "./contract.js";

export default {
  async scheduled(controller, env) {
    const capturedAt = new Date(controller.scheduledTime);
    const response = await fetch(env.FEED_URL, {
      headers: { "Accept-Encoding": "gzip" },
      cf: { encodeResponseBody: "manual" }, // keep the origin's gzip bytes
    });
    if (!response.ok) throw new Error(`Feed fetch failed: ${response.status}`);
    const body = await response.arrayBuffer();
    await env.RAW_BUCKET.put(objectKey(env.SOURCE, env.FEED, capturedAt), body);
  },
};
