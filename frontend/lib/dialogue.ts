'use client'

// Client-side query structuring: deterministic rules that turn
// free text into a first StateContract. The server re-validates everything,
// asks for missing slots, and owns turn_count — this is only a first draft.
import type { StateContract } from './types'

const MONTHS: Record<string, number> = {
  января: 1, февраля: 2, марта: 3, апреля: 4, мая: 5, июня: 6,
  июля: 7, августа: 8, сентября: 9, октября: 10, ноября: 11, декабря: 12,
}

const WEEKDAY_STEMS: Array<[string, number]> = [
  ['воскресень', 0], ['понедельник', 1], ['вторник', 2],
  ['сред', 3], ['четверг', 4], ['пятниц', 5], ['суббот', 6],
]

// Event categories only: venue words ("бар", "театр", "музей") are a different
// axis (`intent`) and must not narrow the event catalogue.
const CATEGORY_KEYWORDS: Array<[RegExp, string]> = [
  [/концерт|музык|джаз|рок|выступлен/i, 'concert'],
  [/спектакл|балет|опера|пьес/i, 'theatre'],
  [/выставк/i, 'exhibition'],
  [/кино(?!театр)|фильм/i, 'film'],
  [/спорт(?!зал)|матч|стадион|футбол|хоккей/i, 'sport'],
  [/детск|для детей|ребен|ребён/i, 'kids'],
]

// Venue intents: where to go, not what event to watch. Cafe is checked before
// bar so "выпить кофе" does not become a bar search.
const VENUE_INTENT_KEYWORDS: Array<[RegExp, string]> = [
  [/кафе|кофейн|кофе/i, 'find_venue_cafe'],
  [/бар|паб|пивн|пивка|выпить/i, 'find_venue_bar'],
  [/ресторан|ужин|обед|поужинать|пообедать|поесть|еда/i, 'find_venue_restaurant'],
  [/кинотеатр/i, 'find_venue_cinema'],
  [/театр/i, 'find_venue_theatre'],
  [/музе[йяеи]|галере/i, 'find_venue_exhibition'],
  [/спортзал|фитнес|тренаж[её]р|потренироваться/i, 'find_venue_gym'],
  [/библиотек|книжн|почитать|книг/i, 'find_venue_library'],
]

const EVENT_INTENT_KEYWORDS: Array<[RegExp, string]> = [
  [/концерт|джаз|рок|музык|выступлен/i, 'find_event_concert'],
  [/спектакл|балет|опера|пьес/i, 'find_event_theatre'],
  [/выставк/i, 'find_event_exhibition'],
  [/кино(?!театр)|фильм/i, 'find_event_film'],
  [/спорт(?!зал)|матч|стадион|футбол|хоккей/i, 'find_event_sport'],
  [/детск|для детей|ребен|ребён/i, 'find_event_kids'],
]

const PLAN_INTENT = /план|маршрут|составь план|собери план/i
const WEATHER_INTENT = /погод|прогноз|дожд|снег|температур/i
const BOOKING_INTENT = /забронир|бронь|купить билет/i
// An explicit "anything goes" request: generic, but not a signal-less turn.
const GENERIC_INTENT = /что-нибудь|что-то|куда сходить|что есть|погулять|чем заняться/i

function firstIntentMatch(text: string,
                          table: Array<[RegExp, string]>): string | undefined {
  for (const [pattern, intent] of table) {
    if (pattern.test(text)) return intent
  }
  return undefined
}

/**
 * Local intent classifier. It only picks the section of the catalogue to use
 * (events, venues or both) plus plan/weather/booking shortcuts; the server
 * still owns the final contract. Returns `null` when the turn carries no
 * intent signal at all (a slot follow-up like "а подешевле?"), so the caller
 * can inherit the previous intent. Never returns "unsupported".
 */
export function detectIntent(text: string): string | null {
  const lowered = text.toLowerCase()
  if (PLAN_INTENT.test(lowered)) return 'plan'
  if (WEATHER_INTENT.test(lowered)) return 'weather'
  if (BOOKING_INTENT.test(lowered)) return 'booking'
  const venue = firstIntentMatch(lowered, VENUE_INTENT_KEYWORDS)
  const event = firstIntentMatch(lowered, EVENT_INTENT_KEYWORDS)
  if (venue && event) return 'both'
  if (venue) return venue
  if (event) return event
  // Explicit "anything" is a generic request, not a follow-up.
  if (GENERIC_INTENT.test(lowered)) return 'both'
  return null
}

// Domain defaults are configuration, not logic.
const DEFAULT_CITY = process.env.NEXT_PUBLIC_DEFAULT_CITY ?? 'Минск'
const DEFAULT_LANGUAGE = process.env.NEXT_PUBLIC_DEFAULT_LANGUAGE ?? 'ru'

export interface ParsedQuery {
  rawExpression: string
  /** Local intent: events/venues section, plan/weather/booking, or null when
   * the turn carries no intent signal (a slot follow-up). */
  intent: string | null
  start?: string
  end?: string
  category: string[]
  partySize: number
  maxPrice?: number
  excludeTags: string[]
  vectorQuery: string
  /** True when the user actually named a date (not an inherited one). */
  dateExplicit: boolean
  /**
   * True when the whole turn is a bare "не важно"/"все равно" answer.
   * It carries no slot of its own: it only applies to slots the server asked
   * about (`clarification_slots`), so it must not wipe an inherited date.
   */
  bareAny: boolean
  /** True when the user explicitly said any date is fine. */
  dateAny: boolean
  /** True when the user explicitly said any city is fine. */
  cityAny: boolean
  /** True when the user explicitly said price does not matter. */
  budgetAny: boolean
  /** True when the user explicitly said party size does not matter. */
  partyAny: boolean
  /** True when the user actually named the party size. */
  partyExplicit: boolean
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function isoDay(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

function nextWeekday(from: Date, target: number): Date {
  const result = new Date(from)
  let delta = (target - from.getDay() + 7) % 7
  if (delta === 0) delta = 7
  result.setDate(result.getDate() + delta)
  return result
}

function nextWeekend(from: Date): { start: Date; end: Date } {
  const saturday = nextWeekday(from, 6)
  const sunday = new Date(saturday)
  sunday.setDate(sunday.getDate() + 1)
  return { start: saturday, end: sunday }
}

export function parseQuery(text: string, now = new Date()): ParsedQuery {
  const lowered = text.toLowerCase()
  const result: ParsedQuery = {
    rawExpression: text.trim().slice(0, 200),
    intent: detectIntent(text),
    category: [],
    partySize: 2,
    excludeTags: [],
    vectorQuery: '',
    dateExplicit: false,
    bareAny: false,
    dateAny: false,
    cityAny: false,
    budgetAny: false,
    partyAny: false,
    partyExplicit: false,
  }

  // --- datetime ---
  let day: Date | null = null
  let endDay: Date | null = null
  let time: string | null = null
  const timeMatch = lowered.match(/(\d{1,2})[:.](\d{2})/)
  if (timeMatch) time = `${pad(Number(timeMatch[1]))}:${timeMatch[2]}`
  // A bare "не важно" answers whatever the server asked about; it is not an
  // "any date" instruction on its own, so keep it in a separate flag.
  result.bareAny = /^(?:не\s+важно|неважно|все\s+равно|любой\s+вариант|без\s+разницы|как\s+угодно)[.!?]*$/.test(lowered)
  result.dateAny = /любая\s+дата|без\s+даты|дата\s+не\s+(?:важна|имеет\s+значения)/.test(lowered)
  result.cityAny = /любой\s+город|без\s+разницы\s+где|не\s+важно\s+где|город\s+не\s+важен/.test(lowered)
  result.budgetAny = /без\s+бюджета|цена\s*не\s*важна|цена\s+неважна|любая\s+цена|деньги\s+не\s+важны|бюджет\s+не\s+важен|бюджет\s+любой/.test(lowered)
  result.partyAny = /компания\s+любая|сколько\s+угодно\s+человек|нас\s+любое|число\s+человек\s+не\s+важно|компания\s+не\s+важна/.test(lowered)
  const numericRange = lowered.match(/(\d{1,2})[./](\d{1,2})\s*[-–—]\s*(\d{1,2})[./](\d{1,2})/)
  const namedRange = lowered.match(/(?:с\s+)?(\d{1,2})\s*(?:[-–—]|по)\s*(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/)
  const tomorrowRange = /завтра\s*[-–—]\s*послезавтра/.test(lowered)
  if (result.dateAny) {
    result.dateExplicit = true
  } else if (numericRange) {
    const startMonth = Number(numericRange[2]) - 1
    const endMonth = Number(numericRange[4]) - 1
    day = new Date(now.getFullYear(), startMonth, Number(numericRange[1]), 12, 0, 0)
    endDay = new Date(now.getFullYear(), endMonth, Number(numericRange[3]), 23, 59, 0)
  } else if (namedRange) {
    const month = MONTHS[namedRange[3]] - 1
    day = new Date(now.getFullYear(), month, Number(namedRange[1]), 12, 0, 0)
    endDay = new Date(now.getFullYear(), month, Number(namedRange[2]), 23, 59, 0)
  } else if (tomorrowRange) {
    day = new Date(now)
    day.setDate(day.getDate() + 1)
    endDay = new Date(now)
    endDay.setDate(endDay.getDate() + 2)
  } else {
    const dayMonth = lowered.match(/(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/)
    if (dayMonth) {
      day = new Date(now.getFullYear(), MONTHS[dayMonth[2]] - 1, Number(dayMonth[1]))
      if (day.getTime() < now.getTime() - 12 * 3600 * 1000) day.setFullYear(day.getFullYear() + 1)
    } else if (/послезавтра/.test(lowered)) {
      day = new Date(now)
      day.setDate(day.getDate() + 2)
    } else if (/завтра/.test(lowered)) {
      day = new Date(now)
      day.setDate(day.getDate() + 1)
    } else if (/сегодня|сегодняшн/.test(lowered)) {
      day = new Date(now)
    } else if (/выходн/.test(lowered)) {
      const weekend = nextWeekend(now)
      day = weekend.start
      endDay = weekend.end
    } else {
      for (const [stem, index] of WEEKDAY_STEMS) {
        if (lowered.includes(stem)) {
          day = nextWeekday(now, index)
          break
        }
      }
    }
  }
  if (day) {
    let dayStart = '12:00'
    let dayEnd = '23:59'
    // JS `\b` only knows ASCII word chars, so `/\bвечер/` never matches
    // Cyrillic. Use plain stems plus an explicit boundary for the noun "день".
    if (/утр|morning/i.test(lowered)) {
      dayStart = '09:00'
      dayEnd = '11:59'
    } else if (/вечер|evening/i.test(lowered)) {
      dayStart = '18:00'
      dayEnd = '23:59'
    } else if (/ноч|night/i.test(lowered)) {
      dayStart = '22:00'
      dayEnd = '23:59'
    } else if (/дн[её]м|дневн|(?:^|[^а-яёa-z])день(?:[^а-яёa-z]|$)/i.test(lowered)) {
      dayStart = '12:00'
      dayEnd = '17:59'
    }
    const stamp = time ?? dayStart
    result.start = `${isoDay(day)}T${stamp}:00`
    const end = endDay ?? day
    const endStamp = time ? '23:59' : dayEnd
    result.end = `${isoDay(end)}T${endStamp}:00`
    result.dateExplicit = true
  }

  // --- category ---
  for (const [pattern, category] of CATEGORY_KEYWORDS) {
    if (pattern.test(lowered)) result.category.push(category)
  }

  // --- party size ---
  const partyRange = lowered.match(/(\d{1,2})\s*[-–—]\s*(\d{1,2})\s+человек/)
  if (partyRange) {
    result.partyExplicit = true
    result.partySize = Math.min(20, Math.max(1, Number(partyRange[2])))
  }
  const party = lowered.match(/нас\s+(\d{1,2})|вдво[её]м|двое|втро[её]м|(\d{1,2})\s+человек/)
  if (party && !partyRange) {
    result.partyExplicit = true
    if (/вдво[её]м|двое/.test(lowered)) result.partySize = 2
    else if (/втро[её]м/.test(lowered)) result.partySize = 3
    else result.partySize = Math.min(20, Math.max(1, Number(party[1] ?? party[2])))
  }

  // --- budget ---
  const budget = lowered.match(/(?:до|не дороже|бюджет)\s+(\d[\d\s]*)\s*(?:руб|р\b|byn)?/)
  if (budget) {
    const perPerson = lowered.match(/на\s+(двоих|двух|каждого|человека)/)
    const total = Number(budget[1].replace(/\s+/g, ''))
    result.maxPrice = perPerson && /двоих|двух/.test(perPerson[0]) ? Math.floor(total / 2) : total
  }

  // --- negative filters ---
  for (const match of lowered.matchAll(/(?:без|кроме|исключить|не\s+хочу)\s+([а-яёa-z,\s]+?)(?=[.,;]|$)/g)) {
    for (const tag of match[1].split(/,|\sи\s/)) {
      const cleaned = tag.trim().replace(/\s+/g, '_').slice(0, 40)
      if (cleaned.length > 2) result.excludeTags.push(cleaned)
    }
  }

  // --- semantic payload: strip facts, keep atmosphere words ---
  let semantic = lowered
    .replace(/\d{1,2}[:.]\d{2}/g, ' ')
    .replace(/\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)/g, ' ')
    .replace(/сегодня|завтра|послезавтра|выходные|выходной|в\s+субботу|в\s+воскресенье/g, ' ')
    .replace(/не дороже\s+\d[\d\s]*\s*(?:руб|р\b|byn)?/g, ' ')
    .replace(/до\s+\d[\d\s]*\s*(?:руб|р\b|byn)?/g, ' ')
    .replace(/без\s+[а-яёa-z,\s]+?(?=[.,;]|$)/g, ' ')
    .replace(/минск|минске|центре|центр|вдвоем|вдвоём|двое|нас\s+\d+/g, ' ')
    .replace(/(найди|найдите|подбери|подберите|покажи|покажите|что-нибудь|что-то|что угодно|пожалуйста)/g, ' ')
    .replace(/(?:на|для)\s+компани[а-яё]*(?:\s+из)?\s*\d*\s*человек[а-яё]*|компани[а-яё]*|\d{1,2}\s+человек[а-яё]*|вдво[её]м|втро[её]м/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/^(?:на|из)\s+|\s+(?:на|из)$/g, '')
  const followUpOnly = /^(?:а\s+)?(?:ещё|еще|подешевле|дешевле|подороже|дороже|другие|другой|варианты|что-нибудь|что-то|а\s+есть\s+ещё)[\s?.!]*$/
  // A bare "не важно" answers a slot question; it is not a semantic topic.
  result.vectorQuery = result.bareAny || followUpOnly.test(semantic) || semantic.length <= 2
    ? ''
    : semantic.slice(0, 300)

  return result
}

export function contractFromParsed(parsed: ParsedQuery, previous?: StateContract): StateContract {
  const previousTurn = previous?.context_state.turn_count ?? 0
  const previousHard = previous?.hard_filters
  const previousNegative = previous?.negative_filters
  // A bare "не важно" only means "any" for the slot the server just asked
  // about. Without that context it must behave as an empty follow-up.
  const asked = previous?.needs_clarification ? (previous.clarification_slots ?? []) : []
  const asksFor = (slot: string) => parsed.bareAny && asked.includes(slot)
  // A signal-less follow-up ("а подешевле?") inherits the previous section.
  const intent = parsed.intent ?? previous?.intent ?? 'both'
  // Categories exist only on the event axe: a venue search ("бар") must not
  // inherit an old event filter, and venue words never add one.
  const isEventIntent = intent === 'both' || intent.startsWith('find_event')
  const excludeTags = Array.from(new Set([
    ...(previousNegative?.exclude_tags ?? []),
    ...parsed.excludeTags,
  ]))
  const contract: StateContract = {
    dialogue_action: 'search',
    intent,
    clarify_missing: previous?.clarify_missing ?? true,
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: {
      location: parsed.cityAny || asksFor('city')
        ? { city: null, any: true }
        : previousHard?.location ?? {},
      category: previousHard?.category ?? [],
      themes: previousHard?.themes ?? [],
      party_size: parsed.partyAny || asksFor('party')
        ? 0
        : parsed.partyExplicit
          ? parsed.partySize
          : previousHard?.party_size,
      amenities_required: previousHard?.amenities_required ?? [],
    },
    negative_filters: {
      exclude_tags: excludeTags,
      exclude_categories: previousNegative?.exclude_categories ?? [],
      exclude_districts: previousNegative?.exclude_districts ?? [],
    },
    semantic_payload: {
      vector_query: parsed.vectorQuery || previous?.semantic_payload.vector_query || '',
      language: previous?.semantic_payload.language ?? DEFAULT_LANGUAGE,
    },
    context_state: {
      turn_count: previousTurn,
      session_id: previous?.context_state.session_id ?? `web_${Date.now()}`,
    },
  }
  if (parsed.start) {
    contract.hard_filters.datetime = {
      start: parsed.start,
      end: parsed.end,
      raw_expression: parsed.rawExpression,
    }
  } else if (parsed.dateAny || asksFor('datetime')) {
    contract.hard_filters.datetime = { any: true, raw_expression: parsed.rawExpression }
  } else if (previousHard?.datetime) {
    // Follow-up ("а подешевле?") keeps the date from the previous turn, even
    // when the user answered another slot with "не важно".
    contract.hard_filters.datetime = previousHard.datetime
  }
  const inheritedCategory = previousHard?.category?.length
    ? previousHard.category
    : undefined
  const category = isEventIntent
    ? (parsed.category.length ? parsed.category : inheritedCategory)
    : undefined
  if (category?.length) contract.hard_filters.category = category
  else if (!isEventIntent) contract.hard_filters.category = []
  if (parsed.budgetAny || asksFor('budget')) {
    contract.hard_filters.budget = { any: true }
  } else if (parsed.maxPrice !== undefined) {
    contract.hard_filters.budget = { max_price_per_person: parsed.maxPrice }
  } else if (previousHard?.budget) {
    contract.hard_filters.budget = previousHard.budget
  }
  return contract
}


const FOLLOW_UP_VECTOR = /^(?:а\s+)?(?:ещё|еще|подешевле|дешевле|подороже|дороже|другие|другой|варианты|что-нибудь|что-то)[\s?.!]*$/i

// Generic sections carry no topic of their own, so a specific intent from the
// other side should win.
const GENERIC = new Set(['find_events', 'find_venues', 'both'])

/** Prefer the model's semantic fields, keep deterministic local date parsing. */
export function mergeContracts(
  remote: StateContract,
  local: StateContract,
  parsed?: ParsedQuery,
  previous?: StateContract,
): StateContract {
  const remoteDate = remote.hard_filters.datetime
  const remoteVector = (remote.semantic_payload.vector_query || '').trim()
  // The local parser owns the slots the user actually named (or answered with
  // a bare "не важно" after the server asked). Everything else keeps the
  // model's value so an inherited local field cannot mask a model filter.
  const asked = previous?.needs_clarification ? (previous.clarification_slots ?? []) : []
  const localDateWins = parsed
    ? parsed.dateExplicit || (parsed.bareAny && asked.includes('datetime'))
    : Boolean(local.hard_filters.datetime?.start)
  const localBudgetWins = parsed
    ? parsed.maxPrice !== undefined
      || parsed.budgetAny
      || (parsed.bareAny && asked.includes('budget'))
    : local.hard_filters.budget !== undefined
  const localPartyWins = parsed
    ? parsed.partyExplicit
      || parsed.partyAny
      || (parsed.bareAny && asked.includes('party'))
    : local.hard_filters.party_size !== undefined
  // A follow-up inherits the date, so the model's "ask for a date" verdict
  // no longer applies: the turn has everything needed to search.
  const action = remote.dialogue_action === 'ask_clarification'
    && local.hard_filters.datetime?.start
    ? 'search'
    : remote.dialogue_action
  // Specific intent wins over generic on either side; local specific RU venue
  // words ("бар", "кофейня") beat a model that folded them into find_events.
  const localIntent = local.intent ?? 'both'
  const intent = remote.intent
    && (GENERIC.has(localIntent) || !GENERIC.has(remote.intent))
    ? remote.intent
    : localIntent
  return {
    ...local,
    dialogue_action: action,
    intent,
    clarify_missing: local.clarify_missing ?? remote.clarify_missing,
    hard_filters: {
      ...local.hard_filters,
      // Local parser owns RU date arithmetic; models often get weekdays wrong.
      // It only wins when the user named a date in this turn (inherited dates
      // must not mask a model-parsed "на следующей неделе").
      datetime: localDateWins
        ? local.hard_filters.datetime
        : remoteDate?.start
          ? {
              start: remoteDate.start,
              end: remoteDate.end,
              raw_expression: remoteDate.raw_expression,
            }
          : local.hard_filters.datetime,
      location: local.hard_filters.location?.any
        ? { ...(local.hard_filters.location ?? {}), city: null, any: true }
        : remote.hard_filters.location?.any
          ? { ...(local.hard_filters.location ?? {}), ...remote.hard_filters.location, city: null, any: true }
          : {
              ...(local.hard_filters.location ?? {}),
              city: remote.hard_filters.location?.city || local.hard_filters.location?.city,
              any: false,
            },
      category: intent.startsWith('find_venue')
        ? []
        : remote.hard_filters.category?.length
          ? remote.hard_filters.category
          : local.hard_filters.category,
      themes: remote.hard_filters.themes?.length
        ? remote.hard_filters.themes
        : local.hard_filters.themes,
      // Party size comes from the deterministic parser (incl. inheritance):
      // the model always defaults it to 2, which would reset a follow-up.
      party_size: localPartyWins
        ? local.hard_filters.party_size
        : local.hard_filters.party_size === 0
          ? 0
          : remote.hard_filters.party_size === 0
            ? 0
            : local.hard_filters.party_size || remote.hard_filters.party_size,
      budget: localBudgetWins
        ? local.hard_filters.budget
        : local.hard_filters.budget?.any
          ? { any: true }
          : remote.hard_filters.budget ?? local.hard_filters.budget,
      amenities_required: remote.hard_filters.amenities_required?.length
        ? remote.hard_filters.amenities_required
        : local.hard_filters.amenities_required,
    },
    negative_filters: {
      exclude_tags: Array.from(new Set([
        ...(local.negative_filters.exclude_tags ?? []),
        ...(remote.negative_filters.exclude_tags ?? []),
      ])),
      exclude_categories: Array.from(new Set([
        ...(local.negative_filters.exclude_categories ?? []),
        ...(remote.negative_filters.exclude_categories ?? []),
      ])),
      exclude_districts: Array.from(new Set([
        ...(local.negative_filters.exclude_districts ?? []),
        ...(remote.negative_filters.exclude_districts ?? []),
      ])),
    },
    semantic_payload: {
      ...local.semantic_payload,
      // "а ещё?" carries no meaning of its own — keep the previous topic.
      vector_query: FOLLOW_UP_VECTOR.test(remoteVector)
        ? local.semantic_payload.vector_query
        : remoteVector || local.semantic_payload.vector_query,
      language: remote.semantic_payload.language || local.semantic_payload.language,
    },
  }
}
