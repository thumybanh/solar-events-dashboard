# Records, for every LMSAL event, the link to its own page on LMSAL's site (provenance).
#
# LMSAL changed how it addresses event pages over the years (relative gev_*.html next to the
# snapshot early on, events_summary/YYYY/MM/DD/gev_*/index.html later, with gaps in both), so the
# address can't be built from the ID. Instead we keep the link exactly as the snapshot page that
# listed the event gives it.
#
# The scraper calls event_links() as it reads each snapshot. Run this file to backfill events that
# don't have a link yet; it only fetches snapshots for those, so it is cheap once caught up.

import json
import os
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup


GEV_RE = re.compile(r'gev_\d{8}_\d{4}')


def event_links(html, snapshot_url):
    """{gev_id: absolute https link} for each event linked on a snapshot page; first link per event wins."""
    links = {}
    for a in BeautifulSoup(html, 'html.parser').find_all('a', href=True):
        href = a['href']
        match = GEV_RE.search(href)
        # the event's own page, not its thumbnails or movies
        if not match or not re.search(r'(\.html?|/)$', href.split('?')[0]):
            continue
        url = urljoin(snapshot_url, href).replace('http://', 'https://', 1)
        links.setdefault(match.group(0), url)
    return links


def backfill(events, fetch, pause=0.2):
    """Adds event_url to events that lack it, reading each needed snapshot page once."""
    missing = {e['event_id']: e for e in events if not e.get('event_url')}
    pages = {}
    for event in missing.values():
        for snapshot in event.get('seen_in_dates') or []:
            pages.setdefault(snapshot, set()).add(event['event_id'])
    for n, (snapshot, ids) in enumerate(pages.items(), 1):
        if all(missing[i].get('event_url') for i in ids):
            continue  # already found on an earlier snapshot
        try:
            links = event_links(fetch(snapshot), snapshot)
        except Exception as e:  # one unreachable page shouldn't stop the rest
            print(f'skipping {snapshot} - {e}')
            continue
        for event_id in ids:
            if event_id in links and not missing[event_id].get('event_url'):
                missing[event_id]['event_url'] = links[event_id]
        if n % 200 == 0:
            print(f'{n}/{len(pages)} snapshot pages read')
        time.sleep(pause)  # be polite to LMSAL's server
    return sum(1 for e in missing.values() if e.get('event_url'))


if __name__ == '__main__':
    import httpx

    from scraper import EVENTS_PATH  # scraper imports this module, so not at the top

    with open(EVENTS_PATH) as f:
        events = json.load(f)

    def fetch(url):
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        return response.text

    found = backfill(events, fetch)
    with open(EVENTS_PATH + '.tmp', 'w') as f:
        json.dump(events, f, indent=2)
    os.replace(EVENTS_PATH + '.tmp', EVENTS_PATH)
    print(f"added {found} event links; {sum(1 for e in events if not e.get('event_url'))} events still without one")
