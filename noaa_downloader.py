import ftplib
import json
import os

# absolute paths so this works from any working directory (cron and CI runners)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_PATH = os.path.join(BASE_DIR, 'events.json')
NOAA_DIR = os.path.join(BASE_DIR, 'noaa_data')

FTP_HOST = 'ftp.swpc.noaa.gov'
FTP_DIR = 'pub/indices/events'


def event_dates():
    with open(EVENTS_PATH, 'r') as r:
        events = json.load(r)
    return {event['event_start'][:10].replace('/', '') for event in events}


def download_missing():
    dates = event_dates()

    # create a new directory/folder 'noaa_data' to contain the files. if the folder already exists
    # then it won't crash when the program creates a new one
    os.makedirs(NOAA_DIR, exist_ok=True)

    missing = sorted(d for d in dates if not os.path.exists(os.path.join(NOAA_DIR, f'{d}events.txt')))
    print(f"{len(dates)} dates in events.json, {len(missing)} missing locally")
    if not missing:
        return 0

    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login() #anonymous login
    print(ftp.getwelcome())
    ftp.cwd(FTP_DIR)

    downloaded = 0
    unavailable = 0
    try:
        for date in missing:
            fileName = f'{date}events.txt'
            finalPath = os.path.join(NOAA_DIR, fileName)
            # download to a .part file first — if the connection drops mid-transfer, a truncated
            # file would otherwise sit there looking complete and never be retried
            partPath = finalPath + '.part'
            try:
                with open(partPath, 'wb') as n:
                    ftp.retrbinary(f'RETR {fileName}', n.write)
            except ftplib.error_perm:
                # NOAA has no report for this date (quiet day, or before their archive starts)
                os.remove(partPath)
                unavailable += 1
                continue
            except Exception as e:
                # connection dropped or timed out — leave the date missing so the next run retries it
                if os.path.exists(partPath):
                    os.remove(partPath)
                print(f"stopping early at {date}: {e}")
                break
            os.replace(partPath, finalPath)
            downloaded += 1
    finally:
        try:
            ftp.quit()
        except Exception:
            pass

    print(f"downloaded {downloaded}, unavailable on NOAA {unavailable}")
    return downloaded


if __name__ == '__main__':
    download_missing()
