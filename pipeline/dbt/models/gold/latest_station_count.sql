-- The latest count of each station, in the fields of the published file
-- (d008 D2, Published file: the latest count of each station). The shell
-- writes the source with only the rows of each system's latest capture, so
-- this model selects columns and never decides which capture is the latest.
with

latest_captures as (

    select * from {{ source('lakehouse', 'latest_captures') }}

),

final as (

    select
        system,
        station_id,
        num_vehicles_available,
        num_docks_available,
        is_renting,
        is_returning,
        last_reported,
        captured_at
    from latest_captures

)

select * from final
