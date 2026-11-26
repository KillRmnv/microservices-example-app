// Pure parser/merge/error-mapping tests for lib/.
// `.mjs` on purpose: `tsc`/Next do not typecheck this file, but Node can still
// import the `.ts` modules through `--experimental-strip-types`.
import test from 'node:test'
import assert from 'node:assert/strict'

import { accumulateShownIds, contractFromParsed, detectIntent, isFollowUpOnly, mergeContracts, parseQuery, resetsShownIds } from '../lib/dialogue.ts'
import { filmFacts, filmRunUntil, filmSessionLabel } from '../lib/catalog.ts'
import { RATE_LIMIT_MESSAGE, isRateLimited } from '../lib/errors.ts'

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

test('cinema words route to the film intent and category', () => {
  for (const query of ['фильм', 'кино', 'кинопоказ', 'сеанс', 'что посмотреть']) {
    assert.equal(detectIntent(query), 'find_event_film', query)
    assert.deepEqual(parseQuery(query).category, ['film'], query)
  }
  // "кинотеатр" stays a place search, not a film event.
  assert.equal(detectIntent('кинотеатр'), 'find_venue_cinema')
})

test('film helpers stay null-safe and format run/session', () => {
  assert.equal(filmRunUntil({}), '')
  assert.equal(filmRunUntil({
    start_at: '2026-11-26T10:00:00', end_at: '2026-11-26T12:00:00',
  }), '')
  assert.equal(filmRunUntil({
    start_at: '2026-11-26T10:00:00', end_at: '2026-12-05T23:00:00',
  }), '05.12')
  assert.equal(filmSessionLabel({}), '')
  const session = filmSessionLabel({
    next_session_at: '2026-11-26T19:30:00', cinema: 'Silver Screen',
  })
  assert.equal(session, 'Ближайший сеанс 19:30 · Silver Screen')
  assert.deepEqual(filmFacts({}), [])
  assert.deepEqual(filmFacts({
    film_genre: ['Фантастика'], film_duration_min: 155,
  }), ['Фантастика', '155 мин'])
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

test('terrace words become a required amenity', () => {
  const parsed = parseQuery('бар с верандой')
  assert.deepEqual(parsed.amenities, ['terrace'])
  const contract = contractFromParsed(parsed, previousTurn())
  assert.deepEqual(contract.hard_filters.amenities_required, ['terrace'])
  assert.deepEqual(parseQuery('столик на улице').amenities, ['terrace'])
  assert.deepEqual(parseQuery('тихая терраса').amenities, ['terrace'])
})

test('a requested amenity survives a follow-up turn', () => {
  const previous = previousTurn()
  previous.hard_filters.amenities_required = ['terrace']
  const contract = contractFromParsed(parseQuery('а подешевле?'), previous)
  assert.deepEqual(contract.hard_filters.amenities_required, ['terrace'])
})

test('a party-total budget stays in total, not per person', () => {
  const before = parseQuery('на двоих до 80')
  assert.equal(before.budgetTotal, 80)
  assert.equal(before.maxPrice, undefined)
  assert.equal(before.budgetBasis, 'total')
  const contract = contractFromParsed(before, previousTurn())
  assert.deepEqual(contract.hard_filters.budget, { total: 80, basis: 'total' })
  const after = parseQuery('до 90 на троих')
  assert.equal(after.budgetTotal, 90)
  assert.equal(after.maxPrice, undefined)
  assert.equal(after.budgetBasis, 'total')
})

test('a local party total beats a remote per-person budget', () => {
  const previous = previousTurn()
  const parsed = parseQuery('на двоих до 120')
  const local = contractFromParsed(parsed, previous)
  const remote = {
    ...previous,
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: { ...previous.hard_filters, budget: { max_price_per_person: 40, basis: 'per_person' } },
  }
  const merged = mergeContracts(remote, local, parsed, previous)
  assert.deepEqual(merged.hard_filters.budget, { total: 120, basis: 'total' })
})

test('per-person budgets keep the old convention', () => {
  const explicit = parseQuery('до 40 на человека')
  assert.equal(explicit.maxPrice, 40)
  assert.equal(explicit.budgetBasis, 'per_person')
  const plain = parseQuery('до 50')
  assert.equal(plain.maxPrice, 50)
  assert.equal(plain.budgetBasis, undefined)
  assert.deepEqual(contractFromParsed(plain, previousTurn()).hard_filters.budget, { max_price_per_person: 50 })
})

test('a query without party words defaults to one person', () => {
  const parsed = parseQuery('джаз в пятницу', NOW)
  assert.equal(parsed.partyExplicit, false)
  assert.equal(parsed.partySize, 1)
  assert.equal(parseQuery('что-нибудь').partySize, 1)
})

test('vague synonyms are recognised as bare "any" answers', () => {
  const phrases = [
    'как хочешь', 'как скажешь', 'на твой вкус', 'на ваше усмотрение',
    'пофиг', 'не принципиально', 'не имеет значения', 'не критично',
    'необязательно', 'что угодно', 'что-нибудь', 'сам реши', 'сам решай',
    'решай сам', 'на выбор', 'мне всё равно', 'мне все равно',
    'без предпочтений', 'не суть', 'любой', 'любая', 'любое', 'любые',
  ]
  for (const phrase of phrases) {
    assert.equal(parseQuery(phrase).bareAny, true, phrase)
  }
})

test('per-slot vague phrases set only their own any-flag', () => {
  for (const phrase of ['когда угодно', 'в любой день', 'дата не важна', 'не важно когда', 'без даты']) {
    const parsed = parseQuery(phrase)
    assert.equal(parsed.dateAny, true, phrase)
    assert.equal(parsed.bareAny, false, phrase)
  }
  for (const phrase of ['где угодно', 'в любом городе', 'город не важен', 'не важно где']) {
    assert.equal(parseQuery(phrase).cityAny, true, phrase)
  }
  for (const phrase of ['без ограничений', 'не важно сколько', 'любой бюджет', 'деньги не важны']) {
    assert.equal(parseQuery(phrase).budgetAny, true, phrase)
  }
  for (const phrase of ['сколько угодно', 'компания не важна', 'любая компания', 'сколько человек не важно']) {
    assert.equal(parseQuery(phrase).partyAny, true, phrase)
  }
})

test('a generic "что-нибудь" is not an any-slot answer by itself', () => {
  const parsed = parseQuery('что-нибудь')
  assert.equal(parsed.dateAny, false)
  assert.equal(parsed.cityAny, false)
  assert.equal(parsed.budgetAny, false)
  assert.equal(parsed.partyAny, false)
  assert.equal(detectIntent('что-нибудь'), 'both')
  const contract = contractFromParsed(parsed)
  assert.equal(contract.hard_filters.datetime, undefined)
  assert.equal(contract.hard_filters.budget, undefined)
})

test('"как хочешь" fills only the date slot the server asked about', () => {
  const previous = {
    ...previousTurn(),
    clarification_slots: ['datetime'],
    clarification_prompt: 'На когда искать?',
  }
  const parsed = parseQuery('как хочешь')
  assert.equal(parsed.bareAny, true)
  const contract = contractFromParsed(parsed, previous)
  assert.equal(contract.hard_filters.datetime?.any, true)
  assert.equal(contract.hard_filters.datetime?.start, undefined)
})

test('only HTTP 429 maps to the rate-limit notice', () => {
  assert.equal(isRateLimited({ status: 429 }), true)
  assert.equal(isRateLimited(Object.assign(new Error('too many'), { status: 429 })), true)
  assert.equal(isRateLimited(Object.assign(new Error('boom'), { status: 500 })), false)
  assert.equal(isRateLimited(Object.assign(new Error('nope'), { status: 401 })), false)
  assert.equal(isRateLimited(new Error('no status')), false)
  assert.equal(isRateLimited(undefined), false)
  assert.equal(isRateLimited(null), false)
  assert.match(RATE_LIMIT_MESSAGE, /Слишком много запросов/)
})

test('clarification is off by default and only kept when turned on', () => {
  const parsed = parseQuery('джаз в пятницу', NOW)
  assert.equal(contractFromParsed(parsed).clarify_missing, false)
  const previous = previousTurn()
  previous.clarify_missing = undefined
  assert.equal(contractFromParsed(parsed, previous).clarify_missing, false)
  previous.clarify_missing = true
  assert.equal(contractFromParsed(parsed, previous).clarify_missing, true)
})

test('follow-up turns are detected locally', () => {
  for (const text of ['а ещё?', 'ещё', 'а подешевле?', 'другие', 'варианты']) {
    assert.equal(isFollowUpOnly(text), true, text)
  }
  for (const text of ['джаз завтра', 'бар с верандой', 'не важно']) {
    assert.equal(isFollowUpOnly(text), false, text)
  }
})

test('shown ids accumulate without duplicates and cap at 100', () => {
  const cards = Array.from({ length: 120 }, (_, index) => ({ detail_id: `card-${index}` }))
  const accumulated = accumulateShownIds(['card-0', 'card-1'], cards)
  assert.equal(accumulated.length, 100)
  assert.equal(new Set(accumulated).size, 100)
  assert.deepEqual(accumulated.slice(0, 2), ['card-0', 'card-1'])
  assert.deepEqual(accumulateShownIds(undefined, [{ detail_id: 'a' }, {}, { detail_id: 'a' }]), ['a'])
})

test('an explicit plan length is parsed and carried in the contract', () => {
  assert.equal(parseQuery('два события').eventCount, 2)
  assert.equal(parseQuery('пара мероприятий').eventCount, 2)
  assert.equal(parseQuery('несколько событий').eventCount, 3)
  assert.equal(parseQuery('три концерта').eventCount, 3)
  assert.equal(parseQuery('5 событий').eventCount, 5)
  assert.equal(parseQuery('концерт').eventCount, undefined)
  assert.equal(parseQuery('десять событий').eventCount, undefined)
  assert.equal(contractFromParsed(parseQuery('два события'), previousTurn()).hard_filters.event_count, 2)
})

test('a follow-up keeps shown ids while an explicit filter resets them', () => {
  const previous = previousTurn()
  previous.context_state.shown_ids = ['a', 'b']
  const followUp = parseQuery('а ещё?')
  assert.equal(resetsShownIds(followUp, previous), false)
  assert.deepEqual(contractFromParsed(followUp, previous).context_state.shown_ids, ['a', 'b'])
  for (const query of ['концерт', 'завтра', 'до 40', 'нас двое', 'без бара', 'бар']) {
    const parsed = parseQuery(query, NOW)
    assert.equal(resetsShownIds(parsed, previous), true, query)
    assert.equal(contractFromParsed(parsed, previous).context_state.shown_ids, undefined, query)
  }
})
