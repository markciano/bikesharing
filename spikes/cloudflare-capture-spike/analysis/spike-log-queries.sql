-- One-off queries over the spike's capture logs (d004 > D2).
--
-- Run them from the repository root, in either of these ways:
--   All at once:   duckdb -f spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql
--   Interactive:   duckdb
--                  .read spikes/cloudflare-capture-spike/analysis/spike-log-queries.sql
--                  (then paste a single query to try changes; .quit to leave)
--
-- DuckDB keeps nothing here: there is no database file, and it reads the JSONL
-- files again on every query. Every timestamp is UTC.

-- Show up to 100 rows per result; the default hides the middle of long results.
.maxrows 100

-- ---------------------------------------------------------------------------
-- Setup: a view gives the files a table name, so the queries stay short.
-- `columns` fixes the types: `error` is almost always null, so automatic
-- detection could not tell that it holds text.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE TEMP VIEW logs AS
SELECT
    strptime(ts, '%Y%m%dT%H%M%SZ') AS captured_at,
    source,
    feed,
    status,
    latency_ms,
    bytes,
    error
FROM read_json(
    'spikes/cloudflare-capture-spike/data/V4/logs/*/*.jsonl',
    format = 'newline_delimited',
    columns = {
        ts: 'VARCHAR',
        source: 'VARCHAR',
        feed: 'VARCHAR',
        status: 'INTEGER',
        latency_ms: 'INTEGER',
        bytes: 'BIGINT',
        error: 'VARCHAR'
    }
);

-- ---------------------------------------------------------------------------
-- 0. Overview: how much is there, and which period does it cover?
-- ---------------------------------------------------------------------------
SELECT
    count(*) AS log_lines,
    count(DISTINCT captured_at) AS passes,
    min(captured_at) AS first_pass,
    max(captured_at) AS last_pass
FROM logs;

-- ---------------------------------------------------------------------------
-- 1. Failures: which responses were not a clean HTTP 200?
-- `IS DISTINCT FROM` also counts nulls, which a plain `<>` would skip.
-- ---------------------------------------------------------------------------
SELECT source, feed, status, error, count(*) AS n
FROM logs
WHERE status IS DISTINCT FROM 200 OR error IS NOT NULL
GROUP BY ALL
ORDER BY n DESC;

-- Same failures per day: isolated incidents or a steady pattern?
SELECT
    captured_at::DATE AS day,
    count(*) AS failures,
    count(DISTINCT source || '/' || feed) AS feeds_affected
FROM logs
WHERE status IS DISTINCT FROM 200 OR error IS NOT NULL
GROUP BY day
ORDER BY day;

-- ---------------------------------------------------------------------------
-- 2. Silent gaps: minutes with no log at all.
-- A pass that is cut may never write its log, so these would not show up as
-- failures above. The query builds every minute of the period and keeps those
-- with no pass. It then joins consecutive minutes into one gap: for minutes in
-- a row, minute minus row_number gives the same value (the "gaps and islands"
-- technique).
-- ---------------------------------------------------------------------------
WITH bounds AS (
    SELECT
        date_trunc('minute', min(captured_at)) AS first_minute,
        date_trunc('minute', max(captured_at)) AS last_minute
    FROM logs
),
expected AS (
    SELECT unnest(generate_series(first_minute, last_minute, INTERVAL 1 MINUTE)) AS minute
    FROM bounds
),
observed AS (
    SELECT DISTINCT date_trunc('minute', captured_at) AS minute
    FROM logs
),
missing AS (
    SELECT minute
    FROM expected
    ANTI JOIN observed USING (minute)
),
islands AS (
    SELECT
        minute,
        minute - to_minutes(row_number() OVER (ORDER BY minute)) AS island
    FROM missing
)
SELECT
    min(minute) AS gap_start,
    max(minute) AS gap_end,
    count(*) AS minutes_missing
FROM islands
GROUP BY island
ORDER BY minutes_missing DESC, gap_start;

-- Completeness per feed: share of the period's minutes with a clean capture.
-- Only the minute-by-minute feeds are meaningful here: static feeds run hourly.
WITH bounds AS (
    SELECT date_diff('minute', min(captured_at), max(captured_at)) + 1 AS total_minutes
    FROM logs
)
SELECT
    source,
    feed,
    count(DISTINCT date_trunc('minute', captured_at)) AS clean_minutes,
    any_value(total_minutes) AS total_minutes,
    round(100.0 * clean_minutes / any_value(total_minutes), 2) AS completeness_pct
FROM logs, bounds
WHERE status = 200 AND error IS NULL
GROUP BY source, feed
ORDER BY completeness_pct DESC;

-- ---------------------------------------------------------------------------
-- 3. Latency and size per feed: useful to choose the fetch timeout.
-- A p99 of 800 means that 99% of the responses took 800 ms or less.
-- A very low min_bytes with HTTP 200 would point to empty or truncated answers.
-- ---------------------------------------------------------------------------
SELECT
    source,
    feed,
    count(*) AS responses,
    round(median(latency_ms)) AS median_ms,
    round(quantile_cont(latency_ms, 0.99)) AS p99_ms,
    max(latency_ms) AS max_ms,
    min(bytes) AS min_bytes,
    max(bytes) AS max_bytes
FROM logs
WHERE status = 200 AND error IS NULL
GROUP BY source, feed
ORDER BY p99_ms DESC;

-- ---------------------------------------------------------------------------
-- 4. Weekends: s006 only observed one weekday.
-- isodow numbers the days from 1 (Monday) to 7 (Sunday).
-- ---------------------------------------------------------------------------
SELECT
    isodow(captured_at) AS day_number,
    dayname(captured_at) AS day_name,
    count(DISTINCT captured_at::DATE) AS days_observed,
    count(*) AS log_lines,
    count(*) FILTER (WHERE status IS DISTINCT FROM 200 OR error IS NOT NULL) AS failures,
    round(median(latency_ms)) AS median_ms,
    round(quantile_cont(latency_ms, 0.99)) AS p99_ms
FROM logs
GROUP BY day_number, day_name
ORDER BY day_number;
