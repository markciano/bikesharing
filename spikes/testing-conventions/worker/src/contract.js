// Functional core: object key of the collector contract (ADR-0012).
// Input: source, feed, capture time (Date). Output: raw/<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz, in UTC.
export function objectKey(source, feed, capturedAt) {
  const iso = capturedAt.toISOString(); // always UTC: 2026-10-18T12:00:00.000Z
  const date = iso.slice(0, 10);
  const stamp = iso.slice(0, 19).replace(/[-:]/g, "") + "Z";
  return `raw/${source}/${feed}/${date}/${stamp}.json.gz`;
}
