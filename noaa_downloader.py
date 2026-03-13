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
    with open(f'noaa_data/{fileName}', 'wb') as n: 
        ftp.retrbinary(f'RETR {fileName}', n.write)

    


