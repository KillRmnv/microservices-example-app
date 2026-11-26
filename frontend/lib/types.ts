export type Role = 'CUSTOMER' | 'ADMIN' | 'EVENT_MANAGER'

export interface User {
  id: number
  username: string
  email: string
  role: Role | string
  isSystem?: boolean
}

export interface LoginResponse {
  jwt: string
  id: number
  role: Role | string
}

export type AdmissionMode = 'SEATABLE' | 'GENERAL'
export type Zone = 'VIP' | 'FAN_ZONE' | 'BASIC'

export interface Event {
  id: number
  title: string
  startsAt: string
  endsAt: string
  venueId: number
  venuePlace: string
  admissionMode: AdmissionMode
}

export interface Venue {
  id: number
  townId: number
  townName: string
  place: string
  capacity: number
}

export interface Town {
  id: number
  name: string
}

export interface Seat {
  id: number
  sector: string
  row: string
  number: string
  venueId: number
  venuePlace: string
}

export interface Ticket {
  id: number
  eventId: number
  eventTitle: string
  zone: Zone
  price: number
  active: boolean
  userId?: number | null
}

export interface SeatableTicket extends Omit<Ticket, 'id'> {
  id: number
  seatId: number
  sector: string
  row: string
  number: string
}

export interface ZonedPrice {
  zone: Zone
  price: number
  count: number
  active: number
}

export type DialogueAction =
  | 'search'
  | 'update_filters'
  | 'confirm_booking'
  | 'ask_clarification'

export interface StateContract {
  dialogue_action: DialogueAction
  intent?: string
  clarify_missing?: boolean
  needs_clarification: boolean
  clarification_prompt: string | null
  clarification_slots?: string[]
  hard_filters: {
    datetime?: {
      start?: string
      end?: string
      raw_expression?: string
      timezone?: string
      any?: boolean
    }
    location?: {
      city?: string | null
      districts?: string[]
      any?: boolean
    }
    category?: string[]
    themes?: string[]
    party_size?: number
    budget?: {
      max_price_per_person?: number
      /** Whole-party cap; the backend derives the per-person figure from it. */
      total?: number | null
      /** "total" means the cap applies to the whole party, not one person. */
      basis?: 'per_person' | 'total'
      any?: boolean
    }
    amenities_required?: string[]
    age_max?: number | null
    min_rating?: number | null
    /** How many stops a plan should contain ("два события"). */
    event_count?: number | null
  }
  negative_filters: {
    exclude_categories?: string[]
    exclude_tags?: string[]
    exclude_districts?: string[]
  }
  semantic_payload: {
    vector_query: string
    language: string
  }
  context_state: {
    turn_count: number
    session_id: string
    /** Card ids already shown to the reader; the backend skips them on "ещё". */
    shown_ids?: string[]
  }
}

// --- public catalog (collector_db, mirrored from scrapers + booking) ---

export interface CatalogEvent {
  id: string
  source: string
  source_url: string
  /** Optional direct ticket page when the source exposes one. */
  ticket_url?: string | null
  booking_event_id: number | null
  title: string
  description?: string | null
  category: string
  start_at: string | null
  end_at: string | null
  venue_name?: string | null
  address?: string | null
  city: string
  price_min?: number | null
  price_max?: number | null
  currency?: string | null
  image_url?: string | null
  venue_id?: string | null
  latitude?: number | null
  longitude?: number | null
  venue_ref?: string | null
  venue_rating?: number | null
  venue_review_count?: number | null
  age_limit?: number | null
  /** Film-only extras; scraped cinema rows may omit any of them. */
  next_session_at?: string | null
  cinema?: string | null
  film_genre?: string[] | null
  film_duration_min?: number | null
}

export interface CatalogVenue {
  id: string
  source: string
  source_url?: string | null
  name: string
  rubric?: string | null
  address?: string | null
  city: string
  latitude?: number | null
  longitude?: number | null
  rating?: number | null
  review_count?: number | null
  schedule?: Record<string, unknown> | null
  events?: CatalogEvent[]
}

export interface CatalogPage<T> {
  total: number
  limit: number
  offset: number
  items: T[]
}
