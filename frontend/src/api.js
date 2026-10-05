// one place for the API address, so a deployed build can point somewhere other than localhost
// (set VITE_API_BASE at build time)
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const queryString = (params) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  }
  return query.toString()
}

// returns {data, total}; a 400 from the API carries a message saying what was wrong, so pass it on
export const getJSON = async (path, params = {}, signal) => {
  let res
  try {
    res = await fetch(`${API_BASE}${path}?${queryString(params)}`, {signal})
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new Error(`Can't reach the API at ${API_BASE}. Is it running?`)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(body?.detail || `The API answered ${res.status}`)
  return {data: body, total: Number(res.headers.get('X-Total-Count')) || 0}
}

export const downloadURL = (path, params) => `${API_BASE}${path}?${queryString(params)}`
