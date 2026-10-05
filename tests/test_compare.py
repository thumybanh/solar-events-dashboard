import json

import pytest

from api_sources import LMSAL_FIELDS, NOAA_FIELDS, SCIQUALITY_FIELDS, FilterError, Source, compare, parse_filters
from test_api import client  # noqa: F401  (the API fixture, for the endpoint tests)


def lmsal(id, start, cls, peak):
    return {'event_id': id, 'event_start': start, 'event_peak': peak, 'event_GOES': cls}


def noaa(id, date, begin, cls, peak=None):
    return {'event_id': id, 'date': date, 'begin': begin, 'peak': peak, 'goes_class': cls}


def sq(id, start, peak, cls, flux):
    return {'event_id': id, 'start': start, 'peak': peak, 'goes_class': cls, 'peak_flux': flux}


@pytest.fixture
def sources(tmp_path):
    data = {
        'lmsal': (LMSAL_FIELDS, [
            lmsal('l1', '2003/01/10 10:00:00', 'M1.0', '10:05:00'),
            lmsal('l2', '2024/05/14 23:58:00', 'X1.0', '00:03:00'),  # peak runs past midnight
            lmsal('l3', '2024/05/20 08:00:00', 'C2.0', '08:04:00'),
        ]),
        'noaa': (NOAA_FIELDS, [
            noaa('n1', '1996-08-01', '1996-08-01 01:00:00', 'B1.0'),
            noaa('n2', '2024-05-14', '2024-05-14 23:58:00', 'X1.0', '2024-05-15 00:03:00'),
            noaa('n3', '2024-05-20', None, 'C1.0'),  # no begin time: counted on its date, no point
        ]),
        'sciquality': (SCIQUALITY_FIELDS, [
            sq('s1', '2024-05-14 23:58:00', '2024-05-15 00:03:00', 'X1.4', 1.43e-4),
        ]),
    }
    built = {}
    for name, (fields, rows) in data.items():
        path = tmp_path / f'{name}.json'
        path.write_text(json.dumps(rows))
        built[name] = Source(name, str(path), fields)
    return built


def run(sources, names, **query):
    return compare(sources, names, parse_filters(**query))


def test_short_range_gives_individual_flares_at_peak_time(sources):
    out = run(sources, ['lmsal', 'noaa', 'sciquality'], start_date='2024-05-01', end_date='2024-05-31')
    assert out['mode'] == 'flares'
    assert out['series']['LMSAL'][0] == {'id': 'l2', 'time': '2024-05-15 00:03:00', 'goes_class': 'X1.0', 'flux': pytest.approx(1e-4)}
    assert out['series']['SciQuality'][0]['flux'] == 1.43e-4  # as published, not rescaled
    assert [p['id'] for p in out['series']['NOAA']] == ['n2']  # n3 has no time to plot
    assert out['totals'] == {'LMSAL': 2, 'NOAA': 2, 'SciQuality': 1}


def test_31_days_is_still_flares_32_is_counts(sources):
    assert run(sources, ['lmsal'], start_date='2024-05-01', end_date='2024-05-31')['mode'] == 'flares'
    out = run(sources, ['lmsal'], start_date='2024-05-01', end_date='2024-06-01')
    assert (out['mode'], out['bin']) == ('counts', 'day')


def test_bins_by_range_length(sources):
    assert run(sources, ['noaa'], start_date='2024-01-01', end_date='2024-12-31')['bin'] == 'day'
    assert run(sources, ['noaa'], start_date='2016-01-01', end_date='2024-12-31')['bin'] == 'month'
    assert run(sources, ['noaa'], start_date='1996-01-01', end_date='2024-12-31')['bin'] == 'year'


def test_every_bin_present_with_zeros(sources):
    out = run(sources, ['lmsal', 'noaa'], start_date='1996-01-01', end_date='2024-12-31')
    years = [b for b, _ in out['series']['LMSAL']]
    assert years == [str(y) for y in range(1996, 2025)]
    assert dict(out['series']['LMSAL'])['1996'] == 0 and dict(out['series']['LMSAL'])['2024'] == 2
    assert dict(out['series']['NOAA'])['2024'] == 2  # the flare without a begin time still counts
    assert out['totals'] == {name: sum(n for _, n in s) for name, s in out['series'].items()}


def test_no_range_uses_the_span_of_the_selected_sources(sources):
    out = run(sources, ['lmsal'])
    assert (out['start'], out['end']) == ('2003-01-10', '2024-05-20')


def test_filters_apply_before_counting(sources):
    out = run(sources, ['lmsal', 'noaa'], start_date='1996-01-01', end_date='2024-12-31', goes_class='X')
    assert out['totals'] == {'LMSAL': 1, 'NOAA': 1}


def test_notes_explain_coverage_and_scaling(sources):
    notes = ' '.join(run(sources, ['lmsal', 'sciquality'], start_date='2010-01-01', end_date='2024-12-31')['notes'])
    assert '2003-01-10' in notes and '0.7' in notes


def test_unknown_or_no_source_is_an_error(sources):
    with pytest.raises(FilterError, match='sources'):
        run(sources, [])
    with pytest.raises(FilterError, match='goes'):
        run(sources, ['lmsal', 'goes'])


def test_compare_endpoint(client):  # noqa: F811
    r = client.get('/compare', params={'sources': 'lmsal,noaa', 'start_date': '2024-05-14', 'end_date': '2024-05-14'})
    assert r.status_code == 200 and r.json()['mode'] == 'flares'
    assert client.get('/compare', params={'sources': ''}).status_code == 400
    r = client.get('/compare', params={'sources': 'lmsal', 'goes_class': 'Z'})
    assert r.status_code == 400 and 'goes_class' in r.json()['detail']


def test_flux_from_class_has_no_float_noise():
    from api_sources import class_to_flux
    assert repr(class_to_flux('C5.8')) == '5.8e-06'
    assert repr(class_to_flux('C1.23')) == '1.23e-06'
