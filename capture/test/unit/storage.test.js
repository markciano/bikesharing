// Unit tests of write-once storage: conditional put with retries, the head check on a
// failed put, the plain put of state and the state read. The bucket is a fake binding,
// since the in-memory R2 cannot fail on demand.
import { describe, expect, it } from "vitest";
import { getState, putOnce, putState, stateKey } from "../../src/storage.js";

const LIMITS = { retryDelayMs: 0 };
const KEY = "raw/bicing/station_status/2026-10-18/20261018T120000Z.json.gz";
const STORED = { key: KEY };

/**
 * A fake R2 binding. `put`, `head` and `get` each take a list of answers, one per call:
 * an `Error` is thrown, anything else is returned; the last answer repeats.
 */
function fakeBucket({ put = [STORED], head = [null], get = [null] } = {}) {
  const calls = { put: [], head: [], get: [] };
  const answer = (list, n) => {
    const a = list[Math.min(n, list.length - 1)];
    if (a instanceof Error) throw a;
    return a;
  };
  return {
    calls,
    async put(key, body, options) {
      calls.put.push({ key, body, options });
      return answer(put, calls.put.length - 1);
    },
    async head(key) {
      calls.head.push(key);
      return answer(head, calls.head.length - 1);
    },
    async get(key) {
      calls.get.push(key);
      return answer(get, calls.get.length - 1);
    },
  };
}

describe("putOnce", () => {
  it("writes with a conditional put on If-None-Match: *", async () => {
    const bucket = fakeBucket();

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 1 });
    expect(bucket.calls.put).toHaveLength(1);
    expect(bucket.calls.put[0].key).toBe(KEY);
    expect(bucket.calls.put[0].body).toBe("body");
    expect(new Headers(bucket.calls.put[0].options.onlyIf).get("If-None-Match")).toBe("*");
  });

  it("counts a null answer, the key already written, as written without a head", async () => {
    const bucket = fakeBucket({ put: [null] });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 1 });
    expect(bucket.calls.head).toHaveLength(0);
  });

  it("writes on the third attempt when the bucket fails twice", async () => {
    const bucket = fakeBucket({ put: [new Error("boom"), new Error("boom"), STORED] });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 3 });
    expect(bucket.calls.put).toHaveLength(3);
  });

  it("returns ok false after 3 attempts when the bucket always fails", async () => {
    const bucket = fakeBucket({ put: [new Error("boom")] });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: false, attempts: 3, error: "boom" });
    expect(bucket.calls.put).toHaveLength(3);
  });

  it("counts a thrown put as written after 1 attempt when head finds the object", async () => {
    const bucket = fakeBucket({
      put: [new Error("The object is locked by the bucket policy. (10069)")],
      head: [STORED],
    });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 1 });
    expect(bucket.calls.put).toHaveLength(1);
    expect(bucket.calls.head).toEqual([KEY]);
  });

  it("retries a thrown put when head finds nothing", async () => {
    const bucket = fakeBucket({ put: [new Error("boom"), STORED], head: [null] });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 2 });
    expect(bucket.calls.put).toHaveLength(2);
  });

  it("retries a thrown put when head also fails", async () => {
    const bucket = fakeBucket({ put: [new Error("boom"), STORED], head: [new Error("head down")] });

    const result = await putOnce(bucket, KEY, "body", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 2 });
  });
});

describe("putState", () => {
  const STATE_KEY = stateKey("bicing");

  it("writes with a plain put, without a condition", async () => {
    const bucket = fakeBucket();

    const result = await putState(bucket, STATE_KEY, "{}", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 1 });
    expect(bucket.calls.put[0].options?.onlyIf).toBeUndefined();
  });

  it("writes on the third attempt when the bucket fails twice", async () => {
    const bucket = fakeBucket({ put: [new Error("boom"), new Error("boom"), STORED] });

    const result = await putState(bucket, STATE_KEY, "{}", LIMITS);

    expect(result).toEqual({ ok: true, attempts: 3 });
  });

  it("returns ok false after 3 attempts when the bucket always fails", async () => {
    const bucket = fakeBucket({ put: [new Error("boom")] });

    const result = await putState(bucket, STATE_KEY, "{}", LIMITS);

    expect(result).toEqual({ ok: false, attempts: 3, error: "boom" });
  });
});

describe("getState", () => {
  it("returns the text of a stored object", async () => {
    const bucket = fakeBucket({ get: [{ text: async () => '{"a":1}' }] });

    expect(await getState(bucket, stateKey("ambici"))).toBe('{"a":1}');
  });

  it("returns null for a missing key", async () => {
    const bucket = fakeBucket({ get: [null] });

    expect(await getState(bucket, stateKey("ambici"))).toBeNull();
  });

  it("returns null when the read throws", async () => {
    const bucket = fakeBucket({ get: [new Error("boom")] });

    expect(await getState(bucket, stateKey("ambici"))).toBeNull();
  });
});

describe("stateKey", () => {
  it("places the index state of a source under state/index/", () => {
    expect(stateKey("bicing")).toBe("state/index/bicing.json");
  });
});
