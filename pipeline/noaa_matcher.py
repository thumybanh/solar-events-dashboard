# Flags LMSAL events and NOAA flares HIGH / LOW / N/A against each other (see match()).
# Only NOAA XRA (X-ray flare) lines take part; noaa_events.py parses them.

import json
import os

# absolute paths so this works from any working directory (cron and CI runners)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')
EVENTS_PATH = os.path.join(DATA_DIR, 'events.json')
NOAA_DIR = os.path.join(DATA_DIR, 'noaa_data')

# An LMSAL event matches a NOAA event when they share a date and GOES class and their begin times
# fall within this many minutes.
#
# The window exists to tolerate small timestamp disagreements between the two catalogues, so the same
# flare is not flagged LOW over a difference of a minute or two.
#
# SET TO 3 ON 2026-09-14. Any value in 1-4 is defensible and the choice is nearly immaterial (HIGH
# spans 61.8% to 62.2% across that range). 3 is the largest lag whose excess over chance stays
# significant (z >= 3) under every background estimate tested (z 4.8-8.0 at lag 3, 2.1-4.6 at lag 4).
# Lags 5-10 are indistinguishable from chance, which is why the original +/-10 was not kept: a HIGH
# flag claims both catalogues saw the same flare, so a false HIGH costs more than a missed borderline
# match. The stricter ">50% real under every estimate" criterion below gives 2; 3 accepts lag 3,
# which is significant but only ~2/3 real at the median background.
#
# Why it cannot be narrowed: judging whether an admitted pair is real requires the chance-coincidence
# rate, and that rate is not a tight parameter. Per-lag counts over |lag| 10-60 run Q1 4.0,
# median 6.0, Q3 9.0 (mean 7.04, range 1-21) — wider than Poisson, because same-day flare clustering
# varies with activity level. The answer moves with the estimate:
#
#   background/pair    largest W with every admitted lag >50% real
#     8.0 (Q1)                    4
#    12.0 (median)                3
#    18.0 (Q3)                    2      <- 2 holds under all of them
#
# Non-monotonicity confirms the noise floor: lag 6 has 16 pairs against lag 5's 10. Real signal
# decays; that does not.
#
# Do not cite mean +/- k*sd here: ~99% of the mass is a single spike at lag 0, so sd is 0.07-0.15 min
# and any sensible k yields a 0-minute window. Note also that "marginal precision >50%" and "z >= 3"
# are not independent criteria — both are (observed - background) against the same estimate.
#
# See README and NOTES.md section 4b, including the earlier derivations that were wrong.
# Reproduce: window_optimization.py.
MATCH_WINDOW_MINUTES = 3

DAY = 1440  # minutes in a day, for end times that run past midnight

# Neither source dates its end time, so an end earlier than its own begin is ambiguous: either the
# flare ran past midnight, or the record is corrupt. NOAA publishes occasional garbled ends —
# e.g. "1330 1337 0655", where the flare supposedly ends 7 hours before it starts. A midnight
# crossing is only accepted if it implies a duration no longer than this.
MAX_FLARE_MINUTES = 360


def resolve_end(begin, end):
    """End time as minutes from the same origin as begin, or None if it cannot be trusted."""
    if begin is None or end is None:
        return None
    if end >= begin:
        return end if end - begin <= MAX_FLARE_MINUTES else None
    wrapped = end + DAY
    return wrapped if wrapped - begin <= MAX_FLARE_MINUTES else None

def parse_noaa_file(fileName):
        noaa_events = [] 
        with open(fileName, 'r') as r: 
            datas = r.readlines()
            for data in datas: 
                if data.startswith('#'):
                    continue
                splitData = data.split()
                if "XRA" in splitData: 
                    XRAindex = splitData.index('XRA')
                    dateFull = os.path.basename(fileName).split('events.')
                    date = dateFull[0]
                    begin = splitData[XRAindex - 5] if splitData[XRAindex - 5] != '////' else None
                    peak = splitData[XRAindex - 4] if splitData[XRAindex - 4] != '////' else None
                    end = splitData[XRAindex - 3] if splitData[XRAindex - 3] != '////' else None
                    goes_class = splitData[XRAindex + 2] if splitData[XRAindex + 2] != '////' else None

                    noaa_event = {
                        'date': date,
                        'begin': begin,
                        'peak': peak,
                        'end': end,
                        'goes_class': goes_class
                    }
                    noaa_events.append(noaa_event)
        return noaa_events


def to_minutes(timestamp):
    """'1423', '14:23:00' or '////' -> minutes since midnight, or None if unusable.

    Times used to be compared as raw HHMM integers, which overstates any gap that crosses an
    hour boundary: 13:01 and 12:59 are 2 minutes apart but 1301 - 1259 = 42.
    """
    digits = ''.join(filter(str.isdigit, timestamp or ''))
    if len(digits) < 4:
        return None
    hours, minutes = int(digits[:2]), int(digits[2:4])
    if hours > 23 or minutes > 59:
        return None
    return hours * 60 + minutes


def _clock(stamp):
    """'2024-05-14 10:02:00' -> minutes since midnight, or None."""
    return to_minutes(stamp[11:16]) if stamp else None


def _candidates(start, cls, others):
    """Flares in others starting within the window: (any found, closest same-class one or None)."""
    found, best = False, None  # best = (time_start_diff, other)
    if start is None or cls is None:
        return False, None
    for other_start, other_cls, other in others:
        if other_start is None:
            continue
        diff = abs(other_start - start)
        if diff > MATCH_WINDOW_MINUTES:
            continue
        found = True
        if other_cls == cls and (best is None or diff < best[0]):  # ties keep file order
            best = (diff, other)
    return found, best


def _flag(found, best):
    return 'HIGH' if best is not None else 'LOW' if found else 'N/A'


def _versions(event):
    """(id, start, stop) for every start time LMSAL gave this flare: its own first, then the duplicate
    entries merged into it (dedupe_lmsal.py), so merging never takes a match away from either side."""
    yield event['event_id'], event['event_start'], event['event_stop']
    for entry in event.get('merged_from') or []:
        yield entry['event_id'], entry['event_start'], entry['event_stop']


def match(lmsal_events, noaa_flares):
    """Flags both catalogues against each other, in place.

    HIGH: the other catalogue has a flare of the same class starting within MATCH_WINDOW_MINUTES
    (the closest such flare is recorded). LOW: it has a flare starting within the window, but of a
    different class. N/A: it has nothing starting within the window, or this flare's own begin time
    or class is missing, so there is nothing to compare.

    A merged LMSAL flare is compared using every start time it was listed with; matched_via names
    the entry whose start matched.
    """
    # same date is guaranteed by the lookup key, so only the time/class checks are left
    lmsal_by_date, noaa_by_date = {}, {}
    for event in lmsal_events:
        for _, start_text, _ in _versions(event):
            date, _, clock = start_text.partition(' ')
            lmsal_by_date.setdefault(date.replace('/', ''), []).append((to_minutes(clock), event['event_GOES'], event))
    for flare in noaa_flares:
        noaa_by_date.setdefault(flare['date'].replace('-', ''), []).append((_clock(flare['begin']), flare['goes_class'], flare))

    for event in lmsal_events:
        found, best, via = False, None, None  # via = (entry id, start minutes, stop) that matched
        for version_id, start_text, stop in _versions(event):
            date, _, clock = start_text.partition(' ')
            start = to_minutes(clock)
            version_found, version_best = _candidates(start, event['event_GOES'], noaa_by_date.get(date.replace('/', ''), []))
            found = found or version_found
            if version_best and (best is None or version_best[0] < best[0]):  # ties keep the own entry
                best, via = version_best, (version_id, start, stop)
        event['quality_flag'] = _flag(found, best)
        event['matched_noaa_id'] = best[1]['event_id'] if best else None
        event['matched_via'] = via[0] if best else None
        event['end_time_diff'] = None
        if best:
            # How well the two sources agree on where the flare ended. Recorded, not
            # used to decide the match: onset is an objective threshold crossing, while
            # the end depends on each pipeline's decay criteria, so end times scatter
            # ~45x wider than begin times. Gating on it would exclude exactly the
            # disagreements this dataset exists to measure.
            noaa_flare = best[1]
            n_end = resolve_end(_clock(noaa_flare['begin']), _clock(noaa_flare['end']))
            l_end = resolve_end(via[1], to_minutes(via[2]))  # the matched entry's own start and stop
            if n_end is not None and l_end is not None:
                event['end_time_diff'] = l_end - n_end

    for date, rows in noaa_by_date.items():
        for start, cls, flare in rows:
            found, best = _candidates(start, cls, lmsal_by_date.get(date, []))
            flare['quality_flag'] = _flag(found, best)
            flare['matched_lmsal_id'] = best[1]['event_id'] if best else None


def convert_position(LMSAL_position):

    lat_dir = LMSAL_position[0]
    lat_num = LMSAL_position[1:3]
    lon_dir = LMSAL_position[3]
    lon_num = LMSAL_position[4:6]

    lat = int(lat_num) if lat_dir == 'N' else -int(lat_num)
    lon = int(lon_num) if lon_dir == 'W' else -int(lon_num)

    return lat, lon


def _write(path, data):
    with open(path + '.tmp', 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(path + '.tmp', path)


if __name__ == '__main__':
    from noaa_events import NOAA_EVENTS_PATH, load_noaa_events  # imports this module, so not at the top

    with open(EVENTS_PATH) as f:
        lmsal_events = json.load(f)
    noaa_flares = load_noaa_events()
    match(lmsal_events, noaa_flares)
    _write(EVENTS_PATH, lmsal_events)
    _write(NOAA_EVENTS_PATH, noaa_flares)

    for name, rows in (('LMSAL', lmsal_events), ('NOAA', noaa_flares)):
        counts = {f: sum(1 for r in rows if r['quality_flag'] == f) for f in ('HIGH', 'LOW', 'N/A')}
        print(f"{name}: {len(rows)} flares, {counts}")
