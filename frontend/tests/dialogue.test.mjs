// Pure parser/merge tests for lib/dialogue.ts.
// `.mjs` on purpose: `tsc`/Next do not typecheck this file, but Node can still
// import the `.ts` module through `--experimental-strip-types`.
import test from 'node:test'
import assert from 'node:assert/strict'

import { contractFromParsed, detectIntent, mergeContracts, parseQuery } from '../lib/dialogue.ts'

const NOW = new Date('2026-11-25T10:00:00')

/** Previous turn: the server asked for city/budget/party after a dated search. */
function previousTurn() {
  return {
    dialogue_action: 'ask_clarification',
    intent: 'find_events',
    clarify_missing: true,
    needs_clarification: true,
    clarification_prompt: 'Уточните город, бюджет и компанию',
    clarification_slots: ['city', 'budget', 'party'],
    hard_filters: {
      datetime: { start: '2026-11-27T18:00:00', end: '2026-11-27T23:59:00' },
      location: { city: 'Минск' },
      category: ['concert'],
      themes: [],
      party_size: 2,
      amenities_required: [],
    },
    negative_filters: {
      exclude_tags: [],
      exclude_categories: [],
      exclude_districts: [],
    },
    semantic_payload: { vector_query: 'джаз', language: 'ru' },
    context_state: { turn_count: 2, session_id: 'web_test' },
  }
}

test('bare "не важно" is context aware, not an any-date instruction', () => {
  const parsed = parseQuery('не важно')
  assert.equal(parsed.bareAny, true)
  assert.equal(parsed.dateAny, false)
})

test('"завтра вечером" resolves to the evening window (Cyrillic-safe)', () => {
  const parsed = parseQuery('завтра вечером', NOW)
  assert.ok(parsed.start?.endsWith('T18:00:00'), `start was ${parsed.start}`)
  assert.ok(parsed.end?.endsWith('T23:59:00'), `end was ${parsed.end}`)
  assert.ok(parsed.start?.startsWith('2026-11-26T'), `start was ${parsed.start}`)
})

test('bare "не важно" only clears the slots the server asked about', () => {
  const contract = contractFromParsed(parseQuery('не важно'), previousTurn())
  assert.equal(contract.hard_filters.datetime?.start, '2026-11-27T18:00:00')
  assert.equal(contract.hard_filters.datetime?.any, undefined)
  assert.deepEqual(contract.hard_filters.location, { city: null, any: true })
  assert.deepEqual(contract.hard_filters.budget, { any: true })
  assert.equal(contract.hard_filters.party_size, 0)
})

test('"любая дата" is an explicit any-date phrase', () => {
  const contract = contractFromParsed(parseQuery('любая дата'), previousTurn())
  assert.equal(contract.hard_filters.datetime?.any, true)
  assert.equal(contract.hard_filters.datetime?.start, undefined)
})

test('"бюджет не важен" clears only the budget, keeps the inherited date', () => {
  const parsed = parseQuery('бюджет не важен')
  assert.equal(parsed.dateAny, false)
  assert.equal(parsed.bareAny, false)
  const contract = contractFromParsed(parsed, previousTurn())
  assert.equal(contract.hard_filters.datetime?.start, '2026-11-27T18:00:00')
  assert.deepEqual(contract.hard_filters.budget, { any: true })
})

test('an explicit local date wins over the model date', () => {
  const previous = previousTurn()
  const parsed = parseQuery('завтра', NOW)
  const local = contractFromParsed(parsed, previous)
  const remote = {
    ...previous,
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: {
      ...previous.hard_filters,
      datetime: { start: '2026-12-31T20:00:00', end: '2026-12-31T23:59:00' },
    },
  }
  const merged = mergeContracts(remote, local, parsed, previous)
  assert.equal(merged.hard_filters.datetime?.start, local.hard_filters.datetime?.start)
  assert.equal(merged.hard_filters.datetime?.start, '2026-11-26T12:00:00')
})

test('detectIntent classifies events, venues, plan, weather and generic turns', () => {
  assert.equal(detectIntent('концерт в пятницу'), 'find_event_concert')
  assert.equal(detectIntent('бар с коктейлями'), 'find_venue_bar')
  assert.equal(detectIntent('какая погода завтра'), 'weather')
  assert.equal(detectIntent('собери план на вечер'), 'plan')
  assert.equal(detectIntent('что-нибудь'), 'both')
})

test('detectIntent returns null for a signal-less follow-up', () => {
  assert.equal(detectIntent('а подешевле?'), null)
  assert.equal(detectIntent('абракадабра'), null)
  assert.equal(detectIntent('спектакль в театре'), 'both')
  assert.equal(detectIntent('выставка в музее'), 'both')
})

test('a signal-less follow-up inherits the previous venue intent', () => {
  const previousVenueBar = contractFromParsed(parseQuery('бар'), previousTurn())
  assert.equal(previousVenueBar.intent, 'find_venue_bar')
  const parsed = parseQuery('а подешевле?')
  assert.equal(parsed.intent, null)
  const contract = contractFromParsed(parsed, previousVenueBar)
  assert.equal(contract.intent, 'find_venue_bar')
  assert.deepEqual(contract.hard_filters.category, [])
})

test('coffee resolves to a cafe, beer to a bar', () => {
  assert.equal(detectIntent('выпить кофе'), 'find_venue_cafe')
  assert.equal(detectIntent('выпить пива'), 'find_venue_bar')
})

test('venue words set the intent but never an event category', () => {
  const parsed = parseQuery('бар')
  assert.equal(parsed.intent, 'find_venue_bar')
  assert.deepEqual(parsed.category, [])
  const contract = contractFromParsed(parsed, previousTurn())
  assert.equal(contract.intent, 'find_venue_bar')
  assert.deepEqual(contract.hard_filters.category, [])
})

test('bare "не важно" carries no semantic vector query', () => {
  assert.equal(parseQuery('не важно').vectorQuery, '')
  assert.equal(parseQuery('не важно').bareAny, true)
})

test('a specific local intent wins over a generic model intent', () => {
  const previous = previousTurn()
  const parsed = parseQuery('бар')
  const local = contractFromParsed(parsed, previous)
  const remote = {
    ...previous,
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    intent: 'find_events',
    hard_filters: { ...previous.hard_filters, category: ['concert'] },
  }
  const merged = mergeContracts(remote, local, parsed, previous)
  assert.equal(merged.intent, 'find_venue_bar')
  assert.deepEqual(merged.hard_filters.category, [])
})

test('a specific model intent still wins over a generic local one', () => {
  const previous = previousTurn()
  const parsed = parseQuery('что-нибудь')
  const local = contractFromParsed(parsed, previous)
  const remote = {
    ...previous,
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    intent: 'find_venue_cafe',
    hard_filters: { ...previous.hard_filters, category: ['cafe'] },
  }
  const merged = mergeContracts(remote, local, parsed, previous)
  assert.equal(merged.intent, 'find_venue_cafe')
  assert.deepEqual(merged.hard_filters.category, [])
})
