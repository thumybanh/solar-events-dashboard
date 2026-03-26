# Solar Events Dashboard

A full-stack web application for exploring, filtering, and visualizing solar flare events from LMSAL (Lockheed Martin Solar and Astrophysics Laboratory) with quality comparison against NOAA data.

---

## Project Structure

```
LMSAL/
├── scraper.py            # Scrapes solar events from LMSAL archive
├── api.py                # FastAPI backend — serves event data
├── noaa_downloader.py    # Downloads NOAA event txt files via FTP
├── noaa_matcher.py       # Parses NOAA data + assigns quality flags
├── coordinates.py        # Converts derived position to pixel coordinates
├── events.json           # Scraped + processed event database
├── noaa_data/            # Downloaded NOAA txt files
└── frontend/
    └── src/
        └── App.jsx       # React frontend dashboard
```

---

## Installation

### Python Dependencies

```bash
pip install httpx beautifulsoup4 fastapi uvicorn
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
python -m uvicorn api:app --reload
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

### 1. Scrape LMSAL Events
```bash
python scraper.py
```
Scrapes solar flare events from the LMSAL archive starting from July 1, 2015. Saves unique events to `events.json` and merges with existing data on subsequent runs.

### 2. Download NOAA Data
```bash
python noaa_downloader.py
```
Connects to the NOAA FTP server (`ftp.swpc.noaa.gov`) and downloads event txt files for each date present in `events.json`. Files saved to `noaa_data/`.

### 3. Match & Assign Quality Flags
```bash
python noaa_matcher.py
```
Parses NOAA txt files and compares each LMSAL event against NOAA data. Assigns a `quality_flag` field to each event:
- `HIGH` — matching event found within ±10 minutes with same GOES class
- `LOW` — no matching event found, or missing data

### 4. Calculate Pixel Coordinates
```bash
python coordinates.py
```
Converts each event's `Derived Position` (e.g. `S11W04`) to pixel coordinates (`pix_x`, `pix_y`) on a 512x512 solar image using heliographic coordinate conversion.

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

### `GET /events/download/`
Same filtering as `/events` but returns a downloadable `events.json` file.

```
http://localhost:8000/events/download/?goes_class=C
```

---

## Frontend Features

- **Filter by date range** — start and end date pickers
- **Filter by GOES class** — search input (e.g. `C`, `M`, `X`)
- **URL filtering** — filter by typing directly in the URL: `http://localhost:5173?goes_class=C`
- **Download CSV** — downloads currently filtered events as CSV
- **Download JSON** — downloads currently filtered events as JSON
- **Solar image popup** — click any event name to view:
  - Solar image from ISWA (SDO/HMI Magnetogram) closest to event time
  - Red dot plotted at the event's derived position on the solar disk
- **Quality flag column** — shows HIGH/LOW data quality for each event

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
| ISWA Images | `https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/observation/solar/sdo/hmi-magnetogram_2048x2048/` | SDO/HMI solar images |

---

## Quality Flag Logic

Each LMSAL event is compared against NOAA data for the same date:

```
HIGH quality → NOAA match found within ±10 minutes AND same GOES class
LOW quality  → no match found, missing GOES class, or missing timestamps
```

NOAA data only includes `XRA` (X-Ray Activity) type events since those are the only ones with GOES classifications.

---

## Coordinate Conversion

Derived positions like `S11W04` are converted to pixel coordinates using heliographic coordinate transformation:

```
HGS (lat/lon degrees)
    → HCC (Heliocentric, meters)
    → HPC (Helioprojective, arcseconds)
    → Pixel coordinates (512x512 space)
```

Based on coordinate conversion code provided by the course instructor.

