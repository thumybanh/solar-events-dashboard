# Parses every NOAA X-ray flare (XRA line) out of the SWPC daily event reports into one record each.
#
# Nothing that is an XRA line is skipped: a field NOAA left blank ('////') or wrote in a form we
# can't read is stored as None, so the flare still shows up and the missing part shows as N/A.
# Location isn't on the XRA line at all. When an observatory also saw the flare in H-alpha, NOAA
# logs an FLA line under the same event number, and that line carries the position (e.g. N19E72).

import json
import os
import re
from datetime import datetime, timedelta

from noaa_matcher import DATA_DIR, NOAA_DIR, resolve_end

NOAA_EVENTS_PATH = os.path.join(DATA_DIR, 'noaa_events.json')

CLASS_RE = re.compile(r'([ABCMX])(\d+(?:[.,]\d+)?)?')
LOCATION_RE = re.compile(r'[NS]\d{2}[EW]\d{2}')


def normalize_class(text):
    """'X1' -> 'X1.0', 'C6,2' -> 'C6.2', 'C1.23' kept; None if it isn't a GOES class."""
    match = CLASS_RE.fullmatch((text or '').strip().upper())
    if not match:
        return None
    letter, number = match.groups()
    if number is None:
        return letter  # NOAA wrote a few 1999 flares as a bare 'C'
    number = number.replace(',', '.')
    decimals = max(len(number.partition('.')[2]), 1)
    return f'{letter}{float(number):.{decimals}f}'


def _minutes(field):
    # NOAA prefixes uncertain times with a letter (B = before, A = after, U = uncertain): keep the time
    match = re.fullmatch(r'[A-Z]?(\d{2})(\d{2})', field or '')
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def _stamp(day, minutes):
    return None if minutes is None else (day + timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:00')


def parse_noaa_file(path):
    day = datetime.strptime(os.path.basename(path)[:8], '%Y%m%d')
    with open(path, errors='ignore') as f:
        lines = [line for line in f if not line.startswith((':', '#'))]

    # event number -> position, from the H-alpha reports of the same event
    locations = {}
    for line in lines:
        tokens = line.replace('+', ' ').split()
        if 'FLA' in tokens:
            j = tokens.index('FLA')
            if j + 1 < len(tokens) and LOCATION_RE.fullmatch(tokens[j + 1]):
                locations.setdefault(tokens[0], tokens[j + 1])

    flares = []
    seen = {}
    for line in lines:
        tokens = line.replace('+', ' ').split()
        if 'XRA' not in tokens:
            continue
        i = tokens.index('XRA')
        number = tokens[0]
        field = lambda k: tokens[k] if 0 <= k < len(tokens) else None

        begin, peak, end = (_minutes(field(k)) for k in (i - 5, i - 4, i - 3))
        # neither time is dated, so a peak or end earlier than the begin ran past midnight
        if begin is not None and peak is not None and peak < begin:
            peak += 1440
        if begin is not None and end is not None:
            end = resolve_end(begin, end)  # None when the implied duration is implausible

        region = field(i + 4)
        seen[number] = seen.get(number, 0) + 1
        event_id = f"noaa_{day:%Y%m%d}_{number}" + (f"_{seen[number]}" if seen[number] > 1 else '')
        flares.append({
            'event_id': event_id,
            'date': day.strftime('%Y-%m-%d'),
            'begin': _stamp(day, begin),
            'peak': _stamp(day, peak),
            'end': _stamp(day, end),
            'goes_class': normalize_class(field(i + 2)),
            'observatory': field(i - 2),
            'active_region': int(region) % 10000 if region and region.isdigit() and int(region) % 10000 else None,
            'location': locations.get(number),
        })
    return flares


def load_noaa_events(noaa_dir=NOAA_DIR):
    flares = []
    for name in sorted(os.listdir(noaa_dir)):
        if re.fullmatch(r'\d{8}events\.txt', name):
            flares.extend(parse_noaa_file(os.path.join(noaa_dir, name)))
    return flares


if __name__ == '__main__':
    flares = load_noaa_events()
    with open(NOAA_EVENTS_PATH + '.tmp', 'w') as f:
        json.dump(flares, f, indent=2)
    os.replace(NOAA_EVENTS_PATH + '.tmp', NOAA_EVENTS_PATH)
    print(f"wrote {len(flares)} NOAA flares, {sum(1 for r in flares if r['location'])} with a location")
