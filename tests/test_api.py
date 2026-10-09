import json

import pytest
from fastapi.testclient import TestClient

from conftest import FIXTURES
from noaa_events import parse_noaa_file
from noaa_matcher import match
from sciquality_events import load_sciquality

LMSAL = [
    {'event_id': 'gev_20240514_0203', 'event_start': '2024/05/14 02:03:00', 'event_stop': '02:19:00',
     'event_peak': '02:09:00', 'event_GOES': 'X1.7', 'event_position': 'N13E15( 3664 )'},
    {'event_id': 'gev_20240514_1725', 'event_start': '2024/05/14 17:25:00', 'event_stop': '18:18:00',
     'event_peak': '17:38:00', 'event_GOES': 'M4.5', 'event_position': 'N19E72( 3682 )'},
    {'event_id': 'gev_20240601_0101', 'event_start': '2024/06/01 01:01:00', 'event_stop': '01:10:00',
     'event_peak': '01:05:00', 'event_GOES': 'C1.0', 'event_position': ''},
]


def build_fixture_files(directory):
    lmsal = json.loads(json.dumps(LMSAL))
    noaa = parse_noaa_file(str(FIXTURES / 'noaa' / '20240514events.txt'))
    match(lmsal, noaa)
    sq = load_sciquality(str(FIXTURES / 'sciquality.csv'))
    paths = {}
    for name, rows in (('LMSAL_EVENTS_PATH', lmsal), ('NOAA_EVENTS_PATH', noaa), ('SCIQUALITY_EVENTS_PATH', sq)):
        path = directory / (name.lower() + '.json')
        path.write_text(json.dumps(rows))
        paths[name] = str(path)
    return paths


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import api
    import api_sources

    paths = build_fixture_files(tmp_path_factory.mktemp('api'))
    env = {'LMSAL_EVENTS_PATH': 'lmsal', 'NOAA_EVENTS_PATH': 'noaa', 'SCIQUALITY_EVENTS_PATH': 'sciquality'}
    saved = {}
    for name, key in env.items():
        source = api_sources.SOURCES[key]
        saved[key] = source.path
        source.path, source._mtime = paths[name], None  # point the live sources at the fixture files
    yield TestClient(api.app)
    for key, path in saved.items():
        api_sources.SOURCES[key].path, api_sources.SOURCES[key]._mtime = path, None


def ids(response):
    assert response.status_code == 200, response.text
    return [e['event_id'] for e in response.json()]


def test_old_endpoints_unchanged(client):
    r = client.get('/events', params={'limit': 2})
    assert r.status_code == 200 and r.headers['X-Total-Count'] == '3'
    assert set(r.json()[0]) >= {'event_id', 'event_start', 'event_GOES', 'quality_flag'}
    assert ids(r) == ['gev_20240601_0101', 'gev_20240514_1725']  # newest first, as before
    assert client.get('/events/gev_20240514_0203').json()['quality_flag'] == 'HIGH'
    assert set(client.get('/stats').json()) >= {'total_events', 'quality_high', 'quality_low', 'quality_na'}


def test_lmsal_new_filters(client):
    assert ids(client.get('/events', params={'active_region': '3664'})) == ['gev_20240514_0203']
    assert ids(client.get('/events', params={'quality_flag': 'n/a'})) == ['gev_20240601_0101']


def test_noaa_filters_accept_loose_spelling(client):
    r = client.get('/noaa/events', params={'start_date': '2024-05-14', 'end_date': '2024-05-14',
                                           'active_region': ' ar13664 ', 'goes_class': 'x1'})
    assert ids(r) == ['noaa_20240514_3120', 'noaa_20240514_2870']


def test_class_bin_does_not_match_x10_and_up(client):
    assert 'noaa_20240514_3120' not in ids(client.get('/noaa/events', params={'goes_class': 'X10'}))


def test_missing_begin_still_found_by_date(client):
    assert 'noaa_20240514_3100' in ids(client.get('/noaa/events', params={'start_date': '2024-05-14', 'end_date': '2024-05-14'}))


def test_flare_with_missing_class_never_matches_a_class_filter(client):
    assert 'noaa_20240514_3110' not in ids(client.get('/noaa/events', params={'goes_class': 'C'}))


@pytest.mark.parametrize('params, word', [
    ({'goes_class': 'Z9'}, 'goes_class'),
    ({'active_region': 'abc'}, 'active_region'),
    ({'start_date': '2024-02-30'}, 'start_date'),
    ({'end_date': 'yesterday'}, 'end_date'),
    ({'quality_flag': 'MEDIUM'}, 'quality_flag'),
    ({'start_date': '2024-05-15', 'end_date': '2024-05-01'}, 'after'),
])
def test_bad_filters_are_400_with_a_message(client, params, word):
    r = client.get('/noaa/events', params=params)
    assert r.status_code == 400 and word in r.json()['detail']


def test_sciquality_has_no_quality_flag(client):
    r = client.get('/sciquality/events', params={'quality_flag': 'HIGH'})
    assert r.status_code == 400 and 'SciQuality' in r.json()['detail']


def test_by_id_and_404(client):
    assert client.get('/noaa/events/noaa_20240514_3040').json()['location'] == 'N19E72'
    assert client.get('/sciquality/events/sq_201702090145').json()['location'] == 'N10E24'
    assert client.get('/sciquality/events/nope').status_code == 404


def test_download_returns_every_match_as_a_file(client):
    r = client.get('/noaa/events/download', params={'goes_class': 'X'})
    assert 'attachment' in r.headers['content-disposition'] and len(r.json()) == 2


def test_stats(client):
    s = client.get('/noaa/stats').json()
    assert s['total_events'] == 7 and s['with_location'] == 1
    assert s['flags'] == {'HIGH': 1, 'LOW': 1, 'N/A': 5}  # M4.5 vs M4.4 at 17:25 is LOW
    assert client.get('/sciquality/stats').json()['flags'] is None


def test_missing_data_file_gives_empty_source_not_a_crash(monkeypatch, tmp_path):
    import api_sources
    source = api_sources.Source('noaa', str(tmp_path / 'absent.json'), api_sources.NOAA_FIELDS)
    assert source.all() == []


def test_closest_solar_image_is_fetched_by_the_api(client, monkeypatch):
    import httpx
    calls = []

    class Reply:
        status_code = 200
        def json(self):
            return {'id': '192675571', 'date': '2026-10-03 16:50:01', 'name': 'HMI Mag'}

    monkeypatch.setattr(httpx, 'get', lambda url, **kw: calls.append((url, kw.get('params'))) or Reply())
    r = client.get('/solar-image/closest', params={'date': '2026-10-03T16:50:00Z', 'source_id': 19})
    assert r.status_code == 200 and r.json()['date'] == '2026-10-03 16:50:01'
    assert calls[0][0].endswith('/getClosestImage/') and calls[0][1] == {'date': '2026-10-03T16:50:00Z', 'sourceId': 19}


def test_closest_solar_image_rejects_bad_input(client):
    assert client.get('/solar-image/closest', params={'date': 'yesterday', 'source_id': 19}).status_code == 400
    assert client.get('/solar-image/closest', params={'date': '2026-10-03T16:50:00Z', 'source_id': 999}).status_code == 400
