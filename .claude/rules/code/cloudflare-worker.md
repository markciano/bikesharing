---
paths:
  - "capture/**/*.js"
  - "capture/**/package.json"
  - "capture/**/*.jsonc"
---

# Cloudflare Worker code and testing rules (JS)

General testing principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (Cloudflare Worker section).

## Code comments

General comment rules are in `general.md`.

- Each module's responsibility goes in a short comment at its top. JSDoc documents every exported function, constant and typedef.
- Types are mandatory in JSDoc (`@param`, `@returns`, `@type`, `@typedef`), since the code is plain JavaScript.

## Tools

- `vitest` with `@cloudflare/vitest-plugin`, which runs the tests inside `workerd`, the Workers runtime, through Miniflare, its local simulator.
- A binding is how the Worker reaches a resource (an R2 bucket, a secret, a value) as an object in `env`, configured in `wrangler.jsonc`; in tests Miniflare provides the same objects, with R2 in memory.
- `npm test --prefix capture` runs every test, `npm test --prefix capture -- <test path>` one file.

## Unit tests

- They cover the functional core: pure exported functions such as `rawKey` or `extraFetch`.
- A module that takes the bucket as a parameter, when a test needs R2 to fail, receives a fake binding: the in-memory R2 cannot fail on demand.

## Integration tests

- They run the `scheduled` handler with an in-memory R2 binding and assert the objects written to it.
- Sources are simulated with Miniflare `outboundService` (in `vitest.config.js`), not with MSW, which decodes the body before the Worker sees it.
- The expected bytes come from the fixture passed as a binding, not from a fetch through the simulated source.

## Contract tests

- Producer side: they read the shared vectors in `contracts/` by relative path and check that the Worker's output meets them.

## Not covered by local tests

- No local simulation verifies `encodeResponseBody: 'manual'`: do not write a test for it; the post-deploy smoke test covers it.

## Files and names

- `test/unit/<module>.test.js`, `test/integration/<module>.test.js` and `test/contract/<contract>.test.js`.
- Test names are plain sentences.
