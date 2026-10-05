import { useEffect, useState } from 'react'
import SourceDashboard from './SourceDashboard.jsx'
import ComparePage from './ComparePage.jsx'
import { SOURCES } from './sources.js'
import { readQuery, writeQuery } from './urlState.js'
import './App.css'

const TABS = [...Object.keys(SOURCES), 'compare']
const FILTER_KEYS = ['start', 'end', 'class', 'ar', 'flag']

const pick = (obj, keys) => Object.fromEntries(keys.filter(k => obj[k]).map(k => [k, obj[k]]))

function App(){
  // everything on screen comes from the address bar, so Back/Forward and shared links just work
  const [query, setQuery] = useState(readQuery)
  useEffect(() => {
    const onPopState = () => setQuery(readQuery())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const go = (next, push = true) => {
    writeQuery(next, push)
    setQuery(next)
  }

  const view = TABS.includes(query.view) ? query.view : 'lmsal'
  const filters = pick(query, FILTER_KEYS)
  const page = Number(query.page) || 0

  const openTab = (tab) => {
    // keep the date range and class when switching sources, so the same search can be checked in each
    const kept = pick(query, ['start', 'end', 'class', 'ar', ...(tab !== 'compare' && SOURCES[tab].hasFlag ? ['flag'] : []), 'sources'])
    go({view: tab, ...kept})
  }

  return (
    <div className="app">
      <header>
        <h1>Solar Events Dashboard</h1>
        <nav className="tabs" aria-label="Data source">
          {TABS.map(tab => (
            <button key={tab} className={tab === view ? 'tab active' : 'tab'} aria-current={tab === view ? 'page' : undefined}
              onClick={() => openTab(tab)}>
              {tab === 'compare' ? 'Compare' : SOURCES[tab].label}
            </button>
          ))}
        </nav>
      </header>

      {view === 'compare' ? (
        <ComparePage
          key={JSON.stringify(query)}
          query={query}
          onSearch={(search) => go({view: 'compare', ...search})}
        />
      ) : (
        <SourceDashboard
          key={JSON.stringify([view, filters])} // a new search (or Back) resets the form to what's applied
          sourceKey={view}
          filters={filters}
          page={page}
          onApply={(next) => go({view, ...pick(next, FILTER_KEYS)})}
          onPage={(n) => go({...query, view, page: n || undefined}, false)}
          onCompare={(current) => go({view: 'compare', ...pick(current, ['start', 'end', 'class', 'ar'])})}
        />
      )}
    </div>
  )
}

export default App
