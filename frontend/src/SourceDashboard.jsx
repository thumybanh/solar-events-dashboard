import { useEffect, useState } from 'react'
import { getJSON, downloadURL } from './api.js'
import { SOURCES, cell, flagHelp } from './sources.js'

const PAGE_SIZE = 100 // rendering all ~50k rows at once locks up the browser

// ~500 pages at 100 rows each, so show a sliding window of numbers instead of all of them
function Pagination({page, total, onChange}){
  const pageCount = Math.ceil(total / PAGE_SIZE)
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
        <button key={n} onClick={() => onChange(n)} className={n === page ? 'active' : ''}>{n + 1}</button>
      ))}
      <button onClick={() => onChange(page + 1)} disabled={page >= pageCount - 1}>Next ›</button>
      <button onClick={() => onChange(pageCount - 1)} disabled={page >= pageCount - 1}>Last »</button>
      <span className="page-count">Page {page + 1} of {pageCount.toLocaleString()}</span>
    </div>
  )
}

// ISWA keeps an HMI magnetogram every 15 minutes, so round the flare time to the nearest one.
// Done with a UTC Date so 23:53 rounds to 00:00 the next day instead of an hour "24".
const imageFor = (time) => {
  const [date, clock = '00:00'] = time.replace(/\//g, '-').split(' ')
  const [y, m, d] = date.split('-').map(Number)
  const [h, min] = clock.split(':').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d, h, Math.round(min / 15) * 15))
  const pad = (n) => String(n).padStart(2, '0')
  const ymd = `${t.getUTCFullYear()}${pad(t.getUTCMonth() + 1)}${pad(t.getUTCDate())}`
  return `https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/observation/solar/sdo/hmi-magnetogram_2048x2048/` +
    `${t.getUTCFullYear()}/${pad(t.getUTCMonth() + 1)}/${ymd}_${pad(t.getUTCHours())}${pad(t.getUTCMinutes())}00_2048_HMIB.jpg`
}

function FlarePopup({event, source, onClose}){
  const hasDot = event.pix_x !== null && event.pix_x !== undefined
  const time = source.imageTime(event)
  return (
    <div className="overlay" onClick={onClose}>
      <div className="popup" onClick={e => e.stopPropagation()} role="dialog" aria-label={event.event_id}>
        <button className="close" onClick={onClose}>✕ Close</button>
        <h2>{event.event_id}</h2>
        <dl className="details">
          {source.columns.filter(c => c.key !== 'event_id').map(c => (
            <div key={c.key}><dt>{c.label}</dt><dd>{cell(event, c)}</dd></div>
          ))}
          {source.hasFlag && event.quality_flag && <p className="flag-help">{flagHelp(event.quality_flag)}</p>}
        </dl>
        {time ? (
          <div className="sun">
            <img src={imageFor(time)} alt={`SDO/HMI magnetogram near ${time}`} />
            {/* pix_x/pix_y are on a 512 px image, so place the dot by percentage and it scales with the picture */}
            {hasDot && <span className="dot" style={{left: `${event.pix_x / 512 * 100}%`, top: `${event.pix_y / 512 * 100}%`}} />}
          </div>
        ) : <p className="muted">No time recorded, so no image.</p>}
        {!hasDot && <p className="muted">No location recorded for this flare, so it isn't marked on the image.</p>}
      </div>
    </div>
  )
}

const toCSV = (events, columns) => {
  // quote every value: positions and IDs never contain commas today, but a quote-safe file costs nothing
  const quote = (text) => `"${String(text).replace(/"/g, '""')}"`
  const rows = events.map(e => columns.map(c => quote(cell(e, c))).join(','))
  return [columns.map(c => quote(c.label)).join(','), ...rows].join('\n')
}

const saveFile = (content, type, filename) => {
  const url = URL.createObjectURL(new Blob([content], {type}))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

const apiFilters = (filters) => ({
  start_date: filters.start, end_date: filters.end, goes_class: filters.class,
  active_region: filters.ar, quality_flag: filters.flag,
})

export default function SourceDashboard({sourceKey, filters, page, onApply, onPage, onCompare}){
  const source = SOURCES[sourceKey]
  const [draft, setDraft] = useState(filters) // what's typed; only applied when Filter is clicked
  const [result, setResult] = useState(null)  // {key, events, total} or {key, error}
  const [selected, setSelected] = useState(null)
  const [downloadError, setDownloadError] = useState(null)

  // loading is "the result on screen is for an older request", so no setState is needed to start a fetch
  const requestKey = JSON.stringify([sourceKey, filters, page])
  const loading = result?.key !== requestKey

  useEffect(() => {
    const controller = new AbortController()
    const params = {...apiFilters(filters), limit: PAGE_SIZE, offset: page * PAGE_SIZE}
    getJSON(`${source.path}/events`, params, controller.signal)
      .then(({data, total}) => setResult({key: requestKey, events: data, total}))
      .catch(err => { if (err.name !== 'AbortError') setResult({key: requestKey, error: err.message}) })
    return () => controller.abort()
  }, [requestKey, source.path, filters, page])

  const set = (key) => (e) => setDraft({...draft, [key]: e.target.value})
  const apply = (e) => { e.preventDefault(); onApply(draft) }

  // downloads pull the full filtered set from the API, not just the page on screen
  const download = (kind) => {
    setDownloadError(null)
    fetch(downloadURL(`${source.path}/events/download`, apiFilters(filters)))
      .then(res => res.ok ? res.json() : Promise.reject(new Error(`The API answered ${res.status}`)))
      .then(all => kind === 'csv'
        ? saveFile(toCSV(all, source.columns), 'text/csv', `${sourceKey}_events.csv`)
        : saveFile(JSON.stringify(all), 'application/json', `${sourceKey}_events.json`))
      .catch(err => setDownloadError(err.message))
  }

  const total = result?.total || 0
  const error = !loading && result?.error

  return (
    <section>
      <p className="about">{source.about}</p>
      <form className="filters" onSubmit={apply}>
        <label>From <input type="date" value={draft.start || ''} onChange={set('start')} /></label>
        <label>To <input type="date" value={draft.end || ''} onChange={set('end')} /></label>
        <label>GOES class <input className="short" placeholder="X, M1, C2.5" value={draft.class || ''} onChange={set('class')} /></label>
        <label>Active region <input className="short" placeholder="13664" value={draft.ar || ''} onChange={set('ar')} /></label>
        {source.hasFlag && (
          <label>Flag
            <select value={draft.flag || ''} onChange={set('flag')}>
              <option value="">Any</option>
              <option>HIGH</option><option>LOW</option><option>N/A</option>
            </select>
          </label>
        )}
        <button type="submit" className="primary">Filter</button>
        <button type="button" onClick={() => onCompare(filters)}>Compare these →</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}

      <div className="toolbar">
        <span>
          {loading ? 'Loading…' : error ? '' : total === 0 ? 'No flares match these filters.' :
            `${total.toLocaleString()} flares — showing ${(page * PAGE_SIZE + 1).toLocaleString()}–${Math.min((page + 1) * PAGE_SIZE, total).toLocaleString()}`}
        </span>
        <span>
          <button onClick={() => download('csv')} disabled={!total}>Download CSV</button>
          <button onClick={() => download('json')} disabled={!total}>Download JSON</button>
        </span>
      </div>
      {downloadError && <p className="error" role="alert">{downloadError}</p>}

      <div className="table-wrap">
        <table className={loading ? 'stale' : ''}>
          <thead>
            <tr>{source.columns.map(c => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {(result?.events || []).map(event => (
              <tr key={event.event_id}>
                {source.columns.map(c => c.key === 'event_id'
                  ? <td key={c.key}><button className="link" onClick={() => setSelected(event)}>{event.event_id}</button></td>
                  : <td key={c.key} className={cell(event, c) === 'N/A' ? 'na' : ''} title={c.key === 'quality_flag' ? flagHelp(event.quality_flag) : undefined}>{cell(event, c)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination page={page} total={total} onChange={onPage} />
      {selected && <FlarePopup event={selected} source={source} onClose={() => setSelected(null)} />}
    </section>
  )
}
