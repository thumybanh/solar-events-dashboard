import json
from fastapi import FastAPI

app = FastAPI()

@app.get('/')
def home():
    return{"message:":"Solar events API is running."}

@app.get('/events')
def get_events(start_date: str = None, end_date: str = None):
    with open('events.json', 'r') as f:
        events = json.load(f)

    # to check the range of dates where the gev appears. 
    if start_date and end_date : 
        events = [e for e in events if start_date <= e['event_start'] >= end_date]

    return events

@app.get('/events/{event_id}')
def get_event(event_id: str):
    with open('events.json', 'r') as f:
        events = json.load(f)

    for event in events: 
        if event["event_id"] == event_id:
            return event
        
    return {"error": "Event not found"}