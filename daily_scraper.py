from datetime import datetime, timedelta

from scraper import scrape_range, load_events, ARCHIVE_START


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


if __name__ == '__main__':
    run_daily_scraper()
