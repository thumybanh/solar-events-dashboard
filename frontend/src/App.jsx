import { useState,useEffect } from "react";

const API_BASE = "http://localhost:8000"
const PAGE_SIZE = 100 // rendering all ~28k rows at once locks up the browser

// ~280 pages at 100 rows each, so show a sliding window of numbers instead of all of them
function Pagination({page, total, pageSize, onChange}){
  const pageCount = Math.ceil(total / pageSize)
  if(pageCount <= 1) return null

  const windowSize = 5
  let first = Math.max(0, page - Math.floor(windowSize / 2))
  const last = Math.min(pageCount, first + windowSize)
  first = Math.max(0, last - windowSize)
  const numbers = Array.from({length: last - first}, (_, i) => first + i)

  return (
    <div className="pagination">
      <button onClick={() => onChange(0)} disabled={page === 0}>« First</button>
      <button onClick={() => onChange(page - 1)} disabled={page === 0}>‹ Prev</button>

      {numbers.map(n => (
        <button
          key={n}
          onClick={() => onChange(n)}
          className={n === page ? 'active' : ''}
        >{n + 1}</button>
      ))}

      <button onClick={() => onChange(page + 1)} disabled={page >= pageCount - 1}>Next ›</button>
      <button onClick={() => onChange(pageCount - 1)} disabled={page >= pageCount - 1}>Last »</button>
      <span className="page-count">Page {page + 1} of {pageCount.toLocaleString()}</span>
    </div>
  )
}

function App(){
  const[events, setEvents] = useState([]) // a state variable (events) and updated it by setEvents
  const[total, setTotal] = useState(0) // how many events match the current filters, across all pages
  const[page, setPage] = useState(0)
  const[appliedFilters, setAppliedFilters] = useState({}) // only updates when Filter is clicked
  const[startDate, setStartDate] = useState('')
  const[endDate, setEndDate] = useState('')
  const[goes_class, setGoesClass] = useState('')
  const[selectedEvent, setSelectedEvent] = useState(null)
  const[imageURL, setImageURL] = useState(null)


// URLSearchParams builds the query string properly — the old version chained multiple "?"
// and broke whenever both dates were set
const buildParams = (filters) => {
  const params = new URLSearchParams()
  if(filters.startDate) params.set('start_date', filters.startDate)
  if(filters.endDate) params.set('end_date', filters.endDate)
  if(filters.goes_class) params.set('goes_class', filters.goes_class)
  return params
}

const fetchEvents = (filters, pageNumber) => {
  const params = buildParams(filters)
  params.set('limit', PAGE_SIZE)
  params.set('offset', pageNumber * PAGE_SIZE)

  fetch(`${API_BASE}/events?${params}`)
    .then(res => {
      // the API reports the unpaginated total in a header so the body stays a plain array
      setTotal(Number(res.headers.get('X-Total-Count')) || 0)
      return res.json()
    })
    .then(data => {setEvents(data)})
}

const applyFilters = () => {
  setPage(0)
  setAppliedFilters({startDate, endDate, goes_class})
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
// const helioDate = (eventStart) =>{
//     return eventStart.replace(/\//g, '-').replace(' ', 'T') + 'Z'
// }


// download feature
// downloads pull the full filtered set from the API, not just the page on screen
const fetchAllFiltered = () => {
  return fetch(`${API_BASE}/events/download/?${buildParams(appliedFilters)}`)
    .then(res => res.json())
}

const saveFile = (content, type, filename) => {
  const blob = new Blob([content], {type})
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

const downloadCSV = () => {
  fetchAllFiltered().then(allEvents => {
    const headers = ["event_id", "event_start", "event_stop", "event_peak", "event_goes", "event_position"]
    const rows = allEvents.map(event => [
      event.event_id, event.event_start,
      event.event_stop, event.event_peak,
      event.event_GOES, event.event_position].join(',')
    )
    const CSVcontent = [headers.join(','), ...rows].join("\n")
    saveFile(CSVcontent, 'text/csv', 'events.csv')
  })
}

const downloadJSON = () => {
  fetchAllFiltered().then(allEvents => {
    saveFile(JSON.stringify(allEvents), 'text/json', 'events.json')
  })
}

// const imageFetch = (event) => {
//   setSelectedEvent(event)

//   const sourceId = getSourceId(event.event_start)
//   const date = helioDate(event.event_start)

//   const imageURL = `https://api.helioviewer.org/v2/getJP2Image/?date=${date}&sourceId=${sourceId}`
//   setImageURL(imageURL)
// }

///////////////// HELIOVIEWER API /////////////////////////
// const imageFetch = async (event) => {
//   setSelectedEvent(event)
//   const date = helioDate(event.event_start)

//   const response = await fetch(`https://api.helioviewer.org/v2/takeScreenshot/?date=${date}&imageScale=5&layers=[SDO,AIA,AIA,171,1,100]&x0=0&y0=0&width=512&height=512`) // [Observatory, Instrument, Detector, Measurement, Visible, Opacity]

//   const data = await response.json()
//   setImageURL(`https://api.helioviewer.org/v2/downloadScreenshot/?id=${data.id}`)
// }
///////////////////////////////////////////////////////////


//////// ISWA VERSION ///////////
const imageFetch = (event) => {
  setSelectedEvent(event)
  const year = event.event_id.substring(4,8)
  const month = event.event_id.substring(8,10)
  const hour = event.event_id.substring(13,15)
  const minute = event.event_id.substring(15,17)
  const full_date = event.event_id.substring(4,12)

  const minuteConvert = Math.round(parseInt(minute) / 15) * 15
  let full_time = ''
  if (minuteConvert == 60){
      const addHour = parseInt(hour) + 1
      full_time = String(addHour).padStart(2,'0') + '00'
  } 
  else {
    full_time = hour + String(minuteConvert).padStart(2,'0')
  }

  setImageURL(`https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/observation/solar/sdo/hmi-magnetogram_2048x2048/${year}/${month}/${full_date}_${full_time}00_2048_HMIB.jpg`) // [Observatory, Instrument, Detector, Measurement, Visible, Opacity]
}

// refetch on first load, when a new filter is applied, and when the page changes
useEffect(()=>{
  fetchEvents(appliedFilters, page)
}, [appliedFilters, page])

  // useEffect( () =>{ // runs when the page loads // change the image jp2 into png so that i can pop up 
  //   fetch("http://localhost:8000/events") //to call the fastapi backend
  //   .then(res => res.json()) // converts the response into json format
  //   .then(data => setEvents(data)) //save the events into state
  // },[])

  return(
    <div>
      <h1>Solar Events Dashboard</h1>
      <p>
        Total unique events: {total.toLocaleString()}
        {total > 0 && ` — showing ${(page * PAGE_SIZE + 1).toLocaleString()}–${Math.min((page + 1) * PAGE_SIZE, total).toLocaleString()}`}
      </p>
      {/* <label>Start date</label> */}
      <input type="date" onChange={e => setStartDate(e.target.value)} />
      {/* <label>End date</label> */}
      <input type="date" onChange={e=> setEndDate(e.target.value)} />
      {/* <label>Search for GOES class</label> */}
      <input type="search" className="goes-input" placeholder="Filter by GOES class" onChange={e=> setGoesClass(e.target.value)}/>
      <button onClick={applyFilters}>Filter</button>
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
            <th>Quality Flag</th>
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
              <td>{event.quality_flag}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <Pagination page={page} total={total} pageSize={PAGE_SIZE} onChange={setPage} />

    {selectedEvent && (
      <div style={{position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(0,0,0,0.7)', display: "flex", justifyContent :'center',alignItems: 'center', zIndex: 1000 }}>
        <div style={{backgroundColor: 'white', padding: '20px', borderRadius: '10px', maxWidth: '600px', width: '90%'}}>
          <button onClick={()=> setSelectedEvent(null)}>X close</button>
          <h2>{selectedEvent.event_id}</h2>
          <p>Start: {selectedEvent.event_start}</p>
          <p>GOES class:{selectedEvent.event_GOES} </p>
          <p>Position: {selectedEvent.event_position}</p>
          {imageURL && 
          <div style ={{position: 'relative', width : '600px', height: '600px'}}>
          <img src={imageURL} style={{width: '100%'}} />
          <div style={{
            position: 'absolute',
            left: selectedEvent.pix_x * (600/512),
            top: selectedEvent.pix_y * (600/512),
            width : '10px',
            height: '10px',
            borderRadius: '50%',
            backgroundColor: 'red'
          }}></div>

    </div>}
        </div>
        
      </div>
    )}

    

    </div>
  )
}
export default App