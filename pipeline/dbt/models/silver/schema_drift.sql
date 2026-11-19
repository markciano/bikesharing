-- The fields each bronze object of the batch adds to or drops from its
-- system's read schema (d008, Transformation in dbt): a read with explicit
-- columns ignores a new field and reads a missing one as null, so drift is
-- found on the objects read with no schema.
with

ambici as (

    select * from {{ source('ambici', 'station_status_raw') }}

),

bicing as (

    select * from {{ source('bicing', 'station_status_raw') }}

),

objects as (

    select
        ambici.json,
        ambici.filename,
        {{ var('station_fields')['ambici'] }} as declared_fields
    from ambici
    union all
    select
        bicing.json,
        bicing.filename,
        {{ var('station_fields')['bicing'] }} as declared_fields
    from bicing

),

keyed as (

    select
        {{ bronze_key('objects.filename') }} as bronze_key,
        objects.json,
        objects.declared_fields
    from objects

),

stations as (

    select
        keyed.bronze_key.system,
        keyed.bronze_key.captured_at,
        unnest(json_extract(keyed.json, '$.data.stations[*]')) as station
    from keyed

),

-- The union of the stations' keys per object, so that an optional field that
-- only some stations carry raises no drift.
observed as (

    select distinct
        stations.system,
        stations.captured_at,
        unnest(json_keys(stations.station)) as field
    from stations

),

declared as (

    select
        keyed.bronze_key.system,
        keyed.bronze_key.captured_at,
        unnest(keyed.declared_fields) as field
    from keyed

),

added as (

    select
        system,
        captured_at,
        field
    from observed
    except
    select
        system,
        captured_at,
        field
    from declared

),

dropped as (

    select
        system,
        captured_at,
        field
    from declared
    except
    select
        system,
        captured_at,
        field
    from observed

),

final as (

    -- `change` is the column the model's contract names, which DuckDB accepts
    -- unquoted.
    select
        system,
        captured_at,
        field,
        'added' as change  -- noqa: RF04
    from added
    union all
    select
        system,
        captured_at,
        field,
        'dropped' as change  -- noqa: RF04
    from dropped

)

select * from final
