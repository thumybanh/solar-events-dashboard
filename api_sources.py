"""The three flare catalogues the API serves, behind one Source class.

Each source is a JSON file the daily pipeline writes (see pipeline/). The records keep their own
field names, so a small field map tells Source where each one keeps its time, class, region and flag.
"""

import json
import os
import re
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_DIR, 'data')

FLAGS = ('HIGH', 'LOW', 'N/A')
CLASS_RE = re.compile(r'([ABCMX])(\d+(?:\.\d+)?)?')
DATE_RE = re.compile(r'(\d{4})[-/](\d{2})[-/](\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?')


class FilterError(ValueError):
    """A filter value the API can't use. The message says what was expected."""


def _lmsal_time(e):
    return e['event_start'].replace('/', '-')


def _lmsal_region(e):
    match = re.search(r'\(\s*(\d+)\s*\)', e.get('event_position') or '')
    return int(match.group(1)) % 10000 if match else None


LMSAL_FIELDS = {
    'label': 'LMSAL',
    'time': _lmsal_time,
    'goes_class': lambda e: e.get('event_GOES'),
    'region': _lmsal_region,
    'flag': lambda e: e.get('quality_flag'),
    'has_location': lambda e: e.get('pix_x') is not None,
}
NOAA_FIELDS = {
    'label': 'NOAA',
    # a flare NOAA left without a begin time is still on its report's date
    'time': lambda e: e.get('begin') or e['date'],
    'goes_class': lambda e: e.get('goes_class'),
    'region': lambda e: e.get('active_region'),
    'flag': lambda e: e.get('quality_flag'),
    'has_location': lambda e: e.get('location') is not None,
}
SCIQUALITY_FIELDS = {
    'label': 'SciQuality',
    'time': lambda e: e.get('start') or e.get('peak'),
    'goes_class': lambda e: e.get('goes_class'),
    'region': lambda e: e.get('active_region'),
    'flag': None,  # not matched against the other catalogues (yet)
    'has_location': lambda e: e.get('location') is not None,
}


def parse_class(text):
    """'X1.7' -> ('X', 1.7); 'C' -> ('C', None); anything else -> None."""
    match = CLASS_RE.fullmatch((text or '').strip().upper())
    if not match:
        return None
    letter, number = match.groups()
    return letter, float(number) if number else None


def class_to_flux(text):
    """GOES class -> peak 1-8 Å flux in W/m² (X1.0 = 1e-4), or None."""
    parsed = parse_class(text)
    if not parsed or parsed[1] is None:
        return None
    return parsed[1] * {'A': 1e-8, 'B': 1e-7, 'C': 1e-6, 'M': 1e-5, 'X': 1e-4}[parsed[0]]


def _date_bound(value, name, end):
    match = DATE_RE.fullmatch(value.strip())
    if not match:
        raise FilterError(f"{name} must be a date like 2024-05-14 (optionally with a time, 2024-05-14 10:30), got {value!r}")
    y, mo, d, h, mi, s = match.groups()
    try:
        moment = datetime(int(y), int(mo), int(d), int(h or 0), int(mi or 0), int(s or 0))
    except ValueError:
        raise FilterError(f"{name} {value!r} is not a real date") from None
    if h is None and end:  # a bare end date includes that whole day
        moment = moment.replace(hour=23, minute=59, second=59)
    return moment.strftime('%Y-%m-%d %H:%M:%S')


def parse_filters(start_date=None, end_date=None, goes_class=None, active_region=None, quality_flag=None):
    """Validates the query filters once; raises FilterError with a readable message."""
    filters = {}
    if start_date:
        filters['start'] = _date_bound(start_date, 'start_date', end=False)
    if end_date:
        filters['end'] = _date_bound(end_date, 'end_date', end=True)
    if 'start' in filters and 'end' in filters and filters['start'] > filters['end']:
        raise FilterError(f"start_date {start_date!r} is after end_date {end_date!r}")
    if goes_class:
        match = CLASS_RE.fullmatch(goes_class.strip().upper().replace(',', '.'))
        if not match:
            raise FilterError(f"goes_class must look like X, X1 or X1.5, got {goes_class!r}")
        filters['goes_class'] = match.groups()
    if active_region:
        match = re.fullmatch(r'(?:AR\s*)?(\d+)', str(active_region).strip().upper())
        if not match or int(match.group(1)) % 10000 == 0:
            raise FilterError(f"active_region must be a region number like 13664, 3664 or AR3664, got {active_region!r}")
        filters['region'] = int(match.group(1)) % 10000
    if quality_flag:
        flag = quality_flag.strip().upper()
        flag = 'N/A' if flag in ('NA', 'N/A') else flag
        if flag not in FLAGS:
            raise FilterError(f"quality_flag must be HIGH, LOW or N/A, got {quality_flag!r}")
        filters['flag'] = flag
    return filters


def _class_matches(text, wanted):
    letter, number = wanted
    parsed = parse_class(text)
    if not parsed or parsed[0] != letter:
        return False
    if number is None:
        return True
    if parsed[1] is None:
        return False
    if '.' not in number:  # 'X1' is the bin X1.0 to X1.9, not X10 and up
        return int(number) <= parsed[1] < int(number) + 1
    decimals = len(number.partition('.')[2])
    return round(parsed[1], decimals) == round(float(number), decimals)


class Source:
    def __init__(self, name, path, fields):
        self.name = name
        self.path = path
        self.fields = fields
        self._mtime = None
        self._rows = []

    @property
    def label(self):
        return self.fields['label']

    @property
    def has_flag(self):
        return self.fields['flag'] is not None

    def all(self):
        """Every record, newest first. Re-read only when the file changes; [] if it doesn't exist yet."""
        if not os.path.exists(self.path):
            return []
        mtime = os.path.getmtime(self.path)
        if mtime != self._mtime:
            with open(self.path) as f:
                rows = json.load(f)
            # sorted once here rather than per request; times are ISO-like, so text order is time order
            self._rows = sorted(rows, key=self.time, reverse=True)
            self._mtime = mtime
        return self._rows

    def time(self, row):
        return self.fields['time'](row) or ''

    def updated(self):
        return os.path.getmtime(self.path) if os.path.exists(self.path) else None

    def filter(self, filters):
        if 'flag' in filters and not self.has_flag:
            raise FilterError(f"{self.label} flares have no quality_flag to filter on")
        f = self.fields
        rows = self.all()
        if 'start' in filters:
            rows = [r for r in rows if f['time'](r) and f['time'](r) >= filters['start'][:len(f['time'](r))]]
        if 'end' in filters:
            rows = [r for r in rows if f['time'](r) and f['time'](r) <= filters['end']]
        if 'goes_class' in filters:
            rows = [r for r in rows if _class_matches(f['goes_class'](r), filters['goes_class'])]
        if 'region' in filters:
            rows = [r for r in rows if f['region'](r) == filters['region']]
        if 'flag' in filters:
            rows = [r for r in rows if f['flag'](r) == filters['flag']]
        return rows

    def find(self, event_id):
        return next((r for r in self.all() if r['event_id'] == event_id), None)

    def stats(self):
        rows = self.all()
        times = sorted(self.time(r)[:10] for r in rows if self.time(r))
        return {
            'total_events': len(rows),
            'first_event': times[0] if times else None,
            'last_event': times[-1] if times else None,
            'flags': {flag: sum(1 for r in rows if self.fields['flag'](r) == flag) for flag in FLAGS} if self.has_flag else None,
            'with_location': sum(1 for r in rows if self.fields['has_location'](r)),
        }


SOURCES = {
    'lmsal': Source('lmsal', os.environ.get('LMSAL_EVENTS_PATH', os.path.join(DATA_DIR, 'events.json')), LMSAL_FIELDS),
    'noaa': Source('noaa', os.environ.get('NOAA_EVENTS_PATH', os.path.join(DATA_DIR, 'noaa_events.json')), NOAA_FIELDS),
    'sciquality': Source('sciquality', os.environ.get('SCIQUALITY_EVENTS_PATH', os.path.join(DATA_DIR, 'sciquality_events.json')), SCIQUALITY_FIELDS),
}
