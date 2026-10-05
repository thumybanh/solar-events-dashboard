from conftest import FIXTURES
from noaa_events import normalize_class, parse_noaa_file

ROWS = {r['event_id']: r for r in parse_noaa_file(str(FIXTURES / 'noaa' / '20240514events.txt'))}


def test_one_record_per_xra_line_nothing_skipped():
    assert len(ROWS) == 7


def test_fields_of_a_normal_flare():
    r = ROWS['noaa_20240514_2870']
    assert (r['date'], r['begin'], r['peak'], r['end']) == (
        '2024-05-14', '2024-05-14 02:03:00', '2024-05-14 02:09:00', '2024-05-14 02:19:00')
    assert (r['goes_class'], r['observatory'], r['active_region'], r['location']) == ('X1.7', 'G16', 3664, None)


def test_location_comes_from_fla_line_with_same_event_number():
    assert ROWS['noaa_20240514_3040']['location'] == 'N19E72'


def test_missing_fields_are_null_not_skipped():
    assert ROWS['noaa_20240514_3100']['begin'] is None
    assert ROWS['noaa_20240514_3100']['peak'] == '2024-05-14 19:00:00'
    assert ROWS['noaa_20240514_3110']['goes_class'] is None


def test_repeated_event_number_gets_suffix():
    assert ROWS['noaa_20240514_3110_2']['goes_class'] == 'C2.0'


def test_end_before_begin_rolls_to_next_day_and_region_is_4_digit():
    r = ROWS['noaa_20240514_3120']
    assert r['end'] == '2024-05-15 00:05:00'
    assert r['goes_class'] == 'X1.0'
    assert r['active_region'] == 3664


def test_qualifier_letter_dropped_and_comma_class():
    r = ROWS['noaa_20240514_3130']
    assert r['begin'] == '2024-05-14 23:40:00'
    assert r['goes_class'] == 'C6.2'


def test_normalize_class():
    assert [normalize_class(c) for c in ['X1', 'C6,2', 'M4.4', 'C1.23', '////', 'C', 'junk']] == [
        'X1.0', 'C6.2', 'M4.4', 'C1.23', None, 'C', None]
