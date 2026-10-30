import { test } from 'node:test'
import assert from 'node:assert/strict'
import { parseFormat } from '../src/urlState.js'

test('no format in the link means no automatic download', () => {
  assert.equal(parseFormat(undefined), null)
  assert.equal(parseFormat(''), null)
})

test('csv and json are accepted in any letter case', () => {
  assert.deepEqual(parseFormat('csv'), {format: 'csv'})
  assert.deepEqual(parseFormat(' JSON '), {format: 'json'})
})

test('anything else says what is accepted', () => {
  assert.deepEqual(parseFormat('xml'), {error: 'format must be csv or json, got "xml".'})
})
