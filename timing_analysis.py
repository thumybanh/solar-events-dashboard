"""Derive the LMSAL/NOAA matching window from the data instead of assuming +/-10.

For every NOAA XRA event we find its counterpart in LMSAL on the same date, record the signed
time difference in minutes, and describe that distribution. Read-only: nothing is written.
"""
import json
import os
import re
import statistics
import sys

sys.path.insert(0, '/Users/mybanh/Desktop/LMSAL')
from noaa_matcher import parse_noaa_file

EVENTS = '/Users/mybanh/Desktop/LMSAL/events.json'
NOAA_DIR = '/Users/mybanh/Desktop/LMSAL/noaa_data'

# noaa_data also holds duplicate copies named "...events 2.txt" / " 3" / " 4" whose dates
# parse to garbage. Only the canonical filenames are read here.
CANONICAL = re.compile(r'^(\d{8})events\.txt$')


def load_noaa_data():
    by_date = {}
    for fileName in os.listdir(NOAA_DIR):
        m = CANONICAL.match(fileName)
        if not m:
            continue
        for r in parse_noaa_file(os.path.join(NOAA_DIR, fileName)):
            by_date.setdefault(m.group(1), []).append(r)
    return by_date


def to_minutes(hhmm):
    """'0123' or '01:23:00' -> minutes since midnight, or None if unusable."""
    digits = ''.join(filter(str.isdigit, hhmm or ''))
    if len(digits) < 4:
        return None
    h, m = int(digits[:2]), int(digits[2:4])
    if h > 23 or m > 59:
        return None
    return h * 60 + m


def lmsal_by_date():
    with open(EVENTS) as f:
        events = json.load(f)
    by_date = {}
    for e in events:
        date = e['event_start'].split(' ')[0].replace('/', '')
        start = to_minutes(e['event_start'].split(' ')[1])
        if start is None:
            continue
        by_date.setdefault(date, []).append({
            'id': e['event_id'],
            'start': start,
            'goes': e['event_GOES'],
        })
    return by_date


def pair_one_day(noaa_events, lmsal_events, require_class):
    """One-to-one assignment: repeatedly take the globally closest still-unused pair.

    Greedy nearest-neighbour would let two NOAA events both claim the same LMSAL event,
    which inflates the tails of the distribution with duplicates.
    """
    candidates = []
    for i, n in enumerate(noaa_events):
        for j, l in enumerate(lmsal_events):
            if require_class and n['goes_class'] != l['goes']:
                continue
            candidates.append((abs(l['start'] - n['begin']), i, j))
    candidates.sort()

    used_n, used_l, pairs = set(), set(), []
    for _, i, j in candidates:
        if i in used_n or j in used_l:
            continue
        used_n.add(i)
        used_l.add(j)
        # signed: positive means LMSAL reports the flare later than NOAA
        pairs.append({
            'diff': lmsal_events[j]['start'] - noaa_events[i]['begin'],
            'class_agree': noaa_events[i]['goes_class'] == lmsal_events[j]['goes'],
        })
    unmatched = len(noaa_events) - len(pairs)
    return pairs, unmatched


def analyse(require_class):
    noaa_by_date = load_noaa_data()
    lmsal = lmsal_by_date()

    pairs, unmatched, no_lmsal_day = [], 0, 0
    total_noaa = 0

    for date, rows in noaa_by_date.items():
        usable = []
        for r in rows:
            begin = to_minutes(r['begin'])
            if begin is None or r['goes_class'] is None:
                continue
            usable.append({'begin': begin, 'goes_class': r['goes_class']})
        if not usable:
            continue
        total_noaa += len(usable)

        day_events = lmsal.get(date)
        if not day_events:
            # NOAA recorded a flare on a day LMSAL has no events at all
            no_lmsal_day += len(usable)
            continue

        day_pairs, day_unmatched = pair_one_day(usable, day_events, require_class)
        pairs.extend(day_pairs)
        unmatched += day_unmatched

    return {
        'total_noaa': total_noaa,
        'pairs': pairs,
        'unmatched': unmatched,
        'no_lmsal_day': no_lmsal_day,
    }


def describe(label, result):
    diffs = [p['diff'] for p in result['pairs']]
    n = len(diffs)
    total = result['total_noaa']

    print(f"\n{'=' * 74}")
    print(f"{label}")
    print('=' * 74)
    print(f"NOAA XRA events with a usable begin time and GOES class : {total:>7,}")
    print(f"  paired with an LMSAL event                            : {n:>7,}  ({n/total:.1%})")
    print(f"  no LMSAL event that day at all                        : {result['no_lmsal_day']:>7,}")
    print(f"  LMSAL had events that day but none left to pair       : {result['unmatched']:>7,}")

    if n < 2:
        print("not enough pairs to describe")
        return None

    mean = statistics.mean(diffs)
    sd = statistics.stdev(diffs)
    median = statistics.median(diffs)
    mad = statistics.median([abs(d - median) for d in diffs])
    exact = sum(1 for d in diffs if d == 0)

    print(f"\nSigned difference, LMSAL start minus NOAA begin (minutes):")
    print(f"  exact matches (diff = 0)   : {exact:>7,}  ({exact/n:.1%} of pairs)")
    print(f"  mean                       : {mean:>10.2f}")
    print(f"  standard deviation         : {sd:>10.2f}")
    print(f"  median                     : {median:>10.2f}")
    print(f"  median abs deviation (MAD) : {mad:>10.2f}")
    print(f"  min / max                  : {min(diffs):>10.0f} / {max(diffs):.0f}")

    qs = statistics.quantiles(diffs, n=100)
    print(f"  1st / 25th / 75th / 99th   : {qs[0]:.0f} / {qs[24]:.0f} / {qs[74]:.0f} / {qs[98]:.0f}")

    print(f"\nCandidate windows (mean +/- k*sd), and how much of NOAA they keep:")
    print(f"  {'window':>28}  {'of pairs':>10}  {'of all NOAA':>12}  {'lost':>8}")
    for k in (1, 2, 3):
        lo, hi = mean - k * sd, mean + k * sd
        kept = sum(1 for d in diffs if lo <= d <= hi)
        print(f"  {k}sd  [{lo:7.1f}, {hi:7.1f}]  {kept/n:>9.1%}  {kept/total:>11.1%}  {1-kept/total:>7.1%}")

    print(f"\n  robust alternative (median +/- k*MAD):")
    for k in (1, 2, 3):
        lo, hi = median - k * mad, median + k * mad
        kept = sum(1 for d in diffs if lo <= d <= hi)
        print(f"  {k}MAD [{lo:7.1f}, {hi:7.1f}]  {kept/n:>9.1%}  {kept/total:>11.1%}  {1-kept/total:>7.1%}")

    print(f"\n  for comparison, the current hard-coded rule:")
    for w in (5, 10, 15, 30):
        kept = sum(1 for d in diffs if abs(d) <= w)
        print(f"  +/-{w:<3} minutes        {kept/n:>9.1%}  {kept/total:>11.1%}  {1-kept/total:>7.1%}")

    if not any(p['class_agree'] is None for p in result['pairs']):
        agree = sum(1 for p in result['pairs'] if p['class_agree'])
        print(f"\nGOES class agreement among paired events: {agree:,} / {n:,} ({agree/n:.1%})")

    return {'mean': mean, 'sd': sd, 'median': median, 'mad': mad, 'n': n, 'total': total}


if __name__ == '__main__':
    a = analyse(require_class=False)
    describe("PAIRED BY TIME ONLY (class-agnostic) — unbiased timing estimate", a)

    b = analyse(require_class=True)
    describe("PAIRED BY TIME, SAME GOES CLASS REQUIRED", b)
