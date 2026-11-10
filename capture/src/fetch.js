// Fetches one source response and returns the gzip bytes to store as received, or
// the failure to log; decompresses an index for its adapter (d004, Source fetch).

/**
 * Production limits; tests pass their own, in milliseconds and bytes, so that the
 * timeout and the size limit are testable (d004, Tests and contracts).
 * @type {Readonly<{ timeoutMs: number, maxBytes: number, retryDelayMs: number,
 *   heartbeatTimeoutMs: number, retry403MinMs: number, retry403MaxMs: number }>}
 */
export const LIMITS = Object.freeze({
  timeoutMs: 60_000,
  maxBytes: 10_000_000,
  retryDelayMs: 250,
  heartbeatTimeoutMs: 10_000,
  retry403MinMs: 3_000,
  retry403MaxMs: 5_000,
});

/** Sent in every source request; the heartbeat does not use it (d006 D5, Every source request identifies the project). */
export const USER_AGENT = "bikesharing-capture (+https://github.com/markciano/bikesharing)";

/** The gzip magic number (RFC 1952): a body is gzip by its bytes, not by its headers. */
const GZIP_MAGIC = [0x1f, 0x8b];

/** Limits on a retried 403's event: headers kept, and bytes per header value and body (d006 D4, A retry is logged as its own event). */
const RETRIED_MAX_HEADERS = 50;
const RETRIED_MAX_BYTES = 1_000;

/**
 * @typedef {{ ok: true, status: number, latencyMs: number,
 *             body: Uint8Array, recompressed: boolean }} FetchOk
 * `body`: gzip bytes, as received or compressed by capture (`recompressed`).
 *
 * @typedef {{ ok: false, status: number | null, latencyMs: number | null,
 *             errorType: 'http' | 'timeout' | 'network' | 'too_large',
 *             error: string }} FetchFailed
 * `status`: null when no response arrived. `latencyMs`: null when no headers arrived (R14).
 * `http`: a status outside 200–299; its body is not stored.
 */

/**
 * @typedef {{ status: 403, latencyMs: number, headers: Record<string, string>,
 *             body: string | null }} Retried
 * The first attempt of a request about to be retried, for `fetch_retried`.
 */

/** Thrown inside a body read that passed `maxBytes`. */
class TooLarge extends Error {}

/**
 * GET with `Accept-Encoding: gzip`, `User-Agent: USER_AGENT` and
 * `encodeResponseBody: "manual"`. One `AbortSignal.timeout(timeoutMs)` covers every
 * attempt and the wait. With `retryOn403`, a 403 calls `onRetry`, waits
 * `retryWait(limits, random)` and fetches once more. Never throws.
 * @param {string} url
 * @param {{ timeoutMs: number, maxBytes: number, retry403MinMs: number, retry403MaxMs: number }} limits
 * @param {{ retryOn403?: boolean, onRetry?: (retried: Retried) => void, random?: () => number }} [options]
 *   Defaults: `false`, a no-op, `Math.random`
 * @returns {Promise<FetchOk | FetchFailed>} The last attempt's result
 */
export async function fetchFeed(url, limits, options = {}) {
  const { retryOn403 = false, onRetry = () => {}, random = Math.random } = options;
  // One deadline for the first attempt, the wait and the retry, so a retried request
  // lasts no longer than one that is not (d006 D3, One 60 s limit covers the retry).
  const signal = AbortSignal.timeout(limits.timeoutMs);

  const first = await attempt(url, limits, signal, retryOn403);
  if (!("forbidden" in first)) return first;

  const { response, latencyMs } = first.forbidden;
  const headers = retriedHeaders(response.headers);
  const body = await retriedBody(response, limits.maxBytes, signal);
  onRetry({ status: 403, latencyMs, headers, body });
  // A deadline spent while reading the 403's body rejects the wait at once: a timeout.
  try {
    await wait(retryWait(limits, random), signal);
  } catch (err) {
    return failed("timeout", null, null, err);
  }
  return /** @type {FetchOk | FetchFailed} */ (await attempt(url, limits, signal));
}

/**
 * One request under the caller's deadline, aborted once the body read exceeds
 * `maxBytes`. `latencyMs` is this attempt's own. With `keep403`, a 403 comes back with
 * its body unread, for the retry's event. Never throws.
 * @param {string} url
 * @param {{ maxBytes: number }} limits
 * @param {AbortSignal} signal
 * @param {boolean} [keep403]
 * @returns {Promise<FetchOk | FetchFailed | { forbidden: { response: Response, latencyMs: number } }>}
 */
async function attempt(url, limits, signal, keep403 = false) {
  const started = Date.now();

  let response;
  try {
    // `manual` keeps the source's gzip bytes undecoded, so they are stored with no
    // compression work (d004, Source fetch).
    response = await fetch(url, {
      headers: { "Accept-Encoding": "gzip", "User-Agent": USER_AGENT },
      encodeResponseBody: "manual",
      signal,
    });
  } catch (err) {
    return failed(signal.aborted ? "timeout" : "network", null, null, err);
  }

  const { status } = response;
  if (status === 403 && keep403) return { forbidden: { response, latencyMs: Date.now() - started } };
  if (status < 200 || status > 299) {
    await response.body?.cancel().catch(() => {});
    return failed("http", status, Date.now() - started, new Error(`HTTP ${status}`));
  }

  let bytes;
  try {
    bytes = await readLimited(response.body, limits.maxBytes, signal);
  } catch (err) {
    const latencyMs = Date.now() - started;
    if (err instanceof TooLarge) return failed("too_large", status, latencyMs, err);
    return failed(signal.aborted ? "timeout" : "network", status, latencyMs, err);
  }
  const latencyMs = Date.now() - started;

  if (isGzip(bytes)) return { ok: true, status, latencyMs, body: bytes, recompressed: false };
  // A plain body is stored compressed, never as plain JSON under a `.json.gz` key, and
  // flagged, since it means the runtime stopped honouring `encodeResponseBody`
  // (d004 D9, Capture logs).
  return { ok: true, status, latencyMs, body: await compress(bytes), recompressed: true };
}

/**
 * Uniform wait before a retry: `retry403MinMs + random() * (retry403MaxMs - retry403MinMs)`. Pure.
 * @param {{ retry403MinMs: number, retry403MaxMs: number }} limits
 * @param {() => number} [random] Default `Math.random`
 * @returns {number} Milliseconds
 */
export function retryWait(limits, random = Math.random) {
  return limits.retry403MinMs + random() * (limits.retry403MaxMs - limits.retry403MinMs);
}

/**
 * Decompresses an index body for its adapter. Never throws.
 * `too_large`: the decompressed size exceeds `maxBytes`; `invalid_index`: the bytes are not valid gzip.
 * @param {Uint8Array} gzipBytes
 * @param {number} maxBytes Limit on the decompressed size
 * @returns {Promise<{ ok: true, text: string }
 *   | { ok: false, errorType: 'too_large' | 'invalid_index', error: string }>}
 */
export async function gunzipText(gzipBytes, maxBytes) {
  try {
    const stream = new Blob([gzipBytes]).stream().pipeThrough(new DecompressionStream("gzip"));
    const bytes = await readLimited(stream, maxBytes);
    return { ok: true, text: new TextDecoder().decode(bytes) };
  } catch (err) {
    return { ok: false, errorType: err instanceof TooLarge ? "too_large" : "invalid_index", error: message(err) };
  }
}

/**
 * Reads a stream whole, stopping once it passes `maxBytes`, since a source's
 * `content-length` cannot be trusted or may be missing (d004, Source fetch).
 * The signal also stops a body that never ends.
 * @param {ReadableStream<Uint8Array> | null} stream
 * @param {number} maxBytes
 * @param {AbortSignal} [signal]
 * @returns {Promise<Uint8Array>}
 */
async function readLimited(stream, maxBytes, signal) {
  if (!stream) return new Uint8Array(0);
  const reader = stream.getReader();
  const aborted = signal ? abortPromise(signal) : null;
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await (aborted ? Promise.race([reader.read(), aborted]) : reader.read());
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new TooLarge(`body exceeds ${maxBytes} bytes`);
      chunks.push(value);
    }
  } catch (err) {
    reader.cancel().catch(() => {});
    throw err;
  }
  return concat(chunks, size);
}

/** @param {AbortSignal} signal @returns {Promise<never>} */
function abortPromise(signal) {
  return new Promise((_, reject) => {
    const abort = () => reject(signal.reason ?? new Error("aborted"));
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}

/**
 * The 403's headers for its event: names in lowercase and sorted, as the Fetch API
 * iterates them, without `set-cookie`, since it can carry a session token; the first
 * `RETRIED_MAX_HEADERS`, each value cut to `RETRIED_MAX_BYTES` (d006 D4, A retry is
 * logged as its own event).
 * @param {Headers} headers
 * @returns {Record<string, string>}
 */
function retriedHeaders(headers) {
  const kept = [...headers]
    .filter(([name]) => name !== "set-cookie")
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .slice(0, RETRIED_MAX_HEADERS);
  return Object.fromEntries(kept.map(([name, value]) => [name, cutUtf8(value, RETRIED_MAX_BYTES)]));
}

/**
 * The 403's body for its event: read within `maxBytes` and the deadline, decompressed
 * if gzip, decoded as UTF-8 and cut to `RETRIED_MAX_BYTES`; null if it cannot be read
 * or decompressed, or the deadline cuts it short. Never throws.
 * @param {Response} response
 * @param {number} maxBytes
 * @param {AbortSignal} signal
 * @returns {Promise<string | null>}
 */
async function retriedBody(response, maxBytes, signal) {
  let bytes;
  try {
    bytes = await readLimited(response.body, maxBytes, signal);
  } catch {
    return null;
  }
  if (!isGzip(bytes)) return cutUtf8(new TextDecoder().decode(bytes), RETRIED_MAX_BYTES);
  const unzipped = await gunzipText(bytes, maxBytes);
  return unzipped.ok ? cutUtf8(unzipped.text, RETRIED_MAX_BYTES) : null;
}

/**
 * `text` cut to at most `maxBytes` of UTF-8, at the last whole character, so the cut
 * never splits one and the event stays within its limit (d006, The 403's headers and body).
 * @param {string} text
 * @param {number} maxBytes
 * @returns {string}
 */
function cutUtf8(text, maxBytes) {
  const bytes = new TextEncoder().encode(text);
  if (bytes.length <= maxBytes) return text;
  let end = maxBytes;
  // A byte 10xxxxxx continues a character, so the cut moves back to where one starts.
  while (end > 0 && (bytes[end] & 0xc0) === 0x80) end -= 1;
  return new TextDecoder().decode(bytes.subarray(0, end));
}

/**
 * Resolves after `ms`, or rejects once `signal` aborts, so the deadline cuts the wait short.
 * @param {number} ms
 * @param {AbortSignal} signal
 * @returns {Promise<void>}
 */
function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer);
      reject(signal.reason ?? new Error("aborted"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
}

/** @param {Uint8Array[]} chunks @param {number} size */
function concat(chunks, size) {
  const out = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out;
}

/** @param {Uint8Array} bytes */
function isGzip(bytes) {
  return bytes.length >= 2 && bytes[0] === GZIP_MAGIC[0] && bytes[1] === GZIP_MAGIC[1];
}

/** @param {Uint8Array} bytes @returns {Promise<Uint8Array>} */
async function compress(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/**
 * @param {FetchFailed['errorType']} errorType
 * @param {number | null} status
 * @param {number | null} latencyMs
 * @param {unknown} err
 * @returns {FetchFailed}
 */
function failed(errorType, status, latencyMs, err) {
  return { ok: false, status, latencyMs, errorType, error: message(err) };
}

/** @param {unknown} err */
function message(err) {
  return err instanceof Error ? err.message : String(err);
}
