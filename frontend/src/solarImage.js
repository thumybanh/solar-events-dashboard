const ISWA_HMI = 'https://iswa.ccmc.gsfc.nasa.gov/iswa_data_tree/observation/solar/sdo/hmi-magnetogram_2048x2048/'
export const FIRST_HMI_IMAGE = '2010-06-21' // ISWA's HMI magnetograms start here (SDO launched 2010)

// ISWA keeps an HMI magnetogram every 15 minutes, so round the flare time to the nearest one.
// Done with a UTC Date so 23:53 rounds to 00:00 the next day instead of an hour "24".
// Returns null for flares before the first image, so the popup can say so instead of showing a broken one.
export const imageFor = (time) => {
  const [date, clock = '00:00'] = time.replace(/\//g, '-').split(' ')
  if (date < FIRST_HMI_IMAGE) return null
  const [y, m, d] = date.split('-').map(Number)
  const [h, min] = clock.split(':').map(Number)
  const t = new Date(Date.UTC(y, m - 1, d, h, Math.round(min / 15) * 15))
  const pad = (n) => String(n).padStart(2, '0')
  const ymd = `${t.getUTCFullYear()}${pad(t.getUTCMonth() + 1)}${pad(t.getUTCDate())}`
  return `${ISWA_HMI}${t.getUTCFullYear()}/${pad(t.getUTCMonth() + 1)}/${ymd}_${pad(t.getUTCHours())}${pad(t.getUTCMinutes())}00_2048_HMIB.jpg`
}
