import { test } from 'node:test'
import assert from 'node:assert/strict'
import { sourceLink } from '../src/sources.js'

test('LMSAL links to the event page LMSAL itself gives', () => {
  const event = {event_id: 'gev_20260704_2029', event_url: 'https://www.lmsal.com/solarsoft/latest_events_archive/events_summary/2026/07/04/gev_20260704_2029/index.html',
    seen_in_dates: ['https://www.lmsal.com/solarsoft/ssw/last_events-2026/last_events_20260705_1201/index.html']}
  assert.deepEqual(sourceLink('lmsal', event), {url: event.event_url, label: 'LMSAL event page', note: ''})
})

test('LMSAL without a recorded page falls back to the snapshot that listed it', () => {
  const event = {event_id: 'gev_20021214_1158', seen_in_dates: ['https://www.lmsal.com/solarsoft/ssw/last_events-2002/last_events_20021218_0957/index.html']}
  assert.deepEqual(sourceLink('lmsal', event), {url: event.seen_in_dates[0], label: 'LMSAL latest-events page listing this event', note: ''})
})

test('NOAA links to that day\'s SWPC event report and names the event number', () => {
  assert.deepEqual(sourceLink('noaa', {event_id: 'noaa_20260704_5640', date: '2026-07-04'}), {
    url: 'https://www.ngdc.noaa.gov/stp/space-weather/swpc-products/daily_reports/solar_event_reports/2026/07/20260704events.txt',
    label: 'NOAA/SWPC event report, 2026-07-04', note: 'event #5640'})
  // a number repeated that day keeps its suffix out of the event number
  assert.equal(sourceLink('noaa', {event_id: 'noaa_20240514_3110_2', date: '2024-05-14'}).note, 'event #3110 (second entry with this number)')
})

test('SciQuality links to that year\'s NCEI flare report and names the flare_id', () => {
  assert.deepEqual(sourceLink('sciquality', {event_id: 'sq_202607042029', start: '2026-07-04 20:29:00'}), {
    url: 'https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/sci_xrsf-l2-flrpt_geo_y2026_v1-0-1.csv',
    label: 'NCEI science-quality flare report, 2026 (CSV)', note: 'flare_id 202607042029'})
})

test('the flag sentence names the other catalogue: NOAA for LMSAL flares, LMSAL for NOAA flares', async () => {
  const { flagHelp } = await import('../src/sources.js')
  assert.equal(flagHelp('HIGH', 'lmsal'), 'The NOAA catalogue has a flare of the same class starting within 3 minutes.')
  assert.equal(flagHelp('LOW', 'lmsal'), 'The NOAA catalogue has a flare starting within 3 minutes, but of a different class.')
  assert.equal(flagHelp('N/A', 'lmsal'), 'The NOAA catalogue has nothing starting within 3 minutes.')
  assert.equal(flagHelp('HIGH', 'noaa'), 'The LMSAL catalogue has a flare of the same class starting within 3 minutes.')
  assert.equal(flagHelp('N/A', 'noaa'), 'The LMSAL catalogue has nothing starting within 3 minutes.')
  assert.equal(flagHelp('N/A', 'sciquality'), '') // SciQuality isn't flagged
  assert.equal(flagHelp(undefined, 'noaa'), '')
})

test('a merged LMSAL flare lists the duplicate entries folded into it, and which start matched NOAA', async () => {
  const { mergedNote } = await import('../src/sources.js')
  const event = {event_id: 'gev_20120929_0750', matched_via: 'gev_20120929_0617', merged_from: [
    {event_id: 'gev_20120929_0617', event_start: '2012/09/29 06:17:00', event_url: 'https://lmsal/0617'}]}
  assert.deepEqual(mergedNote('lmsal', event), {
    entries: [{id: 'gev_20120929_0617', start: '2012/09/29 06:17:00', url: 'https://lmsal/0617'}],
    matchedVia: 'gev_20120929_0617 (start 06:17:00)'})
  assert.equal(mergedNote('lmsal', {...event, matched_via: 'gev_20120929_0750'}).matchedVia, null) // matched with its own start
  assert.equal(mergedNote('lmsal', {event_id: 'gev_1'}), null)
  assert.equal(mergedNote('noaa', event), null)
})
