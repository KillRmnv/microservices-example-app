import type { Event, Ticket, Zone } from './types'

export const placeholders = (n: number): number[] => Array.from({ length: n }, (_, i) => i)

const MONTHS_NOMINATIVE = [
  'ЯНВАРЯ', 'ФЕВРАЛЯ', 'МАРТА', 'АПРЕЛЯ', 'МАЯ', 'ИЮНЯ',
  'ИЮЛЯ', 'АВГУСТА', 'СЕНТЯБРЯ', 'ОКТЯБРЯ', 'НОЯБРЯ', 'ДЕКАБРЯ',
]
const MONTHS_LOWER = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
]
const WEEKDAYS_SHORT = ['ВС', 'ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ']
const WEEKDAYS_FULL = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']

const time = (date: Date): string => `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`

export function formatDateTime(iso: string | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return `${WEEKDAYS_SHORT[date.getDay()]}, ${date.getDate()} ${MONTHS_NOMINATIVE[date.getMonth()]} · ${time(date)}`
}

export function formatFullDate(iso: string | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getDate()} ${MONTHS_LOWER[date.getMonth()]} ${date.getFullYear()}, ${time(date)}`
}

export function formatTimeRange(startIso: string, endIso: string | undefined): string {
  if (!endIso) return '—'
  const start = new Date(startIso)
  const end = new Date(endIso)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return '—'
  const minutes = Math.round((end.getTime() - start.getTime()) / 60000)
  if (minutes <= 0) return time(end)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  const human = [hours ? `${hours} ч` : '', rest ? `${rest} мин` : ''].filter(Boolean).join(' ')
  return `${human} · до ${time(end)}`
}

export function mastheadDate(): string {
  const date = new Date()
  return `${WEEKDAYS_FULL[date.getDay()].toUpperCase()}, ${date.getDate()} ${MONTHS_NOMINATIVE[date.getMonth()]} ${date.getFullYear()}`
}

export function formatMoney(value: number | undefined): string {
  if (value === undefined || value === null) return '—'
  return `${value} руб.`
}

export function admissionLabel(mode: string | undefined): string {
  if (mode === 'SEATABLE') return 'Места по секторам'
  if (mode === 'GENERAL') return 'Общий вход'
  return 'Событие'
}

export function zoneLabel(zone: Zone | string): string {
  if (zone === 'VIP') return 'VIP'
  if (zone === 'FAN_ZONE') return 'FAN ZONE'
  return 'BASIC'
}

export interface ZonePrice {
  zone: Zone
  price: number
  count: number
  active: number
}

export function summarizeZones(tickets: Ticket[]): ZonePrice[] {
  const byZone = new Map<Zone, ZonePrice>()
  tickets.forEach((ticket) => {
    if (!ticket.active) return
    const entry = byZone.get(ticket.zone) ?? { zone: ticket.zone, price: ticket.price, count: 0, active: 0 }
    entry.count += 1
    entry.active += 1
    entry.price = Math.min(entry.price, ticket.price)
    byZone.set(ticket.zone, entry)
  })
  return [...byZone.values()].sort((a, b) => a.price - b.price)
}

export function availabilityBadge(total: number, active: number): { label: string; scarce: boolean } {
  if (total === 0) return { label: 'БИЛЕТОВ НЕТ', scarce: true }
  if (active === 0) return { label: 'РАСПРОДАНО', scarce: true }
  if (active <= 3) return { label: 'ОСТАЛОСЬ МАЛО', scarce: true }
  return { label: 'Места есть', scarce: false }
}

export function minActivePrice(tickets: Ticket[]): number | undefined {
  const prices = tickets.filter((ticket) => ticket.active).map((ticket) => ticket.price)
  return prices.length ? Math.min(...prices) : undefined
}

const EDITORIAL_PHOTOS = [
  'photo-1470229722913-7c0e2dbbafd0',
  'photo-1503095406548-810b24a20123',
  'photo-1554907984-15263bfd63bd',
  'photo-1414235077428-338989a2e8c0',
  'photo-1519501025264-65ba15a82390',
  'photo-1489599849927-2b91ca8354bb',
  'photo-1477414348463-c0eb7f1359b6',
  'photo-1501281668745-f7f57925c3b4',
]

export const fallbackPhotoUrl = `https://images.unsplash.com/${EDITORIAL_PHOTOS[0]}?auto=format&fit=crop&w=900&q=80`

export const eventPhotoUrl = (seed: number, width = 700): string =>
  `https://images.unsplash.com/${EDITORIAL_PHOTOS[seed % EDITORIAL_PHOTOS.length]}?auto=format&fit=crop&w=${width}&q=80`

export function eventImageSeed(event: Event): string {
  return eventPhotoUrl(event.id)
}
