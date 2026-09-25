"""The one place that reads and writes events.json and locates noaa_data/.

Data lives at the repo root, outside the package, so it is not shipped or
overwritten by an install. FLARE_DATA_DIR overrides the location; without it the
default is the repo root, which is two levels above this file
(flarexmatch/fetch/storage.py -> flarexmatch/fetch -> flarexmatch -> root).
That default is correct for a source checkout and for `pip install -e .`. A
non-editable install puts the package under site-packages, where the default is
meaningless -- set FLARE_DATA_DIR in that case.
"""

import json
import os

DATA_DIR = os.environ.get("FLARE_DATA_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

EVENTS_PATH = os.path.join(DATA_DIR, "events.json")
NOAA_DIR = os.path.join(DATA_DIR, "noaa_data")


def load_events():
    """events.json as {event_id: event}. Empty dict if the file is not there yet."""
    try:
        with open(EVENTS_PATH, 'r') as f:
            existing = json.load(f)
        return {e['event_id']: e for e in existing}
    except FileNotFoundError:
        return {}


def save_events(all_events):
    """Write a {event_id: event} mapping back out as a list."""
    _atomic_write(list(all_events.values()))


def load_event_list():
    """events.json as the plain list it is stored as, in file order."""
    with open(EVENTS_PATH, 'r') as f:
        return json.load(f)


def save_event_list(events):
    """Write a list of events back out."""
    _atomic_write(events)


def events_mtime():
    return os.path.getmtime(EVENTS_PATH)


def _atomic_write(events):
    # write to a temp file first, then swap it in — a crash mid-write can't truncate events.json
    tmp_path = EVENTS_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(events, f, indent=2)
    os.replace(tmp_path, EVENTS_PATH)
