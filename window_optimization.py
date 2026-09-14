"""Derive the optimal NOAA/LMSAL matching window by maximising a stated objective.

The distribution of begin-time differences is a mixture of two populations:

    observed(d) = signal(d) + background(d)

where `signal` are genuinely the same flare recorded twice, and `background` are chance
coincidences: a NOAA event and an unrelated LMSAL event of the same GOES class that happen to fall
d minutes apart.

The background is estimated by circularly shifting all LMSAL times within each date by a random
offset and recomputing the lags. This is the right null because solar activity is strongly
clustered: an active day carries many flares in both catalogues, so chance coincidences are far more
likely on active days than on quiet ones. A shift preserves each day's event count, GOES class mix
and intra-day density exactly, and destroys only the fine time alignment. (Substituting events from
*other* dates — the obvious first idea — pairs active days against mostly quiet ones and
underestimates the background by an order of magnitude.)

With signal and background separated we can compute precision and recall as functions of the window
half-width W and choose W by an explicit criterion, rather than by eye.

Read-only: writes nothing.
"""
import json
import os
import random
import re
import statistics
import sys
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from noaa_matcher import parse_noaa_file, to_minutes

EVENTS_PATH = os.path.join(BASE_DIR, 'events.json')
NOAA_DIR = os.path.join(BASE_DIR, 'noaa_data')

# noaa_data also contains duplicate copies ("...events 2.txt") whose dates parse to garbage
CANONICAL = re.compile(r'^(\d{8})events\.txt$')

DAY = 1440             # minutes in a day
MAX_LAG = 720          # lags are wrapped into [-720, 720)
NULL_SAMPLES = 40      # random shifts per date, used only to cross-check the analytic background
SEED = 20260903


def wrap(lag):
    """Fold a lag into [-720, 720) so observed and shifted lags are treated identically."""
    return ((lag + MAX_LAG) % DAY) - MAX_LAG


def load_noaa():
    by_date = defaultdict(list)
    for fileName in os.listdir(NOAA_DIR):
        m = CANONICAL.match(fileName)
        if not m:
            continue
        for r in parse_noaa_file(os.path.join(NOAA_DIR, fileName)):
            begin = to_minutes(r['begin'])
            if begin is None or r['goes_class'] is None:
                continue
            by_date[m.group(1)].append((begin, r['goes_class']))
    return by_date


def load_lmsal():
    with open(EVENTS_PATH) as f:
        events = json.load(f)
    by_date = defaultdict(list)
    for e in events:
        date = e['event_start'].split(' ')[0].replace('/', '')
        start = to_minutes(e['event_start'].split(' ')[1])
        if start is None:
            continue
        by_date[date].append((start, e['event_GOES']))
    return by_date


def lag_counts(noaa_by_date, lmsal_by_date, null=False, rng=None):
    """Histogram of (LMSAL start - NOAA begin) for same-date, same-GOES-class pairs.

    null=False uses the real times (signal + background).
    null=True  circularly shifts every LMSAL time on the date by a random offset, averaged over
               NULL_SAMPLES draws, giving the expected background per real trial.
    """
    counts = defaultdict(float)
    trials = 0

    for date, noaa_events in noaa_by_date.items():
        day_events = lmsal_by_date.get(date)
        if not day_events:
            continue

        if null:
            # every offset is allowed. Excluding small offsets would leave a background deficit at
            # exactly the small lags being measured, since most true lags are 0.
            offsets = [rng.randrange(0, DAY) for _ in range(NULL_SAMPLES)]
            weight = 1.0 / NULL_SAMPLES
        else:
            offsets = [0]
            weight = 1.0

        for begin, goes in noaa_events:
            trials += weight
            for offset in offsets:
                for start, lgoes in day_events:
                    if lgoes != goes:
                        continue
                    counts[wrap(start + offset - begin)] += weight
    return counts, trials


def analytic_background(noaa_by_date, lmsal_by_date):
    """Exact expected background per lag under a uniform random circular shift.

    For one date and one GOES class, shifting the LMSAL times by a uniform random offset spreads
    every pair equally across all 1440 lags, so the expectation per lag is
    (NOAA count) * (LMSAL count) / 1440. Summing over dates and classes gives the exact background
    with no sampling noise, and it conserves the total pair count by construction.
    """
    per_lag = 0.0
    for date, noaa_events in noaa_by_date.items():
        day_events = lmsal_by_date.get(date)
        if not day_events:
            continue
        noaa_classes = defaultdict(int)
        for _, goes in noaa_events:
            noaa_classes[goes] += 1
        lmsal_classes = defaultdict(int)
        for _, goes in day_events:
            lmsal_classes[goes] += 1
        for goes, n in noaa_classes.items():
            per_lag += n * lmsal_classes.get(goes, 0) / DAY
    return {d: per_lag for d in range(-MAX_LAG, MAX_LAG)}


def main():
    rng = random.Random(SEED)
    noaa = load_noaa()
    lmsal = load_lmsal()

    observed, trials = lag_counts(noaa, lmsal, null=False)
    background = analytic_background(noaa, lmsal)

    # cross-check the analytic background against the shuffle it is meant to represent
    sampled, _ = lag_counts(noaa, lmsal, null=True, rng=rng)
    flat = background[0]
    far = [sampled.get(d, 0) for d in range(-MAX_LAG, MAX_LAG) if abs(d) > 60]
    print(f"background per lag: analytic {flat:.3f}, "
          f"sampled mean at |lag|>60 {statistics.mean(far):.3f} "
          f"(should agree; the sampled version is noisy per lag)")

    print(f"NOAA events considered             : {trials:,.0f}")
    print(f"same-date same-class pairs          : {sum(observed.values()):,.0f}")
    print(f"expected chance pairs (null model)  : {sum(background.values()):,.1f}")
    print(f"null: {NULL_SAMPLES} circular time shifts per date, seed {SEED}")
    bg_per_min = sum(background.values()) / DAY
    print(f"mean background density             : {bg_per_min:.2f} pairs per minute of lag")

    # ---- per-minute likelihood ratio -------------------------------------------------
    print(f"\n{'-'*72}")
    print("PER-MINUTE LIKELIHOOD RATIO  observed(d) / background(d)")
    print("The window should stop where this falls to ~1: at that lag an extra minute")
    print("admits as many chance coincidences as real matches.")
    print(f"{'-'*72}")
    print(f"  {'|lag|':>6} {'observed':>10} {'background':>11} {'ratio':>10}")
    for d in [0, 1, 2, 3, 4, 5, 7, 10, 15, 20, 30, 60, 120, 300]:
        obs = observed.get(d, 0) + (observed.get(-d, 0) if d else 0)
        bg = background.get(d, 0) + (background.get(-d, 0) if d else 0)
        ratio = obs / bg if bg > 0 else float('inf')
        r = f"{ratio:>10.1f}" if ratio != float('inf') else f"{'inf':>10}"
        print(f"  {d:>6} {obs:>10.0f} {bg:>11.2f} {r}")

    # ---- per-lag significance --------------------------------------------------------
    # The counts per lag are small, so a single-minute ratio is noisy. The defensible question is
    # whether the excess at each lag is distinguishable from Poisson fluctuation in the background.
    print(f"\n{'-'*72}")
    print("PER-LAG SIGNIFICANCE OF THE EXCESS  z = (observed - background) / sqrt(background)")
    print("z >= 3 is a real excess; z < 2 is indistinguishable from chance coincidence.")
    print(f"{'-'*72}")
    print(f"  {'|lag|':>6} {'observed':>10} {'background':>11} {'excess':>8} {'z':>8}  verdict")

    last_significant = None
    for d in range(0, 31):
        obs = observed.get(d, 0) + (observed.get(-d, 0) if d else 0)
        bg = background.get(d, 0) + (background.get(-d, 0) if d else 0)
        if bg <= 0:
            continue
        excess = obs - bg
        z = excess / (bg ** 0.5)
        verdict = 'significant' if z >= 3 else ('marginal' if z >= 2 else 'noise')
        if z >= 3:
            last_significant = d
        if d <= 12 or d % 5 == 0:
            print(f"  {d:>6} {obs:>10.0f} {bg:>11.2f} {excess:>8.1f} {z:>8.1f}  {verdict}")

    print(f"\n  largest lag with a significant (z>=3) excess: {last_significant} minutes")

    # Single-minute counts are only ~10-30, so bin them. Binning trades resolution for a stable
    # estimate and gives an honest answer to "where does the signal actually stop".
    print(f"\n{'-'*72}")
    print("BINNED EXCESS  (5-minute bins, both signs combined)")
    print(f"{'-'*72}")
    print(f"  {'lag band':>12} {'observed':>10} {'background':>11} {'excess':>9} {'z':>7} {'ratio':>8}")
    edges = [(0, 0), (1, 5), (6, 10), (11, 15), (16, 20), (21, 25), (26, 30),
             (31, 45), (46, 60), (61, 120), (121, 300), (301, 719)]
    signal_stops = None
    for lo, hi in edges:
        obs = bg = 0.0
        for d in range(lo, hi + 1):
            for s in ((d,) if d == 0 else (d, -d)):
                obs += observed.get(s, 0)
                bg += background.get(s, 0)
        if bg <= 0:
            continue
        z = (obs - bg) / (bg ** 0.5)
        ratio = obs / bg
        band = f"{lo}" if lo == hi else f"{lo}-{hi}"
        print(f"  {band:>12} {obs:>10.0f} {bg:>11.1f} {obs-bg:>9.1f} {z:>7.1f} {ratio:>8.2f}")
        if z >= 3:
            signal_stops = hi

    print(f"\n  signal is detectable out to the {signal_stops}-minute band; beyond that the")
    print("  observed counts are consistent with chance coincidence")

    # ---- decompose and optimise ------------------------------------------------------
    total_signal = sum(max(observed.get(d, 0) - background.get(d, 0), 0)
                       for d in range(-MAX_LAG, MAX_LAG + 1))

    print(f"\n{'-'*72}")
    print("PRECISION / RECALL AS A FUNCTION OF WINDOW HALF-WIDTH W")
    print(f"estimated true pairs in total: {total_signal:,.0f}")
    print(f"{'-'*72}")
    print(f"  {'W':>4} {'TP':>9} {'FP':>8} {'precision':>10} {'recall':>8} {'F1':>8} {'Youden J':>9}")

    rows = []
    for W in list(range(0, 31)) + [40, 60, 90, 120, 180, 300, 600]:
        if W > MAX_LAG:
            break
        tp = fp = 0.0
        for d in range(-W, W + 1):
            obs = observed.get(d, 0)
            bg = background.get(d, 0)
            tp += max(obs - bg, 0)
            fp += bg
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / total_signal if total_signal else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        # Youden's J = sensitivity + specificity - 1; with a large negative pool this reduces
        # to recall minus the fraction of the background pool admitted
        total_bg = sum(background.values())
        j = recall - (fp / total_bg if total_bg else 0.0)
        rows.append((W, tp, fp, precision, recall, f1, j))

    for W, tp, fp, p, r, f1, j in rows:
        if W <= 15 or W in (20, 30, 60, 120, 300, 600):
            print(f"  {W:>4} {tp:>9.0f} {fp:>8.1f} {p:>10.4f} {r:>8.4f} {f1:>8.4f} {j:>9.4f}")

    best_f1 = max(rows, key=lambda t: t[5])
    best_j = max(rows, key=lambda t: t[6])
    print(f"\n  argmax F1       : W = {best_f1[0]} minutes  (F1 = {best_f1[5]:.4f})")
    print(f"  argmax Youden J : W = {best_j[0]} minutes  (J  = {best_j[6]:.4f})")

    # ---- ambiguity: a cost precision/recall cannot see -------------------------------
    # Precision counts contamination against the background. It does not count the case where an
    # LMSAL event has a genuine partner but the window also admits a second candidate, so the
    # matcher may bind the wrong one. That risk grows with W and is worth reporting separately.
    print(f"\n{'-'*72}")
    print("AMBIGUITY: LMSAL events with more than one same-class NOAA candidate in range")
    print(f"{'-'*72}")
    print(f"  {'W':>4} {'matched':>9} {'ambiguous':>10} {'% of matched':>13}")
    for W in (0, 2, 4, 5, 10, 15, 20, 22, 25, 30, 45, 60):
        matched = amb = 0
        for date, day_events in lmsal.items():
            noaa_events = noaa.get(date)
            if not noaa_events:
                continue
            for start, goes in day_events:
                c = sum(1 for begin, ngoes in noaa_events
                        if ngoes == goes and abs(begin - start) <= W)
                if c >= 1:
                    matched += 1
                if c > 1:
                    amb += 1
        pct = amb / matched if matched else 0.0
        print(f"  {W:>4} {matched:>9,} {amb:>10,} {pct:>12.2%}")

    # ---- marginal analysis -----------------------------------------------------------
    print(f"\n{'-'*72}")
    print("MARGINAL VALUE OF EACH EXTRA MINUTE")
    print("signal gained vs chance pairs admitted by widening from W-1 to W")
    print(f"{'-'*72}")
    print(f"  {'W':>4} {'+signal':>9} {'+chance':>9} {'marginal ratio':>15}")
    for W in range(1, 21):
        sig = max(observed.get(W, 0) - background.get(W, 0), 0) + \
              max(observed.get(-W, 0) - background.get(-W, 0), 0)
        bg = background.get(W, 0) + background.get(-W, 0)
        ratio = sig / bg if bg > 0 else float('inf')
        r = f"{ratio:>15.2f}" if ratio != float('inf') else f"{'inf':>15}"
        print(f"  {W:>4} {sig:>9.0f} {bg:>9.2f} {r}")

    print(f"\n{'-'*72}")
    print("A window is defensible while the marginal ratio stays above 1.0.")
    print("Below 1.0, widening costs more in false matches than it gains in real ones.")
    print(f"{'-'*72}")


if __name__ == '__main__':
    main()
