'use client'

import Link from 'next/link'
import { Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { Clock3, MapPin } from 'lucide-react'
import { DetailPageHeader, ErrorView, VenueLocationBlock, LoadingView, PageHeader, RuleTitle, SimpleDialog } from '@/components/secondary-page'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { admissionLabel, eventPhotoUrl, fallbackPhotoUrl, formatDateTime, formatMoney, formatTimeRange, summarizeZones } from '@/lib/format'
import type { Event, Seat, Ticket, ZonedPrice } from '@/lib/types'

const ZONE_SUBTITLES: Record<string, string> = {
  VIP: 'Первые ряды, лучшие виды и отдельный вход.',
  FAN_ZONE: 'Танцевальная зона у сцены без рассадки.',
  BASIC: 'Стандартная зона по доступной цене.',
}

function EventDetails() {
  const params = useSearchParams()
  const auth = useAuth()
  const id = Number(params.get('id'))

  const [event, setEvent] = useState<Event>()
  const [venueName, setVenueName] = useState('')
  const [venueCapacity, setVenueCapacity] = useState(0)
  const [town, setTown] = useState('')
  const [zoneTickets, setZoneTickets] = useState<Ticket[]>([])
  const [seats, setSeats] = useState<Seat[]>([])
  const [error, setError] = useState<unknown>()
  const [ticketNotice, setTicketNotice] = useState('')
  const [authPrompt, setAuthPrompt] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    setError(undefined)
    ;(async () => {
      try {
        if (!Number.isFinite(id) || id <= 0) {
          setError(new Error('Событие не найдено'))
          return
        }
        const found = await api.getEventById(id)
        setEvent(found)
        const venue = await api.getVenue(found.venueId)
        setVenueName(venue.place)
        setVenueCapacity(venue.capacity)
        setTown(venue.townName)
        const [tickets, seatList] = await Promise.all([
          api.getTickets(found.id),
          api.getSeats(found.venueId).catch(() => [] as Seat[]),
        ])
        setZoneTickets(tickets)
        setSeats(seatList)
      } catch (e) {
        setError(e)
      }
    })()
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  const zonedPrices: ZonedPrice[] = useMemo(() => summarizeZones(zoneTickets), [zoneTickets])

  const buy = async (zoneInfo: ZonedPrice) => {
    if (!auth.user || !event) {
      setAuthPrompt(true)
      return
    }
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
  if (!event) return <LoadingView light />

  return (
    <div className="detail-page" data-testid="event-detail-page">
      <DetailPageHeader
        kicker="АФИШНЫЙ ВЫПУСК · ПЕРВАЯ СТРАНИЦА"
        title={event.title}
        subline={`${formatDateTime(event.startsAt)} · ${event.venuePlace}`}
        testid="event-title"
      />
      <div className="detail-body">
        <div>
          <div className="media-block">
            <img src={eventPhotoUrl(event.id, 900)} alt={event.title} onError={(e) => { e.currentTarget.src = fallbackPhotoUrl }} />
            <div className="media-bar">
              <div>
                <strong>{event.venuePlace}</strong>
                <span>{admissionLabel(event.admissionMode)} · {formatDateTime(event.startsAt)}</span>
              </div>
            </div>
          </div>

          <div className="detail-section">
            <RuleTitle>Общая информация</RuleTitle>
            <div className="detail-rows">
              <div className="detail-row"><span>Начало</span><strong>{formatDateTime(event.startsAt)}</strong></div>
              <div className="detail-row"><span>Продолжительность</span><strong>{formatTimeRange(event.startsAt, event.endsAt)}</strong></div>
              <div className="detail-row"><span>Формат</span><strong>{admissionLabel(event.admissionMode)}</strong></div>
              <div className="detail-row"><span>Вместимость площадки</span><strong>{venueCapacity}</strong></div>
              <div className="detail-row"><span>Минимальная цена</span><strong>{zonedPrices.length ? formatMoney(zonedPrices[0].price) : 'Билеты скоро появятся'}</strong></div>
            </div>
          </div>

          <div className="detail-section">
            <RuleTitle>Как добраться</RuleTitle>
            <div className="map-skeleton" data-testid="venue-map-placeholder">
              <MapPin size={26} />
              <strong>{event.venuePlace}</strong>
              <p>Карта места появится здесь после подключения 2ГИС.</p>
            </div>
          </div>
        </div>

        <aside className="detail-sidebar">
          <div className="detail-container">
            <VenueLocationBlock town={town || '—'} place={venueName} capacity={venueCapacity} />
          </div>
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
                    disabled={busy || !auth.user || zoneInfo.count === 0}
                    onClick={() => buy(zoneInfo)}
                    data-testid={`buy-zone-${zoneInfo.zone.toLowerCase()}`}
                  >
                    {!auth.user ? 'Войти и купить' : zoneInfo.count > 0 ? 'Купить' : 'Скоро'}
                  </button>
                </div>
              ))
            )}
            {seats.length > 0 && (
              <p className="side-hint seat-count" data-testid="seat-count">На площадке {seats.length} мест по посадочной схеме.</p>
            )}
          </div>
          <div className="detail-note">
            <span>РЕДАКЦИОННАЯ СВОДКА</span>
            <p>Зоны и цены размечаются менеджером площадки. Выбор конкретных мест появится вместе с новой версией продаж.</p>
          </div>
          <div className="detail-actions">
            <Link href="/events" className="read-more"><Clock3 size={14} /> Все события выпуска</Link>
          </div>
        </aside>
      </div>
      {authPrompt && (
        <SimpleDialog title="Нужна подписка" subtitle="Чтобы оформить билет, войдите в личный кабинет." onClose={() => setAuthPrompt(false)}>
          <div className="dialog-actions">
            <Link href="/login" className="apply-button" data-testid="dialog-login-link">Войти</Link>
            <button className="reset-button" onClick={() => setAuthPrompt(false)}>Позже</button>
          </div>
        </SimpleDialog>
      )}
      {ticketNotice && (
        <SimpleDialog title="Редакционная сводка" onClose={() => setTicketNotice('')} testid="buy-notice">
          <p>{ticketNotice}</p>
        </SimpleDialog>
      )}
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
