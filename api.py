import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from daily_scraper import run_daily_scraper
from scraper import EVENTS_PATH

DEFAULT_LIMIT = 1000
MAX_LIMIT = 30000

app = FastAPI(
    title="Solar Events API",
    description=(
        "Solar flare events scraped from the LMSAL SolarSoft archive, cross-checked "
        "against NOAA/GOES X-ray event reports and annotated with image pixel coordinates. "
        "Free to use for research."
    ),
    version="1.0.0",
)

# public read-only dataset — allow any origin so browser-based tools can call it
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['GET'],
    allow_headers=['*'],
    expose_headers=['X-Total-Count'],
)

# events.json is ~20MB, so keep it in memory and only re-read when the file on disk changes
_cache = {"mtime": None, "events": []}


def get_events():
    mtime = os.path.getmtime(EVENTS_PATH)
    if _cache["mtime"] != mtime:
        with open(EVENTS_PATH, 'r') as f:
            events = json.load(f)
        # newest first, so page 1 is the most recent data. sorted once here rather than per
        # request, and it has to happen before pagination slices the list.
        # event_start is "YYYY/MM/DD HH:MM:SS", so a plain string sort is chronological.
        _cache["events"] = sorted(events, key=lambda e: e['event_start'], reverse=True)
        _cache["mtime"] = mtime
    return _cache["events"]


def filter_events(start_date, end_date, goes_class, quality_flag):
    events = get_events()

    # the datepicker in the js is formatted with "-" but the json format is with "/" so we need to replace it
    if start_date:
        events = [e for e in events if e['event_start'] >= start_date.replace('-', '/')]
    if end_date:
        events = [e for e in events if e['event_start'] <= end_date.replace('-', '/')]
    if goes_class:
        events = [e for e in events if e['event_GOES'].startswith(goes_class)]
    if quality_flag:
        events = [e for e in events if e.get('quality_flag') == quality_flag.upper()]
    return events


@app.get('/')
def home():
    return {
        "message": "Solar events API is running.",
        "docs": "/docs",
        "total_events": len(get_events()),
        "endpoints": {
            "/events": "filtered event list (start_date, end_date, goes_class, quality_flag, limit, offset)",
            "/events/{event_id}": "a single event by id, e.g. gev_20260901_0054",
            "/events/download/": "same filters, returned as a file attachment (no limit)",
            "/stats": "dataset summary",
        },
    }


@app.get('/stats')
def stats():
    events = get_events()
    dates = sorted({e['event_start'][:10] for e in events})
    return {
        "total_events": len(events),
        "first_event": dates[0] if dates else None,
        "last_event": dates[-1] if dates else None,
        "quality_high": sum(1 for e in events if e.get('quality_flag') == 'HIGH'),
        "quality_low": sum(1 for e in events if e.get('quality_flag') == 'LOW'),
        "with_coordinates": sum(1 for e in events if e.get('pix_x') is not None),
        "data_updated": datetime.fromtimestamp(
            os.path.getmtime(EVENTS_PATH), tz=timezone.utc
        ).isoformat(),
    }


@app.get('/events')
def list_events(
    response: Response,
    start_date: str = None,
    end_date: str = None,
    goes_class: str = None,
    quality_flag: str = None,
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    events = filter_events(start_date, end_date, goes_class, quality_flag)

    # total count goes in a header so the response body stays a plain array
    response.headers['X-Total-Count'] = str(len(events))
    return events[offset:offset + limit]


# defined before /events/{event_id} so "download" isn't swallowed as an event id
# (both spellings registered, otherwise the version without the slash falls through to that route)
@app.get('/events/download/')
@app.get('/events/download')
def download_events(
    start_date: str = None,
    end_date: str = None,
    goes_class: str = None,
    quality_flag: str = None,
):
    events = filter_events(start_date, end_date, goes_class, quality_flag)
    return Response(
        content=json.dumps(events),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=events.json"},
    )


@app.get('/events/{event_id}')
def get_event(event_id: str):
    for event in get_events():
        if event["event_id"] == event_id:
            return event
    raise HTTPException(status_code=404, detail="Event not found")


@app.get('/scrape', include_in_schema=False)
def scrape_events(background_tasks: BackgroundTasks, token: str = None):
    # scraping is expensive, so it stays behind a token that has to be set on the server
    expected = os.environ.get('SCRAPE_TOKEN')
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(run_daily_scraper)
    return {"status": "started", "message": "scraper running in background"}
