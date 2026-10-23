'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, MapPin } from 'lucide-react'
import { ErrorView, ListPageHeader, LoadingView, PageHeader } from '@/components/secondary-page'
import { api } from '@/lib/api'
import type { Town, Venue } from '@/lib/types'

export default function Page() {
  const [venues, setVenues] = useState<Venue[]>()
  const [towns, setTowns] = useState<Town[]>([])
  const [search, setSearch] = useState('')
  const [townFilter, setTownFilter] = useState<number | null>(null)
  const [error, setError] = useState<unknown>()

  const load = () => {
    setError(undefined)
    ;(async () => {
      try {
        const [venueList, townList] = await Promise.all([api.getVenues(), api.getTowns()])
        setVenues(venueList)
        setTowns(townList)
      } catch (e) {
        setError(e)
      }
    })()
  }

  useEffect(load, [])

  const filtered = useMemo(
    () =>
      (venues ?? [])
        .filter((venue) => (townFilter === null ? true : venue.townId === townFilter))
        .filter((venue) => venue.place.toLowerCase().includes(search.toLowerCase().trim())),
    [venues, search, townFilter],
  )

  if (error) return <ErrorView error={error} onRetry={load} />
  if (!venues) return <LoadingView />

  return (
    <div className="list-page" data-testid="places-page">
      <ListPageHeader
        kicker="СПРАВОЧНИК ГОРОДА"
        title="Места"
        subline="Площадки, где сейчас сверстывается афиша"
        searchValue={search}
        searchPlaceholder="Найти место по названию…"
        onSearchChange={setSearch}
        searchTestId="place-search-name"
        append={
          <select className={townFilter === null ? '' : 'venue-active'} value={townFilter ?? ''} onChange={(e) => setTownFilter(e.target.value ? Number(e.target.value) : null)} data-testid="town-filter">
            <option value="">Все города</option>
            {towns.map((town) => (
              <option key={town.id} value={town.id}>{town.name}</option>
            ))}
          </select>
        }
      />
      {filtered.length === 0 ? (
        <div className="empty-state" data-testid="places-empty"><h3>Справочник пуст</h3><p>Площадки появятся, когда менеджеры их добавят.</p></div>
      ) : (
        <div className="list-cards" data-testid="venues-grid">
          {filtered.map((venue) => (
            <Link href={`/places/detail?id=${venue.id}`} key={venue.id} className="list-card venue-card" data-testid="venue-card">
              <div className="list-card-head">
                <div>
                  <div className="kicker">{venues.find((v) => v.townId === venue.townId)?.townName ?? 'В ГОРОДЕ'}</div>
                  <h3>{venue.place}</h3>
                  <p className="meta-line venue"><MapPin size={13} /> Вместимость: {venue.capacity}</p>
                </div>
                <ArrowRight size={18} className="list-arrow" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
