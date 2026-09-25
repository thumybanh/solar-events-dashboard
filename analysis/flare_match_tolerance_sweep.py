"""
For each LMSAL solar flare event, we ask: "does NOAA's event list contain
a flare that looks like the same event?" We try three different rules for
"looks like the same event," one at a time:
 
  Rule A: same GOES class + same active region + same peak time + same
          end time, but the BEGIN time is allowed to differ by up to W
          minutes.
  Rule B: same GOES class + same active region + same begin time + same
          end time, but the PEAK time is allowed to differ by up to W
          minutes.
  Rule C: same GOES class + same active region + same begin time + same
          peak time, but the END time is allowed to differ by up to W
          minutes.
 
We repeat each rule for W = 0, 1, 2, ... 100 minutes and count how many
LMSAL events find a match under each rule. The output CSV has one row per
(rule, W) combination -- 3 rules x 101 tolerances = 303 rows.
 
WHY THIS IS INTERESTING
------------------------
If loosening a field's tolerance barely changes the match count, that
field almost always already agrees between the two catalogs -- there's
nothing left to "find" by being more lenient. If loosening it keeps
finding new matches, the two catalogs genuinely disagree on that field.
 
HOW TO RUN THIS
----------------
1. This file lives in analysis/; events.json and noaa_data/ stay at the
   repo root one level up, and it finds them from its own location.
2. In a terminal, from anywhere in the repo, run:
       python3 analysis/flare_match_tolerance_sweep.py
3. It prints a short summary and writes flare_match_tolerance_sweep.csv
   to the repo root.
 
No installs needed -- everything used here is in Python's standard
library (json, re, csv, os, datetime, bisect).
"""

import bisect 
import csv, json, os, re
from datetime import datetime, timedelta

"""
STEP 0: setings that can be modify 
"""
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # repo root, one level up from analysis/
EVENTS_JSON = os.path.join(REPO_DIR, "events.json")
NOAA_DIR = os.path.join(REPO_DIR, "noaa_data")
OUTPUT_CSV = os.path.join(REPO_DIR, "flare_match_tolerance_sweep.csv")
MAX_TOLERANCE_MINUTES = 100 # the sweep run from 0 to 100 minutes inclusive

CLASS_RE = re.compile(r"[ABCMX]\d+(\.\d+)?")  # a GOES class like "M1.4" or "C9"

"""
STEP 1: load NOAA's flare list into a simple list of dictionaries
"""

def load_noaa_flares():
    """
    Reads every noaa_data/YYYYMMDDevents.txt file and pulls out the XRA
    (soft X-ray flare) rows. Returns a list of dicts, one per flare:
        {"begin": datetime, "peak": datetime or None,
         "end": datetime or None, "goes_class": "M1.4", "active_region": 3664 or None}
    """
    flares = []
    for filename in sorted(os.listdir(NOAA_DIR)):
        # Skip anything that isn't a plain "YYYYMMDDevents.txt" file
        # (some folders have duplicate copies ending in " 2.txt" -- skip those)
        if not re.fullmatch(r"\d{8}events\.txt", filename):
            continue
 
        file_date = datetime.strptime(filename[:8], "%Y%m%d")
 
        with open(os.path.join(NOAA_DIR, filename), errors="ignore") as f:
            for line in f:
                if line.startswith((":", "#")) or " XRA " not in line:
                    continue  # not a soft X-ray flare row
 
                columns = line.replace("+", " ").split()
                xra_position = columns.index("XRA")
 
                begin_hhmm = columns[1]
                peak_hhmm = columns[2]
                end_hhmm = columns[3]
                goes_class = columns[xra_position + 2] if len(columns) > xra_position + 2 else ""
                region_field = columns[xra_position + 4] if len(columns) > xra_position + 4 else ""
 
                if not (_is_valid_hhmm(begin_hhmm) and CLASS_RE.fullmatch(goes_class)):
                    continue  # skip malformed rows (missing data shows as "////")
 
                begin_dt = _combine(file_date, begin_hhmm)
                peak_dt = _combine(file_date, peak_hhmm) if _is_valid_hhmm(peak_hhmm) else None
                end_dt = _combine(file_date, end_hhmm) if _is_valid_hhmm(end_hhmm) else None
 
                # A flare can end after midnight -- push it to the next day
                # if it looks earlier than the begin time.
                if peak_dt and peak_dt < begin_dt:
                    peak_dt += timedelta(days=1)
                if end_dt and end_dt < begin_dt:
                    end_dt += timedelta(days=1)
 
                active_region = int(region_field) % 10000 if region_field.isdigit() else None
 
                flares.append({
                    "begin": begin_dt, "peak": peak_dt, "end": end_dt,
                    "goes_class": goes_class, "active_region": active_region,
                })
    return flares
 
 
def _is_valid_hhmm(text):
    return text.isdigit() and len(text) == 4 and int(text[:2]) < 24 and int(text[2:]) < 60
 
 
def _combine(day, hhmm):
    return day + timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[2:]))

"""
STEP 2: load LMSAL's event list the same way
"""
def load_lmsal_events():
    """
    Reads events.json and returns a list of dicts in the same shape as
    load_noaa_flares(), so the two sides can be compared directly.
    """
    events = []
    raw_events = json.load(open(EVENTS_JSON))
 
    for ev in raw_events:
        goes_class = (ev.get("event_GOES") or "").strip()
        if not CLASS_RE.fullmatch(goes_class):
            continue
 
        try:
            begin_dt = datetime.strptime(ev["event_start"], "%Y/%m/%d %H:%M:%S")
        except (KeyError, ValueError, TypeError):
            continue  # can't use this event without a valid begin time
 
        peak_dt = _time_after(begin_dt, ev.get("event_peak"))
        end_dt = _time_after(begin_dt, ev.get("event_stop"))
 
        region_match = re.search(r"\(\s*(\d+)\s*\)", ev.get("event_position") or "")
        active_region = int(region_match.group(1)) % 10000 if region_match else None
 
        events.append({
            "begin": begin_dt, "peak": peak_dt, "end": end_dt,
            "goes_class": goes_class, "active_region": active_region,
        })
    return events
 
 
def _time_after(begin_dt, hms_string):
    """event_peak/event_stop are just 'HH:MM:SS' -- attach them to the
    same day as begin_dt, rolling to the next day if needed."""
    try:
        t = datetime.strptime(hms_string, "%H:%M:%S")
    except (ValueError, TypeError):
        return None
    combined = begin_dt.replace(hour=t.hour, minute=t.minute, second=0)
    return combined + timedelta(days=1) if combined < begin_dt else combined

"""
STEP 3:  run one sweep (one field relaxed, the rest held exact)
"""
FIELDS = ("begin", "peak", "end")
FIELD_LABEL = {"begin": "begin_time", "peak": "peak_time", "end": "end_time"}
 
 
def run_one_sweep(relaxed_field, lmsal_events, noaa_flares):
    """
    relaxed_field is "begin", "peak", or "end" -- the ONE time field
    allowed to differ by up to W minutes. The other two time fields,
    plus goes_class and active_region, must match exactly.
 
    Returns a list of dicts, one per tolerance value W = 0..MAX_TOLERANCE_MINUTES.
    """
    fixed_fields = [f for f in FIELDS if f != relaxed_field]
 
    # Only events/flares that have every field we need can ever match.
    comparable_events = [
        e for e in lmsal_events
        if all(e[f] is not None for f in FIELDS) and e["active_region"] is not None
    ]
    comparable_flares = [
        r for r in noaa_flares
        if all(r[f] is not None for f in FIELDS) and r["active_region"] is not None
    ]
 
    # Sort NOAA flares by the relaxed field's time, so we can quickly find
    # all flares within +/- MAX_TOLERANCE_MINUTES of a given event.
    sorted_flares = sorted(comparable_flares, key=lambda r: r[relaxed_field])
    sorted_times = [r[relaxed_field] for r in sorted_flares]
 
    # For each event, find the SMALLEST time difference among NOAA flares
    # that already agree on class, active region, and the two fixed fields.
    best_time_diff_minutes = []
    for event in comparable_events:
        window_start = event[relaxed_field] - timedelta(minutes=MAX_TOLERANCE_MINUTES)
        window_end = event[relaxed_field] + timedelta(minutes=MAX_TOLERANCE_MINUTES)
        lo = bisect.bisect_left(sorted_times, window_start)
        hi = bisect.bisect_right(sorted_times, window_end)
 
        candidate_diffs = []
        for flare in sorted_flares[lo:hi]:
            if flare["goes_class"] != event["goes_class"]:
                continue
            if flare["active_region"] != event["active_region"]:
                continue
            if any(flare[f] != event[f] for f in fixed_fields):
                continue
            diff_minutes = abs((flare[relaxed_field] - event[relaxed_field]).total_seconds()) / 60
            candidate_diffs.append(diff_minutes)
 
        best_time_diff_minutes.append(min(candidate_diffs) if candidate_diffs else None)
 
    # Now count, for each tolerance W, how many events have a best diff <= W.
    rows = []
    n_comparable = len(comparable_events)
    n_total = len(lmsal_events)
    baseline_matches = None
 
    for W in range(MAX_TOLERANCE_MINUTES + 1):
        matches = sum(1 for d in best_time_diff_minutes if d is not None and d <= W)
        if W == 0:
            baseline_matches = matches
        rows.append({
            "relaxed_field": FIELD_LABEL[relaxed_field],
            "fields_required_exact": "goes_class, active_region, "
                                      + ", ".join(FIELD_LABEL[f] for f in fixed_fields),
            "tolerance_minutes": W,
            "lmsal_events_comparable": n_comparable,
            "lmsal_events_total": n_total,
            "events_matched": matches,
            "match_rate_comparable_pct": round(100 * matches / n_comparable, 2),
            "match_rate_all_events_pct": round(100 * matches / n_total, 2),
            "events_gained_vs_0min": matches - baseline_matches,
        })
    return rows
 
"""
STEP 4: put it all together
"""
def main():
    print("Loading NOAA flares...")
    noaa_flares = load_noaa_flares()
    print(f"  {len(noaa_flares)} NOAA XRA flare rows loaded")
 
    print("Loading LMSAL events...")
    lmsal_events = load_lmsal_events()
    print(f"  {len(lmsal_events)} LMSAL events loaded")
 
    all_rows = []
    for field in FIELDS:
        print(f"Sweeping {FIELD_LABEL[field]} tolerance from 0 to {MAX_TOLERANCE_MINUTES} minutes...")
        all_rows.extend(run_one_sweep(field, lmsal_events, noaa_flares))
 
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)
 
    print(f"\nDone. Wrote {len(all_rows)} rows to {OUTPUT_CSV}")
 
 
if __name__ == "__main__":
    main()
