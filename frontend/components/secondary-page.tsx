'use client'

import Link from 'next/link'
import { useEffect, useState, type ReactNode } from 'react'
import { ChevronLeft, Eye, EyeOff, Newspaper, RefreshCcw } from 'lucide-react'
import { NewspaperHeader, RuleTitle } from '@/components/newspaper-header'
import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import type { Event, Seat, SeatableTicket, Ticket, Town, User, Venue } from '@/lib/types'

export { RuleTitle } from '@/components/newspaper-header'

export function PageHeader({
  returnHref,
  light,
  section,
  title,
  lead,
}: {
  returnHref?: string
  light?: boolean
  section?: string
  title?: string
  lead?: string
}) {
  return (
    <>
      <NewspaperHeader returnLink={returnHref ? { href: returnHref, label: 'Назад' } : undefined} />
      {(section || title || lead) && (
        <div className="article-intro">
          {section && <div className="kicker">{section}</div>}
          {title && <h2>{title}</h2>}
          {lead && <p>{lead}</p>}
        </div>
      )}
    </>
  )
}

export function LoadingView({ light, message = 'Вёрстка полосы…' }: { light?: boolean; message?: string }) {
  return <StubView light={light} title={message} text="Секунду, мы сворачиваем типографский станок." icon={<Newspaper size={30} />} />
}

export function ErrorView({ light, error, onRetry }: { light?: boolean; error: unknown; onRetry?: () => void }) {
  return (
    <StubView
      light={light}
      title="Выпуск не поступил"
      text={error instanceof Error ? error.message : 'Что-то пошло не так при связи с редакцией.'}
      icon={<RefreshCcw size={30} />}
      action={onRetry ? { label: 'Повторить', onClick: onRetry } : undefined}
      testid="page-error"
    />
  )
}

export function StubView({
  light,
  title = 'Полоса исчезла из макета',
  text = 'Этот раздел ещё сверстан не до конца: редакция обещает дописать полосу в ближайшем выпуске.',
  icon,
  action,
  testid = 'stub-view',
  children,
}: {
  light?: boolean
  title?: string
  text?: string
  icon?: ReactNode
  action?: { label: string; onClick: () => void }
  testid?: string
  children?: ReactNode
}) {
  return (
    <div className={light ? 'detail-page light' : 'detail-page'} data-testid={testid}>
      {icon && <div className="stub-icon">{icon}</div>}
      <h1>{title}</h1>
      <p>{text}</p>
      <div className="stub-buttons">
        <Link href="/" className="read-more">Вернуться на главную <ChevronLeft size={14} /></Link>
        {action && <button className="reset-button" onClick={action.onClick} data-testid="retry-button">{action.label}</button>}
      </div>
      {children}
    </div>
  )
}

export function NoAccessView({ message, actionLabel, href }: { message: string; actionLabel?: string; href?: string }) {
  return (
    <StubView light title="Раздел для подписчиков" text={message} icon={<EyeOff size={30} />} testid="no-access">
      <div className="stub-buttons">
        <Link href={href ?? '/login'} className="read-more">{actionLabel ?? 'Войти в кабинет'} <ChevronLeft size={14} /></Link>
      </div>
    </StubView>
  )
}

export function SimpleDialog({
  title,
  subtitle,
  children,
  onClose,
  width,
  testid,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  onClose: () => void
  width?: string
  testid?: string
}) {
  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog-card" style={width ? { width } : undefined} onClick={(e) => e.stopPropagation()} data-testid={testid}>
        <div className="dialog-head">
          <div>
            <div className="kicker">РЕДАКЦИОННЫЙ БЛАНК</div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button onClick={onClose} aria-label="Закрыть" data-testid="dialog-close">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function DetailPageHeader({ kicker, title, subline, testid }: { kicker: string; title: string; subline?: string; testid?: string }) {
  return (
    <div className="detail-page-header">
      <div className="kicker">{kicker}</div>
      <h1 data-testid={testid}>{title}</h1>
      {subline && <p className="detail-subline">{subline}</p>}
    </div>
  )
}

export function ListPageHeader({
  kicker,
  title,
  subline,
  searchValue,
  searchPlaceholder,
  onSearchChange,
  onSearchSubmit,
  searchTestId,
  append,
}: {
  kicker: string
  title: string
  subline: string
  searchValue?: string
  searchPlaceholder: string
  onSearchChange: (value: string) => void
  onSearchSubmit?: () => void
  searchTestId: string
  append?: ReactNode
}) {
  return (
    <div className="list-page-header">
      <div className="kicker">{kicker}</div>
      <h1 data-testid="list-title">{title}</h1>
      <p className="list-subline">{subline}</p>
      <div className="list-attach">
        {append}
        <div className="list-search">
          <input
            placeholder={searchPlaceholder}
            value={searchValue ?? ''}
            onChange={(e) => onSearchChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && onSearchSubmit) onSearchSubmit() }}
            data-testid={searchTestId}
          />
        </div>
      </div>
    </div>
  )
}

export function SectionView({ title, children, headRight }: { title: string; children: ReactNode; headRight?: ReactNode }) {
  return (
    <section className="detail-section">
      <div className="section-head section-head-detail">
        <RuleTitle>{title}</RuleTitle>
        {headRight}
      </div>
      {children}
    </section>
  )
}

export function FieldRow({ label, value, bold }: { label: string; value: ReactNode; bold?: boolean }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong className={bold ? 'bold' : undefined}>{value}</strong>
    </div>
  )
}

export function VenueLocationBlock({ town, place, capacity }: { town: string; place: string; capacity: number }) {
  return (
    <div className="venue-location">
      <div className="venue-location-head">
        <Eye size={15} />
        <span>МЕСТО ПРОВЕДЕНИЯ</span>
      </div>
      <div className="venue-location-body">
        <strong className="venue-address">{place}</strong>
        <p>{town} · вместимость {capacity}</p>
      </div>
    </div>
  )
}

/* ── Admin / Manager / Profile pages ─────────────────────────────── */

function usePageError() {
  const [error, setError] = useState<unknown>()
  return { error, setError }
}

function ConfirmDelete({ label, onConfirm, testid }: { label: string; onConfirm: () => void; testid: string }) {
  const [armed, setArmed] = useState(false)
  if (!armed) return <button className="reset-button" onClick={() => setArmed(true)} data-testid={testid}>{label}</button>
  return (
    <span>
      <button className="reset-button" onClick={() => setArmed(false)}>Отмена</button>{' '}
      <button className="apply-button" onClick={() => { setArmed(false); onConfirm() }} data-testid={`${testid}-confirm`}>Точно удалить</button>
    </span>
  )
}

function UsersTab() {
  const [users, setUsers] = useState<User[]>([])
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState('')
  const { error, setError } = usePageError()
  const [editing, setEditing] = useState<User | null>(null)
  const [form, setForm] = useState({ username: '', email: '', role: 'CUSTOMER', password: '' })

  const load = async (filtered = false) => {
    setError(undefined)
    try {
      setUsers(filtered ? await api.searchUsers({ email, username, role }) : await api.getAllUsers())
    } catch (e) { setError(e) }
  }

  useEffect(() => { void load(false) }, [])

  const startEdit = (user: User) => {
    setEditing(user)
    setForm({ username: user.username, email: user.email, role: String(user.role), password: '' })
  }

  const saveEdit = async () => {
    if (!editing) return
    setError(undefined)
    try {
      const payload: { id: number; username: string; email: string; role: string; password?: string } = {
        id: editing.id, username: form.username, email: form.email, role: form.role,
      }
      if (form.password) payload.password = form.password
      await api.updateUser(payload)
      setEditing(null)
      await load(false)
    } catch (e) { setError(e) }
  }

  const remove = async (id: number) => {
    setError(undefined)
    try {
      await api.deleteUser(id)
      await load(false)
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-users">
      <div className="secondary-toolbar">
        <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="admin-user-filter-email" />
        <input placeholder="Имя" value={username} onChange={(e) => setUsername(e.target.value)} data-testid="admin-user-filter-username" />
        <select value={role} onChange={(e) => setRole(e.target.value)} data-testid="admin-user-filter-role">
          <option value="">Все роли</option>
          <option value="CUSTOMER">CUSTOMER</option>
          <option value="EVENT_MANAGER">EVENT_MANAGER</option>
          <option value="ADMIN">ADMIN</option>
        </select>
        <button className="apply-button" onClick={() => void load(true)} data-testid="admin-user-search">Найти</button>
        <button className="reset-button" onClick={() => { setEmail(''); setUsername(''); setRole(''); void load(false) }}>Сбросить</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => void load(false)} /> : null}
      <div className="admin-table">
        {users.map((user) => (
          <div className="table-row" key={user.id} data-testid="admin-user-row">
            <span>#{user.id}</span>
            <span><strong>{user.username}</strong> · {user.email}</span>
            <span>{String(user.role)}</span>
            <span>
              <button className="reset-button" onClick={() => startEdit(user)} data-testid="admin-user-edit">Изменить</button>{' '}
              <ConfirmDelete label="Удалить" onConfirm={() => void remove(user.id)} testid="admin-user-delete" />
            </span>
          </div>
        ))}
      </div>
      {editing && (
        <SimpleDialog title={`Читатель #${editing.id}`} onClose={() => setEditing(null)} testid="admin-user-dialog">
          <label>Имя<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} data-testid="admin-user-form-username" /></label>
          <label>Email<input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="admin-user-form-email" /></label>
          <label>Роль
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} data-testid="admin-user-form-role">
              <option value="CUSTOMER">CUSTOMER</option>
              <option value="EVENT_MANAGER">EVENT_MANAGER</option>
              <option value="ADMIN">ADMIN</option>
            </select>
          </label>
          <label>Новый пароль (необязательно)<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="admin-user-form-password" /></label>
          <button className="apply-button" onClick={() => void saveEdit()} data-testid="admin-user-save">Сохранить</button>
        </SimpleDialog>
      )}
    </div>
  )
}

function TownsTab() {
  const [towns, setTowns] = useState<Town[]>([])
  const [name, setName] = useState('')
  const [renaming, setRenaming] = useState<Town | null>(null)
  const [newName, setNewName] = useState('')
  const { error, setError } = usePageError()

  const load = async () => {
    setError(undefined)
    try { setTowns(await api.getTowns()) } catch (e) { setError(e) }
  }

  useEffect(() => { void load() }, [])

  const create = async () => {
    if (!name.trim()) return
    setError(undefined)
    try {
      await api.createTown(name.trim())
      setName('')
      await load()
    } catch (e) { setError(e) }
  }

  const rename = async () => {
    if (!renaming || !newName.trim()) return
    setError(undefined)
    try {
      await api.updateTown(renaming.id, newName.trim())
      setRenaming(null)
      await load()
    } catch (e) { setError(e) }
  }

  const remove = async (id: number) => {
    setError(undefined)
    try {
      await api.deleteTown(id)
      await load()
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-towns">
      <div className="secondary-toolbar">
        <input placeholder="Новый город" value={name} onChange={(e) => setName(e.target.value)} data-testid="admin-town-name" />
        <button className="apply-button" onClick={() => void create()} data-testid="admin-town-create">Добавить</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => void load()} /> : null}
      <div className="admin-table">
        {towns.map((town) => (
          <div className="table-row" key={town.id} data-testid="admin-town-row">
            <span>#{town.id}</span>
            <span><strong>{town.name}</strong></span>
            <span>
              <button className="reset-button" onClick={() => { setRenaming(town); setNewName(town.name) }} data-testid="admin-town-rename">Переименовать</button>{' '}
              <ConfirmDelete label="Удалить" onConfirm={() => void remove(town.id)} testid="admin-town-delete" />
            </span>
          </div>
        ))}
      </div>
      {renaming && (
        <SimpleDialog title={`Город #${renaming.id}`} onClose={() => setRenaming(null)} testid="admin-town-dialog">
          <label>Название<input value={newName} onChange={(e) => setNewName(e.target.value)} data-testid="admin-town-form-name" /></label>
          <button className="apply-button" onClick={() => void rename()} data-testid="admin-town-save">Сохранить</button>
        </SimpleDialog>
      )}
    </div>
  )
}

function VenuesTab() {
  const [venues, setVenues] = useState<Venue[]>([])
  const [towns, setTowns] = useState<Town[]>([])
  const [editing, setEditing] = useState<Venue | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ townId: 0, place: '', capacity: 100 })
  const { error, setError } = usePageError()

  const load = async () => {
    setError(undefined)
    try {
      const [venueList, townList] = await Promise.all([api.getVenues(), api.getTowns()])
      setVenues(venueList)
      setTowns(townList)
      if (!form.townId && townList.length) setForm((f) => ({ ...f, townId: townList[0].id }))
    } catch (e) { setError(e) }
  }

  useEffect(() => { void load() }, [])

  const openCreate = () => {
    setForm({ townId: towns[0]?.id ?? 0, place: '', capacity: 100 })
    setCreating(true)
  }

  const openEdit = (venue: Venue) => {
    setForm({ townId: venue.townId, place: venue.place, capacity: venue.capacity })
    setEditing(venue)
  }

  const save = async () => {
    setError(undefined)
    try {
      if (editing) await api.updateVenue(editing.id, form)
      else await api.createVenue(form)
      setEditing(null)
      setCreating(false)
      await load()
    } catch (e) { setError(e) }
  }

  const remove = async (id: number) => {
    setError(undefined)
    try {
      await api.deleteVenue(id)
      await load()
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-venues">
      <div className="secondary-toolbar">
        <button className="apply-button" onClick={openCreate} data-testid="admin-venue-create">Новая площадка</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => void load()} /> : null}
      <div className="admin-table">
        {venues.map((venue) => (
          <div className="table-row" key={venue.id} data-testid="admin-venue-row">
            <span>#{venue.id}</span>
            <span><strong>{venue.place}</strong> · {venue.townName} · вместимость {venue.capacity}</span>
            <span>
              <button className="reset-button" onClick={() => openEdit(venue)} data-testid="admin-venue-edit">Изменить</button>{' '}
              <ConfirmDelete label="Удалить" onConfirm={() => void remove(venue.id)} testid="admin-venue-delete" />
            </span>
          </div>
        ))}
      </div>
      {(creating || editing) && (
        <SimpleDialog title={editing ? `Площадка #${editing.id}` : 'Новая площадка'} onClose={() => { setCreating(false); setEditing(null) }} testid="admin-venue-dialog">
          <label>Город
            <select value={form.townId} onChange={(e) => setForm({ ...form, townId: Number(e.target.value) })} data-testid="admin-venue-form-town">
              {towns.map((town) => <option key={town.id} value={town.id}>{town.name}</option>)}
            </select>
          </label>
          <label>Название<input value={form.place} onChange={(e) => setForm({ ...form, place: e.target.value })} data-testid="admin-venue-form-place" /></label>
          <label>Вместимость<input type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: Number(e.target.value) })} data-testid="admin-venue-form-capacity" /></label>
          <button className="apply-button" onClick={() => void save()} data-testid="admin-venue-save">Сохранить</button>
        </SimpleDialog>
      )}
    </div>
  )
}

function EventsTab() {
  const [events, setEvents] = useState<Event[]>([])
  const [venues, setVenues] = useState<Venue[]>([])
  const [editing, setEditing] = useState<Event | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ title: '', startsAt: '', endsAt: '', venueId: 0, admissionMode: 'GENERAL' })
  const { error, setError } = usePageError()

  const load = async () => {
    setError(undefined)
    try {
      const [eventList, venueList] = await Promise.all([api.searchEvents({}, 1, 100), api.getVenues()])
      setEvents(eventList)
      setVenues(venueList)
      if (!form.venueId && venueList.length) setForm((f) => ({ ...f, venueId: venueList[0].id }))
    } catch (e) { setError(e) }
  }

  useEffect(() => { void load() }, [])

  const openCreate = () => {
    setForm({ title: '', startsAt: '', endsAt: '', venueId: venues[0]?.id ?? 0, admissionMode: 'GENERAL' })
    setCreating(true)
  }

  const openEdit = (event: Event) => {
    setForm({
      title: event.title,
      startsAt: event.startsAt.slice(0, 16),
      endsAt: event.endsAt.slice(0, 16),
      venueId: event.venueId,
      admissionMode: event.admissionMode,
    })
    setEditing(event)
  }

  const save = async () => {
    setError(undefined)
    try {
      if (editing) await api.updateEvent(editing.id, form)
      else await api.createEvent(form)
      setEditing(null)
      setCreating(false)
      await load()
    } catch (e) { setError(e) }
  }

  const remove = async (id: number) => {
    setError(undefined)
    try {
      await api.deleteEvent(id)
      await load()
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-events">
      <div className="secondary-toolbar">
        <button className="apply-button" onClick={openCreate} data-testid="admin-event-create">Новое событие</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => void load()} /> : null}
      <div className="admin-table">
        {events.map((event) => (
          <div className="table-row" key={event.id} data-testid="admin-event-row">
            <span>#{event.id}</span>
            <span><strong>{event.title}</strong> · {event.venuePlace} · {event.admissionMode}</span>
            <span>
              <button className="reset-button" onClick={() => openEdit(event)} data-testid="admin-event-edit">Изменить</button>{' '}
              <ConfirmDelete label="Удалить" onConfirm={() => void remove(event.id)} testid="admin-event-delete" />
            </span>
          </div>
        ))}
      </div>
      {(creating || editing) && (
        <SimpleDialog title={editing ? `Событие #${editing.id}` : 'Новое событие'} onClose={() => { setCreating(false); setEditing(null) }} testid="admin-event-dialog">
          <label>Название<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="admin-event-form-title" /></label>
          <label>Начало<input type="datetime-local" value={form.startsAt} onChange={(e) => setForm({ ...form, startsAt: e.target.value })} data-testid="admin-event-form-starts" /></label>
          <label>Конец<input type="datetime-local" value={form.endsAt} onChange={(e) => setForm({ ...form, endsAt: e.target.value })} data-testid="admin-event-form-ends" /></label>
          <label>Площадка
            <select value={form.venueId} onChange={(e) => setForm({ ...form, venueId: Number(e.target.value) })} data-testid="admin-event-form-venue">
              {venues.map((venue) => <option key={venue.id} value={venue.id}>{venue.place}</option>)}
            </select>
          </label>
          <label>Формат входа
            <select value={form.admissionMode} onChange={(e) => setForm({ ...form, admissionMode: e.target.value })} data-testid="admin-event-form-mode">
              <option value="GENERAL">GENERAL</option>
              <option value="SEATABLE">SEATABLE</option>
            </select>
          </label>
          <button className="apply-button" onClick={() => void save()} data-testid="admin-event-save">Сохранить</button>
        </SimpleDialog>
      )}
    </div>
  )
}

function SeatsTab() {
  const [venues, setVenues] = useState<Venue[]>([])
  const [venueId, setVenueId] = useState<number | ''>('')
  const [seats, setSeats] = useState<Seat[]>([])
  const [form, setForm] = useState({ sector: '', row: '', number: '' })
  const { error, setError } = usePageError()

  useEffect(() => {
    ;(async () => {
      try { setVenues(await api.getVenues()) } catch (e) { setError(e) }
    })()
  }, [])

  const loadSeats = async (id: number) => {
    setError(undefined)
    try { setSeats(await api.getSeats(id)) } catch (e) { setError(e) }
  }

  const create = async () => {
    if (venueId === '' || !form.sector.trim()) return
    setError(undefined)
    try {
      await api.createSeat({ sector: form.sector.trim(), row: form.row.trim(), number: form.number.trim(), venueId })
      setForm({ sector: '', row: '', number: '' })
      await loadSeats(venueId)
    } catch (e) { setError(e) }
  }

  const remove = async (id: number) => {
    setError(undefined)
    try {
      await api.deleteSeat(id)
      if (venueId !== '') await loadSeats(venueId)
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-seats">
      <div className="secondary-toolbar">
        <select value={venueId} onChange={(e) => { const id = e.target.value ? Number(e.target.value) : ''; setVenueId(id); if (id !== '') void loadSeats(id) }} data-testid="admin-seat-venue">
          <option value="">Выберите площадку</option>
          {venues.map((venue) => <option key={venue.id} value={venue.id}>{venue.place}</option>)}
        </select>
        <input placeholder="Сектор" value={form.sector} onChange={(e) => setForm({ ...form, sector: e.target.value })} data-testid="admin-seat-sector" />
        <input placeholder="Ряд" value={form.row} onChange={(e) => setForm({ ...form, row: e.target.value })} data-testid="admin-seat-row" />
        <input placeholder="Место" value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} data-testid="admin-seat-number" />
        <button className="apply-button" onClick={() => void create()} data-testid="admin-seat-create">Добавить место</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => venueId !== '' && void loadSeats(venueId)} /> : null}
      <div className="admin-table">
        {seats.map((seat) => (
          <div className="table-row" key={seat.id} data-testid="admin-seat-row">
            <span>#{seat.id}</span>
            <span>Сектор {seat.sector} · ряд {seat.row} · место {seat.number}</span>
            <span><ConfirmDelete label="Удалить" onConfirm={() => void remove(seat.id)} testid="admin-seat-delete" /></span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TicketsTab() {
  const [eventId, setEventId] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [seatable, setSeatable] = useState<SeatableTicket[]>([])
  const { error, setError } = usePageError()

  const search = async () => {
    if (!eventId.trim()) return
    setError(undefined)
    try {
      const [found, foundSeatable] = await Promise.all([
        api.searchTickets({ eventId: eventId.trim() }),
        api.searchSeatableTickets({ eventId: eventId.trim() }),
      ])
      setTickets(found)
      setSeatable(foundSeatable)
    } catch (e) { setError(e) }
  }

  const refund = async (id: number, seatableTicket: boolean) => {
    setError(undefined)
    try {
      if (seatableTicket) await api.refundSeatableTicket(id)
      else await api.refundTicket(id)
      await search()
    } catch (e) { setError(e) }
  }

  return (
    <div data-testid="admin-tab-tickets">
      <div className="secondary-toolbar">
        <input placeholder="ID события" value={eventId} onChange={(e) => setEventId(e.target.value)} data-testid="admin-ticket-event" />
        <button className="apply-button" onClick={() => void search()} data-testid="admin-ticket-search">Найти билеты</button>
      </div>
      {error ? <ErrorView error={error} onRetry={() => void search()} /> : null}
      <div className="admin-table">
        {tickets.map((ticket) => (
          <div className="table-row" key={`t-${ticket.id}`} data-testid="admin-ticket-row">
            <span>#{ticket.id}</span>
            <span>Зона {ticket.zone} · {ticket.price} · {ticket.active ? 'активен' : 'возвращён'}</span>
            <span>
              {ticket.active && <button className="reset-button" onClick={() => void refund(ticket.id, false)} data-testid="admin-ticket-refund">Вернуть</button>}
            </span>
          </div>
        ))}
        {seatable.map((ticket) => (
          <div className="table-row" key={`s-${ticket.id}`} data-testid="admin-ticket-row">
            <span>#{ticket.id}</span>
            <span>Место {ticket.sector}/{ticket.row}/{ticket.number} · {ticket.price} · {ticket.active ? 'активен' : 'возвращён'}</span>
            <span>
              {ticket.active && <button className="reset-button" onClick={() => void refund(ticket.id, true)} data-testid="admin-ticket-refund">Вернуть</button>}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function AdminPage({ manager }: { manager?: boolean }) {
  const auth = useAuth()
  const tabs = manager ? ['events', 'venues', 'seats', 'tickets'] : ['users', 'towns', 'venues', 'events']
  const [tab, setTab] = useState(tabs[0])

  if (!auth.ready) return <LoadingView />
  if (!auth.user) return <NoAccessView message="Войдите в личный кабинет: полоса доступна команде газеты." />
  if (manager && !auth.isManager) return <NoAccessView message="Нужна роль менеджера или администратора." />
  if (!manager && !auth.isAdmin) return <NoAccessView message="Нужна роль администратора." />

  return (
    <main className="newspaper secondary-page" data-testid={manager ? 'manager-page' : 'admin-page'}>
      <PageHeader returnHref="/" />
      <div className="article-intro">
        <div className="kicker">{manager ? 'РУБРИКА МЕНЕДЖЕРА' : 'РЕДАКЦИОННАЯ КОЛЛЕГИЯ'}</div>
        <h2>{manager ? 'Панель менеджера' : 'Админ-панель'}</h2>
      </div>
      <div className="secondary-toolbar" data-testid="admin-tabs">
        {tabs.map((name) => (
          <button key={name} className={tab === name ? 'black-chip' : ''} onClick={() => setTab(name)} data-testid={`admin-tab-${name}`}>
            {name === 'users' ? 'Пользователи' : name === 'towns' ? 'Города' : name === 'venues' ? 'Площадки' : name === 'events' ? 'События' : name === 'seats' ? 'Места' : 'Билеты'}
          </button>
        ))}
      </div>
      <div className="catalog-list">
        {tab === 'users' && <UsersTab />}
        {tab === 'towns' && <TownsTab />}
        {tab === 'venues' && <VenuesTab />}
        {tab === 'events' && <EventsTab />}
        {tab === 'seats' && <SeatsTab />}
        {tab === 'tickets' && <TicketsTab />}
      </div>
    </main>
  )
}

export function ProfilePage() {
  const auth = useAuth()
  const [tab, setTab] = useState<'tickets' | 'info'>('tickets')
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [seatable, setSeatable] = useState<SeatableTicket[]>([])
  const [error, setError] = useState<unknown>()

  useEffect(() => {
    if (!auth.user) return
    ;(async () => {
      try {
        const [found, foundSeatable] = await Promise.all([
          api.getMyTickets(auth.user!.id),
          api.getMySeatableTickets(auth.user!.id),
        ])
        setTickets(found)
        setSeatable(foundSeatable)
      } catch (e) { setError(e) }
    })()
  }, [auth.user])

  if (!auth.ready) return <LoadingView />
  if (!auth.user) return <NoAccessView message="Войдите, чтобы увидеть билеты и настройки подписки." />

  const refund = async (id: number, seatableTicket: boolean) => {
    setError(undefined)
    try {
      if (seatableTicket) {
        await api.refundSeatableTicket(id)
        setSeatable((list) => list.map((t) => (t.id === id ? { ...t, active: false } : t)))
      } else {
        await api.refundTicket(id)
        setTickets((list) => list.map((t) => (t.id === id ? { ...t, active: false } : t)))
      }
    } catch (e) { setError(e) }
  }

  return (
    <main className="newspaper secondary-page" data-testid="profile-page">
      <PageHeader returnHref="/" />
      <div className="admin-layout">
        <nav className="profile-nav" data-testid="profile-nav">
          <button className={tab === 'tickets' ? 'active' : ''} onClick={() => setTab('tickets')} data-testid="profile-tab-tickets">Мои билеты</button>
          <button className={tab === 'info' ? 'active' : ''} onClick={() => setTab('info')} data-testid="profile-tab-info">Профиль</button>
        </nav>
        <div>
          <div className="profile-card">
            <div className="avatar">{auth.user.username.slice(0, 1).toUpperCase()}</div>
            <div>
              <strong data-testid="profile-username">{auth.user.username}</strong>
              <p data-testid="profile-email">{auth.user.email}</p>
              <p data-testid="profile-role">{String(auth.user.role)}</p>
            </div>
            <button className="reset-button" onClick={() => auth.logout()} data-testid="profile-logout">Выйти</button>
          </div>
          {tab === 'info' && (
            <SectionView title="Подписка">
              <FieldRow label="Читатель" value={auth.user.username} bold />
              <FieldRow label="Почта" value={auth.user.email} />
              <FieldRow label="Роль" value={String(auth.user.role)} />
            </SectionView>
          )}
          {tab === 'tickets' && (
            <div>
              {error ? <ErrorView error={error} /> : null}
              <div className="ticket-list">
                {tickets.map((ticket) => (
                  <article key={`t-${ticket.id}`} data-testid="profile-ticket">
                    <div className="ticket-number">БИЛЕТ<strong>№{ticket.id}</strong></div>
                    <div>
                      <h3>{ticket.eventTitle}</h3>
                      <p>Зона {ticket.zone} · {ticket.price} · {ticket.active ? 'активен' : 'возвращён'}</p>
                    </div>
                    <div>{ticket.active && <button className="reset-button" onClick={() => void refund(ticket.id, false)} data-testid="profile-ticket-refund">Вернуть</button>}</div>
                  </article>
                ))}
                {seatable.map((ticket) => (
                  <article key={`s-${ticket.id}`} data-testid="profile-ticket">
                    <div className="ticket-number">БИЛЕТ<strong>№{ticket.id}</strong></div>
                    <div>
                      <h3>{ticket.eventTitle}</h3>
                      <p>Место {ticket.sector}/{ticket.row}/{ticket.number} · {ticket.price} · {ticket.active ? 'активен' : 'возвращён'}</p>
                    </div>
                    <div>{ticket.active && <button className="reset-button" onClick={() => void refund(ticket.id, true)} data-testid="profile-ticket-refund">Вернуть</button>}</div>
                  </article>
                ))}
                {tickets.length === 0 && seatable.length === 0 && (
                  <div className="empty-state" data-testid="profile-tickets-empty"><h3>Билетов пока нет</h3><p>Загляните в афишу и выберите событие.</p></div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
