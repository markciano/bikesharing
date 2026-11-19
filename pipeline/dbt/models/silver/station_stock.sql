-- The station stock of both systems, one row per station and capture (d008 D1,
-- First version of the station stock), with its calendar keys and lineage.
with

ambici as (

    select * from {{ ref('stg_ambici__station_status') }}

),

bicing as (

    select * from {{ ref('stg_bicing__station_status') }}

),

unioned as (

    -- By name, so that each column of one system meets its peer whatever the
    -- order each staging model selects them in.
    select * from ambici
    union all by name
    select * from bicing

),

localized as (

    select
        *,
        -- Instants stay in UTC; the local calendar keys group facts by the day
        -- and minute people in Barcelona live (ADR-0041, Timestamps are stored
        -- in UTC, calendar keys in local time).
        timezone('Europe/Madrid', captured_at) as captured_at_local
    from unioned

),

final as (

    select
        system,
        station_id,
        captured_at,
        captured_at_local::date as local_date,
        (
            60 * hour(captured_at_local) + minute(captured_at_local)
        )::smallint as local_minute,
        num_vehicles_available,
        num_docks_available,
        num_vehicles_disabled,
        num_docks_disabled,
        is_installed,
        is_renting,
        is_returning,
        last_reported,
        last_updated,
        -- Every row names the run and the code that wrote it, since rows
        -- outlive the run's logs (ADR-0043, Lineage at four levels).
        '{{ var("run_id") }}' as run_id,
        '{{ var("code_version") }}' as code_version
    from localized

)

select * from final
