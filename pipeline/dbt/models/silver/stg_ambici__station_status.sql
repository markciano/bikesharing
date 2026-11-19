-- AMBici's station status, one row per station and capture (d008 D1, First
-- version of the station stock). AMBici publishes GBFS 2.3, POSIX instants.
with

source as (

    select * from {{ source('ambici', 'station_status') }}

),

stations as (

    select
        source.last_updated,
        {{ bronze_key('source.filename') }} as bronze_key,
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
        stations.bronze_key.captured_at,
        to_timestamp(stations.station.last_reported) as last_reported,
        to_timestamp(stations.last_updated) as last_updated
    from stations

)

select * from final
