import { useState,useEffect } from "react";

function App(){
  const[events, setEvents] = useState([]) // a state variable (events) and updated it by setEvents

  useEffect( () =>{ // runs when the page loads
    fetch("http://localhost:8000/events") //to call the fastapi backend
    .then(res => res.json()) // converts the response into json format
    .then(data => setEvents(data)) //save the events into state
  },[])

  return(
    <div>
      <h1>Solar Events Dashboard</h1>
      <p>Total unique events: {events.length}</p>

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
            <tr>
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