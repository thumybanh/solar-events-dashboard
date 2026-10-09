import json
import os
import re
import sys
from datetime import datetime, timezone

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

# the pipeline scripts live in pipeline/ and import each other by bare name, so put that folder on the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pipeline'))
from daily_scraper import run_daily_scraper

from api_sources import SOURCES, FilterError, compare, parse_filters

DEFAULT_LIMIT = 1000
MAX_LIMIT = 30000

LMSAL = SOURCES['lmsal']

app = FastAPI(
    title="Solar Events API",
    description=(
        "Solar flare events from three catalogues: the LMSAL SolarSoft archive, NOAA/SWPC "
        "X-ray event reports, and the NCEI science-quality GOES flare report. LMSAL and NOAA "
        "are cross-checked against each other (quality_flag) and every flare with a position "
        "has image pixel coordinates. Free to use for research."
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

def _filters(**query):
    try:
        return parse_filters(**query)
    except FilterError as e:
        # 400 with a message saying what was wrong, instead of quietly returning nothing
        raise HTTPException(status_code=400, detail=str(e))


def _matching(source, query):
    try:
        return source.filter(_filters(**query))
    except FilterError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _updated(source):
    mtime = source.updated()
    return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat() if mtime else None


def get_events():
    return LMSAL.all()


@app.get('/')
def home():
    return {
        "message": "Solar events API is running.",
        "docs": "/docs",
        "total_events": len(get_events()),
        "endpoints": {
            "/events": "LMSAL event list (start_date, end_date, goes_class, active_region, quality_flag, limit, offset)",
            "/events/{event_id}": "a single LMSAL event by id, e.g. gev_20260901_0054",
            "/events/download/": "same filters, returned as a file attachment (no limit)",
            "/stats": "LMSAL dataset summary",
            "/noaa/events": "NOAA/SWPC X-ray flares; same filters, plus /noaa/events/{id}, /noaa/events/download, /noaa/stats",
            "/sciquality/events": "NCEI science-quality GOES flares; same filters except quality_flag, plus /{id}, /download, /stats",
            "/compare": "flare counts or individual flares per source, for the comparison chart",
        },
        "quality_flag": {
            "HIGH": "the other catalogue (LMSAL vs NOAA) has a flare of the same class starting within 3 minutes",
            "LOW": "the other catalogue has a flare starting within 3 minutes, but of a different class",
            "N/A": "the other catalogue has nothing starting within 3 minutes (or this flare has no begin time/class)",
        },
    }


@app.get('/stats')
def stats():
    summary = LMSAL.stats()
    return {
        "total_events": summary['total_events'],
        "first_event": summary['first_event'] and summary['first_event'].replace('-', '/'),
        "last_event": summary['last_event'] and summary['last_event'].replace('-', '/'),
        "quality_high": summary['flags']['HIGH'],
        "quality_low": summary['flags']['LOW'],
        "quality_na": summary['flags']['N/A'],
        "with_coordinates": summary['with_location'],
        "data_updated": _updated(LMSAL),
    }


def add_source_routes(prefix, source):
    """List, download, single-flare and stats routes for one source under `prefix`."""

    def list_events(
        response: Response,
        start_date: str = None,
        end_date: str = None,
        goes_class: str = None,
        active_region: str = None,
        quality_flag: str = None,
        limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ):
        events = _matching(source, dict(start_date=start_date, end_date=end_date, goes_class=goes_class,
                                        active_region=active_region, quality_flag=quality_flag))
        # total count goes in a header so the response body stays a plain array
        response.headers['X-Total-Count'] = str(len(events))
        return events[offset:offset + limit]

    def download_events(
        start_date: str = None,
        end_date: str = None,
        goes_class: str = None,
        active_region: str = None,
        quality_flag: str = None,
    ):
        events = _matching(source, dict(start_date=start_date, end_date=end_date, goes_class=goes_class,
                                        active_region=active_region, quality_flag=quality_flag))
        return Response(
            content=json.dumps(events),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={source.name}_events.json"},
        )

    def get_event(event_id: str):
        event = source.find(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    def source_stats():
        return {**source.stats(), "data_updated": _updated(source)}

    tag = [source.label]
    app.get(f'{prefix}/events', tags=tag)(list_events)
    # registered before /events/{event_id} so "download" isn't swallowed as an event id
    # (both spellings registered, otherwise the version without the slash falls through to that route)
    app.get(f'{prefix}/events/download/', tags=tag)(download_events)
    app.get(f'{prefix}/events/download', tags=tag)(download_events)
    app.get(f'{prefix}/events/{{event_id}}', tags=tag)(get_event)
    if prefix:
        app.get(f'{prefix}/stats', tags=tag)(source_stats)


@app.get('/compare', tags=['Compare'])
def compare_sources(
    sources: str = 'lmsal,noaa,sciquality',
    start_date: str = None,
    end_date: str = None,
    goes_class: str = None,
    active_region: str = None,
):
    """Flare counts per day/month/year (ranges over 31 days) or individual flares (31 days or less)."""
    names = [n.strip().lower() for n in sources.split(',') if n.strip()]
    filters = _filters(start_date=start_date, end_date=end_date, goes_class=goes_class, active_region=active_region)
    try:
        return compare(SOURCES, names, filters)
    except FilterError as e:
        raise HTTPException(status_code=400, detail=str(e))


HELIOVIEWER_SOURCES = {19, 6}  # SDO/HMI and SOHO/MDI magnetograms


@app.get('/solar-image/closest', tags=['Images'])
def closest_solar_image(date: str, source_id: int):
    """Helioviewer's closest magnetogram to a time. Helioviewer only allows this call from
    localhost in a browser, so the deployed site asks it through here instead."""
    import httpx

    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', date):
        raise HTTPException(status_code=400, detail=f"date must look like 2026-10-03T16:50:00Z, got {date!r}")
    if source_id not in HELIOVIEWER_SOURCES:
        raise HTTPException(status_code=400, detail=f"source_id must be 19 (SDO/HMI) or 6 (SOHO/MDI), got {source_id}")
    try:
        reply = httpx.get('https://api.helioviewer.org/v2/getClosestImage/',
                          params={'date': date, 'sourceId': source_id}, timeout=20)
        body = reply.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Helioviewer didn't answer; try again in a moment")
    if reply.status_code != 200 or 'date' not in body:
        raise HTTPException(status_code=502, detail=body.get('error') or "Helioviewer returned no image")
    return body


add_source_routes('', LMSAL)  # LMSAL keeps the original paths: /events, /events/download, /events/{id}
add_source_routes('/noaa', SOURCES['noaa'])
add_source_routes('/sciquality', SOURCES['sciquality'])


@app.get('/scrape', include_in_schema=False)
def scrape_events(background_tasks: BackgroundTasks, token: str = None):
    # scraping is expensive, so it stays behind a token that has to be set on the server
    expected = os.environ.get('SCRAPE_TOKEN')
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    background_tasks.add_task(run_daily_scraper)
    return {"status": "started", "message": "scraper running in background"}
