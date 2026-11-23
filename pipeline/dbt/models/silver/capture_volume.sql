-- Each capture of the batch against the median number of stations of its
-- system's captures in the 7 days before it (d009 D6, Volume drop at 95% of a
-- 7-day median).
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
        count(*) over trailing_week as captures_in_window,
        median(captures.station_count)
            over trailing_week
            as median_station_count
    from captures
    window trailing_week as (
        partition by captures.system
        order by captures.captured_at
        range between interval '7 days' preceding and current row
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
        -- The 95% threshold over 7 days follows the production captures, where
        -- a 24 h median absorbed a sustained drop (d009 D6, Volume drop at 95%
        -- of a 7-day median).
        case
            when captures_in_window < 60 then 'not_evaluated'
            when station_count < 0.95 * median_station_count then 'drop'
            else 'ok'
        end as status
    from windowed
    where is_in_batch

)

select * from final
