import ftplib
import json
import os
with open('events.json', 'r') as r: 
    events = json.load(r)
    dates = set()
    for event in events: 
        eventDate = event['event_start'][:10].replace('/', '')
        dates.add(eventDate)
print(dates)

ftp = ftplib.FTP('ftp.swpc.noaa.gov')
ftp.login() #anonymous login 
print(ftp.getwelcome())

ftp.cwd('pub/indices/events')

os.makedirs('noaa_data', exist_ok=True) # create a new directory/folder 'noaa_data' to contains file. if the folder is existed then it wont crash when the program create a new one
for date in dates:
    fileName = f'{date}events.txt'
    filePath = f'noaa_data/{fileName}'
    if os.path.exists(filePath):
        continue
    try:
        with open(filePath, 'wb') as n:
            ftp.retrbinary(f'RETR {fileName}', n.write)
    except ftplib.error_perm:
        os.remove(filePath)

    


