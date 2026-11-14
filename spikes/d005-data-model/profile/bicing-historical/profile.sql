-- Profile Bicing's history archives against d005's model: questions P2-P7 of the README's section 14, plus the
-- values P1's mapping needs (the mapping itself is done by Chat from headers.csv and profile/bicing/).
-- Input: work/*.parquet written by convert.py (every column as text; columns added, removed and moved between
-- months, so they are read by name with union_by_name), and for P6-P7 the capture spike's bronze copy,
-- spikes/cloudflare-capture-spike/data/V4/raw/bicing/<feed>/<date>/<ts>.json.gz. Run from the project root.
-- Output: one CSV per question next to this file, named p<N>_<what>.csv.
-- Conventions: 'NA' and '' are null (as in T005); instants are UTC; a day is a local day in Europe/Madrid, as
-- the archives are monthly in local time; a movement falls on the day of its later count (d005 D23).

SET TimeZone = 'UTC';
SET memory_limit = '2GB';
SET temp_directory = 'spikes/d005-data-model/profile/bicing-historical/work/tmp';

CREATE MACRO nz(x) AS nullif(nullif(trim(x), 'NA'), '');
CREATE MACRO local_day(s) AS CAST(timezone('Europe/Madrid', to_timestamp(s)) AS DATE);

-- Raw views: every column as text, plus the archive's month taken from its file name (YYYY_MM_...).
CREATE VIEW est_raw AS
SELECT replace(regexp_extract(filename, '(\d{4}_\d{2})_[^/]*$', 1), '_', '-') AS month, * EXCLUDE (filename)
FROM read_parquet('spikes/d005-data-model/profile/bicing-historical/work/*_BicingNou_ESTACIONS.parquet',
                  union_by_name = true, filename = true);

CREATE VIEW inf_raw AS
SELECT replace(regexp_extract(filename, '(\d{4}_\d{2})_[^/]*$', 1), '_', '-') AS month, * EXCLUDE (filename)
FROM read_parquet('spikes/d005-data-model/profile/bicing-historical/work/*_BicingNou_INFORMACIO.parquet',
                  union_by_name = true, filename = true);

-- Typed views: a value that does not cast becomes null here; p1_invalid.csv counts those.
CREATE VIEW est AS
SELECT month,
       TRY_CAST(nz(station_id) AS BIGINT) AS station_id,
       TRY_CAST(nz(last_updated) AS BIGINT) AS last_updated_s,
       TRY_CAST(nz(num_bikes_available) AS BIGINT) AS num_bikes_available,
       TRY_CAST(nz("num_bikes_available_types.mechanical") AS BIGINT) AS mechanical,
       TRY_CAST(nz("num_bikes_available_types.ebike") AS BIGINT) AS ebike,
       TRY_CAST(nz(num_docks_available) AS BIGINT) AS num_docks_available,
       to_timestamp(TRY_CAST(nz(last_reported) AS BIGINT)) AS last_reported,
       nz(is_installed) AS is_installed,
       nz(is_renting) AS is_renting,
       nz(is_returning) AS is_returning,
       nz(status) AS status,
       nz(is_charging_station) AS is_charging_station,
       nz(traffic) AS traffic,
       TRY_CAST(nz(ttl) AS BIGINT) AS ttl
FROM est_raw;

-- post_code stays text: Barcelona's codes start with 08.
CREATE VIEW inf AS
SELECT month,
       TRY_CAST(nz(station_id) AS BIGINT) AS station_id,
       TRY_CAST(nz(last_updated) AS BIGINT) AS last_updated_s,
       nz(name) AS name,
       nz(physical_configuration) AS physical_configuration,
       TRY_CAST(nz(lat) AS DOUBLE) AS lat,
       TRY_CAST(nz(lon) AS DOUBLE) AS lon,
       TRY_CAST(nz(altitude) AS DOUBLE) AS altitude,
       nz(address) AS address,
       nz(post_code) AS post_code,
       TRY_CAST(nz(capacity) AS BIGINT) AS capacity,
       nz(is_charging_station) AS is_charging_station,
       nz(external_id) AS external_id,
       nz(short_name) AS short_name,
       TRY_CAST(nz(nearby_distance) AS BIGINT) AS nearby_distance,
       TRY_CAST(nz(ttl) AS BIGINT) AS ttl
FROM inf_raw;

-- P1 inputs ------------------------------------------------------------------------------------------------

-- Field profile of the typed views, in the format of profile/bicing/ (SUMMARIZE).
COPY (FROM (SUMMARIZE est)) TO 'spikes/d005-data-model/profile/bicing-historical/p1_fields_estacions.csv' (HEADER);
COPY (FROM (SUMMARIZE inf)) TO 'spikes/d005-data-model/profile/bicing-historical/p1_fields_informacio.csv' (HEADER);

-- Raw values of the coded columns (at most 20 per column, most frequent first), with the months they appear in.
COPY (
    WITH v AS (
        SELECT 'ESTACIONS' AS series, col, value, count(*) AS rows, string_agg(DISTINCT month, ' ' ORDER BY month) AS months
        FROM (UNPIVOT (SELECT month, COLUMNS('^(status|traffic|is_charging_station|is_installed|is_renting|is_returning|ttl|V\d+)$') FROM est_raw)
              ON COLUMNS(* EXCLUDE (month)) INTO NAME col VALUE value)
        GROUP BY ALL
        UNION ALL
        SELECT 'INFORMACIO', col, value, count(*), string_agg(DISTINCT month, ' ' ORDER BY month)
        FROM (UNPIVOT (SELECT month, COLUMNS('^(physical_configuration|is_charging_station|x_ride_code_support|is_valet_station|nearby_distance|ttl|V\d+)$') FROM inf_raw)
              ON COLUMNS(* EXCLUDE (month)) INTO NAME col VALUE value)
        GROUP BY ALL
    )
    SELECT series, col AS field, value, rows, months
    FROM v
    QUALIFY row_number() OVER (PARTITION BY series, col ORDER BY rows DESC, value) <= 20
    ORDER BY series, field, rows DESC
) TO 'spikes/d005-data-model/profile/bicing-historical/p1_values.csv' (HEADER);

-- Non-null values of the numeric columns that are not numbers, with the smallest and largest of them.
COPY (
    SELECT 'ESTACIONS' AS series, col AS field, count(*) AS invalid_rows, min(value) AS min_value, max(value) AS max_value
    FROM (UNPIVOT (SELECT COLUMNS('^(station_id|num_bikes_available.*|num_docks_available|last_updated|last_reported|is_installed|is_renting|is_returning|ttl)$') FROM est_raw)
          ON COLUMNS(*) INTO NAME col VALUE value)
    WHERE nz(value) IS NOT NULL AND TRY_CAST(nz(value) AS DOUBLE) IS NULL
    GROUP BY ALL
    UNION ALL
    SELECT 'INFORMACIO', col, count(*), min(value), max(value)
    FROM (UNPIVOT (SELECT COLUMNS('^(station_id|lat|lon|altitude|capacity|nearby_distance|last_updated|ttl)$') FROM inf_raw)
          ON COLUMNS(*) INTO NAME col VALUE value)
    WHERE nz(value) IS NOT NULL AND TRY_CAST(nz(value) AS DOUBLE) IS NULL
    GROUP BY ALL
    ORDER BY series, field
) TO 'spikes/d005-data-model/profile/bicing-historical/p1_invalid.csv' (HEADER);

-- P2. One row per station and snapshot (d005 D4) -----------------------------------------------------------

-- Per month: rows, snapshots, rows without a key, duplicate rows (and keys whose duplicates differ), stations
-- per snapshot, rows whose local month is not the archive's, and the first and last snapshot.
COPY (
    WITH k AS (
        SELECT month, station_id, last_updated_s, count(*) AS n,
               count(DISTINCT hash(num_bikes_available, mechanical, ebike, num_docks_available,
                                   is_installed, is_renting, is_returning, status)) AS versions
        FROM est GROUP BY ALL
    ),
    snap AS (
        SELECT month, last_updated_s, count(*) AS stations
        FROM k WHERE station_id IS NOT NULL AND last_updated_s IS NOT NULL GROUP BY ALL
    ),
    m AS (
        SELECT month,
               sum(n) AS rows,
               sum(n) FILTER (WHERE station_id IS NULL OR last_updated_s IS NULL) AS rows_without_key,
               sum(n - 1) FILTER (WHERE station_id IS NOT NULL AND last_updated_s IS NOT NULL) AS duplicate_rows,
               count(*) FILTER (WHERE versions > 1) AS keys_with_differing_duplicates,
               count(DISTINCT station_id) AS stations,
               sum(n) FILTER (WHERE strftime(local_day(last_updated_s), '%Y-%m') <> month) AS rows_outside_month
        FROM k GROUP BY month
    )
    SELECT m.*, s.snapshots, s.stations_per_snapshot_min, s.stations_per_snapshot_median, s.stations_per_snapshot_max,
           s.first_snapshot_utc, s.last_snapshot_utc
    FROM m JOIN (
        SELECT month, count(*) AS snapshots, min(stations) AS stations_per_snapshot_min,
               median(stations) AS stations_per_snapshot_median, max(stations) AS stations_per_snapshot_max,
               to_timestamp(min(last_updated_s)) AS first_snapshot_utc, to_timestamp(max(last_updated_s)) AS last_snapshot_utc
        FROM snap GROUP BY month
    ) s USING (month)
    ORDER BY month
) TO 'spikes/d005-data-model/profile/bicing-historical/p2_grain.csv' (HEADER);

-- P3. Cadence (d005 D4, D23) -------------------------------------------------------------------------------

-- Distinct snapshots in one sequence across months; each interval belongs to the month of its later snapshot.
CREATE TEMP TABLE seq AS
SELECT month, last_updated_s,
       lag(last_updated_s) OVER (ORDER BY last_updated_s) AS prev_s,
       last_updated_s - lag(last_updated_s) OVER (ORDER BY last_updated_s) AS interval_s
FROM (SELECT last_updated_s, min(month) AS month FROM est WHERE last_updated_s IS NOT NULL GROUP BY last_updated_s);

COPY (
    SELECT month, count(interval_s) AS intervals, min(interval_s) AS min_s, median(interval_s) AS median_s,
           quantile_cont(interval_s, 0.95) AS p95_s, max(interval_s) AS max_s,
           round(100.0 * count(*) FILTER (WHERE interval_s = 300) / count(interval_s), 2) AS pct_exactly_300_s,
           round(100.0 * count(*) FILTER (WHERE interval_s BETWEEN 240 AND 360) / count(interval_s), 2) AS pct_240_to_360_s
    FROM seq GROUP BY month ORDER BY month
) TO 'spikes/d005-data-model/profile/bicing-historical/p3_cadence.csv' (HEADER);

COPY (
    SELECT month, interval_s, count(*) AS intervals
    FROM seq WHERE interval_s IS NOT NULL GROUP BY ALL ORDER BY month, interval_s
) TO 'spikes/d005-data-model/profile/bicing-historical/p3_intervals.csv' (HEADER);

-- P4. Gaps (d005 D23) --------------------------------------------------------------------------------------

-- A gap is an interval over 1.5 times its month's median interval, that is, at least one missed snapshot.
COPY (
    WITH med AS (SELECT month, median(interval_s) AS median_s FROM seq GROUP BY month)
    SELECT month, to_timestamp(prev_s) AS start_utc, to_timestamp(last_updated_s) AS end_utc,
           round(interval_s / 60.0, 1) AS duration_min, round(interval_s / median_s) - 1 AS missed_snapshots
    FROM seq JOIN med USING (month)
    WHERE interval_s > 1.5 * median_s
    ORDER BY start_utc
) TO 'spikes/d005-data-model/profile/bicing-historical/p4_gaps.csv' (HEADER);

-- P5. Mechanical and electric add up to the available bikes (d005 D5, D8) ----------------------------------

COPY (
    SELECT month, count(*) AS rows,
           count(*) FILTER (WHERE mechanical IS NULL OR ebike IS NULL OR num_bikes_available IS NULL) AS rows_with_a_null,
           count(*) FILTER (WHERE mechanical + ebike = num_bikes_available) AS rows_equal,
           count(*) FILTER (WHERE mechanical + ebike <> num_bikes_available) AS rows_different,
           max(abs(mechanical + ebike - num_bikes_available)) AS max_abs_difference
    FROM est GROUP BY month ORDER BY month
) TO 'spikes/d005-data-model/profile/bicing-historical/p5_split.csv' (HEADER);

-- Real-time copy (bronze, GBFS 3.0) for P6 and P7 ---------------------------------------------------------

-- One row per station and last_updated; a response captured twice keeps one row.
CREATE TEMP TABLE rt AS
SELECT TRY_CAST(station_id AS BIGINT) AS station_id, epoch(last_updated)::BIGINT AS last_updated_s,
       any_value(num_vehicles_available) AS nva, any_value(num_vehicles_disabled) AS nvd,
       any_value(num_docks_available) AS nda
FROM (
    SELECT last_updated, unnest(s)
    FROM (SELECT last_updated, unnest(data.stations) AS s
          FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_status/*/*.json.gz'))
)
GROUP BY ALL;

-- The archive's rows within the real-time copy's time range, one row per station and last_updated.
CREATE TEMP TABLE ar AS
SELECT station_id, last_updated_s, any_value(num_bikes_available) AS nba, any_value(num_docks_available) AS nda
FROM est
WHERE month = '2026-10'
  AND last_updated_s BETWEEN (SELECT min(last_updated_s) FROM rt) AND (SELECT max(last_updated_s) FROM rt)
GROUP BY ALL;

-- P6. Station identity and capacity (d005 D5) --------------------------------------------------------------

-- Per station: in the archive and in real time over the overlap, each side's last name, capacity and position,
-- and the distance between both positions.
COPY (
    WITH a AS (
        SELECT station_id, arg_max(name, last_updated_s) AS archive_name, arg_max(capacity, last_updated_s) AS archive_capacity,
               arg_max(lat, last_updated_s) AS alat, arg_max(lon, last_updated_s) AS alon
        FROM inf
        WHERE month = '2026-10'
          AND last_updated_s BETWEEN (SELECT min(last_updated_s) FROM rt) AND (SELECT max(last_updated_s) FROM rt)
        GROUP BY station_id
    ),
    r AS (
        SELECT TRY_CAST(station_id AS BIGINT) AS station_id, arg_max(name[1].text, last_updated) AS realtime_name,
               arg_max(capacity, last_updated) AS realtime_capacity,
               arg_max(lat, last_updated) AS rlat, arg_max(lon, last_updated) AS rlon
        FROM (SELECT last_updated, unnest(s)
              FROM (SELECT last_updated, unnest(data.stations) AS s
                    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_information/*/*.json.gz')))
        GROUP BY 1
    )
    SELECT station_id, a.station_id IS NOT NULL AS in_archive, r.station_id IS NOT NULL AS in_realtime,
           archive_name, realtime_name, archive_capacity, realtime_capacity,
           round(2 * 6371008.8 * asin(sqrt(power(sin(radians(rlat - alat) / 2), 2)
                 + cos(radians(alat)) * cos(radians(rlat)) * power(sin(radians(rlon - alon) / 2), 2))), 1) AS distance_m
    FROM a FULL JOIN r USING (station_id)
    ORDER BY (in_archive AND in_realtime), distance_m DESC NULLS FIRST, station_id
) TO 'spikes/d005-data-model/profile/bicing-historical/p6_identity.csv' (HEADER);

-- Per station whose capacity changes over the year: distinct values, changes, first and last capacity.
COPY (
    WITH c AS (
        SELECT station_id, last_updated_s, capacity,
               capacity IS DISTINCT FROM lag(capacity) OVER (PARTITION BY station_id ORDER BY last_updated_s) AS changed,
               row_number() OVER (PARTITION BY station_id ORDER BY last_updated_s) AS rn
        FROM (SELECT DISTINCT station_id, last_updated_s, capacity FROM inf WHERE station_id IS NOT NULL)
    )
    SELECT station_id, count(DISTINCT capacity) AS distinct_capacities, count(*) FILTER (WHERE changed AND rn > 1) AS changes,
           arg_min(capacity, last_updated_s) AS first_capacity, arg_max(capacity, last_updated_s) AS last_capacity
    FROM c GROUP BY station_id
    HAVING count(*) FILTER (WHERE changed AND rn > 1) > 0
    ORDER BY changes DESC, station_id
) TO 'spikes/d005-data-model/profile/bicing-historical/p6_capacity.csv' (HEADER);

-- P7. Overlap with the real-time copy (d005 D3, D22) -------------------------------------------------------

-- Each archive row paired with the latest real-time response of its station at or before its last_updated.
CREATE TEMP TABLE pairs AS
SELECT ar.station_id, ar.last_updated_s, ar.nba, ar.nda AS archive_nda, rt.nva, rt.nvd, rt.nda AS realtime_nda,
       ar.last_updated_s - rt.last_updated_s AS lag_s
FROM ar ASOF LEFT JOIN rt ON ar.station_id = rt.station_id AND ar.last_updated_s >= rt.last_updated_s;

-- Per match kind: rows, and rows whose docks and bikes agree, reading the archive's bikes as available only
-- and as available plus disabled.
COPY (
    SELECT CASE WHEN lag_s = 0 THEN '1 exact' WHEN lag_s <= 60 THEN '2 within 60 s' ELSE '3 none' END AS match_kind,
           count(*) AS archive_rows, median(lag_s) AS median_lag_s,
           count(*) FILTER (WHERE archive_nda = realtime_nda) AS same_docks,
           count(*) FILTER (WHERE nba = nva) AS bikes_equal_available,
           count(*) FILTER (WHERE nba = nva + nvd) AS bikes_equal_available_plus_disabled,
           count(*) FILTER (WHERE archive_nda = realtime_nda AND nba = nva) AS docks_and_available_equal
    FROM pairs GROUP BY 1 ORDER BY 1
) TO 'spikes/d005-data-model/profile/bicing-historical/p7_counts.csv' (HEADER);

-- Departures and arrivals per full local day of the overlap (d005 D22, D23), from four series of counts:
--   archive_5min_available: the archive as it would enter the model (AMBici's rule, available only);
--   realtime_at_archive_instants: the real-time counts paired above (within 60 s), available plus disabled;
--   realtime_1min_available: every real-time response, available only;
--   realtime_1min_available_plus_disabled: every real-time response, as the model takes Bicing (D22).
-- The first two differ in the rule and the source, the last two only in the rule, and the second and fourth
-- only in cadence.
COPY (
    WITH win AS (
        SELECT local_day(min(last_updated_s)) + 1 AS first_day, local_day(max(last_updated_s)) - 1 AS last_day FROM rt
    ),
    counts AS (
        SELECT 'archive_5min_available' AS series, station_id, last_updated_s, nba AS v FROM ar
        UNION ALL
        SELECT 'realtime_at_archive_instants', station_id, last_updated_s, nva + nvd FROM pairs WHERE lag_s <= 60
        UNION ALL
        SELECT 'realtime_1min_available', station_id, last_updated_s, nva FROM rt
        UNION ALL
        SELECT 'realtime_1min_available_plus_disabled', station_id, last_updated_s, nva + nvd FROM rt
    ),
    moves AS (
        SELECT series, local_day(last_updated_s) AS local_date,
               v - lag(v) OVER (PARTITION BY series, station_id ORDER BY last_updated_s) AS change
        FROM counts, win
        WHERE local_day(last_updated_s) BETWEEN win.first_day AND win.last_day
    )
    SELECT local_date, series, sum(greatest(-change, 0)) AS departures, sum(greatest(change, 0)) AS arrivals
    FROM moves GROUP BY ALL ORDER BY local_date, series
) TO 'spikes/d005-data-model/profile/bicing-historical/p7_movements.csv' (HEADER);
