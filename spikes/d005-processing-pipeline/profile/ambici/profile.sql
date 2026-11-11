-- Profile AMBici's feeds that enter d005's model (GBFS 2.3), one SUMMARIZE per feed.
-- Input: the capture spike's local raw copy, <feed>/<date>/<ts>.json.gz; run from the project root.
-- Output: one CSV per feed next to this file; vehicle_types_available is unnested into its own CSV.
-- Each row carries its pass's header fields (last_updated, ttl, version), so they are profiled too.
-- Schema detection keeps its default sample: in DuckDB 2.0.0, binding the schema of each of
-- thousands of files (union_by_name, or sampling every file) runs out of memory
-- (duckdb/duckdb#27806). keys_check.py, next to this folder, finds keys present in only some files.

CREATE TEMP TABLE station_status AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/station_status/*/*.json.gz')
);

CREATE TEMP TABLE station_status_vehicle_types AS
SELECT station_id, unnest(vt)
FROM (SELECT station_id, unnest(vehicle_types_available) AS vt FROM station_status);

CREATE TEMP TABLE station_information AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/station_information/*/*.json.gz')
);

CREATE TEMP TABLE vehicle_types AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.vehicle_types) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/vehicle_types/*/*.json.gz')
);

CREATE TEMP TABLE system_regions AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.regions) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/system_regions/*/*.json.gz')
);

COPY (FROM (SUMMARIZE station_status)) TO 'spikes/d005-processing-pipeline/profile/ambici/station_status.csv' (HEADER);
COPY (FROM (SUMMARIZE station_status_vehicle_types)) TO 'spikes/d005-processing-pipeline/profile/ambici/station_status_vehicle_types.csv' (HEADER);
COPY (FROM (SUMMARIZE station_information)) TO 'spikes/d005-processing-pipeline/profile/ambici/station_information.csv' (HEADER);
COPY (FROM (SUMMARIZE vehicle_types)) TO 'spikes/d005-processing-pipeline/profile/ambici/vehicle_types.csv' (HEADER);
COPY (FROM (SUMMARIZE system_regions)) TO 'spikes/d005-processing-pipeline/profile/ambici/system_regions.csv' (HEADER);
