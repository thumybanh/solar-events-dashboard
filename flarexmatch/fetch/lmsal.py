import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

from flarexmatch.fetch import storage
from flarexmatch.fetch.storage import EVENTS_PATH, load_events, save_events


BASE_URL = "https://www.lmsal.com/solarsoft"
INDEX_URL = "https://www.lmsal.com/solarsoft/latest_events_archive.html"

ARCHIVE_START = '20150701' # oldest snapshot we care about


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

    for snapshot_url in links:

    # this is within each day snapshot, where there will be links of gev names.
        try:
            snapshot_response = httpx.get(snapshot_url, timeout=30)
        except Exception as e:
            print(f"skipping {snapshot_url} - {e}")
            continue
        snapshot_soup = BeautifulSoup(snapshot_response.text, 'html.parser')

        all_tables = snapshot_soup.find_all('table')

    # some older snapshot pages might be structured differently (like have fewer tables), therefore we skip those
        events_table = None
        for table in all_tables:
            if 'gev_' in table.get_text():
                events_table = table
                break
        if events_table is None:
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

    print(f"Total unique events: {len(all_events)} (+{len(all_events) - before} new)")

    save_events(all_events)

    print(f"saved to {EVENTS_PATH}")
    return all_events


def run_scraper():
    return scrape_range(ARCHIVE_START)


def latest_event_date():
    """Newest event date already in events.json, as YYYYMMDD, or None if there is nothing yet."""
    all_events = load_events()
    dates = [e['event_start'][:10].replace('/', '') for e in all_events.values() if e.get('event_start')]
    return max(dates) if dates else None


def run_daily_scraper():
    # resume from the newest event we already have, so a missed run (laptop asleep, cron error)
    # heals itself on the next run instead of leaving a permanent hole in events.json
    cutoff = latest_event_date()

    if cutoff is None:
        # empty database — fall back to the full archive
        cutoff = ARCHIVE_START
    else:
        # a snapshot page can list events from the previous day, so step back one day
        cutoff = (datetime.strptime(cutoff, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')

    print(f"resuming from {cutoff}")
    return scrape_range(cutoff)


def main():
    """Console-script entry point for flarexmatch-lmsal.

    Deliberately returns None: run_daily_scraper() returns the event mapping, and a
    console script's return value becomes the process exit code, so a successful
    run would exit non-zero.
    """
    run_daily_scraper()


if __name__ == '__main__':
    main()
