import { test } from 'node:test'
import assert from 'node:assert/strict'
import { covered, toCSV } from '../src/compareData.js'
import { imageFor } from '../src/solarImage.js'

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

test('HMI images exist from 2010-06-21, so earlier flares get none', () => {
  assert.equal(imageFor('2010-06-20 23:59:00'), null)
  assert.equal(imageFor('1998/08/24 21:50:00'), null)
  assert.match(imageFor('2024-05-14 16:46:00'), /2024\/05\/20240514_164500_2048_HMIB\.jpg$/)
  assert.match(imageFor('2024-05-14 23:53:00'), /2024\/05\/20240515_000000_2048_HMIB\.jpg$/) // rounds into the next day
})
