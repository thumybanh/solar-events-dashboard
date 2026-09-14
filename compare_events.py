"""Per-event side-by-side comparison of LMSAL against NOAA.

For every LMSAL event, finds its best NOAA counterpart on the same date (nearest begin time, class
ignored when choosing so that class agreement can be reported rather than assumed) and writes one
CSV row with both sources' begin / peak / end times and the differences between them.

Output: comparison.csv   Read-only with respect to events.json.
"""
import collections
import csv
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from noaa_matcher import parse_noaa_file, to_minutes

EVENTS_PATH = os.path.join(BASE_DIR, 'events.json')
NOAA_DIR = os.path.join(BASE_DIR, 'noaa_data')
OUT_PATH = os.path.join(BASE_DIR, 'comparison.csv')
CANONICAL = re.compile(r'^(\d{8})events\.txt$')

SEARCH_WINDOW = 30   # minutes; how far to look for a counterpart before calling it unmatched


def hhmm(minutes):
    if minutes is None:
        return ''
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def load_noaa():
    by_date = collections.defaultdict(list)
    for fileName in os.listdir(NOAA_DIR):
        m = CANONICAL.match(fileName)
        if not m:
            continue
        for r in parse_noaa_file(os.path.join(NOAA_DIR, fileName)):
            by_date[m.group(1)].append({
                'begin': to_minutes(r['begin']),
                'peak': to_minutes(r['peak']),
                'end': to_minutes(r['end']),
                'goes': r['goes_class'] or '',
            })
    return by_date


def main():
    noaa = load_noaa()
    with open(EVENTS_PATH) as f:
        events = json.load(f)

    rows = []
    for e in sorted(events, key=lambda x: x['event_start']):
        date = e['event_start'].split(' ')[0].replace('/', '')
        l_begin = to_minutes(e['event_start'].split(' ')[1])
        l_peak = to_minutes(e['event_peak'])
        l_end = to_minutes(e['event_stop'])
        l_goes = e['event_GOES']

        best, best_gap = None, None
        if l_begin is not None:
            for n in noaa.get(date, []):
                if n['begin'] is None:
                    continue
                gap = abs(n['begin'] - l_begin)
                if gap <= SEARCH_WINDOW and (best_gap is None or gap < best_gap):
                    best, best_gap = n, gap

        # LMSAL event_stop carries no date, so a value before the start means it crossed midnight
        crossed = l_end is not None and l_begin is not None and l_end < l_begin

        row = {
            'date': e['event_start'][:10],
            'event_id': e['event_id'],
            # newly scraped events have no flag yet if the matcher has not run since
            'quality_flag': e.get('quality_flag', ''),
            'lmsal_begin': hhmm(l_begin),
            'noaa_begin': hhmm(best['begin']) if best else '',
            'begin_diff_min': (l_begin - best['begin']) if best else '',
            'lmsal_peak': hhmm(l_peak),
            'noaa_peak': hhmm(best['peak']) if best and best['peak'] is not None else '',
            'peak_diff_min': (l_peak - best['peak']) if best and None not in (l_peak, best['peak']) else '',
            'lmsal_end': hhmm(l_end),
            'noaa_end': hhmm(best['end']) if best and best['end'] is not None else '',
            'end_diff_min': (l_end - best['end']) if best and None not in (l_end, best['end']) and not crossed else '',
            'lmsal_goes': l_goes,
            'noaa_goes': best['goes'] if best else '',
            'goes_match': '' if not best else ('exact' if best['goes'] == l_goes
                          else ('same_letter' if best['goes'][:1] == l_goes[:1] else 'different')),
            'crossed_midnight': 'yes' if crossed else '',
            'counterpart': 'yes' if best else 'none within 30 min',
        }
        rows.append(row)

    with open(OUT_PATH, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    matched = [r for r in rows if r['counterpart'] == 'yes']
    print(f"wrote {OUT_PATH}  ({len(rows):,} rows)")
    print(f"  with a NOAA counterpart within {SEARCH_WINDOW} min : {len(matched):,}")
    print(f"  no counterpart at all                          : {len(rows)-len(matched):,}")

    def agree(field):
        vals = [r[field] for r in matched if r[field] != '']
        return len(vals), sum(1 for v in vals if v == 0)

    print("\n  identical timestamps among matched events:")
    for f, label in (('begin_diff_min', 'begin'), ('peak_diff_min', 'peak'), ('end_diff_min', 'end')):
        n, ex = agree(f)
        print(f"    {label:<6} {ex:>7,} / {n:>7,}  ({ex/n:.1%})")
    gm = collections.Counter(r['goes_match'] for r in matched)
    print(f"    class  {gm['exact']:>7,} / {len(matched):>7,}  ({gm['exact']/len(matched):.1%})"
          f"   same-letter {gm['same_letter']:,}   different {gm['different']:,}")


if __name__ == '__main__':
    main()
