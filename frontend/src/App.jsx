import { useState,useEffect } from "react";

function App(){
  const[events, setEvents] = useState([]) // a state variable (events) and updated it by setEvents
  const[startDate, setStartDate] = useState('')
  const[endDate, setEndDate] = useState('')
  const[goes_class, setGoesClass] = useState('')
  const[selectedEvent, setSelectedEvent] = useState(null)
  const[imageURL, setImageURL] = useState(null)


const fetchEvents = () => { 
  let url = "http://localhost:8000/events"

  if(startDate && endDate){
    url += `?start_date=${startDate}&end_date=${endDate}`
  }
  if(goes_class){
    url += url.includes('?') ? `&goes_class=${goes_class}` : `?goes_class=${goes_class}`
  }
  fetch(url)
    .then(res => res.json())
    .then(data => {setEvents(data)})
  
}

// to figure out which telescope source id to use
const getSourceId = (eventStart) => { 
  const date = eventStart.slice(0, 10).replace(/\//g, '-')

  // this information is based on the time + photo quality + different telescopes.
  const preferredSources = [
    {id: 9, start: "2010-06-02", end: "2026-12-31"},
    {id: 2001, start: "2022-06-15", end: "2026-12-31"},
    {id: 1, start: "1996-01-15", end: "2026-01-21"},
  ]     

  for(let source of preferredSources){
    if(date >= source.start && date <= source.end){ // if it stays in range, then the source is still active
      return source.id
    }
  }
  return 9 //make this default
}

// to reformat the date so that we could call the helioviewer api
const helioDate = (eventStart) =>{
    return eventStart.replace(/\//g, '-').replace(' ', 'T') + 'Z'
}

// download feature
const downloadCSV = () => {
  const headers = ["event_id", "event_start", "event_stop", "event_peak", "event_goes", "event_position"]
  const rows = events.map(event => [
    event.event_id, event.event_start, 
    event.event_stop, event.event_peak, 
    event.event_GOES, event.event_position].join(',')
  )
  const CSVcontent = [headers.join(','), ...rows].join("\n")

  const blob = new Blob([CSVcontent], {type: 'text/csv'})
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'events.csv'
  link.click()
}

const downloadJSON = () => {

  const JSONcontent = JSON.stringify(events)

  const blob = new Blob([JSONcontent], {type: 'text/json'})
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'events.json'
  link.click()
}

// const imageFetch = (event) => {
//   setSelectedEvent(event)

//   const sourceId = getSourceId(event.event_start)
//   const date = helioDate(event.event_start)

//   const imageURL = `https://api.helioviewer.org/v2/getJP2Image/?date=${date}&sourceId=${sourceId}`
//   setImageURL(imageURL)
// }

const imageFetch = async (event) => {
  setSelectedEvent(event)
  const date = helioDate(event.event_start)

  const response = await fetch(`https://api.helioviewer.org/v2/takeScreenshot/?date=${date}&imageScale=5&layers=[SDO,AIA,AIA,171,1,100]&x0=0&y0=0&width=512&height=512`) // [Observatory, Instrument, Detector, Measurement, Visible, Opacity]

  const data = await response.json()
  setImageURL(`https://api.helioviewer.org/v2/downloadScreenshot/?id=${data.id}`)
}

useEffect(()=>{
  fetchEvents()
}, [])

  // useEffect( () =>{ // runs when the page loads // change the image jp2 into png so that i can pop up 
  //   fetch("http://localhost:8000/events") //to call the fastapi backend
  //   .then(res => res.json()) // converts the response into json format
  //   .then(data => setEvents(data)) //save the events into state
  // },[])

  return(
    <div>
      <h1>Solar Events Dashboard</h1>
      <p>Total unique events: {events.length}</p>
      {/* <label>Start date</label> */}
      <input type="date" onChange={e => setStartDate(e.target.value)} />
      {/* <label>End date</label> */}
      <input type="date" onChange={e=> setEndDate(e.target.value)} />
      {/* <label>Search for GOES class</label> */}
      <input type="search" onChange={e=> setGoesClass(e.target.value)}/>
      <button onClick={fetchEvents}>Filter</button>
      <button onClick={downloadCSV}>Download CSV</button>
      <button onClick={downloadJSON}>Download JSON</button>
      <table>
        <thead>
          <tr>
            <th>Event name</th>
            <th>Start</th>
            <th>Stop</th>
            <th>Peak</th>
            <th>GOES class</th>
            <th>Derived Position</th>
          </tr>
        </thead>
        <tbody>
          {events.map(event =>( //for every event in events, loop through to map each items into its corresponding rows
            <tr key = {event.event_id}>
              <td  onClick={() => imageFetch(event)} style = {{cursor: 'pointer'}}>{event.event_id}</td>
              <td>{event.event_start}</td>
              <td>{event.event_stop}</td>
              <td>{event.event_peak}</td>
              <td>{event.event_GOES}</td>
              <td>{event.event_position}</td>
            </tr>
          ))}
        </tbody>
      </table>

    {selectedEvent && (
      <div style={{position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', display: "flex", justifyContent :'center',alignItems: 'center', zIndex: 1000 }}>
        <div style={{backgroundColor: 'white', padding: '20px', borderRadius: '10px', maxWidth: '600px', width: '90%'}}>
          <button onClick={()=> setSelectedEvent(null)}>X close</button>
          <h2>{selectedEvent.event_id}</h2>
          <p>Start: {selectedEvent.event_start}</p>
          <p>GOES class:{selectedEvent.event_GOES} </p>
          <p>Position: {selectedEvent.event_position}</p>
          {imageURL && <img src={imageURL} style={{width: '100%'}}></img>}
        </div>
      </div>
    )}

    </div>
  )
}
export default App