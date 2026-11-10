---
status: Accepted
date: 2026-11-10
---

# Retry a 403 only on sources where it is shown to be transient

## Context and problem statement

Collectors request public bike-sharing APIs and retry no source failure ([d004 › D8](../designs/d004-bronze-data-capture.md#d8-capture-failure-behaviour)): each failed request costs the data of that minute.

- HTTP 403 means the server refuses the request, and repeating it unchanged is not expected to succeed ([RFC 9110 › 403](https://www.rfc-editor.org/rfc/rfc9110#name-403-forbidden)). Retry policies follow this: they retry 429, 5xx and network errors, never 403.
- Bicing answers 403 to isolated requests, never in two consecutive minutes, and a request a few seconds later usually succeeds ([s014 › Conclusion](../spikes/s014-bicing-403.md#5-conclusion)). Its 403s cost about 2% of a feed's minutes, against a 99.5% completeness target ([d004 › D6](../designs/d004-bronze-data-capture.md#d6-capture-completeness-target)).
- No other source has answered 403. A 403 that is a real refusal, such as a block, gets twice the requests if it is retried, from a source that already refuses them.

## Considered Options

Each option is compared on the data it recovers, the load it adds to a source that refuses, and what it costs to change.

### 1. Retry a 403 per source, on evidence

Each source states in its configuration whether its requests retry a 403. A source gets the retry only once its logs show that its 403s are transient.

- Pros:
  - recovers the minutes that a transient 403 costs;
  - a source that refuses for good gets no extra requests;
  - the deviation from RFC 9110 stays where it has been measured.
- Cons:
  - a source whose 403s become transient loses data until a task checks its logs and turns the retry on;
  - one more setting per source.

### 2. Retry a 403 on every source

Every source request retries a 403, with no setting per source.

- Pros:
  - covers a transient 403 on any source as soon as it appears;
  - no setting per source.
- Cons:
  - doubles the requests to a source whose 403 is a real refusal;
  - applies the deviation where nothing supports it.

### 3. Keep no retry on 403

A 403 is a failure like any other and is never retried, as RFC 9110 expects.

- Pros:
  - follows the standard and changes nothing.
- Cons:
  - Bicing keeps losing about 2% of a feed's minutes, below its completeness target.

## Decision Outcome

**Chosen option:** 1. Retry a 403 per source, on evidence.

It recovers the data that Bicing's transient 403s cost, which keeping the standard does not, and it adds no load to a source whose 403 is a real refusal, which a retry on every source does. Turning the retry on for another source costs one setting once its logs show the same pattern.

Why not the others:

- Retry on every source: it extends a deviation from the standard to sources with no evidence for it.
- Keep no retry: Bicing stays below its completeness target, which is the problem itself.

**Scope:** Requests from any collector to a bike-sharing source, for its data and its indexes. It does not cover other failures, which keep d004 › D8; requests to the project's own services, such as storage or the heartbeat; or how the retry waits and how long it may take, set in [d006](../designs/d006-capture-retry-on-403.md).

### The rule

- **Default:** a source does not retry a 403.
- **Evidence to turn it on:** the source's logs show isolated 403s, not in consecutive requests, and a request a few seconds after one succeeds.
- **The retry:** once per request, in the same run.

### Consequences

#### Positive

- **Data recovered:** a transient 403 no longer costs the minute's data on a source that retries it.
- **No load on a refusal:** a source that refuses for good sees the same requests as before.
- **Visible on every source:** a 403 is logged whether it is retried or not, so a new pattern shows in the logs.

#### Negative

- **Late cover:** a source whose 403s become transient loses data until a task turns its retry on.
- **Per-source setting:** each new source must state whether it retries a 403.
- **Deviation kept in force:** the retry rests on a source's observed behaviour, not on what the protocol promises; if that behaviour changes, the retry may stop helping without failing.

## More information

- Decided at framing in [d006 › D1](../designs/d006-capture-retry-on-403.md#d1-a-403-from-bicing-is-retried-once), from the evidence of [s014](../spikes/s014-bicing-403.md).
- The sources that retry a 403 are set in the capture's source configuration; at the time of writing, Bicing only.
