# Working Notes — 2026-09-03

Session record: what changed, what was found, and what is still undecided.
Everything below is **uncommitted** in the working tree unless noted.

---

## 1. Root cause of the stale data

The crontab entry ran `daily_scraper.py` from `$HOME`, because cron does not run jobs from the
script's directory. The scripts used bare relative paths (`'events.json'`), so every nightly run
since April read and wrote `/Users/mybanh/events.json` — not the repo copy. A bare `except:`
swallowed the missing-file error, so each run silently started from an empty database.

The repo's `events.json` had been frozen at 2026-07-21 the whole time.

**Fixed:** all scripts now resolve paths from `__file__`. The crontab entry itself needs no edit.

## 2. Data recovered

| Source | Events |
|---|---|
| Starting point | 27,053 |
| Backfilled 2026-07-22 → 09-01 | +431 |
| Rescued from the stray `~/events.json` | +512 |
| **Total** | **27,996** |

The 512 rescued events came from LMSAL snapshots that have since been dropped from its archive
index — they were unrecoverable by re-scraping and survived only because the broken cron happened
to capture them. The stray file was verified fully absorbed, then deleted.

## 3. Code changes

| File | Change |
|---|---|
| `scraper.py` | absolute paths; shared `scrape_range(cutoff)`; atomic writes via `.tmp` + `os.replace`; `except:` narrowed; no duplicate `seen_in_dates` |
| `daily_scraper.py` | resumes from the newest event on file, so a missed run self-heals over any gap |
| `noaa_downloader.py` | absolute paths; downloads to `.part` and renames on success (a dropped connection used to leave a truncated file that looked complete and was never retried) |
| `noaa_matcher.py` | restored `convert_position` (was missing — `coordinates.py` had been crashing); NOAA rows indexed by date (~120s → 1s); write moved under `__main__` |
| `coordinates.py` | handles the one event with a blank position |
| `api.py` | pagination, open CORS, `/scrape` behind `SCRAPE_TOKEN`, in-memory cache, `/stats`, newest-first ordering, route-order and info-leak fixes |
| `frontend/src/App.jsx` | page controls; date-range filter fixed (chained `?` params produced a malformed URL); downloads now fetch the full filtered set rather than the visible page |
| `.github/workflows/daily-update.yml` | new — daily pipeline run, refuses to commit if the event count drops |

**Matching logic was not altered.** Verified: 27,053 shared events, 0 flag changes, HIGH 3,490 → 3,490.

---

## 4. Findings that need your decision

### 4a. End-time comparison — RESOLVED 2026-09-03

Both issues below are now fixed. Reading A was adopted: matching uses **begin time + GOES class**
within the derived window (see 4b), and the end-time comparison is recorded as `end_time_diff`
rather than used as a gate.

| Stage | HIGH | % |
|---|---|---|
| Original | 3,617 | 12.9% |
| After fixing `HHMM` → real minutes | 4,174 | 14.9% |
| After adopting Reading A (±10) | 17,464 | 62.4% |
| After deriving the window (±1) | 17,309 | 61.8% |
| Window ±3 + closest-match pairing (2026-09-14, 28,101 events) | **17,457** | **62.1%** |

13,290 events moved LOW → HIGH; **zero** moved HIGH → LOW, which is the expected direction when a
wrongly restrictive gate is removed. All raw fields and pixel coordinates verified unchanged.

`end_time_diff` is recorded on 17,097 events: 93.1% agree exactly, 98.3% within 10 minutes,
sd 22.2 min. It is `null` for matched events whose `event_stop` crosses midnight.

The original problem, for the record:

`noaa_matcher.py` compares NOAA's **end** time against LMSAL's **start** time:

```python
time_start_diff = abs(int(NOAA begin) - int(LMSALstart))
time_end_diff   = abs(int(NOAA end)   - int(LMSALstart))   # should be LMSALend
```

`LMSALend` is computed one line earlier and never used. Since most flares last longer than 10
minutes, this rejects nearly every valid match.

The README described the intended rule as "same date + begin time within ±10 minutes + same GOES
class" — no end-time condition at all. The code was stricter than the written spec.

Times were also compared as raw `HHMM` integers, so any gap crossing an hour boundary was
overstated: 13:01 and 12:59 are 2 minutes apart but `1301 - 1259 = 42`. Now converted to minutes
since midnight via `to_minutes()`.

### 4b. Matching window — derivation corrected 2026-09-03, choice NOT final

The original ±10 was arbitrary. Two successive attempts to derive it were both flawed; the third is
below. `MATCH_WINDOW_MINUTES = 1` is the current working value and is **narrower than the corrected
analysis supports**.

**Attempt 1 (wrong).** Argued ±10 was fine because it admits only 0.18% ambiguous matches. That is a
plausibility argument, not an optimisation.

**Attempt 2 (wrong).** Estimated the chance-coincidence background as the analytic expectation under
a uniform circular time shift, `n_noaa x n_lmsal / 1440` = 16.222 pairs per lag. Two errors:

- The null shuffles all 23,360 pairs including the ~17,300 real ones, so signal is redistributed into
  the background. It answers "what if nothing were real", not "what is the chance component of a
  histogram containing real signal".
- It is arithmetically inconsistent with its own histogram: 17,224 pairs sit at lag 0, leaving 6,136
  over 1,439 non-zero lags = 4.26 per lag, a factor of **3.8** below the subtracted value.
- Diagnostic that should have caught it immediately: excess was systematically *negative* from lag 3
  outward (ratio 0.23-0.43). A correctly estimated chance rate cannot sit above the observed counts
  everywhere.

An earlier iteration of the same null also excluded shifts under 30 minutes, which left a background
deficit at exactly the small lags being measured and manufactured a spurious signal tail out to 25
minutes.

**Attempt 3 (current).** Background estimated from the histogram's own signal-free region. It is not
flat — same-day flares cluster in time, so it rises toward small lags: 3.68 per lag at |lag| 301-719,
4.71 at 61-120, 5.50 at 31-45, 7.00 at 6-10.

z = (observed - background) / sqrt(background), under three defensible background estimates:

| \|lag\| | observed | z @ 4.26 | z @ 6.0 | z @ 7.04 |
|-------|----------|----------|---------|----------|
| 0 | 17,224 | 8339 | 7029 | 6489 |
| 1 | 96 | 30.0 | 24.2 | 21.8 |
| 2 | 43 | 11.8 | 8.9 | 7.7 |
| 3 | 32 | 8.0 | 5.8 | 4.8 |
| 4 | 22 | 4.6 | 2.9 | 2.1 |
| 5 | 10 | 0.5 | -0.6 | -1.1 |

**Contiguous significance runs through lag 3** under the conservative estimates and lag 4 under the
global average, breaking cleanly at lag 5 in all three. Signal coverage: 99.16% at lag 0, 99.65%
within +/-1, 99.83% within +/-2, 99.94% within +/-3.

**Update 2026-09-14: window set to W = 3.** Briefly set to 10 the same day (restoring the original
±10), then reverted: lags 5-10 are indistinguishable from chance, and a false HIGH is costlier than a
missed borderline match. 3 is the largest lag significant (z >= 3) under every background estimate
in the table below. It is one wider than the ">50% real under every estimate" criterion (W = 2).

Also fixed the same day: the matcher now pairs with the **closest** same-class NOAA begin inside the
window instead of the first in file order. The old rule never changed a flag, but put
`end_time_diff` against the wrong flare on 3 events at W <= 5 and 13 at W = 10.

**W = 2, applied 2026-09-03. The data cannot narrow this further.**

The window is decided by the chance-coincidence background, and that background is not a tight
parameter: per-lag counts over |lag| 10-60 give Q1 4.0, median 6.0, Q3 9.0 (mean 7.04, range 1-21),
wider than Poisson because clustering varies with activity level. The chosen W moves with it —
4 at Q1, 3 at median, 2 at Q3. **W = 2 is the largest value holding under every estimate.**
Any value in 1-4 is defensible; HIGH spans 61.8%-62.2%.

HIGH = 17,352 (62.0%), LOW = 10,644.

Two method caveats recorded so they are not re-litigated:
- "marginal precision >50%" and "z >= 3" are NOT independent criteria. Both are
  (observed - background) against the same estimate; agreement between them is arithmetic.
- Non-monotonicity marks the noise floor: lag 6 has 16 pairs vs lag 5's 10. Real signal decays.

Arithmetic corrections: widening 1->4 recovers **61** real matches at the median background, not the
65 previously stated - that figure summed lags 2,3,4,5,6 and used max(excess, 0), which clipped lag
5's -2 to zero. Clipping negative excursions is exactly how a phantom signal tail gets manufactured;
all totals now sum raw excess.

**Retracted claim: "three independent criteria agree" was false.**

- *mean +/- k*sd does not agree.* sd of the background-subtracted signal is 0.07-0.15 min depending on
  how much tail is included, so mean +/- 2sd is +/-0.14 to +/-0.30 min, rounding to a **0-minute** window.
  Reaching lag 3 needs k ~ 20. sd measures the width of the spike, not the extent of the tail, and is
  the wrong statistic for a spike-plus-tail shape.
- *An earlier sd of 0.4314 min was an artifact.* With background 16.222, two lags near |lag| ~ 300
  where noise pushed the count above the background were counted as signal and, weighted by lag^2,
  contributed **94.5%** of the variance.
- *F1 and Youden's J are not independent of each other.* Both derive from the same TP/FP
  decomposition, against ground truth defined by the matching rule itself, and with ~99% of pairs at
  lag 0 every window from 0 to 30 scores about 0.998. One criterion viewed two ways.
- *The total-conservation check validated nothing.* A circular shift cannot create or destroy pairs,
  so 23,360 = 23,360 holds by construction whether or not the model is right. Removed.

Every window from 0 to 30 minutes gives 61.5%-63.0% HIGH, so the headline figure is robust to the
choice. Reproduce with `python window_optimization.py` (read-only).

### 4c. Duplicate NOAA files

3,507 of 6,684 files in `noaa_data/` are duplicate copies — `events 2.txt`, `events 3.txt`,
`events 4.txt` — byte-identical to the originals. Their dates parse to garbage, so they never
matched anything and **your flags were never affected**. They would be committed daily by the new
workflow.

**Not deleted.**

### 4d. LOW is not measuring NOAA coverage gaps

Checked per LOW event whether `noaa_data/` holds a file for that date. NOAA files exist for **all
3,177** dates in `events.json` — zero LMSAL events fall on a date with no NOAA file. Breakdown of the
10,687 LOW events:

Verified at the file level: 3,177 LMSAL dates, 3,177 NOAA files, **zero** missing in either
direction, no leftover `.part` files, no truncated downloads. The 550-error concern is empirically
nil. Two files are zero-byte (`20150627`, `20150628`), left by an older version of the downloader's
error path.

| Cause | Events | Share |
|---|---|---|
| **A — no NOAA file on disk** | **0** | **0.0%** |
| B — file present, no usable XRA row | 699 | 6.6% |
| C — XRA rows present, none of the same GOES class | **8,062** | **76.0%** |
| D — same class, outside the time window | 1,851 | 17.4% |

The partition is exhaustive and sums to 10,644. 301 of 3,177 files (9.5%) hold no usable XRA row.

Of that last group, the distance to the nearest same-class NOAA event is: 43 at 2 min, 32 at 3, 22 at
4, 10 at 5, 48 at 6-10, 96 at 11-20, 66 at 21-30, 103 at 31-60, 155 at 61-120, and **1,351 beyond two
hours**. So 70% are different flares, not timestamp disagreement, and no window can legitimately
capture them.

LOW is dominated by **GOES class disagreement**, not timing or coverage. The 6.5% with no usable NOAA
XRA data are a genuinely different condition and arguably need their own flag value ("no data
available") rather than being folded into LOW. 301 of the 3,177 NOAA files contain no usable XRA row.

**Not implemented — needs a decision on flag semantics.**

### 4e. Unreconciled: HIGH percentage denominator

Reported figure is 17,309 / 27,996 = **61.8%**. A figure of 65.3% implies a denominator of 26,512,
which does not correspond to any population reproducible from this data — all events, events with a
parseable start time, events with a GOES class, and events on dates with a NOAA file all give 27,996.
**Needs clarification on what 26,512 refers to.**

---

## 5. Still to do

1. Commit (nothing has been committed; suggested split: pipeline fixes / API + frontend / automation)
2. Push — the workflow cannot run until it is on GitHub
3. Pick a host — Railway is dead (404). Render free tier: start command
   `uvicorn api:app --host 0.0.0.0 --port $PORT`
4. Point `API_BASE` in `frontend/src/App.jsx` at the deployed URL
5. Set `SCRAPE_TOKEN` in the host's env if `/scrape` should be reachable remotely
6. Decide on 4c (duplicate files), 4d (flag semantics for the 699), 4e (denominator)

## 6. Running it locally

```bash
# backend
/opt/miniconda3/bin/python -m uvicorn api:app --port 8000 --reload
# frontend
cd frontend && npm run dev
```

Pipeline order: `daily_scraper.py` → `noaa_downloader.py` → `noaa_matcher.py` → `coordinates.py`
