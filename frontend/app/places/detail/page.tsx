'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { MapPin } from 'lucide-react'
import { DetailPageHeader, ErrorView, FieldRow, LoadingView, PageHeader, RuleTitle, SectionView } from '@/components/secondary-page'
import { api } from '@/lib/api'
import type { Event } from '@/lib/types'

function VenueDetails() {
  const params = useSearchParams()
  const id = Number(params.get('id'))

  const [venue, setVenue] = useState<Awaited<ReturnType<typeof api.getVenue>>>()
  const [events, setEvents] = useState<Event[]>([])
  const [error, setError] = useState<unknown>()

  const load = useCallback(() => {
    setError(undefined)
    ;(async () => {
      try {
        if (!Number.isFinite(id) || id <= 0) {
          setError(new Error('Место не найдено'))
          return
        }
        const found = await api.getVenue(id)
        setVenue(found)
      } catch (e) {
        setError(e)
      }
    })()
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!venue) return
    api.searchEvents({ venueId: venue.id }, 1, 50).then(setEvents).catch((e) => console.warn(e))
  }, [venue?.id])

  const upcoming = useMemo(
    () => [...events].sort((a, b) => a.startsAt.localeCompare(b.startsAt)).slice(0, 4),
    [events],
  )

  if (error) return <ErrorView error={error} onRetry={load} />
  if (!venue) return <LoadingView light />

  return (
    <div className="detail-page" data-testid="venue-detail-page">
      <div className="detail-page-header">
        <DetailPageHeader kicker={`СПРАВОЧНИК · ${venue.place.toUpperCase()}`} title={venue.townName} subline="Площадка и расписание" testid="venue-title" />
      </div>
      <div className="detail-body">
        <div>
          <div className="detail-section">
            <RuleTitle>О месте</RuleTitle>
            <div className="detail-rows">
              <FieldRow label="Площадка" value={venue.place} />
              <FieldRow label="Город" value={venue.townName} />
              <FieldRow label="Вместимость" value={venue.capacity} />
            </div>
          </div>

          <div className="detail-section">
            <RuleTitle>Как добраться</RuleTitle>
            <div className="map-skeleton" data-testid="venue-map-placeholder">
              <MapPin size={26} />
              <strong>{venue.place}</strong>
              <p>Карта города {venue.townName} появится здесь после подключения 2ГИС.</p>
            </div>
          </div>

          <SectionView title="Афиша на площадке">
            {upcoming.length === 0 ? (
              <div className="empty-state compact" data-testid="venue-events-empty"><h3>Событий пока нет</h3><p>Когда менеджеры добавят афишу этого места, она появится здесь.</p></div>
            ) : (
              <div className="detail-story-card-grid">
                {upcoming.map((event) => (
                  <Link href={`/events/detail?id=${event.id}`} className="detail-story-card" key={event.id} data-testid="venue-event-card">
                    <div className="kicker">{venue.townName.toUpperCase()}</div>
                    <h3>{event.title}</h3>
                    <p>{event.venuePlace}</p>
                    <span>Открыть событие</span>
                  </Link>
                ))}
              </div>
            )}
          </SectionView>
        </div>
        <aside className="detail-sidebar">
          <div className="detail-container">
            <div className="venue-location">
              <div className="venue-location-head"><MapPin size={15} /><span>КРАТКАЯ СПРАВКА</span></div>
              <div className="detail-rows stacked">
                <FieldRow label="Место" value={venue.place} />
                <FieldRow label="Город" value={venue.townName} />
                <FieldRow label="Событий в афише" value={events.length} />
              </div>
            </div>
          </div>
          <div className="detail-note">
            <span>МЕСТО В ВЫПУСКЕ</span>
            <p>Редакция добавляет фото и описания площадок в следующих выпусках.</p>
          </div>
          <Link href="/places" className="read-more">Все места города</Link>
        </aside>
      </div>
    </div>
  )
}

export default function Page() {
  return (
    <main className="detail-page-wrap">
      <PageHeader returnHref="/places" />
      <Suspense fallback={<LoadingView light />}>
        <VenueDetails />
      </Suspense>
    </main>
  )
}
