-- Completeness check of production's first 48 h on its own (d004 > D6).
--
-- Input: an `rclone lsf -R` listing of bikesharing-bronze/raw/ saved to a local
-- file (one path per line, `<source>/<feed>/<YYYY-MM-DD>/<YYYYMMDDTHHMMSSZ>.json.gz`;
-- lines ending in `/` are folders). No object is downloaded.
-- Output: per source and dynamic feed, the distinct minutes of the window with at
-- least one object, read from the key's timestamp; `pct` is those minutes over the
-- minutes of the window, in percent, and `below_target` flags a feed under 99.5%.
--
-- Set the three variables below, then run from the repository root:
--   duckdb -f spikes/cloudflare-capture-spike/analysis/capture-completeness.sql
-- Every timestamp is UTC.

-- The listing file and the window [window_start, window_end).
SET VARIABLE listing = 'spikes/cloudflare-capture-spike/analysis/output/prod-completeness.txt';
SET VARIABLE window_start = TIMESTAMP '2026-11-09 12:00:00';
SET VARIABLE window_end = TIMESTAMP '2026-11-11 12:00:00';

-- The dynamic feeds of d004 > D3. A feed with no object in the window still
-- gets a row, with 0 minutes.
WITH dynamic_feeds(source, feed) AS (
  VALUES ('ambici', 'station_status'),
         ('ambici', 'free_bike_status'),
         ('bicing', 'station_status')
),
objects AS (
  SELECT
    split_part(path, '/', 1) AS source,
    split_part(path, '/', 2) AS feed,
    -- `YYYYMMDDTHHMMSSZ.json.gz` -> the minute of the pass.
    strptime(substr(split_part(path, '/', 4), 1, 13), '%Y%m%dT%H%M') AS minute
  FROM read_csv(getvariable('listing'), header = false, delim = '\t',
                columns = {'path': 'VARCHAR'})
  WHERE NOT ends_with(path, '/')
),
in_window AS (
  SELECT source, feed, count(DISTINCT minute) AS minutes
  FROM objects
  WHERE minute >= getvariable('window_start')
    AND minute < getvariable('window_end')
  GROUP BY source, feed
),
window_minutes AS (
  SELECT date_diff('minute', getvariable('window_start'),
                   getvariable('window_end')) AS total
)
SELECT
  d.source,
  d.feed,
  coalesce(w.minutes, 0) AS minutes,
  round(100.0 * coalesce(w.minutes, 0) / t.total, 2) AS pct,
  coalesce(w.minutes, 0) / t.total < 0.995 AS below_target
FROM dynamic_feeds d
CROSS JOIN window_minutes t
LEFT JOIN in_window w USING (source, feed)
ORDER BY d.source, d.feed;
