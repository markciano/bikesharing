-- Each capture of the batch against the median number of stations of its
-- system's captures in the 24 h before it (d008 D4, Volume drop against a
-- rolling median).
with

ambici as (

    select * from {{ source('ambici', 'station_status') }}

),

bicing as (

    select * from {{ source('bicing', 'station_status') }}

),

history as (

    select * from {{ source('lakehouse', 'capture_history') }}

),

listed as (

    select
        ambici.filename,
        len(ambici.data.stations) as listed_stations
    from ambici
    union all
    select
        bicing.filename,
        len(bicing.data.stations) as listed_stations
    from bicing

),

batch_captures as (

    select
        {{ bronze_key('listed.filename') }} as bronze_key,
        -- A capture that lists no station counts 0, so that an empty feed is
        -- measured as a drop, not left out of the history.
        coalesce(listed.listed_stations, 0)::integer as station_count
    from listed

),

captures as (

    select
        batch_captures.bronze_key.system,
        batch_captures.bronze_key.captured_at,
        batch_captures.station_count,
        true as is_in_batch
    from batch_captures
    union all
    select
        history.system,
        history.captured_at,
        history.station_count,
        false as is_in_batch
    from history

),

windowed as (

    -- The window follows each capture's instant, not the run's, so that each
    -- capture of a first load is compared with its own past (d008 D8, First
    -- load in chronological stages).
    select
        captures.*,
        count(*) over trailing_day as captures_in_window,
        median(captures.station_count) over trailing_day as median_station_count
    from captures
    window trailing_day as (
        partition by captures.system
        order by captures.captured_at
        range between interval '24 hours' preceding and current row
        exclude current row
    )

),

final as (

    select
        system,
        captured_at,
        station_count,
        captures_in_window::integer as captures_in_window,
        median_station_count::double as median_station_count,
        -- The threshold, window and minimum baseline are provisional, to be
        -- reviewed against production runs (d008 D4, Volume drop against a
        -- rolling median).
        case
            when captures_in_window < 60 then 'not_evaluated'
            when station_count < 0.9 * median_station_count then 'drop'
            else 'ok'
        end as status
    from windowed
    where is_in_batch

)

select * from final
