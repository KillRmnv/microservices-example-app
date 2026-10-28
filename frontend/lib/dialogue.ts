'use client'

// Client-side query structuring: deterministic rules that turn
// free text into a first StateContract. The server re-validates everything,
// asks for missing slots, and owns turn_count — this is only a first draft.
import type { StateContract } from './types'

const MONTHS: Record<string, number> = {
  января: 1, февраля: 2, марта: 3, апреля: 4, мая: 5, июня: 6,
  июля: 7, августа: 8, сентября: 9, октября: 10, ноября: 11, декабря: 12,
}

const WEEKDAYS = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']

const CATEGORY_KEYWORDS: Array<[RegExp, string]> = [
  [/концерт|музык|джаз|рок/i, 'concert'],
  [/спектакл|театр|балет|опера/i, 'theatre'],
  [/выставк|музей|галере/i, 'exhibition'],
  [/кино|фильм/i, 'film'],
  [/спорт|матч|стадион/i, 'sport'],
  [/детск|для детей/i, 'kids'],
  [/ресторан|кафе|бар|клуб|кофейн|еда|ужин|обед/i, 'restaurant'],
]

// Domain defaults are configuration, not logic.
const DEFAULT_CITY = process.env.NEXT_PUBLIC_DEFAULT_CITY ?? 'Минск'
const DEFAULT_LANGUAGE = process.env.NEXT_PUBLIC_DEFAULT_LANGUAGE ?? 'ru'

export interface ParsedQuery {
  rawExpression: string
  start?: string
  end?: string
  category: string[]
  partySize: number
  maxPrice?: number
  excludeTags: string[]
  vectorQuery: string
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
    category: [],
    partySize: 2,
    excludeTags: [],
    vectorQuery: '',
  }

  // --- datetime ---
  let day: Date | null = null
  let endDay: Date | null = null
  let time: string | null = null
  const timeMatch = lowered.match(/(\d{1,2})[:.](\d{2})/)
  if (timeMatch) time = `${pad(Number(timeMatch[1]))}:${timeMatch[2]}`
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
    for (let index = 0; index < WEEKDAYS.length; index += 1) {
      if (lowered.includes(WEEKDAYS[index])) {
        day = nextWeekday(now, index)
        break
      }
    }
  }
  if (day) {
    const stamp = time ?? '12:00'
    result.start = `${isoDay(day)}T${stamp}:00`
    const end = endDay ?? day
    result.end = `${isoDay(end)}T${time ?? '23:59'}:00`
  }

  // --- category ---
  for (const [pattern, category] of CATEGORY_KEYWORDS) {
    if (pattern.test(lowered)) result.category.push(category)
  }

  // --- party size ---
  const party = lowered.match(/нас\s+(\d{1,2})|вдво[её]м|двое|втро[её]м|(\d{1,2})\s+человек/)
  if (party) {
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
    .replace(/\s+/g, ' ')
    .trim()
  result.vectorQuery = semantic.slice(0, 300)

  return result
}

export function contractFromParsed(parsed: ParsedQuery, previous?: StateContract): StateContract {
  const previousTurn = previous?.context_state.turn_count ?? 0
  const contract: StateContract = {
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: {
      location: { city: DEFAULT_CITY },
      party_size: parsed.partySize,
    },
    negative_filters: { exclude_tags: parsed.excludeTags },
    semantic_payload: { vector_query: parsed.vectorQuery, language: DEFAULT_LANGUAGE },
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
  } else if (parsed.rawExpression) {
    contract.hard_filters.datetime = { raw_expression: parsed.rawExpression }
  }
  if (parsed.category.length) contract.hard_filters.category = parsed.category
  if (parsed.maxPrice !== undefined) {
    contract.hard_filters.budget = { max_price_per_person: parsed.maxPrice }
  }
  return contract
}
