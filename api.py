import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# allows react to talk to this api layer since they both have different port
app.add_middleware(
    CORSMiddleware, 
    allow_origins = ['http://localhost:5173'], # trust this origin
    allow_methods = ['*'], #allow all requests from this 5173 port (GET,POST,ETC)
    allow_headers = ['*'], #allow all headers
)

@app.get('/')
def home():
    return{"message:":"Solar events API is running."}

@app.get('/events')
def get_events(start_date: str = None, end_date: str = None):
    with open('events.json', 'r') as f:
        events = json.load(f)

    # to check the range of dates where the gev appears. 
    if start_date and end_date : 
        events = [e for e in events if start_date.replace('-', '/') <= e['event_start'] <= end_date.replace('-', '/')] # the datepicker in the js is formatted with "-" but the json format is with "/" so we need to replace it

    return events

@app.get('/events/{event_id}')
def get_event(event_id: str):
    with open('events.json', 'r') as f:
        events = json.load(f)

    for event in events: 
        if event["event_id"] == event_id:
            return event
        
    return {"error": "Event not found"}
