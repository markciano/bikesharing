---
paths:
  - "collector/**/*.js"
  - "collector/**/package.json"
---

# Cloudflare Worker testing rules (JS)

General principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (Cloudflare Worker section).

- Tools: `vitest` with `@cloudflare/vitest-plugin`.
- Unit tests cover the functional core (pure exported functions such as `objectKey`).
- Integration tests run the `scheduled` handler in `workerd` with an in-memory R2 binding and assert the object written to it.
- The source API is simulated with Miniflare `outboundService` (in `vitest.config.js`), not with MSW, which decodes the body before the Worker sees it.
- The expected bytes come from the fixture passed as a binding, not from a fetch through the mocked path.
- No local mock verifies `encodeResponseBody: 'manual'`: do not write a mock-based test for it; a post-deploy smoke test covers it.
- Files `test/unit/<module>.test.js` and `test/integration/<module>.test.js`; test names are plain sentences stating behaviour and condition.
- Pin Node in `package.json` `engines` to a release inside the range the test tools support, not to the version installed on one machine.

TODO: update the `paths:` and this scope when the collector design fixes the layout (`collector/{bicing/,ambici/}`).
