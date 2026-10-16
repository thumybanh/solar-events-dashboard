// what each catalogue looks like in the dashboard: where its API lives and which columns it has.
// Records keep their source's own field names, so every lookup goes through this table.

const flux = (value) => value.toExponential(2)

export const SOURCES = {
  lmsal: {
    label: 'LMSAL',
    path: '',
    hasFlag: true,
    about: 'Flares from the LMSAL SolarSoft latest-events archive, from 2002-09-26.',
    columns: [
      {key: 'event_id', label: 'Event ID'},
      {key: 'event_start', label: 'Start'},
      {key: 'event_stop', label: 'Stop'},
      {key: 'event_peak', label: 'Peak'},
      {key: 'event_GOES', label: 'GOES class'},
      {key: 'event_position', label: 'Position'},
      {key: 'quality_flag', label: 'Flag'},
    ],
    imageTime: (e) => e.event_start,
  },
  noaa: {
    label: 'NOAA',
    path: '/noaa',
    hasFlag: true,
    about: 'X-ray flares from the NOAA/SWPC daily event reports, from 1996-07-31.',
    columns: [
      {key: 'event_id', label: 'ID'},
      {key: 'begin', label: 'Begin'},
      {key: 'peak', label: 'Peak'},
      {key: 'end', label: 'End'},
      {key: 'goes_class', label: 'GOES class'},
      {key: 'location', label: 'Location'},
      {key: 'active_region', label: 'AR'},
      {key: 'quality_flag', label: 'Flag'},
    ],
    imageTime: (e) => e.begin || e.peak || e.date,
  },
  sciquality: {
    label: 'SciQuality',
    path: '/sciquality',
    hasFlag: false,
    about: 'Flares from the NCEI science-quality GOES XRS flare report, from 1995-01-03. Fluxes as published (unscaled).',
    columns: [
      {key: 'event_id', label: 'ID'},
      {key: 'start', label: 'Start'},
      {key: 'peak', label: 'Peak'},
      {key: 'end', label: 'End'},
      {key: 'goes_class', label: 'Class'},
      {key: 'peak_flux', label: 'Peak flux (W m⁻²)', format: flux},
      {key: 'satellite', label: 'Satellite'},
      {key: 'location', label: 'Location'},
      {key: 'active_region', label: 'AR'},
    ],
    imageTime: (e) => e.start || e.peak,
  },
}

// a missing value still shows, as N/A, so it's clear the flare exists but that detail doesn't
export const cell = (event, column) => {
  const value = event[column.key]
  if (value === null || value === undefined || value === '') return 'N/A'
  return column.format ? column.format(value) : String(value)
}

const FLAG_HELP = {
  HIGH: 'The other catalogue has a flare of the same class starting within 3 minutes.',
  LOW: 'The other catalogue has a flare starting within 3 minutes, but of a different class.',
  'N/A': 'The other catalogue has nothing starting within 3 minutes.',
}
export const flagHelp = (flag) => FLAG_HELP[flag] || ''

// Where each flare's record came from (provenance). LMSAL has a page per event; NOAA publishes one
// report per day and NCEI one CSV per year, so for those the note names the line to look for.
const NOAA_REPORTS = 'https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports'
const NCEI_REPORTS = 'https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv'
const ORDINAL = {2: 'second', 3: 'third', 4: 'fourth'}

export const sourceLink = (sourceKey, event) => {
  if (sourceKey === 'lmsal') {
    // the link LMSAL's own snapshot gave; old events without one fall back to the snapshot itself
    return event.event_url
      ? {url: event.event_url, label: 'LMSAL event page', note: ''}
      : {url: event.seen_in_dates?.[0], label: 'LMSAL latest-events page listing this event', note: ''}
  }
  if (sourceKey === 'noaa') {
    const [, ymd, number, repeat] = event.event_id.split('_')
    const which = repeat ? ` (${ORDINAL[repeat] || `#${repeat}`} entry with this number)` : ''
    return {url: `${NOAA_REPORTS}/${ymd.slice(0, 4)}/${ymd.slice(4, 6)}/${ymd}events.txt`,
      label: `NOAA/SWPC event report, ${event.date}`, note: `event #${number}${which}`}
  }
  const flareId = event.event_id.replace(/^sq_/, '').replace(/_\d+$/, '')
  const year = flareId.slice(0, 4)
  return {url: `${NCEI_REPORTS}/sci_xrsf-l2-flrpt_geo_y${year}_v1-0-1.csv`,
    label: `NCEI science-quality flare report, ${year} (CSV)`, note: `flare_id ${flareId}`}
}
