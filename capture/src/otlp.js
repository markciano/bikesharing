// Builds a pass's OTLP request from its JSON lines and sends it once to Grafana Cloud,
// without ever throwing, so the copy of the logs can never affect a pass (d009, Capture's
// OTLP sender).

/**
 * @typedef {object} OtlpTarget
 * @property {string} endpoint `OTLP_ENDPOINT` variable: Grafana Cloud's OTLP/HTTP logs URL, ending in `/v1/logs`
 * @property {string} token `OTLP_TOKEN` secret: the Basic credential, base64 of `<instance ID>:<token>`
 */

/**
 * @typedef {{ errorType: 'http' | 'timeout' | 'network', status: number | null, error: string }} OtlpSendFailed
 * `status`: null when no response arrived.
 */

/** OTLP severity number of each level (OpenTelemetry Logs data model). */
export const SEVERITY_NUMBER = Object.freeze({ info: 9, warn: 13, error: 17 });

/** Fields that become resource or record properties, so they are not attributes. */
const NOT_ATTRIBUTES = new Set(["ts", "level", "component", "version"]);

/**
 * The pass's `ExportLogsServiceRequest`: one resource per distinct `component` and
 * `version` in order of first appearance, one record per line in order, whose body is the
 * line itself (d009, OTLP request mapping). Pure. It reads only the shape of a line, never
 * a list of events or systems, so a new event needs no change here.
 * @param {string[]} lines The pass's JSON lines, as written to R2, without their newline
 * @returns {{ resourceLogs: object[] }}
 */
export function buildLogsRequest(lines) {
  /** @type {Map<string, { component: string, version: string, logRecords: object[] }>} */
  const resources = new Map();
  for (const text of lines) {
    const fields = JSON.parse(text);
    const key = JSON.stringify([fields.component, fields.version]);
    if (!resources.has(key)) resources.set(key, { component: fields.component, version: fields.version, logRecords: [] });
    resources.get(key).logRecords.push(toRecord(text, fields));
  }
  return {
    resourceLogs: [...resources.values()].map(({ component, version, logRecords }) => ({
      resource: {
        attributes: [
          { key: "service.name", value: { stringValue: component } },
          { key: "service.version", value: { stringValue: version } },
        ],
      },
      scopeLogs: [{ scope: { name: component }, logRecords }],
    })),
  };
}

/**
 * One POST of `buildLogsRequest(lines)` to `target.endpoint`, with `Authorization: Basic <token>`,
 * aborted by `AbortSignal.timeout(limits.otlpTimeoutMs)`, 10 s in production. The body is
 * read and discarded within the same timeout, so the timeout covers the whole response.
 * Never throws.
 * @param {OtlpTarget} target
 * @param {string[]} lines
 * @param {{ otlpTimeoutMs: number }} limits
 * @returns {Promise<OtlpSendFailed | null>} `null` when Grafana answers 2xx, or when there are no lines
 */
export async function sendLogs(target, lines, limits) {
  if (lines.length === 0) return null;
  const signal = AbortSignal.timeout(limits.otlpTimeoutMs);

  let response;
  try {
    response = await fetch(target.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Basic ${target.token}` },
      body: JSON.stringify(buildLogsRequest(lines)),
      signal,
    });
  } catch (err) {
    return failed(signal.aborted ? "timeout" : "network", null, err);
  }

  const { status } = response;
  try {
    await response.arrayBuffer();
  } catch (err) {
    return failed(signal.aborted ? "timeout" : "network", status, err);
  }

  if (status < 200 || status > 299) return failed("http", status, new Error(`HTTP ${status}`));
  return null;
}

/**
 * @param {string} text The line as written
 * @param {Record<string, unknown>} fields The line parsed
 * @returns {object}
 */
function toRecord(text, fields) {
  return {
    timeUnixNano: (BigInt(Date.parse(String(fields.ts))) * 1_000_000n).toString(),
    severityText: fields.level,
    severityNumber: SEVERITY_NUMBER[/** @type {keyof typeof SEVERITY_NUMBER} */ (fields.level)],
    body: { stringValue: text },
    attributes: Object.entries(fields)
      .filter(([key, value]) => !NOT_ATTRIBUTES.has(key) && value !== null)
      .map(([key, value]) => ({ key, value: toAnyValue(value) })),
  };
}

/** @param {unknown} value A non-null JSON value @returns {object} */
function toAnyValue(value) {
  if (typeof value === "string") return { stringValue: value };
  if (typeof value === "boolean") return { boolValue: value };
  if (typeof value === "number") {
    return Number.isSafeInteger(value) ? { intValue: String(value) } : { doubleValue: value };
  }
  return { stringValue: JSON.stringify(value) };
}

/**
 * @param {OtlpSendFailed['errorType']} errorType
 * @param {number | null} status
 * @param {unknown} err
 * @returns {OtlpSendFailed}
 */
function failed(errorType, status, err) {
  return { errorType, status, error: describe(err) };
}

/** @param {unknown} err @returns {string} */
function describe(err) {
  if (err && typeof err === "object" && "message" in err) {
    const name = "name" in err ? String(err.name) : "Error";
    return `${name}: ${String(err.message)}`;
  }
  return String(err);
}
