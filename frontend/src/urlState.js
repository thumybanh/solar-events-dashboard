// the current tab and filters live in the address bar, so Back works and a search can be shared as a link
const KEYS = ['view', 'start', 'end', 'class', 'ar', 'flag', 'sources', 'page']

export const readQuery = () => {
  const params = new URLSearchParams(window.location.search)
  return Object.fromEntries(KEYS.filter(k => params.get(k)).map(k => [k, params.get(k)]))
}

export const writeQuery = (state, push = true) => {
  const params = new URLSearchParams()
  for (const key of KEYS) {
    if (state[key] !== undefined && state[key] !== null && state[key] !== '') params.set(key, state[key])
  }
  const url = `${window.location.pathname}${params.toString() ? '?' + params : ''}`
  if (push) window.history.pushState(null, '', url)
  else window.history.replaceState(null, '', url)
}
