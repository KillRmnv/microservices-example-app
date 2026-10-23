'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight,
  CalendarDays,
  ChevronDown,
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
import { AssistantFab, ChatPanel } from '@/components/chat-panel'
import { api } from '@/lib/api'
import { admissionLabel, formatDateTime } from '@/lib/format'
import type { Event, SeatableTicket, Ticket, Town, Venue } from '@/lib/types'

interface EventCard {
  id: number
  title: string
  date: string
  place: string
  price?: string
  tag: string
  scarce: boolean
}

const CITIES = ['МИНСК', 'БРЕСТ', 'ГРОДНО']

function dayStart(offset: number): number {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d.getTime() + offset * 86_400_000
}

export default function Page() {
  const [dark, setDark] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [activeDay, setActiveDay] = useState('Все даты')
  const [customDate, setCustomDate] = useState('')
  const [activeCategory, setActiveCategory] = useState('Все')
  const [activeDistrict, setActiveDistrict] = useState<string[]>([])
  const [maxBudget, setMaxBudget] = useState(100)
  const [atmosphere, setAtmosphere] = useState('')
  const [view, setView] = useState<'grid' | 'map'>('grid')
  const [liked, setLiked] = useState<number[]>([])
  const [cityOpen, setCityOpen] = useState(false)
  const [city, setCity] = useState('МИНСК')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [events, setEvents] = useState<Event[]>([])
  const [venues, setVenues] = useState<Venue[]>([])
  const [towns, setTowns] = useState<Town[]>([])
  const [minPrices, setMinPrices] = useState<Map<number, number>>(new Map())

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [eventsList, venuesList, townsList, tickets, seatable] = await Promise.all([
          api.searchEvents({}, 1, 30),
          api.getVenues(),
          api.getTowns(),
          api.searchTickets({ active: true }, 1, 500),
          api.searchSeatableTickets({ active: true }, 1, 500),
        ])
        if (cancelled) return
        setEvents(eventsList)
        setVenues(venuesList)
        setTowns(townsList)
        const mins = new Map<number, number>()
        tickets.forEach((t) => {
          if (t.eventId == null) return
          const cur = mins.get(t.eventId)
          if (cur === undefined || t.price < cur) mins.set(t.eventId, t.price)
        })
        seatable.forEach((t) => {
          const cur = mins.get(t.eventId) ?? Number.POSITIVE_INFINITY
          if (t.price < cur) mins.set(t.eventId, t.price)
        })
        setMinPrices(mins)
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
  }, [])

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
        .filter((event) => matchesDay(event.startsAt))
        .filter((event) => {
          if (maxBudget < 100) {
            const price = minPrices.get(event.id)
            if (price === undefined || price > maxBudget) return false
          }
          return true
        })
        .sort((a, b) => new Date(a.startsAt).getTime() - new Date(b.startsAt).getTime())
        .slice(0, 12)
        .map((event) => {
          const price = minPrices.get(event.id)
          return {
            id: event.id,
            title: event.title,
            date: formatDateTime(event.startsAt),
            place: event.venuePlace,
            price: price !== undefined ? `от ${price} руб.` : undefined,
            tag: price === undefined ? admissionLabel(event.admissionMode).toUpperCase() : 'МЕСТА ЕСТЬ',
            scarce: price === undefined,
          }
        }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events, minPrices, activeDay, customDate, maxBudget],
  )

  const lead = cards[0]
  const rest = cards.slice(1)
  const sidebarVenues = useMemo(() => venues.slice(0, 6), [venues])
  const districts = ['Центральный', 'Советский', 'Фрунзенский', 'Октябрьский']
  const categories = ['Все', 'Концерты', 'Театр', 'Кино', 'Выставки', 'Рестораны']
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
    <main className={dark ? 'newspaper dark-mode' : 'newspaper'} data-testid="home-page">
      <NewspaperHeader dark={dark} onThemeToggle={() => setDark(!dark)} />

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
            <div className="map-placeholder" role="status" data-testid="map-placeholder">
              <MapPin size={28} />
              <h3>Карта событий</h3>
              <p>Здесь появится карта мест Минска: события, venues и подсказки ассистента.</p>
              <Link href="/places" className="read-more">Смотреть места <ArrowRight size={15} /></Link>
            </div>
          ) : (
            <>
              {!loading && lead && (
                <div className="lead-story" data-testid="lead-story">
                  <div className="lead-image">
                    <img src={`https://images.unsplash.com/photo-1501386761578-eac5c94b800a?auto=format&fit=crop&w=1000&q=85&seed=${lead.id}`} alt={lead.title} />
                    <span className="image-caption">ФОТО: АРХИВ РЕДАКЦИИ</span>
                  </div>
                  <div className="lead-copy">
                    <div className="kicker">ВЫБОР РЕДАКЦИИ</div>
                    <h3>{lead.title}</h3>
                    <p className="meta-line"><CalendarDays size={14} /> {lead.date}</p>
                    <p className="meta-line"><MapPin size={14} /> {lead.place}</p>
                    <p>{lead.price ? `${lead.tag} · ${lead.price}` : lead.tag}</p>
                    <Link href={`/events/detail?id=${lead.id}`} className="read-more" data-testid="lead-story-link">Читать далее <ArrowRight size={15} /></Link>
                  </div>
                </div>
              )}
              <div className="story-grid" data-testid="events-grid">
                {!loading && rest.map((event, index) => (
                  <article className="story-card" key={event.id} data-testid="event-card">
                    <div className="card-image">
                      <img src={`https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=700&q=75&seed=${event.id}`} alt={event.title} />
                      <button
                        className={liked.includes(event.id) ? 'fav-heart liked' : 'fav-heart'}
                        aria-label="Добавить в избранное"
                        onClick={() => setLiked(liked.includes(event.id) ? liked.filter((id) => id !== event.id) : [...liked, event.id])}
                        data-testid={`favorite-${event.id}`}
                      >
                        <Heart size={16} fill={liked.includes(event.id) ? 'currentColor' : 'none'} />
                      </button>
                    </div>
                    <div className="kicker">{index % 2 === 0 ? 'СОБЫТИЕ' : 'АФИША'}</div>
                    <h3><Link href={`/events/detail?id=${event.id}`}>{event.title}</Link></h3>
                    <p className="meta-line"><Clock3 size={13} /> {event.date}</p>
                    <p className="meta-line venue"><MapPin size={13} /> {event.place}</p>
                    <div className="card-footer">
                      <span className={event.scarce ? 'scarce' : ''}>{event.tag}</span>
                      <strong>{event.price ?? '—'}</strong>
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
            {sidebarVenues.map((venue) => {
              const town = towns.find((t) => t.id === venue.townId)
              const Icon = [Coffee, Sparkles, Utensils, Film, Music, PartyPopper][venue.id % 6]
              return (
                <article className="place-card" key={venue.id} data-testid="place-card">
                  <div className="place-icon"><Icon size={21} /></div>
                  <div>
                    <div className="kicker">МЕСТО{town ? ` · ${town.name.toUpperCase()}` : ''}</div>
                    <h3><Link href={`/places/detail?id=${venue.id}`}>{venue.place}</Link></h3>
                    <p>Вместимость: {venue.capacity}</p>
                  </div>
                  <Star size={17} className="place-star" />
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

      <AssistantFab onOpen={() => setChatOpen(true)} />
      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />

      <div className="city-picker-placeholder">
        <button className="city-btn" onClick={() => setCityOpen(!cityOpen)} data-testid="city-fab">
          <MapPin size={15} /> {city} <ChevronDown size={13} />
        </button>
        {cityOpen && (
          <div className="city-menu-fab" data-testid="city-options">
            {CITIES.map((c) => (
              <button key={c} onClick={() => { setCity(c); setCityOpen(false) }}>{c}</button>
            ))}
          </div>
        )}
      </div>

      <footer><div className="footer-line"><span>© 2026 «Досуг» · городская газета о досуге</span><span className="footer-links"><Link href="/about">О проекте</Link></span></div></footer>
    </main>
  )
}
