# ways to filter: 
# 1. only accept XRA type flare 
# 2. if empty / no information then replace it with null. if null then immediately low qulality

import json
import os

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

noaa_list = []
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


def load_noaa_data():
    noaa_by_date = {} # group by date so each LMSAL event only compares against NOAA rows from its own day
    for fileName in os.listdir('noaa_data'):
        results = parse_noaa_file(os.path.join('noaa_data', fileName))
        noaa_list.extend(results) # use extend because 'extend' add each item individually -> flat list instead of adds whole list as one item like append
        for r in results:
            if r['date'] is not None:
                noaa_by_date.setdefault(r['date'], []).append(r)
    return noaa_by_date


def match_events(noaa_by_date) :
     LMSAL_events = []
     with open('events.json', 'r') as f:
        events = json.load(f)
        for event in events:
                LMSALdate = event['event_start'].split(' ')[0].replace('/','')
                LMSALstart = to_minutes(event['event_start'].split(' ')[1])
                LMSALpeak = to_minutes(event['event_peak'])
                LMSALend = to_minutes(event['event_stop'])
                LMSALGOES = event['event_GOES']

                event['quality_flag'] = 'LOW'

                event['end_time_diff'] = None

                if LMSALstart is None:
                    LMSAL_events.append(event)
                    continue

                # same_date is guaranteed by the lookup key, so only the time/class checks are left.
                # Keep the closest candidate rather than stopping at the first one in file order:
                # when two same-class NOAA flares fall inside the window, the first can be the wrong
                # flare, which leaves the flag right but end_time_diff measured against another event.
                best = None # (time_start_diff, NOAA_begin, NOAA_event)
                for NOAA_event in noaa_by_date.get(LMSALdate, []):
                    NOAA_begin = to_minutes(NOAA_event['begin'])
                    if NOAA_begin is None: continue

                    if NOAA_event['goes_class'] is not None:
                        same_class = NOAA_event['goes_class'] == LMSALGOES
                    else : continue

                    time_start_diff = abs(NOAA_begin - LMSALstart)

                    if time_start_diff <= MATCH_WINDOW_MINUTES and same_class :
                         if best is None or time_start_diff < best[0]: # ties keep file order
                             best = (time_start_diff, NOAA_begin, NOAA_event)

                if best is not None:
                     _, NOAA_begin, NOAA_event = best
                     event['quality_flag'] = 'HIGH'
                     # How well the two sources agree on where the flare ended. Recorded, not
                     # used to decide the match: onset is an objective threshold crossing, while
                     # the end depends on each pipeline's decay criteria, so end times scatter
                     # ~45x wider than begin times. Gating on it would exclude exactly the
                     # disagreements this dataset exists to measure.
                     n_end = resolve_end(NOAA_begin, to_minutes(NOAA_event['end']))
                     l_end = resolve_end(LMSALstart, LMSALend)
                     if n_end is not None and l_end is not None:
                         event['end_time_diff'] = l_end - n_end
                LMSAL_events.append(event)
        return LMSAL_events


def convert_position(LMSAL_position):

    lat_dir = LMSAL_position[0]
    lat_num = LMSAL_position[1:3]
    lon_dir = LMSAL_position[3]
    lon_num = LMSAL_position[4:6]

    lat = int(lat_num) if lat_dir == 'N' else -int(lat_num)
    lon = int(lon_num) if lon_dir == 'W' else -int(lon_num)

    return lat, lon


if __name__ == '__main__':
    LMSAL_list = match_events(load_noaa_data())

    with open('events.json', 'w') as f:
         json.dump(LMSAL_list, f, indent=2)

    print(f"matched {len(LMSAL_list)} events, HIGH: {sum(1 for e in LMSAL_list if e['quality_flag'] == 'HIGH')}")


                    



        
        
        