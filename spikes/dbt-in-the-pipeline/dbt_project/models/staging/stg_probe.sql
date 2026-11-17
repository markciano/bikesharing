-- Probe A: the typed rows of the window that meet the schema; the rest go to stg_probe_quarantine.
-- Input: base_probe_read, uncast. Output: one row per station and object, with the types of the contract in stg_probe.yml.
-- The casts are the same as in stg_probe_quarantine; a row is kept only if every required field casts to a non-null value.

with typed as (

    select
        try_cast(station_id as varchar) as station_id,
        try_cast(num_vehicles_available as integer) as num_vehicles_available,
        try_cast(num_docks_available as integer) as num_docks_available,
        try_cast(is_renting as boolean) as is_renting,
        captured_at,
        source_key
    from {{ ref('base_probe_read') }}

)

select *
from typed
where station_id is not null
    and num_vehicles_available is not null
    and num_docks_available is not null
    and is_renting is not null
    and captured_at is not null
    and source_key is not null
