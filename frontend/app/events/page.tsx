'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { ArrowRight, Clock3, MapPin, Search } from 'lucide-react'
import { ErrorView, ListPageHeader, LoadingView, PageHeader, SimpleDialog } from '@/components/secondary-page'
import { api } from '@/lib/api'
import { formatDateTime } from '@/lib/format'
import type { Event, Venue } from '@/lib/types'

function EventsList() {
  const params = useSearchParams()
  const [events, setEvents] = useState<Event[]>()

  const [search, setSearch] = useState('')
  const [error, setError] = useState<unknown>()
  const [venueFilter, setVenueFilter] = useState<number | null>(null)
  const [venues, setVenues] = useState<Venue[]>([])
  const [dialogOpen, setDialogOpen] = useState<Event | null>(null)

  useEffect(() => {
    ;(async () => {
      try {
        const [venueList] = await Promise.all([api.getVenues()])
        setVenues(venueList)
      } catch (e) {
        setError(e)
      }
    })()
  }, [])

  useEffect(() => {
    ;(async () => {
      const venueId = params.get('venueId')
      if (venueId) setVenueFilter(Number(venueId))
      try {
        const found = await api.searchEvents(venueId ? { venueId } : {}, 1, 40)
        setEvents(found)
      } catch (e) {
        setError(e)
      }
    })()
  }, [params])

  const filtered = useMemo(() => {
    if (!events) return []
    const query = search.toLowerCase().trim()
    return events.filter((event) => {
      if (query && !event.title.toLowerCase().includes(query)) return false
      return true
    })
  }, [events, search])

  const reload = useCallback(() => {
    setError(undefined)
    api
      .searchEvents(venueFilter ? { venueId: venueFilter } : {}, 1, 40)
      .then(setEvents)
      .catch(setError)
  }, [venueFilter])

  if (error) return <ErrorView error={error} onRetry={reload} />
  if (!events) return <LoadingView />

  return (
    <div className="list-page" data-testid="events-page">
      <ListPageHeader
        kicker="АФИША ГОРОДА"
        title="События"
        subline={`В выпуске ${filtered.length}${filtered.length === 1 ? '' : ''} событий`}
        searchValue={search}
        searchPlaceholder="Найти событие по названию…"
        onSearchChange={setSearch}
        searchTestId="event-search-name"
        append={
          <label className="list-select" data-testid="event-venue-filter-wrap">
            <select className={venueFilter === null ? '' : 'venue-active'} value={venueFilter ?? ''} onChange={(e) => setVenueFilter(e.target.value ? Number(e.target.value) : null)} style={{ width: '100%' }} data-testid="event-venue-filter">
              <option value="">Все площадки</option>
              {venues.map((venue) => (
                <option key={venue.id} value={venue.id} disabled={false}>
                  {venue.place}
                </option>
              ))}
            </select>
          </label>
        }
      />
      {filtered.length === 0 ? (
        <div className="empty-state"><h3>Пока пусто</h3><p>Афиша появится, когда менеджеры добавят события.</p></div>
      ) : (
        <div className="list-cards" data-testid="events-grid">
          {filtered.map((event) => (
            <Link href={`/events/detail?id=${event.id}`} key={event.id} className="list-card event-card" data-testid="event-card">
              <div className="list-card-head">
                <div>
                  <div className="kicker">{event.admissionMode === 'SEATABLE' ? 'МЕСТА ПО СЕКТОРАМ' : 'БЕЗ РАССАДКИ'}</div>
                  <h3>{event.title}</h3>
                  <p className="meta-line"><Clock3 size={13} /> {formatDateTime(event.startsAt)}</p>
                  <p className="meta-line venue"><MapPin size={13} /> {event.venuePlace}</p>
                </div>
                <ArrowRight size={18} className="list-arrow" />
              </div>
            </Link>
          ))}
        </div>
      )}
      {dialogOpen && (
        <SimpleDialog title={dialogOpen.title} subtitle={`${formatDateTime(dialogOpen.startsAt)} · ${dialogOpen.venuePlace}`} onClose={() => setDialogOpen(null)}>
          <p>Здесь будет подробная афиша события.</p>
        </SimpleDialog>
      )}
    </div>
  )
}

export default function Page() {
  return (
    <main className="detail-page-wrap" data-testid="events-page-wrap">
      <PageHeader returnHref="/" />
      <Suspense fallback={<LoadingView light />}>
        <EventsList />
      </Suspense>
    </main>
  )
}
