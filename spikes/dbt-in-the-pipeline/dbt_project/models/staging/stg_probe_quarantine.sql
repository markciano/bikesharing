-- Probe A: the rows of the window that break the schema of stg_probe (ADR-0042: quarantined, the rest of the batch goes on).
-- Input: base_probe_read, uncast. Output: one row per failing row, with its object's key, its raw station key and the first field that failed.
-- The casts are the same as in stg_probe.

with typed as (

    select
        station_id as raw_station_id,
        try_cast(station_id as varchar) as station_id,
        try_cast(num_vehicles_available as integer) as num_vehicles_available,
        try_cast(num_docks_available as integer) as num_docks_available,
        try_cast(is_renting as boolean) as is_renting,
        captured_at,
        source_key
    from {{ ref('base_probe_read') }}

),

checked as (

    select
        source_key,
        raw_station_id,
        case
            when station_id is null then 'station_id'
            when num_vehicles_available is null then 'num_vehicles_available'
            when num_docks_available is null then 'num_docks_available'
            when is_renting is null then 'is_renting'
            when captured_at is null then 'captured_at'
        end as failed_field
    from typed

)

select *
from checked
where failed_field is not null
