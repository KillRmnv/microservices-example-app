'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { MapPin } from 'lucide-react'
import { DetailPageHeader, ErrorView, FieldRow, LoadingView, PageHeader, RuleTitle, SectionView } from '@/components/secondary-page'
import { CatalogEventCard } from '@/components/catalog-card'
import { MapView } from '@/components/map-view'
import { api } from '@/lib/api'
import { venueCoords } from '@/lib/catalog'
import type { CatalogVenue } from '@/lib/types'

function VenueDetails() {
  const params = useSearchParams()
  const id = params.get('id') ?? ''

  const [venue, setVenue] = useState<CatalogVenue>()
  const [error, setError] = useState<unknown>()

  const load = useCallback(() => {
    setError(undefined)
    ;(async () => {
      try {
        if (!id) throw new Error('Место не найдено')
        setVenue(await api.catalogVenue(id))
      } catch (e) {
        setError(e)
      }
    })()
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  if (error) return <ErrorView error={error} onRetry={load} />
  if (!venue) return <LoadingView light />

  const coords = venueCoords(venue)
  const events = venue.events ?? []

  return (
    <div className="detail-page" data-testid="venue-detail-page">
      <div className="detail-page-header">
        <DetailPageHeader
          kicker={`СПРАВОЧНИК · ${(venue.rubric || 'место').toUpperCase()}`}
          title={venue.name}
          subline={venue.address || venue.city}
          testid="venue-title"
        />
      </div>
      <div className="detail-body">
        <div>
          <div className="detail-section">
            <RuleTitle>О месте</RuleTitle>
            <div className="detail-rows">
              <FieldRow label="Площадка" value={venue.name} />
              <FieldRow label="Город" value={venue.city} />
              <FieldRow label="Рубрика" value={venue.rubric || '—'} />
              <FieldRow label="Адрес" value={venue.address || '—'} />
              {venue.rating != null && <FieldRow label="Рейтинг 2ГИС" value={`${Number(venue.rating).toFixed(1)} (${venue.review_count ?? 0} отзывов)`} />}
            </div>
          </div>

          <div className="detail-section">
            <RuleTitle>Как добраться</RuleTitle>
            {coords ? (
              <MapView latitude={coords[0]} longitude={coords[1]} label={venue.name} address={venue.address} />
            ) : (
              <div className="map-skeleton" data-testid="venue-map-placeholder">
                <MapPin size={26} />
                <strong>{venue.name}</strong>
                <p>{venue.address || 'Адрес уточняется'}</p>
              </div>
            )}
          </div>

          <SectionView title="Афиша на площадке">
            {events.length === 0 ? (
              <div className="empty-state compact" data-testid="venue-events-empty">
                <h3>Событий пока нет</h3>
                <p>Когда на этой площадке появится афиша, она будет здесь.</p>
              </div>
            ) : (
              <div className="story-grid">
                {events.slice(0, 6).map((event) => <CatalogEventCard event={event} key={event.id} />)}
              </div>
            )}
          </SectionView>
        </div>
        <aside className="detail-sidebar">
          <div className="detail-container">
            <div className="venue-location">
              <div className="venue-location-head"><MapPin size={15} /><span>КРАТКАЯ СПРАВКА</span></div>
              <div className="detail-rows stacked">
                <FieldRow label="Место" value={venue.name} />
                <FieldRow label="Город" value={venue.city} />
                <FieldRow label="Событий в афише" value={events.length} />
              </div>
            </div>
          </div>
          <div className="detail-note">
            <span>ДАННЫЕ 2ГИС</span>
            <p>Адрес, рубрика и рейтинг подтянуты из справочника 2ГИС.</p>
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
