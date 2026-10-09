// Solar images come from Helioviewer, which returns the image closest to any time we ask for.
// The old version guessed ISWA file names on a 15-minute grid, which broke wherever ISWA's
// files are off that grid (2010-2011) or missing (ISWA stopped updating at 2026-09-24).
import { API_BASE } from './api.js'

const HELIOVIEWER = 'https://api.helioviewer.org/v2'

// Helioviewer source ids for full-disk magnetograms
const HMI = {id: 19, label: 'SDO/HMI magnetogram'} // from 2010
const MDI = {id: 6, label: 'SOHO/MDI magnetogram'} // 1996-2011
const HMI_FROM = '2010-06-01'

// Only show an image taken this close to the flare; SOHO had long outages (e.g. mid-1998),
// and an image from weeks away would show the wrong Sun
export const MAX_IMAGE_GAP_MINUTES = 60

export const imageSourceFor = (time) => (time.replace(/\//g, '-') >= HMI_FROM ? HMI : MDI)

// '2026/10/03 16:50:00', '2026-10-03 16:50:00' or '2026-10-03' -> '2026-10-03T16:50:00Z'
export const helioDate = (time) => {
  const [date, clock = '00:00:00'] = time.replace(/\//g, '-').split(' ')
  return `${date}T${clock.length === 5 ? clock + ':00' : clock}Z`
}

export const minutesApart = (flareDate, imageDate) =>
  Math.round(Math.abs(new Date(flareDate) - new Date(imageDate.replace(' ', 'T') + 'Z')) / 60000)

// Helioviewer only answers this lookup from localhost in a browser, so it goes through our API
export const closestImageURL = (date, sourceId) =>
  `${API_BASE}/solar-image/closest?${new URLSearchParams({date, source_id: sourceId})}`

// asks which image is closest, so the popup can say when there isn't one near the flare
export const closestImage = async (time, signal) => {
  const date = helioDate(time)
  const source = imageSourceFor(time)
  const res = await fetch(closestImageURL(date, source.id), {signal})
  const body = await res.json()
  if (!res.ok || !body.date) throw new Error(body.detail || 'Helioviewer did not return an image')
  return {date, source, imageDate: body.date, gap: minutesApart(date, body.date)}
}

// 512 px at 4.8 arcsec per px, centred on the Sun: the same frame pix_x/pix_y were computed in
// (a 4096 px, 0.6 arcsec/px image scaled by 1/8), so the flare dot lands in the right place
export const screenshotURL = (date, sourceId) => `${HELIOVIEWER}/takeScreenshot/?` + new URLSearchParams({
  date, imageScale: '4.8', layers: `[${sourceId},1,100]`, x0: '0', y0: '0', width: '512', height: '512', display: 'true',
})
