# Turns the NCEI science-quality GOES flare report (CSV) into data/sciquality_events.json.
#
# Every row is kept. Empty fields become None and show as N/A in the dashboard. Flux is stored as
# published: before 2019-12-09 SWPC (and so LMSAL) scaled GOES fluxes by 0.7 and this report did
# not, and the dashboard shows that difference rather than hiding it.

import csv
import json
import os

from noaa_matcher import DATA_DIR
from sciquality_downloader import current_file

SCIQUALITY_EVENTS_PATH = os.path.join(DATA_DIR, 'sciquality_events.json')


def format_location(lat, lon):
    """Heliographic latitude/longitude in degrees (west positive) -> 'N10E24'."""
    return f"{'N' if lat >= 0 else 'S'}{abs(round(lat)):02d}{'W' if lon >= 0 else 'E'}{abs(round(lon)):02d}"


def _text(value):
    value = (value or '').strip()
    return value or None


def _number(value):
    value = _text(value)
    return float(value) if value is not None else None


def _location(row):
    # the X-ray-derived position (2017 on) is independent of SWPC; fall back to SWPC's optical one
    for source, prefix in (('XRS', 'flare_loc_xrs_hgs_'), ('SWPC', 'flare_loc_swpc_hgs_')):
        lat, lon = _number(row.get(prefix + 'lat')), _number(row.get(prefix + 'lon'))
        if lat is not None and lon is not None:
            return format_location(lat, lon), source
    return None, None


def load_sciquality(csv_path):
    flares = []
    seen = {}
    with open(csv_path, newline='') as f:
        for row in csv.DictReader(f):
            flare_id = _text(row.get('flare_id')) or 'unknown'
            seen[flare_id] = seen.get(flare_id, 0) + 1
            region = _text(row.get('active_region'))
            location, location_source = _location(row)
            flares.append({
                'event_id': f'sq_{flare_id}' + (f'_{seen[flare_id]}' if seen[flare_id] > 1 else ''),
                'start': _text(row.get('start_time')),
                'peak': _text(row.get('time')),
                'end': _text(row.get('end_time')),
                'goes_class': _text(row.get('flare_class')),
                'peak_flux': _number(row.get('xrsb_irrad')),
                'background_flux': _number(row.get('background_irrad')),
                'satellite': _text(row.get('xrsb_irrad_source')),
                'active_region': int(region) % 10000 if region and region.isdigit() and int(region) % 10000 else None,
                'location': location,
                'location_source': location_source,
            })
    return flares


if __name__ == '__main__':
    flares = load_sciquality(current_file())
    with open(SCIQUALITY_EVENTS_PATH + '.tmp', 'w') as f:
        json.dump(flares, f, indent=2)
    os.replace(SCIQUALITY_EVENTS_PATH + '.tmp', SCIQUALITY_EVENTS_PATH)
    print(f"wrote {len(flares)} SciQuality flares, {sum(1 for r in flares if r['location'])} with a location")
