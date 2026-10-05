import { useEffect, useRef, useState } from 'react'
import CompareChart from './CompareChart.jsx'
import { getJSON } from './api.js'
import { SERIES, SOURCE_KEYS } from './chartStyle.js'
import { toCSV } from './compareData.js'

const ALL_SOURCES = Object.values(SOURCE_KEYS)

const saveFile = (content, type, filename) => {
  const url = URL.createObjectURL(new Blob([content], {type}))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

// a range that doesn't start or end on a bin boundary has a partial first or last bin, which reads
// like a real drop in activity unless the caption says so
const partialBins = (data) => {
  if (data.mode !== 'counts' || data.bin === 'day') return ''
  const lastDay = (ymd) => new Date(Date.UTC(+ymd.slice(0, 4), +ymd.slice(5, 7), 0)).getUTCDate()
  const startsClean = data.bin === 'year' ? data.start.endsWith('-01-01') : data.start.endsWith('-01')
  const endsClean = data.bin === 'year' ? data.end.endsWith('-12-31') : +data.end.slice(8) === lastDay(data.end)
  const parts = [!startsClean && `the first ${data.bin} starts ${data.start}`, !endsClean && `the last ${data.bin} ends ${data.end}`].filter(Boolean)
  return parts.length ? `Partial bins: ${parts.join(' and ')}. ` : ''
}

// the figure caption says exactly what is plotted, so a downloaded figure can be read on its own
const caption = (data, query) => {
  const names = Object.keys(data.series).map(l => SERIES[l].label)
  const what = data.mode === 'flares'
    ? `Peak 1–8 Å flux of each flare in ${names.join(', ')}`
    : `Number of flares per ${data.bin} in ${names.join(', ')}`
  const filters = [query.class && `GOES class ${query.class.toUpperCase()}`, query.ar && `active region ${query.ar}`].filter(Boolean)
  return `${what}, ${data.start} to ${data.end} (UTC)${filters.length ? ', ' + filters.join(', ') : ''}. ` +
    (data.mode === 'flares'
      ? 'Flares are selected by start time and plotted at peak time; open marks that coincide are the same flare in several catalogues. '
      : 'Flares are counted by start time; each line runs only between its catalogue\'s first and latest date. ' + partialBins(data)) +
    data.notes.join(' ')
}

export default function ComparePage({query, onSearch}){
  const selected = query.sources ? query.sources.split(',').filter(s => ALL_SOURCES.includes(s)) : ALL_SOURCES
  const [draft, setDraft] = useState({start: query.start || '', end: query.end || '', class: query.class || '', ar: query.ar || '', sources: selected})
  const [result, setResult] = useState(null)
  const svgRef = useRef(null)

  const requestKey = JSON.stringify([query.start, query.end, query.class, query.ar, selected])
  const loading = result?.key !== requestKey

  useEffect(() => {
    if (!selected.length) return
    const controller = new AbortController()
    getJSON('/compare', {sources: selected.join(','), start_date: query.start, end_date: query.end,
      goes_class: query.class, active_region: query.ar}, controller.signal)
      .then(({data}) => setResult({key: requestKey, data}))
      .catch(err => { if (err.name !== 'AbortError') setResult({key: requestKey, error: err.message}) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- requestKey captures every input
  }, [requestKey])

  const set = (key) => (e) => setDraft({...draft, [key]: e.target.value})
  const toggle = (key) => setDraft({...draft, sources: draft.sources.includes(key)
    ? draft.sources.filter(s => s !== key) : ALL_SOURCES.filter(s => s === key || draft.sources.includes(s))})
  const search = (e) => {
    e.preventDefault()
    onSearch({start: draft.start, end: draft.end, class: draft.class, ar: draft.ar,
      sources: draft.sources.length === ALL_SOURCES.length ? undefined : draft.sources.join(',')})
  }

  const data = !loading && result?.data
  const error = !selected.length ? 'Pick at least one source to compare.' : !loading && result?.error
  const empty = data && Object.values(data.totals).every(n => n === 0)

  const downloadSVG = () => {
    const markup = new XMLSerializer().serializeToString(svgRef.current)
    saveFile(`<?xml version="1.0" encoding="UTF-8"?>\n${markup}`, 'image/svg+xml', 'flare_comparison.svg')
  }

  return (
    <section>
      <p className="about">
        Search once and see how the catalogues compare. Up to 31 days shows each flare by its peak flux;
        longer ranges show how many flares each catalogue lists per day, month or year.
      </p>
      <form className="filters" onSubmit={search}>
        <label>From <input type="date" value={draft.start} onChange={set('start')} /></label>
        <label>To <input type="date" value={draft.end} onChange={set('end')} /></label>
        <label>GOES class <input className="short" placeholder="X, M1, C2.5" value={draft.class} onChange={set('class')} /></label>
        <label>Active region <input className="short" placeholder="13664" value={draft.ar} onChange={set('ar')} /></label>
        <fieldset>
          <legend>Sources</legend>
          {Object.entries(SOURCE_KEYS).map(([label, key]) => (
            <label key={key}><input type="checkbox" checked={draft.sources.includes(key)} onChange={() => toggle(key)} /> {SERIES[label].label}</label>
          ))}
        </fieldset>
        <button type="submit" className="primary" disabled={!draft.sources.length}>Compare</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {loading && selected.length > 0 && <p className="muted">Loading…</p>}

      {data && (
        <>
          <div className="compare-summary">
            {Object.entries(data.totals).map(([label, n]) => (
              <span key={label}><strong>{SERIES[label].label}</strong> {n.toLocaleString()} flares</span>
            ))}
          </div>
          {empty ? <p className="muted">No flares match this search in any selected catalogue.</p> : (
            <figure className="figure">
              <CompareChart data={data} ref={svgRef} />
              <figcaption>{caption(data, query)}</figcaption>
            </figure>
          )}
          <div className="toolbar">
            <span />
            <span>
              <button onClick={downloadSVG} disabled={empty}>Download figure (SVG)</button>
              <button onClick={() => saveFile(toCSV(data), 'text/csv', 'flare_comparison.csv')}>Download data (CSV)</button>
            </span>
          </div>
        </>
      )}
    </section>
  )
}
