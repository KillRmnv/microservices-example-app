'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  CalendarDays,
  ChevronRight,
  Clock3,
  Coffee,
  Film,
  Filter,
  Heart,
  MapPin,
  MessageSquareText,
  Music,
  PartyPopper,
  SlidersHorizontal,
  Sparkles,
  Star,
  Utensils,
} from 'lucide-react'
import { NewspaperHeader, RuleTitle } from '@/components/newspaper-header'
import { MapView } from '@/components/map-view'
import { api } from '@/lib/api'
import { useCity } from '@/lib/city'
import { CATEGORY_LABELS, FALLBACK_EVENT_IMAGE, eventImage, eventPlace, eventPrice, isBookable, todayIso } from '@/lib/catalog'
import { formatDateTime } from '@/lib/format'
import type { CatalogEvent, CatalogVenue } from '@/lib/types'

interface EventCard {
  id: string
  title: string
  date: string
  place: string
  price?: string
  tag: string
  scarce: boolean
  image: string
  bookable: boolean
  startsAt: string
}

function dayStart(offset: number): number {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime() + offset * 86_400_000
}

export default function Page() {
  const [activeDay, setActiveDay] = useState('Все даты')
  const [customDate, setCustomDate] = useState('')
  const [activeCategory, setActiveCategory] = useState('Все')
  const [activeDistrict, setActiveDistrict] = useState<string[]>([])
  const [maxBudget, setMaxBudget] = useState(100)
  const [atmosphere, setAtmosphere] = useState('')
  const [view, setView] = useState<'grid' | 'map'>('grid')
  const [liked, setLiked] = useState<string[]>([])
  const { city } = useCity()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [events, setEvents] = useState<CatalogEvent[]>([])
  const [venues, setVenues] = useState<CatalogVenue[]>([])

  const catalogCity = city

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [eventsPage, venuesPage] = await Promise.all([
          api.catalogEvents({ city: catalogCity, dateFrom: todayIso(), limit: 60 }),
          api.catalogVenues({ city: catalogCity, limit: 8 }),
        ])
        if (cancelled) return
        setEvents(eventsPage.items)
        setVenues(venuesPage.items)
        setLoading(false)
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Ошибка загрузки')
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [catalogCity])

  const matchesDay = (startsAt: string) => {
    const ts = new Date(startsAt).getTime()
    if (customDate) {
      const target = new Date(`${customDate}T00:00:00`).getTime()
      const eventDay = new Date(new Date(startsAt).setHours(0, 0, 0, 0)).getTime()
      return eventDay === target
    }
    if (activeDay === 'Сегодня') return ts >= dayStart(0) && ts < dayStart(1)
    if (activeDay === 'Завтра') return ts >= dayStart(1) && ts < dayStart(2)
    if (activeDay === 'Выходные') {
      const date = new Date(startsAt)
      return (date.getDay() === 6 || date.getDay() === 0) && ts >= dayStart(0) && ts < dayStart(7)
    }
    return true
  }

  const cards: EventCard[] = useMemo(
    () =>
      events
        .filter((event) => event.start_at && matchesDay(event.start_at))
        .filter((event) => {
          const category = (CATEGORY_LABELS[event.category] ?? '').toLowerCase()
          if (activeCategory !== 'Все' && category !== activeCategory.toLowerCase()) return false
          if (maxBudget < 100) {
            const price = event.price_min
            if (price == null || price > maxBudget) return false
          }
          return true
        })
        .sort((a, b) => new Date(a.start_at ?? 0).getTime() - new Date(b.start_at ?? 0).getTime())
        .slice(0, 12)
        .map((event) => ({
          id: event.id,
          title: event.title,
          date: formatDateTime(event.start_at ?? undefined),
          place: eventPlace(event),
          price: eventPrice(event),
          tag: isBookable(event) ? 'МЕСТА ЕСТЬ' : 'ВНЕШНЯЯ АФИША',
          scarce: !isBookable(event),
          image: eventImage(event),
          bookable: isBookable(event),
          startsAt: event.start_at ?? '',
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events, activeDay, customDate, maxBudget, activeCategory],
  )

  const lead = cards[0]
  const rest = cards.slice(1)
  const sidebarVenues = useMemo(() => venues.slice(0, 6), [venues])
  const districts = ['Центральный', 'Советский', 'Фрунзенский', 'Октябрьский']
  const categories = ['Все', 'Концерты', 'Театр', 'Кино', 'Выставки', 'Спорт', 'Детям']
  const activeFilterCount = useMemo(() => {
    let count = 0
    if (activeDay !== 'Все даты' || customDate) count += 1
    if (activeCategory !== 'Все') count += 1
    count += activeDistrict.length
    if (maxBudget < 100) count += 1
    if (atmosphere.trim()) count += 1
    return count
  }, [activeDay, customDate, activeCategory, activeDistrict, maxBudget, atmosphere])

  const resetFilters = () => {
    setActiveDay('Все даты')
    setActiveCategory('Все')
    setActiveDistrict([])
    setMaxBudget(100)
    setAtmosphere('')
    setCustomDate('')
  }

  return (
    <main className="newspaper" data-testid="home-page">
      <NewspaperHeader />

      <div className="page-grid">
        <section className="content">
          <div className="intro">
            <div>
              <div className="kicker">ПЕРВАЯ ПОЛОСА · ВЫПУСК 014</div>
              <h2>Куда пойти<br /><em>сегодня</em></h2>
            </div>
            <p className="intro-copy">Собрали лучшее, что происходит в городе: от тихих выставок до концертов под открытым небом. Выбирайте по настроению.</p>
          </div>

          <div className="filters-row">
            <div className="filter-tabs" data-testid="home-day-tabs">
              {['Все даты', 'Сегодня', 'Завтра', 'Выходные'].map((day) => (
                <button key={day} className={activeDay === day && !customDate ? 'selected' : ''} onClick={() => { setActiveDay(day); setCustomDate('') }}>{day}</button>
              ))}
            </div>
            <button className="filter-button"><SlidersHorizontal size={15} /> Фильтры <span>{activeFilterCount}</span></button>
          </div>

          <div className="section-head">
            <RuleTitle>{loading ? 'Загружаем выпуск…' : error ? 'Выпуск не поступил' : 'События недели'}</RuleTitle>
            <div className="view-switch" data-testid="home-view-switch">
              <button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} data-testid="view-grid">Сетка</button>
              <button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')} data-testid="view-map">Карта</button>
            </div>
          </div>

          {error ? (
            <div className="empty-state" data-testid="home-error"><h3>Не удалось связаться с редакцией</h3><p>{error}</p></div>
          ) : view === 'map' ? (
            <div data-testid="home-map">
              <MapView
                label={`События · ${catalogCity}`}
                markers={events
                  .filter((event) => event.latitude != null && event.longitude != null)
                  .slice(0, 40)
                  .map((event) => ({
                    latitude: Number(event.latitude),
                    longitude: Number(event.longitude),
                    label: event.title,
                  }))}
              />
              <p className="side-hint">На карте — площадки ближайших событий. Нажмите «Места», чтобы посмотреть весь справочник 2ГИС.</p>
              <Link href="/places" className="read-more">Смотреть места <ArrowRight size={15} /></Link>
            </div>
          ) : (
            <>
              {!loading && lead && (
                <div className="lead-story" data-testid="lead-story">
                  <div className="lead-image">
                    <img src={lead.image} alt={lead.title} onError={(e) => { e.currentTarget.src = FALLBACK_EVENT_IMAGE }} />
                    <span className="image-caption">{lead.bookable ? 'БИЛЕТЫ В КАССЕ' : 'ИСТОЧНИК: ВНЕШНЯЯ АФИША'}</span>
                  </div>
                  <div className="lead-copy">
                    <div className="kicker">ВЫБОР РЕДАКЦИИ</div>
                    <h3>{lead.title}</h3>
                    <p className="meta-line"><CalendarDays size={14} /> {lead.date}</p>
                    <p className="meta-line"><MapPin size={14} /> {lead.place}</p>
                    <p>{lead.tag} · {lead.price}</p>
                    <Link href={`/events/detail?id=${encodeURIComponent(lead.id)}`} className="read-more" data-testid="lead-story-link">Читать далее <ArrowRight size={15} /></Link>
                  </div>
                </div>
              )}
              <div className="story-grid" data-testid="events-grid">
                {!loading && rest.map((event, index) => (
                  <article className="story-card" key={event.id} data-testid="event-card">
                    <div className="card-image">
                      <img src={event.image} alt={event.title} loading="lazy" onError={(e) => { e.currentTarget.src = FALLBACK_EVENT_IMAGE }} />
                      <button
                        className={liked.includes(event.id) ? 'fav-heart liked' : 'fav-heart'}
                        aria-label="Добавить в избранное"
                        onClick={() => setLiked(liked.includes(event.id) ? liked.filter((id) => id !== event.id) : [...liked, event.id])}
                        data-testid={`favorite-${event.id}`}
                      >
                        <Heart size={16} fill={liked.includes(event.id) ? 'currentColor' : 'none'} />
                      </button>
                    </div>
                    <div className="kicker">{(index % 2 === 0 ? 'СОБЫТИЕ' : 'АФИША') + (event.bookable ? ' · БИЛЕТЫ' : '')}</div>
                    <h3><Link href={`/events/detail?id=${encodeURIComponent(event.id)}`}>{event.title}</Link></h3>
                    <p className="meta-line"><Clock3 size={13} /> {event.date}</p>
                    <p className="meta-line venue"><MapPin size={13} /> {event.place}</p>
                    <div className="card-footer">
                      <span className={event.scarce ? 'scarce' : ''}>{event.tag}</span>
                      <strong>{event.price}</strong>
                    </div>
                  </article>
                ))}
                {loading && [0, 1, 2, 3, 4, 5].map((i) => (
                  <div className="story-card" key={i} data-testid="event-card-skeleton">
                    <div className="card-image skeleton" />
                    <div className="kicker">—</div>
                    <h3>Загрузка…</h3>
                  </div>
                ))}
                {!loading && cards.length === 0 && (
                  <div className="empty-state"><h3>По этой подборке пусто</h3><p>Смягчите фильтры или посмотрите все события.</p><Link href="/events" className="read-more">Все события <ArrowRight size={14} /></Link></div>
                )}
              </div>
            </>
          )}

          <div className="section-head places-head">
            <RuleTitle>Места для вечера</RuleTitle>
            <Link href="/places" className="all-link" data-testid="all-places-link">Все места <ArrowRight size={15} /></Link>
          </div>
          <div className="places-grid" data-testid="places-grid">
            {sidebarVenues.slice(0, 6).map((venue, index) => {
              const Icon = [Coffee, Sparkles, Utensils, Film, Music, PartyPopper][index % 6]
              return (
                <article className="place-card" key={venue.id} data-testid="place-card">
                  <div className="place-icon"><Icon size={21} /></div>
                  <div>
                    <div className="kicker">{(venue.rubric || 'МЕСТО').toUpperCase()}{venue.city ? ` · ${venue.city.toUpperCase()}` : ''}</div>
                    <h3><Link href={`/places/detail?id=${encodeURIComponent(venue.id)}`}>{venue.name}</Link></h3>
                    <p>{venue.address || venue.city}</p>
                  </div>
                  {venue.rating != null ? <span className="place-rating"><Star size={15} /> {Number(venue.rating).toFixed(1)}</span> : <Star size={17} className="place-star" />}
                </article>
              )
            })}
            {!loading && venues.length === 0 && <div className="empty-state"><h3>Справочник мест пуст</h3><p>Площадки появятся, как только менеджеры их добавят.</p></div>}
          </div>
        </section>

        <aside className="sidebar" data-testid="filters-sidebar">
          <div className="sidebar-heading">
            <Filter size={16} />
            <span>Настроить выпуск</span>
            {activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}
          </div>
          <div className="side-section">
            <label>КОГДА</label>
            <div className="side-chips" data-testid="filters-days">
              {['Сегодня', 'Завтра', 'Выходные'].map((day) => (
                <button key={day} className={activeDay === day && !customDate ? 'black-chip' : ''} onClick={() => { setActiveDay(day); setCustomDate('') }}>{day}</button>
              ))}
            </div>
            <label className="date-line">
              <CalendarDays size={15} />
              <span>{customDate ? new Date(`${customDate}T00:00:00`).toLocaleDateString('ru-RU') : 'Любая дата'}</span>
              <ChevronRight size={14} />
              <input aria-label="Выбрать любую дату" type="date" value={customDate} onChange={(e) => { setCustomDate(e.target.value); setActiveDay('Все даты') }} data-testid="filters-date" />
            </label>
          </div>
          <div className="side-section">
            <label>КАТЕГОРИИ</label>
            <div className="category-list" data-testid="filters-categories">
              {categories.map((cat) => (
                <button key={cat} className={activeCategory === cat ? 'cat-active' : ''} onClick={() => setActiveCategory(cat)}>
                  {activeCategory === cat && <span className="checkbox">×</span>}
                  {cat}
                </button>
              ))}
            </div>
            <p className="side-hint">Отбор по категориям уточнятся, когда появится ассистент. Даты и бюджет уже работают.</p>
          </div>
          <div className="side-section">
            <label>РАЙОН</label>
            <div className="side-chips" data-testid="filters-districts">
              {districts.map((district) => (
                <button key={district} className={activeDistrict.includes(district) ? 'black-chip' : ''} onClick={() => setActiveDistrict(activeDistrict.includes(district) ? activeDistrict.filter((d) => d !== district) : [...activeDistrict, district])}>{district}</button>
              ))}
            </div>
            <p className="side-hint">Районы прикрепляются к месту площадки.</p>
          </div>
          <div className="side-section">
            <label>БЮДЖЕТ <span className="label-value">{maxBudget < 100 ? `до ${maxBudget} руб.` : 'любой'}</span></label>
            <input type="range" min="10" max="100" step="5" value={maxBudget} onChange={(e) => setMaxBudget(Number(e.target.value))} data-testid="filters-budget" />
          </div>
          <div className="side-section">
            <label>АТМОСФЕРА</label>
            <textarea placeholder="Например: уютно, живая музыка, без толпы…" rows={3} value={atmosphere} onChange={(e) => setAtmosphere(e.target.value)} data-testid="filters-atmosphere" />
          </div>
          <button className="apply-button" onClick={() => setView('grid')} data-testid="apply-filters">Показать подборку <ArrowRight size={15} /></button>
          <button className="reset-button" onClick={resetFilters} data-testid="reset-filters">Сбросить всё</button>
          <div className="ad-note">
            <span>МЕСТО ПОД ОБЪЯВЛЕНИЕ</span>
            <p>Ваше событие может быть здесь</p>
            <button>Узнать больше</button>
          </div>
          <div className="ad-note editorial-note">
            <MessageSquareText size={16} />
            <span>ОПЫТ ГЕНЕРАЦИИ</span>
            <p>Фронтенд-приложение сгенерировано и доработано ассистентом.</p>
          </div>
        </aside>
      </div>

    </main>
  )
}
