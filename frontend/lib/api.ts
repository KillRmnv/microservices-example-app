import type {
  Event,
  LoginResponse,
  Role,
  Seat,
  SeatableTicket,
  Ticket,
  Town,
  User,
  Venue,
} from './types'

const TOKEN_KEY = 'dosugToken'
const EMAIL_KEY = 'dosugEmail'
const ROLE_KEY = 'dosugRole'
const USER_ID_KEY = 'dosugUserId'

function readStorage(key: string): string {
  if (typeof window === 'undefined') return ''
  try {
    return window.localStorage.getItem(key) ?? ''
  } catch {
    return ''
  }
}

function writeStorage(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    /* private mode etc. — session simply won't persist */
  }
}

function clearStorage(): void {
  if (typeof window === 'undefined') return
  try {
    ;[TOKEN_KEY, EMAIL_KEY, ROLE_KEY, USER_ID_KEY].forEach((k) => window.localStorage.removeItem(k))
  } catch {
    /* ignore */
  }
}

export const tokenStore = {
  get token() {
    return readStorage(TOKEN_KEY)
  },
  get email() {
    return readStorage(EMAIL_KEY)
  },
  get role() {
    return readStorage(ROLE_KEY)
  },
  get userId() {
    return readStorage(USER_ID_KEY)
  },
  setSession(data: LoginResponse, email: string) {
    writeStorage(TOKEN_KEY, data.jwt)
    writeStorage(EMAIL_KEY, email)
    writeStorage(ROLE_KEY, String(data.role).toUpperCase())
    writeStorage(USER_ID_KEY, String(data.id))
  },
  clear() {
    clearStorage()
  },
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) ?? {}),
  }
  const token = tokenStore.token
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(endpoint, { ...options, headers })
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    const data = await response.json().catch(() => null)
    if (data && typeof data === 'object') {
      // RFC 9457 Problem Details first, legacy {message} second.
      const problem = data as { detail?: unknown; title?: unknown; message?: unknown }
      if (typeof problem.detail === 'string' && problem.detail) {
        message = problem.detail
      } else if (typeof problem.title === 'string' && problem.title) {
        message = problem.title
      } else if (typeof problem.message === 'string' && problem.message) {
        message = problem.message
      }
    }
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  request,
  get: <T>(endpoint: string) => request<T>(endpoint),
  post: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(endpoint: string, body: unknown) =>
    request<T>(endpoint, { method: 'PUT', body: JSON.stringify(body) }),
  del: <T>(endpoint: string, body?: unknown) =>
    request<T>(endpoint, { method: 'DELETE', body: body === undefined ? undefined : JSON.stringify(body) }),

  // --- auth ---
  login: (email: string, password: string) => api.post<LoginResponse>('/users/auth/login', { email, password }),
  register: (email: string, password: string, username: string, role: Role | string = 'CUSTOMER') =>
    api.post('/users/auth/register', { email, password, username, role, isSystem: false }),
  forgetPassword: (email: string) =>
    request<void>(`/users/auth/forget-password?email=${encodeURIComponent(email)}`, { method: 'POST' }),
  validateResetToken: (token: string) => api.get<boolean>(`/users/auth/validate-reset-token?token=${encodeURIComponent(token)}`),
  resetPassword: (token: string, newPassword: string) =>
    api.post<void>('/users/auth/reset-password', { token, newPassword }),

  // --- users ---
  getUserById: (id: number) => api.get<User>(`/users/${id}`),
  getCurrentUser: () => api.get<User>('/users/me'),
  getAllUsers: () => api.get<User[]>('/users'),
  searchUsers: (filter: { email?: string; username?: string; role?: string }) => {
    const params = new URLSearchParams()
    if (filter.email) params.append('email', filter.email)
    if (filter.username) params.append('username', filter.username)
    if (filter.role) params.append('role', filter.role)
    return api.get<User[]>(`/users/search?${params}`)
  },
  updateUser: (data: { id: number; username: string; email: string; role: string; password?: string; isSystem?: boolean }) =>
    api.put<User>('/users', data),
  deleteUser: (id: number) => api.del<void>('/users', { id }),

  // --- events ---
  getEvents: () => api.get<Event[]>('/booking/events'),
  getEventById: (id: number) => api.get<Event>(`/booking/events/${id}`),
  searchEvents: (filter: Record<string, unknown>, page = 1, size = 24) => {
    const params = new URLSearchParams()
    Object.entries(filter).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
    })
    params.append('page', String(page))
    params.append('size', String(size))
    return api.get<Event[]>(`/booking/events/search?${params}`)
  },
  createEvent: (data: { title: string; startsAt: string; endsAt: string; venueId: number; admissionMode: string }) =>
    api.post<Event>('/booking/events', data),
  updateEvent: (id: number, data: { title: string; startsAt: string; endsAt: string; venueId: number; admissionMode: string }) =>
    api.put<Event>(`/booking/events/${id}`, data),
  deleteEvent: (id: number) => api.del<void>(`/booking/events/${id}`),

  // --- towns ---
  getTowns: () => api.get<Town[]>('/booking/towns'),
  createTown: (name: string) => api.post<Town>('/booking/towns', { name }),
  updateTown: (id: number, name: string) => api.put<Town>(`/booking/towns/${id}`, { name }),
  deleteTown: (id: number) => api.del<void>(`/booking/towns/${id}`),

  // --- venues ---
  getVenues: () => api.get<Venue[]>('/booking/venues'),
  getVenue: (id: number) => api.get<Venue>(`/booking/venues/${id}`),
  searchVenues: (filter: Record<string, unknown>, page = 1, size = 24) => {
    const params = new URLSearchParams()
    Object.entries(filter).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
    })
    params.append('page', String(page))
    params.append('size', String(size))
    return api.get<Venue[]>(`/booking/venues/search?${params}`)
  },
  createVenue: (data: { townId: number; place: string; capacity: number }) => api.post<Venue>('/booking/venues', data),
  updateVenue: (id: number, data: { townId: number; place: string; capacity: number }) =>
    api.put<Venue>(`/booking/venues/${id}`, data),
  deleteVenue: (id: number) => api.del<void>(`/booking/venues/${id}`),

  // --- seats ---
  getSeats: (venueId: number) => api.get<Seat[]>(`/booking/seats/search?venueId=${venueId}&page=1&size=500`),
  createSeat: (data: { sector: string; row: string; number: string; venueId: number }) => api.post<Seat>('/booking/seats', data),
  deleteSeat: (id: number) => api.del<void>(`/booking/seats/${id}`),

  // --- tickets ---
  searchTickets: (filter: Record<string, unknown>, page = 1, size = 50) => {
    const params = new URLSearchParams()
    Object.entries(filter).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
    })
    params.append('page', String(page))
    params.append('size', String(size))
    return api.get<Ticket[]>(`/booking/tickets/search?${params}`)
  },
  searchSeatableTickets: (filter: Record<string, unknown>, page = 1, size = 50) => {
    const params = new URLSearchParams()
    Object.entries(filter).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.append(key, String(value))
    })
    params.append('page', String(page))
    params.append('size', String(size))
    return api.get<SeatableTicket[]>(`/booking/seatable-tickets/search?${params}`)
  },
  getTickets: (eventId: number) => api.get<Ticket[]>(`/booking/tickets/search?eventId=${eventId}&page=1&size=500`),
  getMyTickets: (userId: number) => api.get<Ticket[]>(`/booking/tickets/search?userId=${userId}&page=1&size=500`),
  getMySeatableTickets: (userId: number) =>
    api.get<SeatableTicket[]>(`/booking/seatable-tickets/search?userId=${userId}&page=1&size=500`),
  createTicket: (data: { eventId: number; zone: string; price: number; active: boolean; userId: number }) =>
    api.post<Ticket>('/booking/tickets', data),
  deleteTicket: (id: number) => api.del<void>(`/booking/tickets/${id}`),
  refundTicket: (id: number) => api.post<void>(`/booking/tickets/${id}/refund`),
  getSeatableTickets: (eventId: number) =>
    api.get<SeatableTicket[]>(`/booking/seatable-tickets/search?eventId=${eventId}&page=1&size=500`),
  createSeatableTicket: (data: { eventId: number; seatId: number; zone: string; price: number; active: boolean; userId: number }) =>
    api.post<SeatableTicket>('/booking/seatable-tickets', data),
  refundSeatableTicket: (id: number) => api.post<void>(`/booking/seatable-tickets/${id}/refund`),
}
