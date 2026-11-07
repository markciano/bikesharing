// Sends the Healthchecks.io signal that capture is storing data, without ever
// letting its secret URL reach a result (d004 D10, Capture heartbeat).

/**
 * @typedef {{ ok: true, status: number, latencyMs: number }} HeartbeatOk
 *
 * @typedef {{ ok: false, status: number | null, latencyMs: number | null,
 *             errorType: 'http' | 'timeout' | 'network', error: string }} HeartbeatFailed
 * `status`: null when no response arrived. `latencyMs`: null when no headers arrived.
 */

/**
 * GET to `url`, aborted by `AbortSignal.timeout(heartbeatTimeoutMs)`, 10 s in production
 * as in Healthchecks.io's examples. The body is read and discarded within the same
 * timeout, so the timeout covers the whole response and no connection is left open.
 * Never throws.
 * `error` is built from the error's name and message with every occurrence of `url`
 * removed, so no result carries the URL (d004 D12, Capture security).
 * @param {string} url `HEARTBEAT_URL`
 * @param {{ heartbeatTimeoutMs: number }} limits
 * @returns {Promise<HeartbeatOk | HeartbeatFailed>}
 */
export async function sendHeartbeat(url, limits) {
  const started = Date.now();
  const signal = AbortSignal.timeout(limits.heartbeatTimeoutMs);

  let response;
  try {
    response = await fetch(url, { signal });
  } catch (err) {
    return failed(signal.aborted ? "timeout" : "network", null, null, err, url);
  }

  const { status } = response;
  try {
    await discardBody(response, signal);
  } catch (err) {
    return failed(signal.aborted ? "timeout" : "network", status, Date.now() - started, err, url);
  }
  const latencyMs = Date.now() - started;

  if (status < 200 || status > 299) {
    return failed("http", status, latencyMs, new Error(`HTTP ${status}`), url);
  }
  return { ok: true, status, latencyMs };
}

/**
 * Reads the body to its end, or cancels it once the signal aborts, so a body that
 * never ends cannot hold the pass past the timeout.
 * @param {Response} response
 * @param {AbortSignal} signal
 * @returns {Promise<void>}
 */
async function discardBody(response, signal) {
  if (!response.body) return;
  const reader = response.body.getReader();
  const aborted = new Promise((_, reject) => {
    const abort = () => reject(signal.reason ?? new Error("aborted"));
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
  });
  try {
    for (;;) {
      const { done } = await Promise.race([reader.read(), aborted]);
      if (done) return;
    }
  } catch (err) {
    reader.cancel().catch(() => {});
    throw err;
  }
}

/**
 * @param {HeartbeatFailed['errorType']} errorType
 * @param {number | null} status
 * @param {number | null} latencyMs
 * @param {unknown} err
 * @param {string} url Removed from the error text, since it is a secret
 * @returns {HeartbeatFailed}
 */
function failed(errorType, status, latencyMs, err, url) {
  return { ok: false, status, latencyMs, errorType, error: redact(describe(err), url) };
}

/** @param {unknown} err @returns {string} */
function describe(err) {
  if (err && typeof err === "object" && "message" in err) {
    const name = "name" in err ? String(err.name) : "Error";
    return `${name}: ${String(err.message)}`;
  }
  return String(err);
}

/** @param {string} text @param {string} url @returns {string} */
function redact(text, url) {
  return url ? text.split(url).join("[redacted]") : text;
}
