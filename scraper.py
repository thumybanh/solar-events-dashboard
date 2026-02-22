import httpx
from bs4 import BeautifulSoup
import json

BASE_URL = "https://www.lmsal.com/solarsoft"
INDEX_URL = "https://www.lmsal.com/solarsoft/latest_events_archive.html"

# this is from the main website, where they have links for each snapshot per day. 
response = httpx.get(INDEX_URL, timeout=10)
soup = BeautifulSoup(response.text, 'html.parser')

links = []
for a_tag in soup.find_all('a'):
    href = a_tag.get('href')
    if href and "last_events" in href:
        full_url = BASE_URL + '/' + href
        links.append(full_url)
links = links[:50] #limit to only 50 links to test


# first_snapshot_url = links[0]
all_events = {}

for snapshot_url in links: 

# this is within each day snapshot, where there will be links of gev names. 
    try: 
        snapshot_response = httpx.get(snapshot_url, timeout=10)
    except Exception as e:
        print(f"skipping {snapshot_url} - {e}")
        continue
    snapshot_soup = BeautifulSoup(snapshot_response.text, 'html.parser')

    all_tables = snapshot_soup.find_all('table')


# from this loop, I found the table we need is table four. 
# for i, table in enumerate(all_tables):
#     first_row = table.find('tr')
#     print(f"Table {i}: {first_row.get_text(strip=True)[:100]}")

# some older snapshot pages might be structure differently (like have fewer tables), therefore we skip those
    if len(all_tables) < 5:
        continue

    events_table = all_tables[4]
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
                # Already seen — just append this snapshot to seen_in_dates
                all_events[all_texts[i]]["seen_in_dates"].append(snapshot_url)

            i += 6 #Jump forward to the next gev. 
        else:
            i += 1 #if not detected "gev", then it will move on
                
print(f"Total unique events: {len(all_events)}")
for event in all_events.values():
    print(event)

with open('events.json', 'w') as f:
    json.dump(list(all_events.values()), f, indent = 2)

print("saved to events.json")