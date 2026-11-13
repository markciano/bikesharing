-- Whether a Bicing station whose last_reported is old still sends new counts.
-- Input: the capture spike's local raw copy, <feed>/<date>/<ts>.json.gz; run from the project root.
-- Output, next to this file:
--   last_reported_by_age.csv: per age band of last_reported (feed time minus last_reported), the passes,
--     the passes whose counts differ from the station's previous pass, and that share.
--   last_reported_stale.csv: per station with any pass over 24 h old, its passes, the stale ones,
--     the count changes among those, its oldest last_reported and the stale passes per status flag.

SET TimeZone = 'UTC';

CREATE TEMP TABLE station_status AS
SELECT last_updated, unnest(s)
FROM (
    SELECT last_updated, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_status/*/*.json.gz')
);

-- One row per station and pass, with the age of last_reported and whether any count changed
-- since the station's previous pass (the first pass of a station has no previous one: not counted).
CREATE TEMP TABLE passes AS
SELECT
    station_id,
    last_updated,
    last_reported,
    last_updated - last_reported AS age,
    is_installed,
    is_renting,
    is_returning,
    (num_vehicles_available, num_vehicles_disabled, num_docks_available, num_docks_disabled)
        IS DISTINCT FROM lag((num_vehicles_available, num_vehicles_disabled, num_docks_available, num_docks_disabled))
            OVER (PARTITION BY station_id ORDER BY last_updated) AS changed,
    lag(last_updated) OVER (PARTITION BY station_id ORDER BY last_updated) IS NOT NULL AS has_previous
FROM station_status;

COPY (
    SELECT
        CASE
            WHEN age < INTERVAL 10 MINUTE THEN '1: < 10 min'
            WHEN age < INTERVAL 1 HOUR THEN '2: 10 min - 1 h'
            WHEN age < INTERVAL 24 HOUR THEN '3: 1 h - 24 h'
            ELSE '4: >= 24 h'
        END AS age_band,
        count(*) AS passes,
        count(*) FILTER (WHERE changed) AS passes_changed,
        round(100.0 * count(*) FILTER (WHERE changed) / count(*), 2) AS pct_changed
    FROM passes
    WHERE has_previous
    GROUP BY 1
    ORDER BY 1
) TO 'spikes/d005-data-model/last-reported/last_reported_by_age.csv' (HEADER);

COPY (
    SELECT
        station_id,
        count(*) AS passes,
        count(*) FILTER (WHERE age >= INTERVAL 24 HOUR) AS stale_passes,
        count(*) FILTER (WHERE age >= INTERVAL 24 HOUR AND changed AND has_previous) AS stale_changes,
        min(last_reported) AS oldest_last_reported,
        count(*) FILTER (WHERE age >= INTERVAL 24 HOUR AND is_installed) AS stale_installed,
        count(*) FILTER (WHERE age >= INTERVAL 24 HOUR AND is_renting) AS stale_renting,
        count(*) FILTER (WHERE age >= INTERVAL 24 HOUR AND is_returning) AS stale_returning
    FROM passes
    GROUP BY station_id
    HAVING stale_passes > 0
    ORDER BY stale_changes DESC, stale_passes DESC
) TO 'spikes/d005-data-model/last-reported/last_reported_stale.csv' (HEADER);
