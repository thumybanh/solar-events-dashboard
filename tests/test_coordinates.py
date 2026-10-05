import json

import pytest

from coordinates import add_pixels, location_to_pix


def test_lmsal_position_matches_existing_pixels():
    # gev_20260926_2104 in events.json, computed by the original module-level code
    assert location_to_pix('N09W89( 4534 )') == (pytest.approx(453.4482356051685), pytest.approx(224.72262357775287))


def test_plain_location_like_noaa_and_sciquality():
    assert location_to_pix('N09W89') == location_to_pix('N09W89( 4534 )')


def test_missing_or_bad_location_gives_no_pixels():
    assert location_to_pix(None) == (None, None)
    assert location_to_pix('') == (None, None)
    assert location_to_pix('1-8A') == (None, None)


def test_add_pixels_writes_every_row(tmp_path):
    path = tmp_path / 'flares.json'
    path.write_text(json.dumps([{'location': 'N09W89'}, {'location': None}]))
    assert add_pixels(str(path), 'location') == 1
    rows = json.loads(path.read_text())
    assert rows[0]['pix_x'] == pytest.approx(453.4482356051685)
    assert rows[1]['pix_x'] is None and rows[1]['pix_y'] is None
