# Solar Events Dashboard
 
A full-stack web application for exploring, filtering, and visualizing solar flare events from LMSAL (Lockheed Martin Solar and Astrophysics Laboratory) with quality comparison against NOAA/GOES data and solar image visualization.
 
---
 
## Project Structure
 
```
LMSAL/
├── scraper.py            # One-time full scrape of all events from 2015 to present
├── daily_scraper.py      # Resumes from the newest event in events.json (run daily)
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
Resumes from the newest event already in `events.json` and scrapes every LMSAL snapshot from that date forward. Merges new events into the existing `events.json` without touching historical data.

Because the cutoff comes from the data rather than from today's date, a missed run heals itself: if the machine was asleep for six weeks, the next run scrapes all six weeks. No separate backfill step is needed.

All file paths resolve relative to the script's own folder, so it can be run from any working directory (cron runs jobs from `$HOME`).
 
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
| `HIGH` | NOAA event on the same date, same GOES class, begin times within `MATCH_WINDOW_MINUTES` |
| `LOW` | No such match found |
 
Only `XRA` (X-Ray Activity) type NOAA events are used since those are the only ones with GOES
classifications. See **Quality Flag Logic** below for what the flag does and does not measure, and
for how the window was derived.
 
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
 
## API Reference
 
Interactive documentation is served at `/docs` on any running instance.
 
### Endpoints
 
| Endpoint | Description |
|----------|-------------|
| `GET /` | Service info and endpoint index |
| `GET /stats` | Dataset summary — totals, date range, quality split, last update time |
| `GET /events` | Filtered event list (paginated) |
| `GET /events/{event_id}` | A single event, e.g. `gev_20260901_0054` |
| `GET /events/download/` | Same filters, returned as a file attachment with no row limit |
 
### Query parameters
 
Accepted by `/events` and `/events/download/`:
 
| Parameter | Example | Description |
|-----------|---------|-------------|
| `start_date` | `2026-04-01` | Events starting on or after this date |
| `end_date` | `2026-04-30` | Events starting on or before this date |
| `goes_class` | `M` or `C1` | GOES class prefix match |
| `quality_flag` | `HIGH` | Filter by NOAA cross-check result |
| `limit` | `500` | Rows per page — `/events` only, default 1000, max 30000 |
| `offset` | `1000` | Row to start from — `/events` only |
 
`/events` returns a plain JSON array, ordered newest first — so page 1 is the most recent data.
The total number of matching events, ignoring pagination, is returned in the `X-Total-Count`
response header.
 
### Examples
 
```bash
# every M-class flare in April 2026
curl "$API/events?start_date=2026-04-01&end_date=2026-04-30&goes_class=M"
 
# second page of 500
curl "$API/events?limit=500&offset=500"
 
# how many events match, without downloading them all
curl -sD - -o /dev/null "$API/events?goes_class=X&limit=1" | grep -i x-total-count
 
# the whole filtered set as a file
curl -OJ "$API/events/download/?quality_flag=HIGH"
```
 
```python
import httpx
 
events = httpx.get("$API/events", params={
    "start_date": "2026-01-01",
    "goes_class": "M",
    "limit": 5000,
}).json()
```
 
CORS is open, so the API can be called directly from browser-based tools and notebooks.
 
---
 
## Automated Daily Updates
 
`.github/workflows/daily-update.yml` runs the full pipeline every day at 06:00 UTC and commits
the refreshed data back to the repository. It can also be triggered by hand from the Actions tab.
 
The workflow refuses to commit if the event count ever drops, since the pipeline only ever adds
events — a decrease would mean something parsed wrong. A failed NOAA download does not fail the
run, because the next run retries every date still missing.
 
Because each update is a commit, the dataset is versioned: an analysis can be pinned to a specific
day's state of the data and reproduced later.
 
---
 
## Keeping the Database Up To Date
 
```
First time setup:
1. Run scraper.py          → builds full historical database (2015 to now)
2. Run noaa_downloader.py  → downloads NOAA comparison files
3. Run noaa_matcher.py     → assigns quality flags
4. Run coordinates.py      → adds pixel coordinates
 
Daily maintenance:
1. Run daily_scraper.py    → adds every event since the newest one on file
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
| `end_time_diff` | LMSAL stop minus NOAA end, in minutes; `null` when unavailable | `0` |
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
 
> ### What the flag actually measures
>
> **`HIGH` should not be read as "two independent sources agree."**
>
> Across matched pairs, begin times are identical to the minute in **99.2%** of cases, the mean
> offset is **−0.0001 minutes**, and end times agree exactly in **93.1%** of cases. Two independent
> detection pipelines — different instruments, different background subtraction, different onset
> criteria — do not produce agreement like that. The overwhelming likelihood is that LMSAL ingests
> NOAA's event list rather than deriving onset times independently.
>
> If so, `HIGH` means *"this LMSAL record was successfully matched back to the NOAA row it derives
> from"*. That is a **provenance and integrity check**, not independent confirmation of a flare. It
> is still a useful thing to measure — it detects transcription errors, dropped records and
> classification drift — but it cannot be cited as cross-instrument validation.
>
> Anyone using this dataset for that purpose should establish LMSAL's independence first.
 
Each LMSAL event is compared against NOAA/GOES XRA events for the same date:
 
```
HIGH quality → same date + begin time within ±10 minutes + same GOES class
LOW quality  → no match found, or missing GOES class or timestamps
```
 
NOAA data only includes `XRA` (X-Ray Activity) type events since those are the only ones with GOES classifications. Events with `////` (missing data) are automatically assigned `LOW` quality.
 
### Choosing the matching window
 
The window is derived from the lag distribution — the histogram of (LMSAL begin − NOAA begin) over
same-date, same-class pairs. That histogram is a mixture of real matches and chance coincidences, so
the chance rate has to be estimated before any excess can be judged significant.
 
**Estimating the chance rate.** An earlier version of this analysis used the analytic expectation
under a uniform circular time shift, `n_noaa × n_lmsal / 1440` = 16.222 pairs per lag. That is
wrong for this purpose: it shuffles all 23,360 pairs including the ~17,300 real ones, so it
redistributes signal into the background. It is inconsistent with the histogram it was applied to —
17,224 pairs sit at lag 0, leaving 6,136 across 1,439 non-zero lags, or 4.26 per lag, a factor of
3.8 below the subtracted value. The symptom was systematically *negative* excess from lag 3 outward,
which is impossible for a correctly estimated chance rate.
 
The background is instead estimated from the histogram's own signal-free region. It is not flat —
same-day flares cluster in time, so it rises toward small lags:
 
| \|lag\| band | pairs per lag |
|------------|---------------|
| 6–10 | 7.00 |
| 11–15 | 11.90 |
| 31–45 | 5.50 |
| 61–120 | 4.71 |
| 301–719 | 3.68 |
 
**Significance of the excess**, as z = (observed − background) / √background, under three
defensible background estimates:
 
| \|lag\| | observed | z @ 4.26/lag | z @ 6.0/lag | z @ 7.04/lag |
|-------|----------|--------------|-------------|--------------|
| 0 | 17,224 | 8339 | 7029 | 6489 |
| 1 | 96 | 30.0 | 24.2 | 21.8 |
| 2 | 43 | 11.8 | 8.9 | 7.7 |
| 3 | 32 | 8.0 | 5.8 | 4.8 |
| 4 | 22 | 4.6 | 2.9 | 2.1 |
| 5 | 10 | 0.5 | −0.6 | −1.1 |
 
Contiguous significance (z ≥ 3) runs through **lag 3** under the conservative background estimates
and **lag 4** under the global average. It breaks cleanly at lag 5 under all three.
 
**Signal coverage** (background 6.0/lag): 99.16% of detectable signal sits at lag 0, 99.65% within
±1, 99.83% within ±2, 99.94% within ±3.
 
**Why mean ± k·σ does not settle it.** The standard-deviation approach is degenerate for this
distribution. Because ~99% of the mass is a single spike at zero, σ of the background-subtracted
signal is 0.07–0.15 minutes depending on how far the tail is included. So mean ± 2σ is ±0.14 to
±0.30 minutes, which rounds to a **zero-minute** window, and reaching lag 3 would require k ≈ 20.
σ describes the width of the spike, not the extent of the tail — it is the wrong statistic for a
spike-plus-tail shape, and it does *not* agree with the significance-based answer.
 
**F1 and Youden's J are not an independent check.** Both are computed from the same TP/FP
decomposition, against ground truth defined by the matching rule itself, and with 99% of pairs at
lag 0 every window from 0 to 30 scores ≈0.998. They are one criterion viewed two ways and cannot
discriminate here.
 
**The data cannot pin this down, and that is the honest answer.** Judging whether a newly admitted
pair is genuine requires the chance-coincidence rate, and that rate is not a tight parameter.
Per-lag counts over \|lag\| 10–60 run Q1 4.0, median 6.0, Q3 9.0 (mean 7.04, range 1–21) — wider
than Poisson, because same-day flare clustering varies with activity level. The chosen window moves
with the estimate:
 
| background per ± pair | largest W where every admitted lag is >50% real |
|------------------------|--------------------------------------------------|
| 8.0 (Q1) | 4 |
| 12.0 (median) | 3 |
| 18.0 (Q3) | 2 |
 
By this analysis W = 2 is the largest value that holds under *every* estimate including the most
conservative, and any value in 1–4 is defensible.

**Current setting: `MATCH_WINDOW_MINUTES = 3`** (2026-09-14). Lag 3 is the largest lag whose excess
stays significant (z ≥ 3) under every background estimate above; lag 4 is marginal and lags 5–10 are
indistinguishable from chance. A `HIGH` flag claims both catalogues saw the same flare, so a false
`HIGH` is treated as costlier than a missed borderline match — which is why the original ±10 was
not kept (it was briefly restored on 2026-09-14 and reverted the same day).

When more than one same-class NOAA flare falls inside the window, the matcher pairs the event with
the **closest** begin time. It previously took the first candidate in file order, which left flags
correct but measured `end_time_diff` against the wrong flare (3 events at W ≤ 5, 13 at W = 10).
 
Two caveats on the method, both of which argue against over-claiming precision here. Non-monotonicity
shows the noise floor has been reached — lag 6 has 16 pairs against lag 5's 10, and real signal
decays while that does not. And "marginal precision >50%" and "z ≥ 3" are not independent criteria:
both are (observed − background) against the same estimate, so their agreement is arithmetic rather
than corroboration.
 
None of this is load-bearing: HIGH is 61.8% at W=1, 62.0% at W=2, 62.1% at W=3, 62.2% at W=4, and
62.4% at W=10. The window is not what determines the quality split.
 
Reproduce with `python window_optimization.py` and `python timing_analysis.py`. Both are read-only.
 
### What drives the LOW population
 
`LOW` is not measuring NOAA coverage gaps. NOAA files are present for **all 3,177** dates in
`events.json`, so no LMSAL event lacks a NOAA file entirely. Breaking the 10,687 LOW events down:
 
| Cause | Events | Share of LOW |
|-------|--------|--------------|
| No NOAA file on disk for that date | **0** | 0.0% |
| File present, no usable XRA row | 699 | 6.6% |
| XRA rows present, none of the same GOES class | **8,062** | **76.0%** |
| Same GOES class present, outside the time window | 1,851 | 17.4% |

File coverage is exactly complete — 3,177 LMSAL dates, 3,177 NOAA files, none missing in either
direction and no truncated downloads. 301 files (9.5%) contain no usable XRA row, and two are
zero-byte, left behind by an older version of the downloader's error path.
 
So `LOW` is dominated by **GOES class disagreement**, not timing. Widening the time window cannot
fix it: of the 1,926 LOW events that do have a same-class NOAA event that day, 70% are more than two
hours away — different flares, not timestamp disagreement. Only 165 events across every window from
0 to 30 minutes are recoverable by timing tolerance at all.
 
The 6.5% with no usable NOAA XRA data are a different condition — "no data available" rather than
"data available and disagreeing" — and arguably deserve their own flag value rather than being
folded into `LOW`.
 
### Why end times are recorded, not matched on
 
Matching uses begin time only. End times scatter roughly 45× wider than begin times
(sd 22.6 vs 0.48 minutes) because flare onset is an objective threshold crossing while the end
depends on each pipeline's decay criteria. Requiring end-time agreement would also be circular:
events where the two sources disagree would be excluded from the comparison rather than counted as
disagreements.
 
Instead each matched event stores `end_time_diff` — LMSAL stop minus NOAA end, in minutes — so
duration agreement is a reportable result. It is `null` for unmatched events, for events where NOAA
gives no end time, and for the 212 events whose `event_stop` crosses midnight (that field carries no
date, so the difference would be meaningless).
 
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

 
