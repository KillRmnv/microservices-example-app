'use client'

import { useCallback, useEffect, useState } from 'react'
import { ErrorView, ListPageHeader, LoadingView, PageHeader } from '@/components/secondary-page'
import { CatalogPlaceCard } from '@/components/catalog-card'
import { api } from '@/lib/api'
import type { CatalogVenue } from '@/lib/types'

const PAGE_SIZE = 30
const CITIES = ['Минск', 'Гродно', 'Брест']
const RUBRICS = ['кафе', 'рестораны', 'бары', 'кинотеатры', 'театры', 'музеи', 'клубы', 'выставки', 'караоке', 'парки', 'библиотеки', 'спортзалы']

export default function Page() {
  const [venues, setVenues] = useState<CatalogVenue[]>([])
  const [total, setTotal] = useState(0)
  const [city, setCity] = useState('Минск')
  const [rubric, setRubric] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<unknown>()

  const load = useCallback(async (offset = 0, append = false) => {
    setError(undefined)
    if (offset === 0) setLoading(true)
    else setLoadingMore(true)
    try {
      const page = await api.catalogVenues({
        city: city || undefined,
        rubric: rubric || undefined,
        q: search.trim() || undefined,
        limit: PAGE_SIZE,
        offset,
      })
      setVenues((current) => (append ? [...current, ...page.items] : page.items))
      setTotal(page.total)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [city, rubric, search])

  useEffect(() => {
    void load(0, false)
  }, [load])

  if (error) return <ErrorView error={error} onRetry={() => load(0, false)} />
  if (loading) return <LoadingView />

  return (
    <main className="detail-page-wrap" data-testid="places-page-wrap">
      <PageHeader returnHref="/" />
      <div className="list-page" data-testid="places-page">
        <ListPageHeader
          kicker="СПРАВОЧНИК ГОРОДА · 2ГИС"
          title="Места"
          subline={`${total} площадок, где можно провести вечер`}
          searchValue={search}
          searchPlaceholder="Найти место: «кофейня», «филармония»…"
          onSearchChange={setSearch}
          onSearchSubmit={() => load(0, false)}
          searchTestId="place-search-name"
          append={
            <div className="catalog-filters">
              <select value={city} onChange={(e) => setCity(e.target.value)} data-testid="place-city-filter">
                {CITIES.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
              <select value={rubric} onChange={(e) => setRubric(e.target.value)} data-testid="place-rubric-filter">
                <option value="">Все рубрики</option>
                {RUBRICS.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </div>
          }
        />

        {venues.length === 0 ? (
          <div className="empty-state" data-testid="places-empty">
            <h3>Справочник пуст</h3>
            <p>Попробуйте другую рубрику или город.</p>
          </div>
        ) : (
          <div className="places-grid" data-testid="venues-grid">
            {venues.map((venue) => <CatalogPlaceCard venue={venue} key={venue.id} />)}
          </div>
        )}

        {venues.length > 0 && venues.length < total && (
          <div className="load-more-row">
            <button className="apply-button" disabled={loadingMore} onClick={() => load(venues.length, true)} data-testid="places-load-more">
              {loadingMore ? 'Загружаем…' : `Показать ещё (${total - venues.length})`}
            </button>
          </div>
        )}
      </div>
    </main>
  )
}
