---
paths:
  - "capture/**/*.js"
  - "capture/**/package.json"
  - "capture/**/*.jsonc"
---

# Cloudflare Worker code and testing rules (JS)

General testing principles are in `testing.md`; reasons and detail in the [testing strategy](../../../docs/testing-strategy.md) (Cloudflare Worker section).

## Code comments

- Every module starts with a short comment stating its responsibility. JSDoc documents every exported function, constant and typedef.
- Types are mandatory in JSDoc (`@param`, `@returns`, `@type`, `@typedef`), since the code is plain JavaScript.
- Inline comments explain *why* a non-obvious decision was made, never *what* the code does.
- A comment can be understood on its own: it states the rule or the reason in words, never only a document ID.
- A comment that cites a document writes `(<doc ID> <item ID>, <item title>)`, e.g. `(d004 D8, Capture failure behaviour)` or `(ADR-0012, Collectors decoupled by output contract)`. Never a bare item ID such as `(D3)`, and no file paths or anchors, which neither the editor nor GitHub follows from a comment; the doc ID finds the file, since file names start with it.
  - An item without a title, such as a requirement, is cited through the decision it comes from: `(d004 D12, Capture security)` rather than `R21`.
  - A section without an item ID is cited by document and section title: `(d004, Pass logs)`.
- A test that verifies a Test plan row says so above it, `// Verifies <design ID> <R>`, e.g. `// Verifies d004 R7`: a traceability tag, cited by requirement since that is what the Test plan lists.
  - TODO(T039): relocate the rules of this file that apply beyond the capture Worker, such as this tag and the comment conventions, to project-wide rules when d004 closes.

## Tools

- `vitest` with `@cloudflare/vitest-plugin`, which runs the tests inside `workerd`, the Workers runtime, through Miniflare, its local simulator.
- A binding is how the Worker reaches a resource (an R2 bucket, a secret, a value) as an object in `env`, configured in `wrangler.jsonc`; in tests Miniflare provides the same objects, with R2 in memory.
- Run the tests from the project root with `npm test --prefix capture`, and one file with `npm test --prefix capture -- <test path>`; this is the form `.claude/settings.json` allows.
  - TODO(T039): generalize how tests are run to every component, in a project-wide rule, when d004 closes.

## Unit tests

- They cover the functional core: pure exported functions such as `rawKey` or `extraFetch`.
- A module that takes the bucket as a parameter, when a test needs R2 to fail, receives a fake binding: the in-memory R2 cannot fail on demand.

## Integration tests

- They run the `scheduled` handler with an in-memory R2 binding and assert the objects written to it.
- Sources are simulated with Miniflare `outboundService` (in `vitest.config.js`), not with MSW, which decodes the body before the Worker sees it.
- The expected bytes come from the fixture passed as a binding, not from a fetch through the simulated source.
- Timeouts and size limits are parameters; tests pass milliseconds and bytes, never the production values.

## Contract tests

- Producer side: they read the shared vectors in `contracts/` by relative path and check that the Worker's output meets them.

## Not covered by local tests

- No local simulation verifies `encodeResponseBody: 'manual'`: do not write a test for it; the post-deploy smoke test covers it.

## Files and names

- `test/unit/<module>.test.js`, `test/integration/<module>.test.js` and `test/contract/<contract>.test.js`.
- Test names are plain sentences stating behaviour and condition.
