---
status: accepted
date: 2026-10-15
---

# Cloudflare Workers and R2 for real-time capture

## Context and Problem Statement

Where real-time capture runs was open (T012). The AMBici and Bicing dynamic feeds must be captured every minute, always on, at no cost. The spike [Cloudflare Workers + R2 as the real-time capture platform](../spikes/s006-cloudflare-capture.md) tested two capture variants on the Free plan against fixed exit criteria.

Which platform and capture design should real-time capture use?

## Considered Options

* Cloudflare Workers (Free plan, Cron Triggers) + R2, storing the origin's gzip bytes unchanged (spike variant V4)
* Cloudflare Workers + R2, compressing in the Worker with `CompressionStream` (spike variant V2)
* Capture on the owner's machine

## Decision Outcome

Chosen option: "Cloudflare Workers + R2, storing the origin's gzip bytes unchanged", because it is the only option that met every exit criterion of the spike: 99.9–100 % capture per dynamic feed, typical CPU of 5 ms per pass, and €0 billed. V2 lost about 30 % of its captures to the 10 ms CPU limit. The owner's machine is not always on.

* The Worker is written in JS. It fetches with `Accept-Encoding: gzip` and `encodeResponseBody: 'manual'`, and stores the response body in R2 without decompressing or compressing it.
* Static feeds are fetched once a day, staggered across the day, so that no pass groups them.
* Production uses a new bucket. The production capturer and the spike's V4 run in parallel until the first full day in the new bucket is verified; then the spike's V4 and its bucket are retired.

### Consequences

* Good: no compression work, so CPU stays well below the limit on a dynamic-only pass.
* Good: the raw objects are the origin's bytes, as ADR-0006 requires.
* Bad: `encodeResponseBody: 'manual'` is not documented. If the runtime stopped honouring it, objects would be stored decoded; the capture analysis reports them as `invalid_gzip`.
* Bad: the Free plan's CPU enforcement rule is not documented; passes above 10 ms have not been cut so far, but this is not relied on.
* The collector is not Python, unlike what ADR-0010 assumes; see ADR-0012.
* The inputs for the production design are listed in the spike's Conclusion.
