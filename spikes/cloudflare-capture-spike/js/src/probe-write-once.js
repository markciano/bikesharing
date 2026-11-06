// Write-once probe for T039 (d004 › Write-once).
// Run with `wrangler dev -c wrangler.probe.jsonc [--env miniflare]`, then request `/`.
// The fetch handler exists only for this local run; the Worker is never deployed.

const FIRST = 'first';
const SECOND = 'second';

const ifNoneMatch = () => new Headers({ 'If-None-Match': '*' });

// What a put returned: an object, null, or an error, without throwing.
async function observe(promise) {
  try {
    const result = await promise;
    return result === null
      ? { returned: 'null' }
      : { returned: 'object', etag: result.etag };
  } catch (err) {
    return { returned: 'error', name: err.name, message: err.message };
  }
}

async function bodyOf(bucket, key) {
  const object = await bucket.get(key);
  return object === null ? null : object.text();
}

async function probeCase(bucket, name, key, expected, put) {
  const observed = await observe(put());
  const bodyAfter = await bodyOf(bucket, key);
  return { case: name, key, expected, observed, body_after: bodyAfter };
}

// Cases on one prefix. `locked` adds the plain put on an existing key.
async function runPrefix(bucket, prefix, locked) {
  const key = `${prefix}probe-${Date.now()}`;
  const label = locked ? 'locked' : 'unlocked';
  const cases = [];

  cases.push(await probeCase(bucket, `${label}: conditional put, new key`, key,
    `object; body "${FIRST}"`,
    () => bucket.put(key, FIRST, { onlyIf: ifNoneMatch() })));

  cases.push(await probeCase(bucket, `${label}: conditional put (Headers), existing key`, key,
    `null; body still "${FIRST}"`,
    () => bucket.put(key, SECOND, { onlyIf: ifNoneMatch() })));

  cases.push(await probeCase(bucket, `${label}: conditional put (etagDoesNotMatch "*"), existing key`, key,
    `informative: null expected; body still "${FIRST}"`,
    () => bucket.put(key, SECOND, { onlyIf: { etagDoesNotMatch: '*' } })));

  if (locked) {
    cases.push(await probeCase(bucket, `${label}: plain put, existing key`, key,
      `error, recorded; body still "${FIRST}"`,
      () => bucket.put(key, SECOND)));
  } else {
    // Unlocked objects are removed; locked ones stay until their retention ends.
    await bucket.delete(key);
  }

  return cases;
}

export default {
  async fetch(request, env) {
    const lockedPrefix = env.LOCKED_PREFIX;
    const cases = await runPrefix(env.BUCKET, 'open/', false);
    if (lockedPrefix) {
      cases.push(...(await runPrefix(env.BUCKET, lockedPrefix, true)));
    }
    const target = lockedPrefix ? 'r2 (remote binding)' : 'miniflare (in-memory R2)';
    return Response.json({ target, ran_at: new Date().toISOString(), cases }, {
      headers: { 'cache-control': 'no-store' },
    });
  },
};
