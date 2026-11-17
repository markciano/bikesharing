-- Probe A: reads the bronze objects of one hour of one feed, chosen through var(), and unnests the stations.
-- Input: s3://<bucket>/raw/<source>/<feed>/<date>/<YYYYMMDD>T<HH>*.json.gz on R2, the GBFS station_status body.
-- Output: one row per station and object; the feed's fields stay as read_json infers them, uncast.

with objects as (

    select
        filename,
        unnest(data.stations) as station
    from read_json(
        's3://{{ env_var("R2_BUCKET") }}/raw/{{ var("source") }}/{{ var("feed") }}/{{ var("date") }}/{{ var("date") | replace("-", "") }}T{{ var("hour") }}*.json.gz',
        filename = true
    )

)

select
    station.station_id,
    station.num_vehicles_available,
    station.num_docks_available,
    station.is_renting,
    -- The capture time is the run id in the object's name, YYYYMMDDTHHMMSSZ, in UTC.
    strptime(regexp_extract(filename, '(\d{8}T\d{6}Z)\.json\.gz$', 1), '%Y%m%dT%H%M%SZ') as captured_at,
    -- The object's key, without the s3://<bucket>/ prefix.
    regexp_replace(filename, '^s3://[^/]+/', '') as source_key
from objects
