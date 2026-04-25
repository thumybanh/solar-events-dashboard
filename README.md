# Solar Events Dashboard
 
A full-stack web application for exploring, filtering, and visualizing solar flare events from LMSAL (Lockheed Martin Solar and Astrophysics Laboratory) with quality comparison against NOAA/GOES data and solar image visualization.
 
---
 
## Project Structure
 
```
LMSAL/
├── scraper.py            # One-time full scrape of all events from 2015 to present
├── daily_scraper.py      # Scrapes only today and yesterday's new events (run daily)
├── api.py                # FastAPI backend — serves event data
├── noaa_downloader.py    # Downloads NOAA event txt files via FTP
├── noaa_matcher.py       # Parses NOAA data + assigns quality flags
├── coordinates.py        # Converts derived position to pixel coordinates
├── events.json           # Scraped + processed event database
├── noaa_data/            # Downloaded NOAA txt files
├── requirements.txt      # Python dependencies
└── frontend/
    └── src/
        ├── App.jsx       # React frontend dashboard
        └── index.css     # Global styles
```
 
---
 
## Installation
 
### Python Dependencies
 
```bash
pip install -r requirements.txt
```
 
Or manually:
 
```bash
pip install httpx beautifulsoup4 fastapi uvicorn python-multipart
```
 
### Node.js Dependencies
 
```bash
cd frontend
npm install
```
 
---
 
## How to Run
 
**Terminal 1 — Start the FastAPI backend:**
```bash
cd path/to/LMSAL
/opt/miniconda3/bin/python -m uvicorn api:app --reload
```
 
**Terminal 2 — Start the React frontend:**
```bash
cd path/to/LMSAL/frontend
npm run dev
```
 
- Backend runs at: `http://localhost:8000`
- Frontend runs at: `http://localhost:5173`
---
 
## Scripts — Run in Order
 
### 1. Scrape All Historical LMSAL Events (run once)
```bash
/opt/miniconda3/bin/python scraper.py
```
Scrapes all solar flare events from the LMSAL archive starting from July 1, 2015 up to today. Merges with existing `events.json` without overwriting historical data. Only needs to be run once to build the initial database.
 
### 2. Update with New Events (run daily)
```bash
/opt/miniconda3/bin/python daily_scraper.py
```
Scrapes only today's and yesterday's new events from LMSAL. Merges new events into the existing `events.json` without touching historical data.
 
To automate daily updates using macOS crontab:
```bash
# Open crontab editor
crontab -e
 
# Add this line to run at midnight every day
0 0 * * * /opt/miniconda3/bin/python /path/to/LMSAL/daily_scraper.py
```
 
### 3. Download NOAA Data
```bash
/opt/miniconda3/bin/python noaa_downloader.py
```
Connects to the NOAA FTP server (`ftp.swpc.noaa.gov`) and downloads event txt files for each unique date present in `events.json`. Files saved to `noaa_data/`. Automatically skips dates where NOAA has no data.
 
### 4. Match & Assign Quality Flags
```bash
/opt/miniconda3/bin/python noaa_matcher.py
```
Parses NOAA txt files and compares each LMSAL event against NOAA data. Assigns a `quality_flag` to each event based on time difference and GOES class matching:
 
| Flag | Condition |
|------|-----------|
| `HIGH` | Match found within ±10 minutes with same GOES class |
| `LOW` | No matching event found, or missing data |
 
Only `XRA` (X-Ray Activity) type NOAA events are used since those are the only ones with GOES classifications.
 
### 5. Calculate Pixel Coordinates
```bash
/opt/miniconda3/bin/python coordinates.py
```
Converts each event's derived position (e.g. `S11W04`) to pixel coordinates (`pix_x`, `pix_y`) on a 512x512 solar image using heliographic coordinate transformation:
 
```
HGS (lat/lon degrees)
    → HCC (Heliocentric, meters)
    → HPC (Helioprojective, arcseconds)
    → Pixel coordinates (512x512 space)
```
 
---
 
## Keeping the Database Up To Date
 
```
First time setup:
1. Run scraper.py          → builds full historical database (2015 to now)
2. Run noaa_downloader.py  → downloads NOAA comparison files
3. Run noaa_matcher.py     → assigns quality flags
4. Run coordinates.py      → adds pixel coordinates
 
Daily maintenance:
1. Run daily_scraper.py    → adds yesterday and today's new events
2. Run noaa_downloader.py  → downloads any new NOAA files
3. Run noaa_matcher.py     → updates quality flags
4. Run coordinates.py      → updates pixel coordinates
```
 
---
 
## API Endpoints
 
### `GET /events`
Returns filtered list of solar events.
 
**Query Parameters:**
| Parameter | Format | Example |
|-----------|--------|---------|
| `start_date` | YYYY-MM-DD | `2026-02-16` |
| `end_date` | YYYY-MM-DD | `2026-02-19` |
| `goes_class` | Letter prefix | `C` or `M` |
 
**Examples:**
```
http://localhost:8000/events
http://localhost:8000/events?goes_class=C
http://localhost:8000/events?start_date=2026-02-16&end_date=2026-02-19
http://localhost:8000/events?start_date=2026-02-16&goes_class=M
```
 
### `GET /events/{event_id}`
Returns a single event by ID.
 
```
http://localhost:8000/events/gev_20260216_1224
```
 
### `GET /events/download/`
Same filtering as `/events` but returns a downloadable `events.json` file.
 
```
http://localhost:8000/events/download/?goes_class=C
```
 
### `GET /scrape`
Triggers the daily scraper to run in the background and fetch new events.
 
```
http://localhost:8000/scrape
```
 
---
 
## Frontend Features
 
- **Filter by date range** — start and end date pickers
- **Filter by GOES class** — search input (e.g. `C`, `M`, `X`)
- **URL filtering** — filter by typing directly in the URL: `http://localhost:5173?goes_class=C`
- **Download CSV** — downloads currently filtered events as CSV
- **Download JSON** — downloads currently filtered events as JSON
- **Quality flag column** — shows HIGH/LOW data quality for each event
- **Solar image popup** — click any event name to view:
  - SDO/HMI Magnetogram from ISWA closest to event time (rounded to nearest 15 minutes)
  - Red dot plotted at the event's derived position on the solar disk
---
 
## Event Data Fields
 
Each event in `events.json` contains:
 
| Field | Description | Example |
|-------|-------------|---------|
| `event_id` | Unique event identifier | `gev_20260216_1224` |
| `event_start` | Start date and time | `2026/02/16 12:24:00` |
| `event_stop` | Stop time | `13:42:00` |
| `event_peak` | Peak time | `13:07:00` |
| `event_GOES` | GOES classification | `C1.0` |
| `event_position` | Derived heliographic position | `S18E10` |
| `seen_in_dates` | LMSAL snapshot URLs where event appeared | `[...]` |
| `quality_flag` | NOAA comparison result | `HIGH` or `LOW` |
| `pix_x` | X pixel coordinate on 512x512 image | `300.5` |
| `pix_y` | Y pixel coordinate on 512x512 image | `210.3` |
 
---
 
## Data Sources
 
| Source | URL | Description |
|--------|-----|-------------|
| LMSAL Archive | `https://www.lmsal.com/solarsoft/latest_events_archive.html` | Solar flare event snapshots |
| NOAA FTP | `ftp://ftp.swpc.noaa.gov/pub/indices/events` | Daily solar event reports |
| ISWA Images | `https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/observation/solar/sdo/hmi-magnetogram_2048x2048/` | SDO/HMI magnetogram images |
 
---
 
## Quality Flag Logic
 
Each LMSAL event is compared against NOAA/GOES XRA events for the same date:
 
```
HIGH quality → same date + begin time within ±10 minutes + same GOES class
LOW quality  → no match found, or missing GOES class or timestamps
```
 
NOAA data only includes `XRA` (X-Ray Activity) type events since those are the only ones with GOES classifications. Events with `////` (missing data) are automatically assigned `LOW` quality.
 
---
 
## Coordinate Conversion
 
Derived positions like `S11W04` mean:
- `S11` → 11 degrees south (negative latitude)
- `W04` → 4 degrees west (positive longitude)
These are converted to image pixel coordinates using heliographic coordinate transformation based on conversion code provided by the course instructor (Dr. Chetraj Pandey).
 
---
 
## Git Branches
 
| Branch | Description |
|--------|-------------|
| `main` | Stable base version |
| `imageFeature` | Helioviewer image integration (paused — API down) |
| `iswaImage` | ISWA image integration with position plotting |
| `asyncScraper` | Async scraping for faster data collection |
| `optimal_time_range` | Optimal window analysis for quality flags |
| `old_time_range` | Latest working branch with daily scraper |

 
