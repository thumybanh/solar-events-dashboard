import httpx
from bs4 import BeautifulSoup
import json
import os


BASE_URL = "https://www.lmsal.com/solarsoft"
INDEX_URL = "https://www.lmsal.com/solarsoft/latest_events_archive.html"

# absolute paths so the scripts work from any working directory (cron runs them from $HOME)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')
EVENTS_PATH = os.path.join(DATA_DIR, 'events.json')

ARCHIVE_START = '20020926' # first LMSAL event (gev_20020926_1140); oldest snapshot is 20021001


def load_events():
    try:
        with open(EVENTS_PATH, 'r') as f:
            existing = json.load(f)
        return {e['event_id']: e for e in existing}
    except FileNotFoundError:
        return {}


def save_events(all_events):
    # write to a temp file first, then swap it in — a crash mid-write can't truncate events.json
    tmp_path = EVENTS_PATH + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(list(all_events.values()), f, indent=2)
    os.replace(tmp_path, EVENTS_PATH)


def scrape_range(cutoff):
    """Scrape every archive snapshot dated on or after cutoff (YYYYMMDD) and merge into events.json."""
    all_events = load_events()
    before = len(all_events)

    # this is from the main website, where they have links for each snapshot per day.
    response = httpx.get(INDEX_URL, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')

    links = []
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if href and "last_events_" in href:
            date = href.split('last_events_')[1][:8]
            if date >= cutoff:
                links.append(BASE_URL + '/' + href)

    print(f"{len(links)} snapshots on or after {cutoff}")

    skipped = 0
    for n, snapshot_url in enumerate(links, 1):

        # save every 200 snapshots so a crash on a long backfill doesn't lose everything
        if n % 200 == 0:
            print(f"{n}/{len(links)} snapshots, {len(all_events)} events so far")
            save_events(all_events)

    # this is within each day snapshot, where there will be links of gev names.
        try:
            snapshot_response = httpx.get(snapshot_url, timeout=30)
        except Exception as e:
            print(f"skipping {snapshot_url} - {e}")
            skipped += 1
            continue
        if snapshot_response.status_code != 200:
            print(f"skipping {snapshot_url} - HTTP {snapshot_response.status_code}")
            skipped += 1
            continue
        snapshot_soup = BeautifulSoup(snapshot_response.text, 'html.parser')

        all_tables = snapshot_soup.find_all('table')

    # the event table is the one with gev_ names AND a position column. the position column is named
    # differently over the years ("Derived Position (EIT High Cadence Wavelength)", "Derived Position
    # (SXI-GOES12 or ...)", plain "Derived Position"), but the columns are always in the same order.
    # some pages also have note/caption tables that quote a gev_ row or even the header, so take
    # the matching table with the most gev_ rows. pages with no such table (gaps in the archive,
    # broken snapshots) are skipped.
        events_table = None
        most_events = 0
        for table in all_tables:
            cells = [cell.get_text(' ', strip=True) for cell in table.find_all(['th', 'td'])]
            n_events = sum(c.startswith('gev_') for c in cells)
            if n_events > most_events and any(c.startswith('Derived Position') for c in cells):
                events_table = table
                most_events = n_events
        if events_table is None:
            print(f"skipping {snapshot_url} - no event table")
            skipped += 1
            continue

        all_cells = events_table.find_all('td')
        all_texts = [cell.get_text(strip=True) for cell in all_cells]

        i = 0
        while(i < len(all_texts)):
            if all_texts[i].startswith('gev_'):
                event = {
                    "event_id": all_texts[i],
                    "event_start": all_texts[i+1],
                    "event_stop": all_texts[i+2],
                    "event_peak": all_texts[i+3],
                    "event_GOES": all_texts[i+4],
                    "event_position": all_texts[i+5]
                }
                if all_texts[i] not in all_events:
                    # First time seeing this event — add it with seen_in_dates
                    event["seen_in_dates"] = [snapshot_url] #adding a new field into the event{}
                    all_events[all_texts[i]] = event

                else:
                    # Already seen — append this snapshot to seen_in_dates unless it's already listed
                    if snapshot_url not in all_events[all_texts[i]]["seen_in_dates"]:
                        all_events[all_texts[i]]["seen_in_dates"].append(snapshot_url)

                i += 6 #Jump forward to the next gev.
            else:
                i += 1 #if not detected "gev", then it will move on

    print(f"Total unique events: {len(all_events)} (+{len(all_events) - before} new), {skipped} snapshots skipped")

    save_events(all_events)

    print(f"saved to {EVENTS_PATH}")
    return all_events


def run_scraper():
    return scrape_range(ARCHIVE_START)


if __name__ == '__main__':
    run_scraper()
