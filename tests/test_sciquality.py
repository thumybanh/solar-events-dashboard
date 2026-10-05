from conftest import FIXTURES
from sciquality_downloader import is_acceptable, pick_newest
from sciquality_events import format_location, load_sciquality

FIXTURE = FIXTURES / 'sciquality.csv'


def test_pick_newest_by_end_date():
    html = ('<a href="sci_xrsf-l2-flrpt_geo_s19950103_e20260929_v1-0-1.csv">a</a>'
            '<a href="sci_xrsf-l2-flrpt_geo_s19950103_e20261004_v1-0-1.csv">b</a>'
            '<a href="sci_xrsf-l2-flrpt_geo_s19950103_e20260101_v1-0-1.csv">c</a>')
    assert pick_newest(html) == 'sci_xrsf-l2-flrpt_geo_s19950103_e20261004_v1-0-1.csv'
    assert pick_newest('<html>nothing here</html>') is None


def test_is_acceptable_needs_same_header_and_no_fewer_rows(tmp_path):
    lines = FIXTURE.read_text().splitlines()
    smaller = tmp_path / 'smaller.csv'
    smaller.write_text('\n'.join(lines[:-1]) + '\n')
    wrong_header = tmp_path / 'wrong.csv'
    wrong_header.write_text('a,b,c\n' + '\n'.join(lines[1:]) + '\n')
    assert is_acceptable(str(FIXTURE), str(smaller))
    assert not is_acceptable(str(smaller), str(FIXTURE))
    assert not is_acceptable(str(wrong_header), str(FIXTURE))
    assert is_acceptable(str(FIXTURE), None)  # nothing to compare against yet


def test_format_location():
    assert format_location(10.4, -24.4) == 'N10E24'
    assert format_location(-12.0, 6.0) == 'S12W06'


def test_rows():
    rows = {r['event_id']: r for r in load_sciquality(str(FIXTURE))}
    xrs = rows['sq_201702090145']
    assert (xrs['start'], xrs['peak'], xrs['end']) == ('2017-02-09 01:45:00', '2017-02-09 01:51:00', '2017-02-09 01:55:00')
    assert (xrs['goes_class'], xrs['peak_flux'], xrs['satellite']) == ('C1.6', 1.695e-06, 'GOES-16')
    assert (xrs['location'], xrs['location_source']) == ('N10E24', 'XRS')
    assert rows['sq_199501311915']['location'] == 'S14E63'
    assert rows['sq_199501311915']['location_source'] == 'SWPC'
    assert rows['sq_199501242229']['end'] is None
    nothing = rows['sq_199501030004']
    assert nothing['location'] is None and nothing['location_source'] is None and nothing['active_region'] is None


def test_repeated_flare_id_gets_suffix(tmp_path):
    lines = FIXTURE.read_text().splitlines()
    doubled = tmp_path / 'doubled.csv'
    doubled.write_text('\n'.join(lines + [lines[1]]) + '\n')
    ids = [r['event_id'] for r in load_sciquality(str(doubled))]
    assert ids.count('sq_199501030004') == 1 and 'sq_199501030004_2' in ids
