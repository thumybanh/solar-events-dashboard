import { test } from 'node:test'
import assert from 'node:assert/strict'
import { covered, toCSV } from '../src/compareData.js'
import { helioDate, imageSourceFor, minutesApart, screenshotURL } from '../src/solarImage.js'

const counts = {
  mode: 'counts', bin: 'year',
  coverage: {LMSAL: '2002-09-26', SciQuality: '1995-01-03'},
  coverage_end: {LMSAL: '2026-10-03', SciQuality: '2025-12-31'},
  series: {
    LMSAL: [['2001', 0], ['2002', 770], ['2026', 2980]],
    SciQuality: [['2001', 3600], ['2002', 3590], ['2026', 0]],
  },
}

test('a bin is covered only between a catalogue\'s first and last date', () => {
  assert.equal(covered(counts, 'LMSAL', '2001'), false)
  assert.equal(covered(counts, 'LMSAL', '2002'), true)
  assert.equal(covered(counts, 'SciQuality', '2026'), false)
  assert.equal(covered(counts, 'SciQuality', '2025'), true)
})

test('CSV leaves bins outside coverage empty instead of writing 0', () => {
  assert.equal(toCSV(counts), 'year,LMSAL,SciQuality\n2001,,3600\n2002,770,3590\n2026,2980,')
})

test('CSV for individual flares writes N/A for missing values', () => {
  const flares = {mode: 'flares', series: {NOAA: [{id: 'n1', time: '2024-05-14 02:09:00', goes_class: null, flux: null}]}}
  assert.equal(toCSV(flares), 'source,id,peak_time,goes_class,peak_flux_w_m2\nNOAA,n1,2024-05-14 02:09:00,N/A,N/A')
})

test('SDO/HMI magnetograms from mid-2010, SOHO/MDI before', () => {
  assert.equal(imageSourceFor('2024-05-14 16:46:00').id, 19)
  assert.equal(imageSourceFor('2010/06/21 13:41:00').id, 19)
  assert.equal(imageSourceFor('1998-08-24 21:50:00').id, 6)
})

test('flare times in any source format become Helioviewer UTC dates', () => {
  assert.equal(helioDate('2026/10/03 16:50:00'), '2026-10-03T16:50:00Z')
  assert.equal(helioDate('2026-10-03 16:50:00'), '2026-10-03T16:50:00Z')
  assert.equal(helioDate('2026-10-03'), '2026-10-03T00:00:00Z')
})

test('how far the closest image is from the flare', () => {
  assert.equal(minutesApart('2026-10-03T16:50:00Z', '2026-10-03 16:50:01'), 0)
  assert.ok(minutesApart('1998-08-24T21:50:00Z', '1998-10-20 01:30:04') > 60 * 24 * 50)
})

test('screenshot is 512 px at 4.8 arcsec/px centred on the Sun, matching pix_x/pix_y', () => {
  const url = screenshotURL('2026-10-03T16:50:00Z', 19)
  assert.match(url, /^https:\/\/api\.helioviewer\.org\/v2\/takeScreenshot\/\?/)
  for (const part of ['date=2026-10-03T16%3A50%3A00Z', 'imageScale=4.8', 'layers=%5B19%2C1%2C100%5D', 'x0=0', 'y0=0', 'width=512', 'height=512', 'display=true'])
    assert.ok(url.includes(part), part)
})
