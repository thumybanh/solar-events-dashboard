import ftplib
import io
import os
import tarfile
from datetime import date, timedelta

# absolute paths so this works from any working directory (cron and CI runners)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOAA_DIR = os.path.join(BASE_DIR, 'noaa_data')
# dates NOAA has no report for, even in its yearly archive — kept so we don't re-download
# a whole year's archive every run just to find the same day still missing
UNAVAILABLE_PATH = os.path.join(BASE_DIR, 'noaa_unavailable.txt')

FTP_HOST = 'ftp.swpc.noaa.gov'
FTP_DIR = 'pub/indices/events'   # one file per day, but only from 2015-06-29 onward
WAREHOUSE_DIR = 'pub/warehouse'  # <year>/<year>_events.tar.gz for older years

NOAA_START = date(1996, 7, 31)   # oldest daily event report NOAA has


def all_dates():
    """Every calendar day from NOAA_START up to yesterday, as YYYYMMDD.

    We fetch by calendar rather than only the days LMSAL has events on, so days that
    only one of the two sources reported still show up when comparing them."""
    day, last = NOAA_START, date.today() - timedelta(days=1)
    while day <= last:
        yield day.strftime('%Y%m%d')
        day += timedelta(days=1)


def load_unavailable():
    try:
        with open(UNAVAILABLE_PATH, 'r') as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()


def save_unavailable(unavailable):
    with open(UNAVAILABLE_PATH, 'w') as f:
        f.write('\n'.join(sorted(unavailable)) + '\n')


def local_path(d):
    return os.path.join(NOAA_DIR, f'{d}events.txt')


def fetch_archive_year(ftp, year, wanted):
    """Download <year>_events.tar.gz and unpack the wanted days into noaa_data. Returns how many were written."""
    archive = io.BytesIO()
    ftp.retrbinary(f'RETR /{WAREHOUSE_DIR}/{year}/{year}_events.tar.gz', archive.write)
    archive.seek(0)

    written = 0
    with tarfile.open(fileobj=archive, mode='r:gz') as tar:
        for member in tar.getmembers():
            name = os.path.basename(member.name)
            d = name.replace('events.txt', '')
            if not member.isfile() or d not in wanted:
                continue
            # write to a .part file first so a crash can't leave a truncated file looking complete
            partPath = local_path(d) + '.part'
            with open(partPath, 'wb') as n:
                n.write(tar.extractfile(member).read())
            os.replace(partPath, local_path(d))
            written += 1
    return written


def download_missing():
    # create a new directory/folder 'noaa_data' to contain the files. if the folder already exists
    # then it won't crash when the program creates a new one
    os.makedirs(NOAA_DIR, exist_ok=True)

    unavailable = load_unavailable()
    dates = list(all_dates())
    missing = [d for d in dates if d not in unavailable and not os.path.exists(local_path(d))]
    print(f"{len(dates)} days since {NOAA_START}, {len(missing)} missing locally")
    if not missing:
        return 0

    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login() #anonymous login
    print(ftp.getwelcome())

    downloaded = 0
    try:
        # days in the daily folder are fetched one by one, everything older comes from the yearly archive
        daily = set(ftp.nlst(FTP_DIR))
        daily = {os.path.basename(p) for p in daily}

        by_year = {}
        for d in missing:
            if f'{d}events.txt' not in daily:
                by_year.setdefault(d[:4], set()).add(d)

        for year, wanted in sorted(by_year.items()):
            try:
                written = fetch_archive_year(ftp, year, wanted)
            except ftplib.error_perm:
                # no archive for this year yet (e.g. the current year) — try again next run
                print(f"{year}: no archive on NOAA")
                continue
            except Exception as e:
                # connection dropped or timed out — leave the dates missing so the next run retries them
                print(f"stopping early at {year} archive: {e}")
                break
            downloaded += written
            # anything the archive didn't have, NOAA doesn't have at all
            gone = {d for d in wanted if not os.path.exists(local_path(d))}
            unavailable |= gone
            print(f"{year}: {written} days from archive, {len(gone)} not in archive")

        ftp.cwd('/' + FTP_DIR)
        for d in missing:
            fileName = f'{d}events.txt'
            if fileName not in daily or os.path.exists(local_path(d)):
                continue
            finalPath = local_path(d)
            # download to a .part file first — if the connection drops mid-transfer, a truncated
            # file would otherwise sit there looking complete and never be retried
            partPath = finalPath + '.part'
            try:
                with open(partPath, 'wb') as n:
                    ftp.retrbinary(f'RETR {fileName}', n.write)
            except Exception as e:
                # connection dropped or timed out — leave the date missing so the next run retries it
                if os.path.exists(partPath):
                    os.remove(partPath)
                print(f"stopping early at {d}: {e}")
                break
            os.replace(partPath, finalPath)
            downloaded += 1
    finally:
        save_unavailable(unavailable)
        try:
            ftp.quit()
        except Exception:
            pass

    print(f"downloaded {downloaded}, {len(unavailable)} days NOAA has no report for")
    return downloaded


if __name__ == '__main__':
    download_missing()
