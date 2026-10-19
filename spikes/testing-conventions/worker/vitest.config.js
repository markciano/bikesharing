// Vitest config for the Worker PoC: tests run inside workerd (@cloudflare/vitest-plugin).
// The source API is simulated with Miniflare's outboundService, which sits after workerd's network layer.
// The gzip fixture is also passed to the tests as a binding, so they compare against the known source.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

const served = gzipSync(readFileSync(new URL("../contract/fixtures/station_status.json", import.meta.url)));

export default defineConfig({
  plugins: [
    cloudflareTest({
      wrangler: { configPath: "./wrangler.jsonc" },
      miniflare: {
        bindings: { SERVED_GZIP_B64: served.toString("base64") },
        outboundService: () => new Response(served, { headers: { "Content-Encoding": "gzip" } }),
      },
    }),
  ],
});
