-- Bicing: how the station_status counts add up against capacity, and which hypotheses fit the mismatches.
-- diff = va + vd + da + dd - cap (va/vd vehicles available/disabled, da/dd docks available/disabled;
-- cap: the largest capacity in station_information over the window).
-- H1 diff = 0; H2 over, diff <= least(vd, dd) (a disabled vehicle in a disabled dock, counted twice);
-- H3 over, diff <= least(va, vd) (a vehicle counted as available and disabled);
-- H4/H5 under: runs of consecutive deficit passes per station, by duration (short ones fit reservations).
-- Input: the capture spike's local raw copy; run from the project root. Output: tables on stdout.

SET enable_progress_bar = false;
SET TimeZone = 'UTC';

CREATE TEMP TABLE b_status AS
SELECT CAST(last_updated AS TIMESTAMPTZ) AS ts, unnest(s) FROM (
    SELECT last_updated, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_status/*/*.json.gz')
);
CREATE TEMP TABLE b_cap AS
SELECT s.station_id, max(s.capacity) AS cap
FROM (
    SELECT unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_information/*/*.json.gz')
)
GROUP BY 1;

CREATE TEMP TABLE items AS
SELECT station_id, ts, cap,
       num_vehicles_available AS va, num_vehicles_disabled AS vd,
       num_docks_available AS da, num_docks_disabled AS dd,
       num_vehicles_available + num_vehicles_disabled + num_docks_available + num_docks_disabled - cap AS diff
FROM b_status JOIN b_cap USING (station_id)
-- In-service items only: an out-of-service station reports 0 vehicles (d005 › D16).
WHERE is_installed AND is_renting AND is_returning;

-- Equal, over and under; H2 and H3 over the items above capacity
SELECT count(*) AS items,
       count(*) FILTER (diff = 0) AS h1_equal,
       count(*) FILTER (diff > 0) AS over,
       count(*) FILTER (diff > 0 AND diff <= least(vd, dd) AND diff > least(va, vd)) AS over_h2_only,
       count(*) FILTER (diff > 0 AND diff <= least(va, vd) AND diff > least(vd, dd)) AS over_h3_only,
       count(*) FILTER (diff > 0 AND diff <= least(vd, dd) AND diff <= least(va, vd)) AS over_h2_and_h3,
       count(*) FILTER (diff > 0 AND diff > least(vd, dd) AND diff > least(va, vd)) AS over_neither,
       count(*) FILTER (diff < 0) AS under
FROM items;

-- Items above capacity: size of the excess and the disabled counts beside it
SELECT count(*) AS over,
       count(*) FILTER (diff = 1) AS excess_1,
       max(diff) AS max_excess,
       count(*) FILTER (diff <= vd) AS excess_le_vd,
       count(*) FILTER (vd = 0) AS no_disabled_vehicle,
       count(*) FILTER (dd < diff) AS dd_below_excess,
       count(DISTINCT station_id) AS stations
FROM items
WHERE diff > 0;

-- Stations per hypothesis (items above capacity)
SELECT count(DISTINCT station_id) FILTER (diff > 0) AS st_over,
       count(DISTINCT station_id) FILTER (diff > 0 AND diff <= least(vd, dd)) AS st_h2,
       count(DISTINCT station_id) FILTER (diff > 0 AND diff <= least(va, vd)) AS st_h3,
       count(DISTINCT station_id) FILTER (diff > 0 AND diff > least(vd, dd) AND diff > least(va, vd)) AS st_neither
FROM items;

-- H4/H5: deficit runs (gaps and islands per station)
CREATE TEMP TABLE runs AS
WITH flagged AS (
    SELECT *, diff < 0 AS under,
           row_number() OVER (PARTITION BY station_id ORDER BY ts)
         - row_number() OVER (PARTITION BY station_id, diff < 0 ORDER BY ts) AS grp
    FROM items
)
SELECT station_id, grp, count(*) AS passes, min(ts) AS start_ts, max(ts) AS end_ts,
       max(ts) - min(ts) AS duration, min(diff) AS worst_deficit, max(diff) AS least_deficit
FROM flagged
WHERE under
GROUP BY ALL;

SELECT CASE
           WHEN duration <= INTERVAL 6 MINUTE THEN '1: <= 6 min'
           WHEN duration <= INTERVAL 1 HOUR THEN '2: 6 min - 1 h'
           WHEN duration <= INTERVAL 1 DAY THEN '3: 1 h - 1 d'
           ELSE '4: > 1 d'
       END AS run_length,
       count(*) AS runs,
       sum(passes) AS items,
       count(DISTINCT station_id) AS stations,
       round(avg(-worst_deficit), 1) AS avg_worst_deficit,
       max(-worst_deficit) AS max_deficit
FROM runs
GROUP BY 1
ORDER BY 1;

-- Short runs by deficit size (reservation-like ones should be small)
SELECT -worst_deficit AS deficit, count(*) AS runs, sum(passes) AS items
FROM runs
WHERE duration <= INTERVAL 6 MINUTE
GROUP BY 1
ORDER BY 1;

-- Longest runs: stations under capacity for most of the window
SELECT station_id, cap, passes, duration, -worst_deficit AS worst_deficit, -least_deficit AS least_deficit
FROM runs JOIN b_cap USING (station_id)
ORDER BY duration DESC
LIMIT 10;
