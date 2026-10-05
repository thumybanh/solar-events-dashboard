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
