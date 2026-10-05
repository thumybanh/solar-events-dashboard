# Keeps data/goes_sciquality/ on the newest NCEI science-quality GOES flare report.
#
# NCEI republishes the whole report as one CSV whose name carries its end date
# (sci_xrsf-l2-flrpt_geo_s19950103_e20260929_v1-0-1.csv), so "update" means: find the newest name
# in the directory listing, download it, and swap it in only if it looks like a complete report.
# A failure leaves yesterday's file in place, the same way a missed NOAA download is harmless.

import csv
import glob
import os
import re
import sys

from noaa_matcher import DATA_DIR

SQ_DIR = os.path.join(DATA_DIR, 'goes_sciquality')
LISTING_URL = ('https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/'
               'l2/data/xrsf-l2-flrpt_science/csv/')
NAME_RE = re.compile(r'sci_xrsf-l2-flrpt_geo_s\d{8}_e(\d{8})_v[\d-]+\.csv')


def pick_newest(listing_html):
    names = set(m.group(0) for m in NAME_RE.finditer(listing_html))
    return max(names, key=lambda n: NAME_RE.fullmatch(n).group(1)) if names else None


def current_file():
    files = glob.glob(os.path.join(SQ_DIR, 'sci_xrsf-l2-flrpt_geo_*.csv'))
    return max(files, key=lambda p: NAME_RE.fullmatch(os.path.basename(p)).group(1)) if files else None


def _header_and_rows(path):
    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        return header, sum(1 for _ in reader)


def is_acceptable(new_path, old_path):
    """A download replaces the old report only if it has the same columns and no fewer flares."""
    new_header, new_rows = _header_and_rows(new_path)
    if not new_header or new_rows == 0:
        return False
    if old_path is None:
        return True
    old_header, old_rows = _header_and_rows(old_path)
    return new_header == old_header and new_rows >= old_rows


def main():
    import httpx

    old = current_file()
    try:
        name = pick_newest(httpx.get(LISTING_URL, timeout=60, follow_redirects=True).text)
        if name is None:
            print('No SciQuality report found in the NCEI listing; keeping the current file.')
            return
        if old and os.path.basename(old) == name:
            print(f'{name} is already the newest report.')
            return
        target = os.path.join(SQ_DIR, name)
        with httpx.stream('GET', LISTING_URL + name, timeout=300, follow_redirects=True) as response:
            response.raise_for_status()
            with open(target + '.part', 'wb') as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)
    except Exception as e:  # network trouble must not fail the daily run
        print(f'SciQuality download failed ({e}); keeping the current file.')
        return

    if not is_acceptable(target + '.part', old):
        os.remove(target + '.part')
        print(f'{name} has a different header or fewer flares than {old}; keeping the current file.')
        return
    os.replace(target + '.part', target)
    if old and old != target:
        os.remove(old)
    print(f'Updated SciQuality report to {name}')


if __name__ == '__main__':
    sys.exit(main())
