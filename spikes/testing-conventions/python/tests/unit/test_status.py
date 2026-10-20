"""Unit tests for poc.status: GBFS parsing and staleness."""

from datetime import datetime, timedelta, timezone

from poc.status import find_stale, parse_stations


def test_parse_stations_returns_one_record_per_station(make_payload, make_station):
    payload = make_payload([make_station("1"), make_station("2")])

    stations = parse_stations(payload)

    assert [s.station_id for s in stations] == ["1", "2"]


def test_parse_stations_converts_last_reported_to_utc(make_payload, make_station):
    payload = make_payload([make_station(last_reported=1792324800)])

    (station,) = parse_stations(payload)

    assert station.last_reported == datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_stations_empty_list_returns_empty(make_payload):
    assert parse_stations(make_payload([])) == []


def test_find_stale_flags_station_older_than_max_age(now, make_payload, make_station):
    old = int((now - timedelta(minutes=11)).timestamp())
    stations = parse_stations(make_payload([make_station("1", last_reported=old)]))

    stale = find_stale(stations, now, max_age=timedelta(minutes=10))

    assert [s.station_id for s in stale] == ["1"]


def test_find_stale_keeps_station_exactly_at_max_age(now, make_payload, make_station):
    edge = int((now - timedelta(minutes=10)).timestamp())
    stations = parse_stations(make_payload([make_station("1", last_reported=edge)]))

    assert find_stale(stations, now, max_age=timedelta(minutes=10)) == []


def test_find_stale_depends_on_the_given_now(now, make_payload, make_station):
    reported = int(now.timestamp())
    stations = parse_stations(make_payload([make_station("1", last_reported=reported)]))

    later = now + timedelta(hours=1)

    assert find_stale(stations, now, max_age=timedelta(minutes=10)) == []
    assert len(find_stale(stations, later, max_age=timedelta(minutes=10))) == 1
