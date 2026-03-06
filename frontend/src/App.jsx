import { useState,useEffect } from "react";


function App(){
  const[events, setEvents] = useState([]) // a state variable (events) and updated it by setEvents
  const[startDate, setStartDate] = useState('')
  const[endDate, setEndDate] = useState('')
  const[goes_class, setGoesClass] = useState('')


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

// const imageURL = `https://api.helioviewer.org/v2/getJP2Image/?date=${date}&sourceId=${sourceId}`



useEffect(()=>{
  fetchEvents()
}, [])

  // useEffect( () =>{ // runs when the page loads
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
              <td>{event.event_id}</td>
              <td>{event.event_start}</td>
              <td>{event.event_stop}</td>
              <td>{event.event_peak}</td>
              <td>{event.event_GOES}</td>
              <td>{event.event_position}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
export default App