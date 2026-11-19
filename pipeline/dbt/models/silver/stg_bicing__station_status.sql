-- Bicing's station status, one row per station and capture (d008 D1, First
-- version of the station stock). Bicing publishes GBFS 3.0, RFC 3339 instants.
with

source as (

    select * from {{ source('bicing', 'station_status') }}

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
        stations.station.num_docks_available,
        stations.station.num_vehicles_disabled,
        stations.station.num_docks_disabled,
        stations.station.is_installed,
        stations.station.is_renting,
        stations.station.is_returning,
        -- Bicing's instants carry their offset, so the cast keeps the instant
        -- published whatever the session's time zone.
        stations.station.last_reported::timestamptz as last_reported,
        stations.last_updated::timestamptz as last_updated,
        timezone(
            'UTC', strptime(stations.bronze_key.run_id, '%Y%m%dT%H%M%SZ')
        ) as captured_at,
        -- A station neither renting nor returning is out of service: the
        -- vehicles it lists cannot be rented, so they are not stock (d005 D16,
        -- Vehicles at an out-of-service station).
        case
            when
                not stations.station.is_renting
                and not stations.station.is_returning
                then null
            else stations.station.num_vehicles_available
        end as num_vehicles_available
    from stations

)

select * from final
