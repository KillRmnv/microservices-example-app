'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { ArrowRight, CalendarDays, MapPin } from 'lucide-react'
import { ErrorView, ListPageHeader, LoadingView, PageHeader } from '@/components/secondary-page'
import { CatalogEventCard } from '@/components/catalog-card'
import { api } from '@/lib/api'
import { CATEGORY_OPTIONS, categoryLabel, eventImage, eventPlace, eventPrice, isBookable, todayIso } from '@/lib/catalog'
import { formatDateTime } from '@/lib/format'
import type { CatalogEvent } from '@/lib/types'

const PAGE_SIZE = 24
const CITIES = ['Минск', 'Гродно', 'Брест']

function EventsList() {
  const params = useSearchParams()
  const [search, setSearch] = useState('')
  const [city, setCity] = useState('Минск')
  const [category, setCategory] = useState('')
  const [date, setDate] = useState('')
  const [events, setEvents] = useState<CatalogEvent[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<unknown>()
  const [searching, setSearching] = useState(false)

  const load = useCallback(async (nextOffset = 0, append = false) => {
    setError(undefined)
    if (nextOffset === 0) setLoading(true)
    else setLoadingMore(true)
    try {
      const page = await api.catalogEvents({
        city: city || undefined,
        category: category || undefined,
        dateFrom: date || todayIso(),
        dateTo: date || undefined,
        limit: PAGE_SIZE,
        offset: nextOffset,
      })
      setEvents((current) => (append ? [...current, ...page.items] : page.items))
      setTotal(page.total)
      setOffset(nextOffset)
    } catch (e) {
      setError(e)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [city, category, date])

  useEffect(() => {
    const fromUrl = params.get('category')
    if (fromUrl) setCategory(fromUrl)
  }, [params])

  useEffect(() => {
    void load(0, false)
  }, [load])

  const searchNow = async () => {
    const query = search.trim()
    if (!query) {
      await load(0, false)
      return
    }
    setSearching(true)
    setError(undefined)
    try {
      let found: CatalogEvent[] = []
      try {
        const ids = await api.hybridSearchEvents(query, { city: city || undefined, category: category || undefined, limit: PAGE_SIZE })
        if (ids.length) {
          const page = await api.catalogEvents({ ids, limit: ids.length })
          const byId = new Map(page.items.map((item) => [item.id, item]))
          found = ids.map((id) => byId.get(id)).filter((item): item is CatalogEvent => Boolean(item))
        }
      } catch {
        found = []
      }
      if (!found.length) {
        found = await api.catalogSearchEvents(query, { city: city || undefined, category: category || undefined, limit: PAGE_SIZE })
      }
      setEvents(found)
      setTotal(found.length)
    } catch (e) {
      setError(e)
    } finally {
      setSearching(false)
    }
  }

  const lead = useMemo(() => events[0], [events])
  const rest = useMemo(() => events.slice(1), [events])

  if (error) return <ErrorView error={error} onRetry={() => load(0, false)} />
  if (loading) return <LoadingView />

  return (
    <div className="list-page" data-testid="events-page">
      <ListPageHeader
        kicker="АФИША ГОРОДА"
        title="События"
        subline={`В выпуске ${total} ${total === 1 ? 'событие' : 'событий'}`}
        searchValue={search}
        searchPlaceholder="Найти событие: «джаз», «балет», «UFC»…"
        onSearchChange={setSearch}
        onSearchSubmit={searchNow}
        searchTestId="event-search-name"
        append={
          <div className="catalog-filters">
            <select value={city} onChange={(e) => setCity(e.target.value)} data-testid="event-city-filter">
              {CITIES.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
            <select value={category} onChange={(e) => setCategory(e.target.value)} data-testid="event-category-filter">
              <option value="">Все категории</option>
              {CATEGORY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="event-date-filter" aria-label="Дата события" />
          </div>
        }
      />

      {searching && <LoadingView light />}

      {!searching && events.length === 0 && (
        <div className="empty-state" data-testid="events-empty">
          <h3>Пока пусто</h3>
          <p>Смягчите фильтры или загляните позже — афиша обновляется каждый день.</p>
        </div>
      )}

      {!searching && lead && (
        <div className="lead-story" data-testid="lead-story">
          <div className="lead-image">
            <img src={eventImage(lead)} alt={lead.title} />
            <span className="image-caption">{isBookable(lead) ? 'БИЛЕТЫ В КАССЕ' : 'ИСТОЧНИК: ВНЕШНЯЯ АФИША'}</span>
          </div>
          <div className="lead-copy">
            <div className="kicker">ВЫБОР РЕДАКЦИИ · {categoryLabel(lead.category).toUpperCase()}</div>
            <h3>{lead.title}</h3>
            <p className="meta-line"><CalendarDays size={14} /> {formatDateTime(lead.start_at ?? undefined)}</p>
            <p className="meta-line"><MapPin size={14} /> {eventPlace(lead)}</p>
            <p>{eventPrice(lead)}</p>
            <Link href={`/events/detail?id=${encodeURIComponent(lead.id)}`} className="read-more" data-testid="lead-story-link">
              Читать далее <ArrowRight size={15} />
            </Link>
          </div>
        </div>
      )}

      {!searching && rest.length > 0 && (
        <div className="story-grid" data-testid="events-grid">
          {rest.map((event) => <CatalogEventCard event={event} key={event.id} />)}
        </div>
      )}

      {!searching && events.length > 0 && events.length < total && (
        <div className="load-more-row">
          <button className="apply-button" disabled={loadingMore} onClick={() => load(offset + PAGE_SIZE, true)} data-testid="events-load-more">
            {loadingMore ? 'Загружаем…' : `Показать ещё (${total - events.length})`}
          </button>
        </div>
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
