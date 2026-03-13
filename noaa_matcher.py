# ways to filter: 
# 1. only accept XRA type flare 
# 2. if empty / no information then replace it with null. if null then immediately low qulality

import json
import os 

noaa_list = [] 
def parse_noaa_file(fileName):
        noaa_events = [] 
        with open(fileName, 'r') as r: 
            datas = r.readlines()
            for data in datas: 
                if data.startswith('#'):
                    continue
                splitData = data.split()
                if "XRA" in splitData: 
                    XRAindex = splitData.index('XRA')
                    dateFull = os.path.basename(fileName).split('events.')
                    date = dateFull[0]
                    begin = splitData[XRAindex - 5] if splitData[XRAindex - 5] != '////' else None
                    peak = splitData[XRAindex - 4] if splitData[XRAindex - 4] != '////' else None
                    end = splitData[XRAindex - 3] if splitData[XRAindex - 3] != '////' else None
                    goes_class = splitData[XRAindex + 2] if splitData[XRAindex + 2] != '////' else None

                    noaa_event = {
                        'date': date,
                        'begin': begin,
                        'peak': peak,
                        'end': end,
                        'goes_class': goes_class
                    }
                    noaa_events.append(noaa_event)
        return noaa_events

    
for fileName in os.listdir('noaa_data'):
    results = parse_noaa_file(os.path.join('noaa_data', fileName))
    noaa_list.extend(results) # use extend because 'extend' add each item individually -> flat list instead of adds whole list as one item like append

print(f"Total NOAA events: {len(noaa_list)}")
print(noaa_list[:3])

LMSAL_list = []
def match_events() : 
     LMSAL_events = []
     with open('events.json', 'r') as f: 
        events = json.load(f)
        for event in events: 
                LMSALdate = event['event_start'].split(' ')[0].replace('/','')
                LMSALstart = event['event_start'].split(' ')[1].replace(':','')[:4]
                LMSALpeak = event['event_peak'].replace(':', '')[:4]
                LMSALend = event['event_stop'].replace(':','')[:4]
                LMSALGOES = event['event_GOES'] 

                event['quality_flag'] = 'LOW'

                for NOAA_event in noaa_list: 
                    if NOAA_event['date'] is not None:
                        same_date = NOAA_event['date'] == LMSALdate 
                    else: continue

                    if NOAA_event['begin'] is not None and NOAA_event['end'] is not None: 
                        time_start_diff = abs(int(NOAA_event['begin']) - int(LMSALstart))
                        time_end_diff = abs(int(NOAA_event['end']) - int(LMSALend))
                    else: continue

                    if NOAA_event['goes_class'] is not None: 
                        same_class = NOAA_event['goes_class'] == LMSALGOES
                    else : continue

                    if same_date and time_start_diff <= 10 and time_end_diff <=10 and same_class : 
                         event['quality_flag'] = 'HIGH'
                         break # already found high, therefore stop    
                LMSAL_events.append(event)
        return LMSAL_events
     
LMSAL_list.extend(match_events())


with open('events.json', 'w') as f: 
     json.dump(LMSAL_list, f, indent=2)


                    



        
        
        