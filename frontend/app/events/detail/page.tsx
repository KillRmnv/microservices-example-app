'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ExternalLink, MapPin } from 'lucide-react'
import { DetailPageHeader, ErrorView, LoadingView, PageHeader, RuleTitle, VenueLocationBlock } from '@/components/secondary-page'
import { MapView } from '@/components/map-view'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { FALLBACK_EVENT_IMAGE, categoryLabel, eventImage, eventPlace, eventPrice, isBookable, sourceLabel } from '@/lib/catalog'
import { admissionLabel, formatDateTime, formatEventDuration, formatMoney, summarizeZones } from '@/lib/format'
import { formatDescription } from '@/lib/format-text'
import type { CatalogEvent, Event, Seat, Ticket, ZonedPrice } from '@/lib/types'

const ZONE_SUBTITLES: Record<string, string> = {
  VIP: 'Первые ряды, лучшие виды и отдельный вход.',
  FAN_ZONE: 'Танцевальная зона у сцены без рассадки.',
  BASIC: 'Стандартная зона по доступной цене.',
}

function EventDetails() {
  const params = useSearchParams()
  const auth = useAuth()
  const router = useRouter()
  const id = params.get('id') ?? ''

  const [catalog, setCatalog] = useState<CatalogEvent>()
  const [event, setEvent] = useState<Event>()
  const [venueName, setVenueName] = useState('')
  const [venueCapacity, setVenueCapacity] = useState(0)
  const [town, setTown] = useState('')
  const [zoneTickets, setZoneTickets] = useState<Ticket[]>([])
  const [seats, setSeats] = useState<Seat[]>([])
  const [error, setError] = useState<unknown>()
  const [ticketNotice, setTicketNotice] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(undefined)
    ;(async () => {
      try {
        if (!id) throw new Error('Событие не найдено')
        const found = await api.catalogEvent(id)
        setCatalog(found)
        if (found.booking_event_id != null) {
          const bookingEvent = await api.getEventById(found.booking_event_id)
          setEvent(bookingEvent)
          const venue = await api.getVenue(bookingEvent.venueId)
          setVenueName(venue.place)
          setVenueCapacity(venue.capacity)
          setTown(venue.townName)
          const [tickets, seatableTickets, seatList] = await Promise.all([
            api.getTickets(bookingEvent.id).catch(() => [] as Ticket[]),
            api.searchSeatableTickets({ eventId: bookingEvent.id, active: true }, 1, 500)
              .catch(() => [] as Ticket[]),
            api.getSeats(bookingEvent.venueId).catch(() => [] as Seat[]),
          ])
          setZoneTickets([...tickets, ...seatableTickets])
          setSeats(seatList)
        }
      } catch (e) {
        setError(e)
      }
    })()
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  const zonedPrices: ZonedPrice[] = useMemo(() => summarizeZones(zoneTickets), [zoneTickets])
  const description = useMemo(() => formatDescription(catalog?.description), [catalog?.description])

  const buy = async (zoneInfo: ZonedPrice) => {
    if (!auth.user) {
      router.push('/login')
      return
    }
    if (!event) return
    setBusy(true)
    try {
      const created = await api.createTicket({ eventId: event.id, zone: zoneInfo.zone, price: zoneInfo.price, active: true, userId: auth.user.id })
      setTicketNotice(`Билет №${created.id} оформлен. Он появится в вашем кабинете.`)
    } catch (e) {
      setTicketNotice(e instanceof Error ? e.message : 'Не удалось оформить билет')
    } finally {
      setBusy(false)
    }
  }

  if (error) return <ErrorView error={error} onRetry={load} />
  if (!catalog) return <LoadingView light />

  const bookable = isBookable(catalog)
  const coords = catalog.latitude != null && catalog.longitude != null
    ? [Number(catalog.latitude), Number(catalog.longitude)] as [number, number]
    : null
  const startsAt = event?.startsAt ?? catalog.start_at ?? undefined
  const endsAt = event?.endsAt ?? catalog.end_at ?? undefined

  return (
    <div className="detail-page" data-testid="event-detail-page">
      <DetailPageHeader
        kicker={`АФИШНЫЙ ВЫПУСК · ${categoryLabel(catalog.category).toUpperCase()}`}
        title={catalog.title}
        subline={`${formatDateTime(startsAt)} · ${eventPlace(catalog)}`}
        testid="event-title"
      />
      <div className="detail-body">
        <div>
          <div className="media-block">
            <img src={eventImage(catalog)} alt={catalog.title} onError={(e) => { e.currentTarget.src = FALLBACK_EVENT_IMAGE }} />
            <div className="media-bar">
              <div>
                <strong>{eventPlace(catalog)}</strong>
                <span>
                  {bookable ? admissionLabel(event?.admissionMode) : sourceLabel(catalog.source)} · {formatDateTime(startsAt)}
                </span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <RuleTitle>Общая информация</RuleTitle>
            <div className="detail-rows">
              <div className="detail-row"><span>Начало</span><strong>{formatDateTime(startsAt)}</strong></div>
              <div className="detail-row"><span>Продолжительность</span><strong>{formatEventDuration(startsAt, endsAt)}</strong></div>
              <div className="detail-row"><span>Формат</span><strong>{bookable ? admissionLabel(event?.admissionMode) : sourceLabel(catalog.source)}</strong></div>
              <div className="detail-row"><span>Категория</span><strong>{categoryLabel(catalog.category)}</strong></div>
              {venueCapacity > 0 && <div className="detail-row"><span>Вместимость площадки</span><strong>{venueCapacity}</strong></div>}
              <div className="detail-row">
                <span>Цена</span>
                <strong>{bookable && zonedPrices.length ? formatMoney(zonedPrices[0].price) : eventPrice(catalog)}</strong>
              </div>
            </div>
          </div>

          {catalog.description && (
            <div className="detail-section">
              <RuleTitle>Описание</RuleTitle>
              <div className="detail-description" data-testid="event-description">
                {description.map((paragraph, index) => (
                  <p key={`${index}-${paragraph.slice(0, 24)}`}>{paragraph}</p>
                ))}
              </div>
            </div>
          )}

          <div className="detail-section">
            <RuleTitle>Как добраться</RuleTitle>
            {coords ? (
              <MapView latitude={coords[0]} longitude={coords[1]} label={catalog.venue_name || venueName} address={catalog.address} />
            ) : (
              <div className="map-skeleton" data-testid="venue-map-placeholder">
                <MapPin size={26} />
                <strong>{catalog.venue_name || venueName || 'Площадка'}</strong>
                <p>{catalog.address || 'Адрес уточняется'}</p>
                <p>Карта появится, когда площадка найдётся в справочнике 2ГИС.</p>
              </div>
            )}
          </div>
        </div>

        <aside className="detail-sidebar">
          <div className="detail-container">
            {bookable ? (
              <VenueLocationBlock town={town || '—'} place={venueName} capacity={venueCapacity} />
            ) : (
              <div className="venue-location">
                <div className="venue-location-head"><MapPin size={15} /><span>ИСТОЧНИК</span></div>
                <div className="detail-rows stacked">
                  <div className="detail-row"><span>Афиша</span><strong>{sourceLabel(catalog.source)}</strong></div>
                  {catalog.address && <div className="detail-row"><span>Адрес</span><strong>{catalog.address}</strong></div>}
                </div>
              </div>
            )}
          </div>

          {bookable ? (
            <div className="price-list">
              <RuleTitle>Билеты по зонам</RuleTitle>
              {zonedPrices.length === 0 ? (
                <div className="empty-state compact"><h3>Продажи ещё не открылись</h3><p>Как только менеджер добавит билеты, цены появятся здесь.</p></div>
              ) : (
                zonedPrices.map((zoneInfo) => (
                  <div className="price-row" key={zoneInfo.zone} data-testid={`zone-price-${zoneInfo.zone.toLowerCase().replace(/_(.)/g, (_, c: string) => c.toUpperCase())}`}>
                    <div className="price-cell">
                      <span className="price-label">{zoneInfo.zone === 'VIP' ? 'VIP' : zoneInfo.zone === 'FAN_ZONE' ? 'Фан-зона' : 'Стандарт'}</span>
                      <strong>{formatMoney(zoneInfo.price)}</strong>
                      <span className="price-hint">{`свободно: ${zoneInfo.active} из ${zoneInfo.count}`}</span>
                      <p>{ZONE_SUBTITLES[zoneInfo.zone]}</p>
                    </div>
                    <button
                      className="buy-button"
                      disabled={busy || zoneInfo.count === 0}
                      onClick={() => buy(zoneInfo)}
                      data-testid={`buy-zone-${zoneInfo.zone.toLowerCase()}`}
                    >
                      {!auth.user ? 'Войти и купить' : zoneInfo.count > 0 ? 'Купить' : 'Скоро'}
                    </button>
                  </div>
                ))
              )}
              {seats.length > 0 && <p className="side-hint seat-count" data-testid="seat-count">На площадке {seats.length} мест по посадочной схеме.</p>}
              {ticketNotice && <p className="side-hint" data-testid="ticket-notice">{ticketNotice}</p>}
            </div>
          ) : (
            <div className="price-list">
              <RuleTitle>Билеты</RuleTitle>
              <p className="side-hint">Это событие собрано из открытой афиши. Наличие и цену уточняйте у источника.</p>
              {catalog.source_url && (
                <a className="apply-button" href={catalog.source_url} target="_blank" rel="noreferrer" data-testid="event-source-link">
                  Открыть на источнике <ExternalLink size={14} />
                </a>
              )}
            </div>
          )}

          <div className="detail-note">
            <span>РЕДАКЦИОННАЯ СВОДКА</span>
            <p>Информация собрана автоматически из открытых афиш города.</p>
          </div>
          <Link href="/events" className="read-more">Все события</Link>
        </aside>
      </div>
    </div>
  )
}

export default function Page() {
  return (
    <main className="detail-page-wrap">
      <PageHeader returnHref="/events" />
      <Suspense fallback={<LoadingView light />}>
        <EventDetails />
      </Suspense>
    </main>
  )
}
