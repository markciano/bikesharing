-- Profile Bicing's feeds that enter d005's model (GBFS 3.0), one SUMMARIZE per feed.
-- Input: the capture spike's local raw copy, <feed>/<date>/<ts>.json.gz; run from the project root.
-- Output: one CSV per feed next to this file; vehicle_types_available is unnested into its own CSV.
-- Each row carries its pass's header fields (last_updated, ttl, version), so they are profiled too.
-- Schema detection keeps its default sample: in DuckDB 2.0.0, binding the schema of each of
-- thousands of files (union_by_name, or sampling every file) runs out of memory
-- (duckdb/duckdb#27806). keys_check.py, next to this folder, finds keys present in only some files.
-- system_regions is not profiled: Bicing publishes it empty (d005 D3).

CREATE TEMP TABLE station_status AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_status/*/*.json.gz')
);

CREATE TEMP TABLE station_status_vehicle_types AS
SELECT station_id, unnest(vt)
FROM (SELECT station_id, unnest(vehicle_types_available) AS vt FROM station_status);

CREATE TEMP TABLE station_information AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/station_information/*/*.json.gz')
);

CREATE TEMP TABLE vehicle_types AS
SELECT last_updated, ttl, version, unnest(s)
FROM (
    SELECT last_updated, ttl, version, unnest(data.vehicle_types) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/bicing/vehicle_types/*/*.json.gz')
);

COPY (FROM (SUMMARIZE station_status)) TO 'spikes/d005-data-model/profile/bicing/station_status.csv' (HEADER);
COPY (FROM (SUMMARIZE station_status_vehicle_types)) TO 'spikes/d005-data-model/profile/bicing/station_status_vehicle_types.csv' (HEADER);
COPY (FROM (SUMMARIZE station_information)) TO 'spikes/d005-data-model/profile/bicing/station_information.csv' (HEADER);
COPY (FROM (SUMMARIZE vehicle_types)) TO 'spikes/d005-data-model/profile/bicing/vehicle_types.csv' (HEADER);
