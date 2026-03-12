import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

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
def get_events(start_date: str = None, end_date: str = None, goes_class: str = None):
    with open('events.json', 'r') as f:
        events = json.load(f)

    # to check the range of dates where the gev appears. 
    # if start_date and end_date: 
    #     events = [e for e in events if start_date.replace('-', '/') <= e['event_start'] <= end_date.replace('-', '/')] # the datepicker in the js is formatted with "-" but the json format is with "/" so we need to replace it
    if start_date: 
         events = [e for e in events if e['event_start'] >= start_date.replace('-', '/')]
    if end_date: 
        events = [e for e in events if e['even_start'] <= end_date.replace('-', '/')]
    if goes_class: 
        events = [e for e in events if e['event_GOES'].startswith(goes_class)]
    return events

@app.get('/events/{event_id}')
def get_event(event_id: str):
    with open('events.json', 'r') as f:
        events = json.load(f)

    for event in events: 
        if event["event_id"] == event_id:
            return event
        
    return {"error": "Event not found"}


@app.get('/events/download/')
def download_events(start_date: str = None, end_date: str = None, goes_class: str = None):
    with open('events.json', 'r') as f:
        events = json.load(f)

    if start_date: 
         events = [e for e in events if e['event_start'] >= start_date.replace('-', '/')]
    if end_date: 
         events = [e for e in events if e['event_start'] <= end_date.replace('-', '/')]
    if goes_class: 
        events = [e for e in events if e['event_GOES'].startswith(goes_class)]

    return Response(
        content=json.dumps(events),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=events.json"}
    )
