-- AMBici stations whose available bikes exceed their capacity, per station.
-- Input: the capture spike's local raw copy, <feed>/<date>/<ts>.json.gz; run from the project root.
-- Output: over_capacity.csv next to this file: per station, its capacity (the largest in the window),
-- the passes over it, the largest bike count and bikes + docks, and the first and last time seen (UTC).

SET TimeZone = 'UTC';

CREATE TEMP TABLE station_status AS
SELECT last_updated, unnest(s)
FROM (
    SELECT last_updated, unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/station_status/*/*.json.gz')
);

CREATE TEMP TABLE capacity AS
SELECT s.station_id, max(s.capacity) AS capacity
FROM (
    SELECT unnest(data.stations) AS s
    FROM read_json('spikes/cloudflare-capture-spike/data/V4/raw/ambici/station_information/*/*.json.gz')
)
GROUP BY 1;

COPY (
    SELECT
        station_id,
        capacity,
        count(*) AS passes_over,
        max(num_bikes_available) AS max_bikes,
        max(num_bikes_available + num_docks_available) AS max_bikes_and_docks,
        to_timestamp(min(last_updated)) AS first_seen,
        to_timestamp(max(last_updated)) AS last_seen
    FROM station_status
    JOIN capacity USING (station_id)
    WHERE num_bikes_available > capacity
    GROUP BY ALL
    ORDER BY passes_over DESC
) TO 'spikes/d005-data-model/over-capacity/over_capacity.csv' (HEADER);
