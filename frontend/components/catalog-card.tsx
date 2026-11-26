'use client'

import Link from 'next/link'
import { CalendarDays, MapPin, Star } from 'lucide-react'
import {
  categoryLabel,
  eventImage,
  eventPlace,
  eventPrice,
  eventTicketUrl,
  filmFacts,
  filmRunUntil,
  filmSessionLabel,
  isBookable,
  isFilmEvent,
  reviewsLabel,
} from '@/lib/catalog'
import { formatDateTime } from '@/lib/format'
import type { CatalogEvent, CatalogVenue } from '@/lib/types'
import { EventImage } from '@/components/event-image'

export function CatalogEventCard({ event }: { event: CatalogEvent }) {
  const film = isFilmEvent(event)
  const ticketUrl = eventTicketUrl(event)
  const facts = film ? filmFacts(event) : []
  const runUntil = film ? filmRunUntil(event) : ''
  const session = film ? filmSessionLabel(event) : ''
  return (
    <article className="story-card" data-testid="event-card">
      <EventImage className="card-image" src={eventImage(event)} alt={event.title}>
        {isBookable(event) && <span className="card-badge">БИЛЕТЫ</span>}
      </EventImage>
      <div className="kicker">{categoryLabel(event.category).toUpperCase()}</div>
      <h3><Link href={`/events/detail?id=${encodeURIComponent(event.id)}`}>{event.title}</Link></h3>
      <p className="meta-line"><CalendarDays size={13} /> {formatDateTime(event.start_at ?? undefined)}</p>
      {runUntil && (
        <p className="meta-line" data-testid="event-film-run">Прокат до {runUntil}</p>
      )}
      {session && (
        <p className="meta-line" data-testid="event-film-session">{session}</p>
      )}
      {facts.length > 0 && (
        <p className="film-facts" data-testid="event-film-facts">
          {facts.map((fact) => <span className="chip chip-muted" key={fact}>{fact}</span>)}
        </p>
      )}
      <p className="meta-line venue"><MapPin size={13} /> {eventPlace(event)}</p>
      {event.venue_rating != null && (
        <p className="meta-line venue-rating" data-testid="event-venue-rating">
          <span className="place-rating"><Star size={13} /> {Number(event.venue_rating).toFixed(1)}</span>
          <span>
            2ГИС{event.venue_review_count != null ? ` · ${reviewsLabel(event.venue_review_count)}` : ''}
          </span>
        </p>
      )}
      <div className="card-footer">
        <span className={isBookable(event) ? '' : 'scarce'}>{isBookable(event) ? 'МЕСТА ЕСТЬ' : 'ВНЕШНЯЯ АФИША'}</span>
        <strong>{eventPrice(event)}</strong>
      </div>
      {film && ticketUrl && (
        <a
          className="read-more card-ticket-link"
          href={ticketUrl}
          target="_blank"
          rel="noreferrer"
          data-testid="event-ticket-link"
        >
          Билеты
        </a>
      )}
    </article>
  )
}

export function CatalogPlaceCard({ venue }: { venue: CatalogVenue }) {
  return (
    <article className="place-card" data-testid="place-card">
      <div className="place-icon"><MapPin size={20} /></div>
      <div>
        <div className="kicker">
          {(venue.rubric || 'место').toUpperCase()}{venue.city ? ` · ${venue.city.toUpperCase()}` : ''}
        </div>
        <h3><Link href={`/places/detail?id=${encodeURIComponent(venue.id)}`}>{venue.name}</Link></h3>
        <p>{venue.address || venue.city}</p>
      </div>
      {venue.rating != null ? (
        <span className="place-rating"><Star size={15} /> {Number(venue.rating).toFixed(1)}</span>
      ) : (
        <Star size={17} className="place-star" />
      )}
    </article>
  )
}
