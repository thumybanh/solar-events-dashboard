"""Field-by-field cross-check of LMSAL against NOAA for the same flare.

Pairs are formed on date + begin time ONLY — the GOES class is deliberately not used as a matching
criterion, so that class agreement can be measured rather than assumed. Pairing is one-to-one
(each NOAA row and each LMSAL event used at most once, closest first) so a busy day cannot inflate
the agreement rate through double counting.

For each pair, all four fields are then compared: begin, peak, end, GOES class.

Read-only: writes nothing.
"""
import collections
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from noaa_matcher import parse_noaa_file, to_minutes

EVENTS_PATH = os.path.join(BASE_DIR, 'events.json')
NOAA_DIR = os.path.join(BASE_DIR, 'noaa_data')
CANONICAL = re.compile(r'^(\d{8})events\.txt$')

PAIR_WINDOW = 2   # minutes on begin time, for forming pairs


def load():
    noaa = collections.defaultdict(list)
    for fileName in os.listdir(NOAA_DIR):
        m = CANONICAL.match(fileName)
        if not m:
            continue
        for r in parse_noaa_file(os.path.join(NOAA_DIR, fileName)):
            noaa[m.group(1)].append({
                'begin': to_minutes(r['begin']),
                'peak': to_minutes(r['peak']),
                'end': to_minutes(r['end']),
                'goes': r['goes_class'],
            })

    with open(EVENTS_PATH) as f:
        events = json.load(f)
    lmsal = collections.defaultdict(list)
    for e in events:
        date = e['event_start'].split(' ')[0].replace('/', '')
        lmsal[date].append({
            'id': e['event_id'],
            'begin': to_minutes(e['event_start'].split(' ')[1]),
            'peak': to_minutes(e['event_peak']),
            'end': to_minutes(e['event_stop']),
            'goes': e['event_GOES'],
        })
    return noaa, lmsal


def pair_day(noaa_rows, lmsal_rows, window):
    """One-to-one assignment on begin time, closest pairs first."""
    cands = []
    for i, n in enumerate(noaa_rows):
        if n['begin'] is None:
            continue
        for j, l in enumerate(lmsal_rows):
            if l['begin'] is None:
                continue
            gap = abs(n['begin'] - l['begin'])
            if gap <= window:
                cands.append((gap, i, j))
    cands.sort()
    used_n, used_l, pairs = set(), set(), []
    for gap, i, j in cands:
        if i in used_n or j in used_l:
            continue
        used_n.add(i)
        used_l.add(j)
        pairs.append((noaa_rows[i], lmsal_rows[j]))
    return pairs


def main():
    noaa, lmsal = load()
    pairs = []
    for date, lrows in lmsal.items():
        nrows = noaa.get(date)
        if nrows:
            pairs.extend(pair_day(nrows, lrows, PAIR_WINDOW))

    print(f"Pairs formed on date + begin time within +/-{PAIR_WINDOW} min "
          f"(GOES class NOT used for pairing): {len(pairs):,}\n")

    stats = collections.OrderedDict()
    for field in ('begin', 'peak', 'end'):
        comparable = [(n[field], l[field]) for n, l in pairs
                      if n[field] is not None and l[field] is not None]
        # an LMSAL end earlier than its begin means event_stop crossed midnight; it carries no date
        if field == 'end':
            comparable = [(nv, lv) for (nv, lv), (n, l) in zip(comparable,
                          [(n, l) for n, l in pairs if n[field] is not None and l[field] is not None])
                          if l['begin'] is not None and lv >= l['begin']]
        exact = sum(1 for a, b in comparable if a == b)
        w1 = sum(1 for a, b in comparable if abs(a - b) <= 1)
        stats[field] = (len(comparable), exact, w1)

    cls = [(n['goes'], l['goes']) for n, l in pairs if n['goes'] and l['goes']]
    cls_exact = sum(1 for a, b in cls if a == b)

    print(f"  {'field':<8} {'comparable':>11} {'identical':>11} {'%':>8} {'within 1 min':>14} {'%':>8}")
    for field, (n, ex, w1) in stats.items():
        print(f"  {field:<8} {n:>11,} {ex:>11,} {ex/n:>7.1%} {w1:>14,} {w1/n:>7.1%}")
    print(f"  {'class':<8} {len(cls):>11,} {cls_exact:>11,} {cls_exact/len(cls):>7.1%}")

    # how many pairs agree on everything at once
    full = same3 = 0
    for n, l in pairs:
        if None in (n['begin'], l['begin'], n['peak'], l['peak'], n['end'], l['end']):
            continue
        if l['end'] < l['begin']:
            continue
        same3 += 1
        if (n['begin'] == l['begin'] and n['peak'] == l['peak'] and n['end'] == l['end']):
            full += 1
    print(f"\n  all three timestamps identical to the minute: {full:,} of {same3:,} ({full/same3:.1%})")

    both = sum(1 for n, l in pairs
               if n['begin'] is not None and l['begin'] is not None
               and n['peak'] is not None and l['peak'] is not None
               and n['end'] is not None and l['end'] is not None
               and l['end'] >= l['begin']
               and n['goes'] and l['goes']
               and n['begin'] == l['begin'] and n['peak'] == l['peak']
               and n['end'] == l['end'] and n['goes'] == l['goes'])
    print(f"  all three timestamps AND the GOES class identical: {both:,} ({both/same3:.1%})")

    print("\nCLASS DISAGREEMENT among pairs whose begin times match exactly")
    dis = collections.Counter()
    for n, l in pairs:
        if n['begin'] == l['begin'] and n['goes'] and l['goes'] and n['goes'] != l['goes']:
            dis[(n['goes'][0], l['goes'][0])] += 1
    same_letter = sum(v for (a, b), v in dis.items() if a == b)
    print(f"  disagreeing pairs: {sum(dis.values()):,}")
    print(f"    same letter, different magnitude (e.g. C1.0 vs C1.2): {same_letter:,}")
    print(f"    different letter entirely: {sum(dis.values())-same_letter:,}")
    print("  most common letter transitions (NOAA -> LMSAL):")
    for (a, b), v in dis.most_common(6):
        print(f"    {a} -> {b}: {v:,}")


if __name__ == '__main__':
    main()
