import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.lmsal.com/solarsoft"
INDEX_URL = "https://www.lmsal.com/solarsoft/latest_events_archive.html"

# this is from the main website, where they have links for each snapshot per day. 
response = httpx.get(INDEX_URL)
soup = BeautifulSoup(response.text, 'html.parser')

links = []
for a_tag in soup.find_all('a'):
    href = a_tag.get('href')
    if href and "last_events" in href:
        full_url = BASE_URL + '/' + href
        links.append(full_url)

first_snapshot_url = links[0]
print("Fetching ", first_snapshot_url)


# this is within each day snapshot, where there will be links of gev names. 
snapshot_response = httpx.get(first_snapshot_url)
snapshot_soup = BeautifulSoup(snapshot_response.text, 'html.parser')

all_tables = snapshot_soup.find_all('table')


# from this loop, I found the table we need is table four. 
# for i, table in enumerate(all_tables):
#     first_row = table.find('tr')
#     print(f"Table {i}: {first_row.get_text(strip=True)[:100]}")

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
        print(event)
        i += 6 #Jump forward to the next gev. 
    else:
        i += 1 #if not detected "gev", then it will move on