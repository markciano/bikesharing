// Fetches one source response and returns the gzip bytes to store as received, or
// the failure to log; decompresses an index for its adapter (d004, Source fetch).

/**
 * Production limits; tests pass their own, in milliseconds and bytes, so that the
 * timeout and the size limit are testable (d004, Tests and contracts).
 * @type {Readonly<{ timeoutMs: number, maxBytes: number, retryDelayMs: number, heartbeatTimeoutMs: number }>}
 */
export const LIMITS = Object.freeze({
  timeoutMs: 60_000,
  maxBytes: 10_000_000,
  retryDelayMs: 250,
  heartbeatTimeoutMs: 10_000,
});

/** Sent in every source request; the heartbeat does not use it (d006 D5, Every source request identifies the project). */
export const USER_AGENT = "bikesharing-capture (+https://github.com/markciano/bikesharing)";

/** The gzip magic number (RFC 1952): a body is gzip by its bytes, not by its headers. */
const GZIP_MAGIC = [0x1f, 0x8b];

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

/** Thrown inside a body read that passed `maxBytes`. */
class TooLarge extends Error {}

/**
 * GET with `Accept-Encoding: gzip`, `User-Agent: USER_AGENT` and
 * `encodeResponseBody: "manual"`, aborted by
 * `AbortSignal.timeout(timeoutMs)` and once the body read exceeds `maxBytes`. Never throws.
 * @param {string} url
 * @param {{ timeoutMs: number, maxBytes: number }} limits
 * @returns {Promise<FetchOk | FetchFailed>}
 */
export async function fetchFeed(url, limits) {
  const started = Date.now();
  const signal = AbortSignal.timeout(limits.timeoutMs);

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
