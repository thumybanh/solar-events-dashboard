"""The three flare catalogues the API serves, behind one Source class.

Each source is a JSON file the daily pipeline writes (see pipeline/). The records keep their own
field names, so a small field map tells Source where each one keeps its time, class, region and flag.
"""

import json
import os
import re
from datetime import datetime, timedelta

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


def _lmsal_peak(e):
    # event_peak is a bare clock time; a peak earlier than the start ran past midnight
    start = datetime.strptime(e['event_start'], '%Y/%m/%d %H:%M:%S')
    try:
        clock = datetime.strptime(e.get('event_peak') or '', '%H:%M:%S')
    except ValueError:
        return start.strftime('%Y-%m-%d %H:%M:%S')
    peak = start.replace(hour=clock.hour, minute=clock.minute, second=clock.second)
    if peak < start:
        peak += timedelta(days=1)
    return peak.strftime('%Y-%m-%d %H:%M:%S')


LMSAL_FIELDS = {
    'label': 'LMSAL',
    'peak': _lmsal_peak,
    'flux': lambda e: class_to_flux(e.get('event_GOES')),
    'time': _lmsal_time,
    'goes_class': lambda e: e.get('event_GOES'),
    'region': _lmsal_region,
    'flag': lambda e: e.get('quality_flag'),
    'has_location': lambda e: e.get('pix_x') is not None,
}
NOAA_FIELDS = {
    'label': 'NOAA',
    'peak': lambda e: e.get('peak') or e.get('begin'),
    'flux': lambda e: class_to_flux(e.get('goes_class')),
    # a flare NOAA left without a begin time is still on its report's date
    'time': lambda e: e.get('begin') or e['date'],
    'goes_class': lambda e: e.get('goes_class'),
    'region': lambda e: e.get('active_region'),
    'flag': lambda e: e.get('quality_flag'),
    'has_location': lambda e: e.get('location') is not None,
}
SCIQUALITY_FIELDS = {
    'label': 'SciQuality',
    'peak': lambda e: e.get('peak') or e.get('start'),
    'flux': lambda e: e.get('peak_flux'),  # as published: no 0.7 scaling before 2019-12-09
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
    # 10 significant digits drop the float noise (5.8 * 1e-6 = 5.7999999999999995e-06)
    return float(f"{parsed[1] * {'A': 1e-8, 'B': 1e-7, 'C': 1e-6, 'M': 1e-5, 'X': 1e-4}[parsed[0]]:.10g}")


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
        # an ID that was merged into another flare as a duplicate still finds that flare
        return next((r for r in self.all() if r['event_id'] == event_id
                     or any(m['event_id'] == event_id for m in r.get('merged_from') or [])), None)

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


FLARES_MAX_DAYS = 31     # up to a month, plot each flare; longer ranges are counted per bin
DAY_BINS_MAX_DAYS = 366
MONTH_BINS_MAX_DAYS = 3660
SCALING_CHANGE = '2019-12-09'


def _bins(start, end, size):
    """Every bin label from start to end (dates 'YYYY-MM-DD'), zeros included."""
    first, last = datetime.strptime(start, '%Y-%m-%d'), datetime.strptime(end, '%Y-%m-%d')
    if size == 'day':
        return [(first + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((last - first).days + 1)]
    if size == 'month':
        months = (last.year - first.year) * 12 + last.month - first.month
        return [f"{first.year + (first.month - 1 + i) // 12}-{(first.month - 1 + i) % 12 + 1:02d}" for i in range(months + 1)]
    return [str(y) for y in range(first.year, last.year + 1)]


def compare(sources, names, filters):
    """Chart data for the selected sources: individual flares for short ranges, counts per bin otherwise."""
    if not names:
        raise FilterError("sources must name at least one of lmsal, noaa, sciquality")
    unknown = [n for n in names if n not in sources]
    if unknown:
        raise FilterError(f"sources must be lmsal, noaa or sciquality, got {', '.join(unknown)}")

    chosen = [sources[n] for n in names]
    dated = {s.label: [r for r in s.filter(filters) if s.time(r)] for s in chosen}

    start = filters.get('start', '')[:10]
    end = filters.get('end', '')[:10]
    if not start or not end:
        days = [s.time(r)[:10] for s in chosen for r in dated[s.label]]
        start = start or (min(days) if days else '')
        end = end or (max(days) if days else '')

    # first and last date each catalogue has anything, so the chart shows "no data" instead of zero
    # before a catalogue starts and after its latest update
    spans = {s.label: s.stats() for s in chosen}
    coverage = {label: st['first_event'] for label, st in spans.items()}
    coverage_end = {label: st['last_event'] for label, st in spans.items()}
    notes = []
    if any(coverage.values()):
        notes.append('Coverage: ' + ', '.join(f'{label} from {first}' for label, first in coverage.items() if first) + '.')
    result = {'start': start or None, 'end': end or None, 'notes': notes, 'coverage': coverage, 'coverage_end': coverage_end,
              'totals': {label: len(rows) for label, rows in dated.items()}}
    if not start or not end:  # nothing matched, so there is no span to derive a missing end from
        return {**result, 'mode': 'counts', 'bin': 'year', 'series': {label: [] for label in dated}}

    span = (datetime.strptime(end, '%Y-%m-%d') - datetime.strptime(start, '%Y-%m-%d')).days + 1
    # the 0.7 scaling only shows where flux is plotted or a class filter sorts flares by class
    if 'sciquality' in names and start < SCALING_CHANGE and (span <= FLARES_MAX_DAYS or 'goes_class' in filters):
        result['notes'].append('Before 2019-12-09, LMSAL and NOAA fluxes and classes follow the SWPC convention of '
                               'scaling GOES fluxes by 0.7; SciQuality is unscaled, so the same flare reads about 1.4x '
                               'higher (and can fall in a higher class) in SciQuality. Values are shown as published.')
    if span <= FLARES_MAX_DAYS:
        series = {}
        for s in chosen:
            points = []
            for r in dated[s.label]:
                time = s.fields['peak'](r)
                if time:
                    points.append({'id': r['event_id'], 'time': time, 'goes_class': s.fields['goes_class'](r),
                                   'flux': s.fields['flux'](r)})
            series[s.label] = sorted(points, key=lambda p: p['time'])
        return {**result, 'mode': 'flares', 'series': series}

    size = 'day' if span <= DAY_BINS_MAX_DAYS else 'month' if span <= MONTH_BINS_MAX_DAYS else 'year'
    width = {'day': 10, 'month': 7, 'year': 4}[size]
    labels = _bins(start, end, size)
    series = {}
    for s in chosen:
        counts = dict.fromkeys(labels, 0)
        for r in dated[s.label]:
            key = s.time(r)[:width]
            if key in counts:
                counts[key] += 1
        series[s.label] = list(counts.items())
    return {**result, 'mode': 'counts', 'bin': size, 'series': series}


SOURCES = {
    'lmsal': Source('lmsal', os.environ.get('LMSAL_EVENTS_PATH', os.path.join(DATA_DIR, 'events.json')), LMSAL_FIELDS),
    'noaa': Source('noaa', os.environ.get('NOAA_EVENTS_PATH', os.path.join(DATA_DIR, 'noaa_events.json')), NOAA_FIELDS),
    'sciquality': Source('sciquality', os.environ.get('SCIQUALITY_EVENTS_PATH', os.path.join(DATA_DIR, 'sciquality_events.json')), SCIQUALITY_FIELDS),
}
