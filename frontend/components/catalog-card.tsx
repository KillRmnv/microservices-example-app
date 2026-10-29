'use client'

import Link from 'next/link'
import { CalendarDays, MapPin, Star } from 'lucide-react'
import { FALLBACK_EVENT_IMAGE, categoryLabel, eventImage, eventPlace, eventPrice, isBookable } from '@/lib/catalog'
import { formatDateTime } from '@/lib/format'
import type { CatalogEvent, CatalogVenue } from '@/lib/types'

export function CatalogEventCard({ event }: { event: CatalogEvent }) {
  return (
    <article className="story-card" data-testid="event-card">
      <div className="card-image">
        <img src={eventImage(event)} alt={event.title} loading="lazy" onError={(e) => { e.currentTarget.src = FALLBACK_EVENT_IMAGE }} />
        {isBookable(event) && <span className="card-badge">БИЛЕТЫ</span>}
      </div>
      <div className="kicker">{categoryLabel(event.category).toUpperCase()}</div>
      <h3><Link href={`/events/detail?id=${encodeURIComponent(event.id)}`}>{event.title}</Link></h3>
      <p className="meta-line"><CalendarDays size={13} /> {formatDateTime(event.start_at ?? undefined)}</p>
      <p className="meta-line venue"><MapPin size={13} /> {eventPlace(event)}</p>
      <div className="card-footer">
        <span className={isBookable(event) ? '' : 'scarce'}>{isBookable(event) ? 'МЕСТА ЕСТЬ' : 'ВНЕШНЯЯ АФИША'}</span>
        <strong>{eventPrice(event)}</strong>
      </div>
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
