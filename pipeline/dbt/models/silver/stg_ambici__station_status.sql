-- AMBici's station status, one row per station and capture (d008 D1, First
-- version of the station stock). AMBici publishes GBFS 2.3, POSIX instants.
with

source as (

    select * from {{ source('ambici', 'station_status') }}

),

stations as (

    select
        source.last_updated,
        -- The local path ends with the object's bronze key, which holds its
        -- system and capture instant (ADR-0012, Collectors decoupled by output
        -- contract).
        regexp_extract(
            source.filename,
            'raw/([a-z]+)/[a-z_]+/[0-9-]+/(\d{8}T\d{6}Z)\.json\.gz$',
            ['system', 'run_id']
        ) as bronze_key,
        unnest(source.data.stations) as station
    from source

),

final as (

    select
        stations.bronze_key.system,
        stations.station.station_id,
        -- Measures take their GBFS 3.0 names, so that both systems share one
        -- column (d005 D14, Vocabulary of the measures).
        stations.station.num_bikes_available as num_vehicles_available,
        stations.station.num_docks_available,
        stations.station.is_installed,
        stations.station.is_renting,
        stations.station.is_returning,
        -- AMBici publishes no disabled counts; null states that they are
        -- unknown, not zero (d005 D15, Disabled vehicles and docks).
        null::integer as num_vehicles_disabled,
        null::integer as num_docks_disabled,
        timezone(
            'UTC', strptime(stations.bronze_key.run_id, '%Y%m%dT%H%M%SZ')
        ) as captured_at,
        to_timestamp(stations.station.last_reported) as last_reported,
        to_timestamp(stations.last_updated) as last_updated
    from stations

)

select * from final
