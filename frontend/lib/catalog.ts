import type { CatalogEvent, CatalogVenue } from './types'

export const CATEGORY_LABELS: Record<string, string> = {
  concert: 'Концерты',
  theatre: 'Театр',
  exhibition: 'Выставки',
  film: 'Кино',
  sport: 'Спорт',
  kids: 'Детям',
  other: 'Другое',
}

export const CATEGORY_OPTIONS = Object.entries(CATEGORY_LABELS)

// Feed codes -> the name a reader recognises. Unknown codes are shown as-is
// (a concrete source beats a vague "external listing" label).
export const SOURCE_LABELS: Record<string, string> = {
  ticketpro: 'Ticketpro',
  telegram: 'Telegram',
  afisha_me: 'Afisha.me',
  relax: 'Afisha.relax.by',
  bycard: 'ByCard',
  '24afisha': '24afisha',
  twogis_places: '2ГИС',
  twogis: '2ГИС',
  booking: 'Досуг',
  assistant: 'Ассистент',
}

export function sourceLabel(source: string | null | undefined): string {
  const raw = (source ?? '').trim()
  if (!raw) return 'Источник'
  return SOURCE_LABELS[raw.toLowerCase()] ?? raw
}

export function categoryLabel(category: string | null | undefined): string {
  if (!category) return 'Событие'
  return CATEGORY_LABELS[category] ?? category
}

export const FALLBACK_EVENT_IMAGE = '/event-placeholder.svg'

export function eventImage(event: CatalogEvent): string {
  return event.image_url?.trim() || FALLBACK_EVENT_IMAGE
}

export function eventPlace(event: CatalogEvent): string {
  return event.venue_name?.trim() || event.city || 'Город'
}

export function eventPrice(event: CatalogEvent): string {
  if (event.price_min == null && event.price_max == null) return 'цена уточняется'
  const currency = event.currency || 'BYN'
  const suffix = currency === 'BYN' ? 'руб.' : currency
  if (event.price_min != null && event.price_max != null && event.price_max > event.price_min) {
    return `${event.price_min}–${event.price_max} ${suffix}`
  }
  return `от ${event.price_min ?? event.price_max} ${suffix}`
}

export function isBookable(event: CatalogEvent): boolean {
  return event.booking_event_id != null
}

/** Fields a film row may carry; all are optional in older payloads. */
export interface FilmMetaSource {
  category?: string | null
  start_at?: string | null
  end_at?: string | null
  next_session_at?: string | null
  cinema?: string | null
  film_genre?: string[] | null
  film_duration_min?: number | null
}

const pad2 = (value: number): string => String(value).padStart(2, '0')

export function isFilmEvent(event: FilmMetaSource): boolean {
  const category = (event.category ?? '').trim().toLowerCase()
  return category === 'film'
    || (event.film_genre?.length ?? 0) > 0
    || event.film_duration_min != null
}

/** "05.12" for a multi-day cinema run, empty for a single show. */
export function filmRunUntil(event: FilmMetaSource): string {
  if (!event.start_at || !event.end_at) return ''
  const start = new Date(event.start_at).getTime()
  const end = new Date(event.end_at).getTime()
  if (!Number.isFinite(start) || !Number.isFinite(end)) return ''
  if (end - start <= 24 * 60 * 60 * 1000) return ''
  const date = new Date(event.end_at)
  return `${pad2(date.getDate())}.${pad2(date.getMonth() + 1)}`
}

/** "19:30" of the nearest exact show, empty when the source has none. */
export function filmSessionTime(event: FilmMetaSource): string {
  if (!event.next_session_at) return ''
  const date = new Date(event.next_session_at)
  if (Number.isNaN(date.getTime())) return ''
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

export function filmSessionLabel(event: FilmMetaSource): string {
  const time = filmSessionTime(event)
  if (!time) return ''
  const cinema = event.cinema?.trim()
  return cinema ? `Ближайший сеанс ${time} · ${cinema}` : `Ближайший сеанс ${time}`
}

/** Short genre/duration chips the backend also exposes structurally. */
export function filmFacts(event: FilmMetaSource): string[] {
  const facts = (event.film_genre ?? []).map((genre) => genre.trim()).filter(Boolean)
  if (event.film_duration_min != null && event.film_duration_min > 0) {
    facts.push(`${event.film_duration_min} мин`)
  }
  return facts
}

/** "Продажа билетов" link: a dedicated ticket page first, the source next. */
export function eventTicketUrl(event: Pick<CatalogEvent, 'source_url' | 'ticket_url'>): string {
  return event.ticket_url?.trim() || event.source_url?.trim() || ''
}

/** "128 отзывов" — the count label next to a venue rating. */
export function reviewsLabel(count: number): string {
  const mod10 = count % 10
  const mod100 = count % 100
  const noun = mod10 === 1 && mod100 !== 11
    ? 'отзыв'
    : mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)
      ? 'отзыва'
      : 'отзывов'
  return `${count} ${noun}`
}

export function venueCoords(venue: Pick<CatalogVenue, 'latitude' | 'longitude'>): [number, number] | null {
  if (venue.latitude == null || venue.longitude == null) return null
  return [Number(venue.latitude), Number(venue.longitude)]
}

export function twoGisLink(lat: number, lon: number): string {
  return `https://2gis.by/geo/${lon},${lat}`
}

export function todayIso(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
