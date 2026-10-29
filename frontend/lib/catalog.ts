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
