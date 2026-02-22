import { useState,useEffect } from "react";

function App(){
  const[events, setEvents] = useState([]) // a state variable (events) and updated it by setEvents
  const[startDate, setStartDate] = useState('')
  const[endDate, setEndDate] = useState('')


const fetchEvents = () => {
  let url = "http://localhost:8000/events"


  if(startDate && endDate){
    url += `?start_date=${startDate}&end_date=${endDate}`
  }
  console.log("Fetching URL:", url)
  fetch(url)
    .then(res => res.json())
    .then(data => setEvents(data))
}

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

      <input type="date" onChange={e => setStartDate(e.target.value)} />
      <input type="date" onChange={e=> setEndDate(e.target.value)} />
      <button onClick={fetchEvents}>Filter</button>
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