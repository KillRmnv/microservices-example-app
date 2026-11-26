'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, CheckCircle2, CloudRain, HelpCircle, MessageCircle, MessageSquare, Plus, RefreshCcw, Star, Sun, Trash2, X } from 'lucide-react'
import type { StateContract } from '@/lib/types'
import { api, ApiError, tokenStore } from '@/lib/api'
import { filmFacts, filmSessionLabel, filmSessionTime, sourceLabel } from '@/lib/catalog'
import {
  createHold,
  isMockMode,
  requestPlan,
  sendDialogue,
  structureQuery,
  type DialogMessage,
} from '@/lib/assistant'
import { accumulateShownIds, contractFromParsed, isFollowUpOnly, mergeContracts, parseQuery } from '@/lib/dialogue'
import { RATE_LIMIT_MESSAGE, isRateLimited } from '@/lib/errors'
import {
  type Chat,
  type ChatMessage,
  createChat,
  loadActiveChatId,
  loadChats,
  nextChatNumber,
  saveActiveChatId,
  saveChats,
  titleFromMessage,
  welcomeMessage,
} from '@/lib/chats'

function isBookable(eventId: string | undefined): eventId is string {
  return !!eventId && /^\d+$/.test(eventId)
}

/** Catalog detail pages are keyed by the Qdrant UUID, not by numeric booking ids. */
function isDetailId(value: string | undefined): value is string {
  return !!value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}

function plural(count: number, forms: [string, string, string]): string {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1]
  return forms[2]
}

function ratingValue(rating: number | null | undefined): number | null {
  return typeof rating === 'number' && Number.isFinite(rating) ? rating : null
}

/** Only the states that block "Выбрать" get a badge. */
function statusLabel(status: string | null | undefined): string | null {
  if (status === 'sold_out') return 'нет билетов'
  if (status === 'cancelled') return 'отменено'
  return null
}

/** age_max 17+ means "adults only", 12 and below means "kids welcome". */
function ageLabel(ageMax: number): string {
  if (ageMax >= 17) return 'без 18+'
  if (ageMax <= 12) return 'можно с детьми'
  return `возраст: до ${ageMax}+`
}

/** 0 means "any party size" in the contract; a hold needs a concrete count,
 * so it falls back to 1 — the safest default, matching the server's
 * ASSISTANT_DEFAULT_PARTY_SIZE. */
function holdPartySize(contract?: StateContract | null): number {
  const size = contract?.hard_filters.party_size
  return typeof size === 'number' && size > 0 ? size : 1
}

const CITIES = 'Минск'
const THEME_LABELS: Record<string, string> = {
  classical: 'классика',
  jazz: 'джаз',
  rock: 'рок',
  beer: 'пиво',
  kids: 'детям',
}

function formatWhen(dt: StateContract['hard_filters']['datetime']): string | null {
  if (!dt) return null
  if (dt.any) return 'любая дата'
  if (!dt.start) return null
  const start = new Date(dt.start)
  if (Number.isNaN(start.getTime())) return null
  const fmt = (date: Date) => date.toLocaleDateString('ru-RU', {
    day: 'numeric', month: 'long', year: 'numeric',
  })
  const end = dt.end ? new Date(dt.end) : null
  if (end && !Number.isNaN(end.getTime())
      && end.toDateString() !== start.toDateString()) {
    return `${fmt(start)} — ${fmt(end)}`
  }
  return fmt(start)
}

function timeOfDay(date: Date): string {
  const hour = date.getHours()
  if (hour < 5) return 'НОЧЬ'
  if (hour < 12) return 'УТРО'
  if (hour < 17) return 'ДЕНЬ'
  if (hour < 23) return 'ВЕЧЕР'
  return 'НОЧЬ'
}

function planLabel(contract: StateContract | undefined,
                   plan: ChatMessage['plan']): string {
  const start = contract?.hard_filters.datetime?.start
  const date = start ? new Date(start) : null
  const firstTime = plan?.find((step) => /^\d{1,2}:\d{2}$/.test(step.time))?.time
  let hour = date && !Number.isNaN(date.getTime()) ? date.getHours() : 12
  if (firstTime) hour = Number(firstTime.split(':')[0])
  const period = hour < 5 ? 'НОЧЬ' : hour < 12 ? 'УТРО'
    : hour < 17 ? 'ДЕНЬ' : 'ВЕЧЕР'
  return date && !Number.isNaN(date.getTime())
    ? `ПЛАН ${period} · ${formatWhen(contract?.hard_filters.datetime)}`
    : `ПЛАН ${period}`
}

function baseContract(): StateContract {
  return {
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: {
      location: { city: CITIES },
      // Same default as the server: one guest unless the user says otherwise.
      party_size: 1,
    },
    negative_filters: {},
    semantic_payload: { vector_query: '', language: 'ru' },
    context_state: { turn_count: 1, session_id: 'client_session' },
  }
}

function contractMessage(id: number, patch: Partial<StateContract['hard_filters']>, negative: Partial<StateContract['negative_filters']>, vector: string): ChatMessage {
  const contract = baseContract()
  contract.hard_filters = { ...contract.hard_filters, ...patch }
  contract.negative_filters = { ...contract.negative_filters, ...negative }
  contract.semantic_payload.vector_query = vector
  contract.context_state.turn_count += 1
  return { id, kind: 'filters', text: 'Условия поиска собраны и зафиксированы в контракте диалога.', filters: contract }
}

const SCENARIOS: Record<string, ChatMessage[]> = {
  'Что-нибудь на выходные': [
    {
      id: 2,
      kind: 'filters',
      text: 'Уточняю даты и собираю выпуск выходного дня.',
      filters: {
        ...baseContract(),
        hard_filters: {
          ...baseContract().hard_filters,
          datetime: { start: '2026-10-24T11:00:00', end: '2026-10-25T23:59:59', raw_expression: 'в выходные' },
        },
        context_state: { turn_count: 2, session_id: 'client_session' },
      },
    },
    {
      id: 3,
      kind: 'weather',
      text: 'Суббота — облачно, +11. Вечером возможен дождь: событие под открытым небом лучше ставить до 18:00.',
    },
    {
      id: 4,
      kind: 'results',
      text: 'Готово. На выходных город играет вот так:',
      results: [
        { title: 'Музыка на воде', meta: 'СБ, 24 ОКТЯБРЯ · 19:00 · Дворец Республики', price: 'от 45 руб.' },
        { title: 'Тихий свет', meta: 'до 21:00 · Национальный художественный музей', price: 'от 12 руб.' },
        { title: 'Двенадцатая ночь', meta: 'ВС, 25 ОКТЯБРЯ · 18:30 · Театр имени Янки Купалы', price: 'от 38 руб.' },
      ],
    },
  ],
  'Тихое место с джазом': [
    contractMessage(2, { category: ['bar', 'restaurant', 'cafe'] }, { exclude_tags: ['loud_music', 'fastfood', 'children_zone'] }, 'тихий свет, приглушённая атмосфера, живой джаз или лаунж, разговор без крика'),
    {
      id: 3,
      kind: 'results',
      text: 'Нашла три столика по вашей атмосфере:',
      results: [
        { title: 'Полночь', meta: 'Центральный · джаз · 18+', price: 'от 35 руб.' },
        { title: 'Своя кофейня', meta: 'Немига · тишина · десерты', price: 'до 25 руб.' },
        { title: 'Ресторан «Гвоздь»', meta: 'Троицкое предместье · живая музыка', price: 'от 50 руб.' },
      ],
    },
  ],
  'План на дождливый вечер': [
    {
      id: 2,
      kind: 'weather',
      text: 'Проверяю прогноз: завтра вечером дождь. Уличное — исключаю, собираю план в помещении.',
      filters: {
        ...baseContract(),
        negative_filters: { exclude_categories: ['outdoors', 'walking'] },
        semantic_payload: { vector_query: '', language: 'ru' },
        context_state: { turn_count: 2, session_id: 'client_session' },
      },
    },
    {
      id: 3,
      kind: 'plan',
      text: 'Черновик плана. Подтвердите — и я проверю наличие мест:',
      plan: [
        { time: '17:30', title: 'Спектакль «Двенадцатая ночь»', detail: 'Театр имени Янки Купалы · 1 ч 40 мин', source: 'kudago.com' },
        { time: '20:00', title: 'Ужин у «Гвоздя»', detail: 'Троицкое предместье · столик на двоих', source: '2gis.by' },
        { time: '22:00', title: 'Джаз в «Полночи»', detail: 'Центральный р-н · 15 минут пешком', source: '2gis.by' },
      ],
    },
  ],
}

export function AssistantFab({ onOpen }: { onOpen: () => void }) {
  return (
    <button className="assistant-fab" onClick={onOpen} data-testid="assistant-fab">
      <MessageCircle size={19} />
      <span>Спросить ассистента</span>
    </button>
  )
}

export function ChatPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [chats, setChats] = useState<Chat[]>([])
  const [activeChatId, setActiveChatId] = useState('')
  const [listOpen, setListOpen] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState<number | null>(null)
  const [planThinking, setPlanThinking] = useState<number | null>(null)
  const [clarifyMissing, setClarifyMissing] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)
  // Chat list is a panel mode, not an overlay: keep the dialogue mounted state
  // (messages + scroll) while it is open.
  const listToggleRef = useRef<HTMLButtonElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const savedScroll = useRef(0)
  const listWasOpen = useRef(false)
  // One degraded-mode notice per chat, no matter how many turns fall back.
  const degradedNotices = useRef<Set<string>>(new Set())
  const mock = isMockMode()

  useEffect(() => {
    try {
      const saved = localStorage.getItem('dosugClarify')
      if (saved !== null) setClarifyMissing(saved === 'true')
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    const loaded = loadChats()
    setChats(loaded)
    setActiveChatId(loadActiveChatId(loaded))
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (hydrated) saveChats(chats)
  }, [chats, hydrated])

  useEffect(() => {
    if (hydrated && activeChatId) saveActiveChatId(activeChatId)
  }, [activeChatId, hydrated])

  const activeChat = chats.find((chat) => chat.id === activeChatId) ?? chats[0]
  const messages = activeChat?.messages ?? []

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, activeChatId, thinking, planThinking])

  // Focus follows the mode: first chat row on open, toggle on close.
  useEffect(() => {
    if (listOpen) {
      listRef.current?.querySelector<HTMLElement>('[data-testid="chat-list-item"]')?.focus()
    } else if (listWasOpen.current) {
      listToggleRef.current?.focus()
    }
    listWasOpen.current = listOpen
  }, [listOpen])

  // Escape leaves the list without closing the whole assistant.
  useEffect(() => {
    if (!listOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        setListOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [listOpen])

  // The body unmounts while the list is open: restore its scroll position.
  useEffect(() => {
    if (!listOpen && bodyRef.current) {
      bodyRef.current.scrollTop = savedScroll.current
    }
  }, [listOpen])

  const nextId = () => Date.now() + Math.floor(Math.random() * 1000)

  const updateChat = (chatId: string, update: (chat: Chat) => Chat) => {
    setChats((prev) => prev.map((chat) => (
      chat.id === chatId ? { ...update(chat), updatedAt: Date.now() } : chat
    )))
  }

  const toggleClarify = () => {
    const next = !clarifyMissing
    setClarifyMissing(next)
    try {
      localStorage.setItem('dosugClarify', String(next))
    } catch {
      /* ignore */
    }
    if (activeChat?.contract) {
      updateChat(activeChat.id, (chat) => ({
        ...chat,
        contract: chat.contract
          ? { ...chat.contract, clarify_missing: next }
          : chat.contract,
      }))
    }
  }

  const appendToChat = (chatId: string, items: ChatMessage[]) => {
    if (!items.length) return
    updateChat(chatId, (chat) => ({ ...chat, messages: [...chat.messages, ...items] }))
  }

  const addUserMessage = (chatId: string, text: string) => {
    updateChat(chatId, (chat) => ({
      ...chat,
      title: chat.title === 'Новый чат' ? titleFromMessage(text) : chat.title,
      messages: [...chat.messages, { id: nextId(), kind: 'user', text }],
    }))
  }

  const pushError = (text: string, chatId = activeChatId) => {
    appendToChat(chatId, [{ id: nextId(), kind: 'assistant', text, error: true }])
  }

  // A throttle is temporary and says nothing about the assistant's health:
  // one plain notice, no error styling and no degraded banner.
  const pushRateLimited = (chatId: string) => {
    appendToChat(chatId, [{ id: nextId(), kind: 'assistant', text: RATE_LIMIT_MESSAGE }])
  }

  // Holds are secured by the gateway: anonymous clicks must not reach the API.
  const LOGIN_PROMPT = 'Войдите в аккаунт, чтобы оформить бронь — /login'

  const pushLoginPrompt = (chatId: string) => {
    appendToChat(chatId, [{ id: nextId(), kind: 'assistant', text: LOGIN_PROMPT }])
  }

  const canHold = (chatId: string): boolean => {
    if (tokenStore.token) return true
    pushLoginPrompt(chatId)
    return false
  }

  const startNewChat = (): Chat => {
    const chat = createChat(null, nextChatNumber(chats))
    setChats((prev) => [chat, ...prev].slice(0, 20))
    setActiveChatId(chat.id)
    setListOpen(false)
    setDraft('')
    return chat
  }

  const switchChat = (chatId: string) => {
    setActiveChatId(chatId)
    setListOpen(false)
  }

  const deleteChat = (chatId: string) => {
    const rest = chats.filter((chat) => chat.id !== chatId)
    if (!rest.length) {
      const fresh = createChat(null, nextChatNumber([]))
      setChats([fresh])
      setActiveChatId(fresh.id)
      return
    }
    setChats(rest)
    if (chatId === activeChatId) setActiveChatId(rest[0].id)
  }

  const openChatList = () => {
    if (!listOpen) savedScroll.current = bodyRef.current?.scrollTop ?? 0
    setListOpen(!listOpen)
  }

  const closeChatList = () => setListOpen(false)

  const sendLive = async (chatId: string, text: string,
                          previous?: StateContract | null) => {
    setBusy(true)
    // "Thinking" indicator appears only on slow turns (reasoning lane);
    // fast turns resolve before the first tick.
    const startedAt = Date.now()
    setThinking(0)
    const timer = window.setInterval(() => {
      setThinking(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    try {
      const parsed = parseQuery(text)
      let contract = contractFromParsed(parsed, previous ?? undefined)
      contract.clarify_missing = clarifyMissing
      // "а ещё?" reuses the previous contract + shown ids: no LLM call and no
      // fresh structuring, the backend simply pages past what was already shown.
      const followUp = isFollowUpOnly(text) && Boolean(previous)
      if (!followUp) {
        try {
          // Model fills semantic slots; deterministic parser keeps RU dates.
          const remote = await structureQuery(text, contract.semantic_payload.language || 'ru',
            previous?.context_state.session_id, undefined, previous ?? undefined)
          if (remote.supported === false) {
            appendToChat(chatId, [{
              id: nextId(),
              kind: 'assistant',
              text: remote.reply || 'Я помогаю с событиями, местами и планом вечера в Минске. Спросите, например: «джаз завтра».',
            }])
            return
          }
          contract = mergeContracts(remote.contract, contract, parsed, previous ?? undefined)
        } catch (e) {
          // A throttle is not a model outage: say it plainly once and stop —
          // the dialogue call would only be throttled again. No degraded notice.
          if (isRateLimited(e)) {
            pushRateLimited(chatId)
            return
          }
          // The model stage is optional: keep the deterministic contract and
          // continue to /dialogue/v2 instead of failing the turn. One neutral
          // notice per chat keeps the degraded mode visible but quiet.
          if (!degradedNotices.current.has(chatId)) {
            degradedNotices.current.add(chatId)
            appendToChat(chatId, [{
              id: nextId(),
              kind: 'assistant',
              text: 'Модель недоступна — ищу по локальным правилам.',
            }])
          }
        }
      }
      const response = await sendDialogue(contract)
      const shownCards = response.messages.flatMap((message: DialogMessage) =>
        message.kind === 'results' ? message.results ?? [] : [])
      const shownIds = accumulateShownIds(contract.context_state.shown_ids, shownCards)
      const nextContract: StateContract = {
        ...response.contract,
        context_state: {
          ...response.contract.context_state,
          ...(shownIds.length ? { shown_ids: shownIds } : {}),
        },
      }
      const incoming = response.messages.length
        ? response.messages.map((message: DialogMessage, index: number) => ({
            id: nextId() + index,
            kind: message.kind,
            text: message.text,
            results: message.results,
            weather: message.weather,
            plan: message.plan,
            filters: message.kind === 'filters' ? nextContract : undefined,
          }))
        : [{
            id: nextId(),
            kind: 'assistant' as const,
            text: followUp
              ? response.contract.clarification_prompt || 'Больше вариантов нет — измените условия поиска.'
              : response.contract.clarification_prompt
                || 'Уточните запрос — например, дату и время.',
          }]
      updateChat(chatId, (chat) => ({
        ...chat,
        contract: nextContract,
        messages: [...chat.messages, ...incoming],
      }))
    } catch (e) {
      if (isRateLimited(e)) {
        pushRateLimited(chatId)
        return
      }
      pushError(e instanceof Error ? `Не получилось связаться с ассистентом: ${e.message}` : 'Не получилось связаться с ассистентом.', chatId)
    } finally {
      window.clearInterval(timer)
      setThinking(null)
      setBusy(false)
    }
  }

  const buildPlan = async () => {
    if (!activeChat) return
    const contract = activeChat.contract
    if (!contract) {
      pushError('Сначала опишите, что ищете, — тогда соберу план вечера.', activeChat.id)
      return
    }
    const contexts = activeChat.messages
      .filter((message) => message.kind === 'filters' && message.filters)
      .map((message) => message.filters as StateContract)
    addUserMessage(activeChat.id, 'Собери план вечера')
    setBusy(true)
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setPlanThinking(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    setPlanThinking(0)
    try {
      const response = await requestPlan(contract, contexts)
      const incoming = response.messages.length
        ? response.messages.map((message: DialogMessage, index: number) => ({
            id: nextId() + index,
            kind: message.kind,
            text: message.text,
            results: message.results,
            weather: message.weather,
            plan: message.plan,
          }))
        : [{
            id: nextId(),
            kind: 'assistant' as const,
            text: response.contract.clarification_prompt
              || 'Уточните условия — тогда соберу план.',
          }]
      updateChat(activeChat.id, (chat) => ({
        ...chat,
        contract: response.contract,
        messages: [...chat.messages, ...incoming],
      }))
    } catch (e) {
      if (isRateLimited(e)) {
        pushRateLimited(activeChat.id)
        return
      }
      pushError(e instanceof Error ? `Не получилось собрать план: ${e.message}` : 'Не получилось собрать план.', activeChat.id)
    } finally {
      window.clearInterval(timer)
      setPlanThinking(null)
      setBusy(false)
    }
  }

  const selectResult = async (chatId: string,
                               result: { title: string; meta: string; price: string; event_id?: string }) => {
    if (!isBookable(result.event_id)) return
    if (!canHold(chatId)) return
    const chat = chats.find((item) => item.id === chatId)
    const contract = chat?.contract
    const sessionId = contract?.context_state.session_id ?? `web_${Date.now()}`
    // 0 means "any party size" in the contract; a hold needs a concrete count.
    const partySize = holdPartySize(contract)
    setBusy(true)
    try {
      const tickets = await api.getTickets(Number(result.event_id))
      const active = tickets.filter((ticket) => ticket.active)
      if (!active.length) {
        pushError('Похоже, билеты разобрали — выберите другое событие.', chatId)
        return
      }
      const cheapest = active.reduce((best, ticket) => (ticket.price < best.price ? ticket : best))
      const hold = await createHold({
        session_id: sessionId,
        event_id: Number(result.event_id),
        zone: String(cheapest.zone),
        price: cheapest.price,
        party_size: partySize,
      })
      appendToChat(chatId, [{
        id: nextId(),
        kind: 'plan',
        text: `Держу для вас: ${result.title} — ${cheapest.zone}, ${cheapest.price} руб. Бронь сгорит через 10 минут.`,
        plan: [{ time: 'hold', title: result.title, detail: `${result.meta} · ${result.price}`, source: 'assistant' }],
        holdId: hold.id,
      }])
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        pushLoginPrompt(chatId)
        return
      }
      pushError(e instanceof Error ? `Не удалось оформить бронь: ${e.message}` : 'Не удалось оформить бронь.', chatId)
    } finally {
      setBusy(false)
    }
  }

  const confirmPlan = async (chatId: string, message: ChatMessage) => {
    const steps = (message.plan ?? []).filter((step) =>
      step.bookable && step.event_id && /^\d+$/.test(step.event_id))
    if (!steps.length) {
      pushError('В этом плане нет событий с онлайн-бронью — откройте события по ссылкам.', chatId)
      return
    }
    if (!canHold(chatId)) return
    const chat = chats.find((item) => item.id === chatId)
    const contract = chat?.contract
    const sessionId = contract?.context_state.session_id ?? `web_${Date.now()}`
    const partySize = holdPartySize(contract)
    setBusy(true)
    const booked: string[] = []
    const failed: string[] = []
    try {
      for (const step of steps) {
        try {
          const tickets = await api.getTickets(Number(step.event_id))
          const active = tickets.filter((ticket) => ticket.active)
          if (!active.length) {
            failed.push(`${step.title}: нет активных билетов`)
            continue
          }
          const cheapest = active.reduce((best, ticket) =>
            (ticket.price < best.price ? ticket : best))
          const hold = await createHold({
            session_id: sessionId,
            event_id: Number(step.event_id),
            zone: String(cheapest.zone),
            price: cheapest.price,
            party_size: partySize,
          })
          booked.push(`${step.title} — ${cheapest.zone}, ${cheapest.price} руб. (бронь №${hold.id})`)
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) {
            pushLoginPrompt(chatId)
            return
          }
          failed.push(`${step.title}: ${e instanceof Error ? e.message : 'ошибка брони'}`)
        }
      }
      const lines = [
        booked.length ? `План подтверждён. Брони на 10 минут:\n${booked.join('\n')}` : '',
        failed.length ? `Не удалось забронировать:\n${failed.join('\n')}` : '',
      ].filter(Boolean)
      appendToChat(chatId, [{
        id: nextId(),
        kind: 'assistant',
        text: lines.join('\n\n') || 'Не удалось подтвердить план.',
        error: booked.length === 0,
      }])
    } finally {
      setBusy(false)
    }
  }

  const dismissPlan = (chatId: string, messageId: number) => {
    updateChat(chatId, (chat) => ({
      ...chat,
      contract: null,
      messages: chat.messages.filter((item) => item.id !== messageId),
    }))
  }

  if (!open) return null

  const pushScenario = (chatId: string, label: string) => {
    const script = SCENARIOS[label]
    if (!script) return
    updateChat(chatId, (chat) => ({
      ...chat,
      title: chat.title === 'Новый чат' ? titleFromMessage(label) : chat.title,
      messages: [
        ...chat.messages,
        { id: nextId(), kind: 'user', text: label },
        ...script.map((message, index) => ({ ...message, id: nextId() + index })),
      ],
    }))
  }

  const send = () => {
    const text = draft.trim()
    if (!text || busy || !activeChat) return
    setDraft('')
    addUserMessage(activeChat.id, text)
    if (!mock) {
      void sendLive(activeChat.id, text, activeChat.contract)
      return
    }
    const known = Object.keys(SCENARIOS).find((key) =>
      key.toLowerCase().split(' ').some((word) => word.length > 3 && text.toLowerCase().includes(word)),
    );
    setTimeout(() => {
      if (known) {
        pushScenario(activeChat.id, known)
      } else {
        appendToChat(activeChat.id, [{
          id: nextId(),
          kind: 'assistant',
          text: 'Уточню: вас интересует событие на конкретную дату или место для вечера? Напишите, сколько вас будет и какой бюджет на человека.',
        }])
      }
    }, 400)
  }

  const chatNumber = activeChat?.number ?? 1
  const summaryDate = activeChat ? new Date(activeChat.createdAt) : new Date()

  return (
    <div className="chat-overlay" onClick={onClose} data-testid="chat-overlay">
      <section className="chat-panel" onClick={(e) => e.stopPropagation()} data-testid="chat-panel">
        <header>
          <div>
            <div className="kicker">СПРАВКА РЕДАКЦИИ · {mock ? 'РЕЖИМ ДЕМО' : 'ОНЛАЙН'}</div>
            <h2>Ваш помощник</h2>
          </div>
          <div className="chat-header-actions">
            <button
              ref={listToggleRef}
              onClick={openChatList}
              aria-label="Чаты"
              aria-expanded={listOpen}
              aria-controls="chat-list-panel"
              data-testid="chat-list-toggle"
            ><MessageSquare size={18} /></button>
            <button
              onClick={toggleClarify}
              aria-label={clarifyMissing ? 'Отключить уточнения' : 'Включить уточнения'}
              className={clarifyMissing ? 'chat-toggle active' : 'chat-toggle'}
              data-testid="chat-clarify-toggle"
              title={clarifyMissing ? 'Ассистент уточняет недостающие параметры' : 'Ассистент ищет сразу'}
            >
              <HelpCircle size={18} />
            </button>
            <button onClick={() => { startNewChat() }} aria-label="Новый чат" data-testid="chat-new"><Plus size={19} /></button>
            <button onClick={onClose} aria-label="Закрыть" data-testid="chat-close"><X size={19} /></button>
          </div>
        </header>
        {listOpen ? (
          <div className="chat-list-view" id="chat-list-panel" data-testid="chat-list" ref={listRef}>
            <div className="chat-list-head">
              <button onClick={closeChatList} aria-label="Назад к диалогу" data-testid="chat-list-back">← Назад</button>
              <span>ЧАТЫ · {chats.length}</span>
              <button onClick={() => { startNewChat() }} data-testid="chat-list-new"><Plus size={14} /> Новый</button>
            </div>
            {chats.map((chat) => (
              <div className={`chat-list-row ${chat.id === activeChat?.id ? 'active' : ''}`} key={chat.id}>
                <button className="chat-list-open" onClick={() => switchChat(chat.id)} data-testid="chat-list-item">
                  <strong>{chat.title || welcomeMessage().text}</strong>
                  <span>{new Date(chat.updatedAt).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                </button>
                <button className="chat-list-delete" onClick={() => deleteChat(chat.id)} aria-label="Удалить чат" data-testid="chat-delete"><Trash2 size={14} /></button>
              </div>
            ))}
          </div>
        ) : (
          <>
        <div className="chat-summary" data-testid="chat-summary">
          СВОДКА № {chatNumber} · {summaryDate.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })} · {timeOfDay(summaryDate)}
        </div>
        <div className="chat-body" ref={bodyRef}>
          {messages.map((message) => {
            if (message.kind === 'user') {
              return <div className="user-message" key={message.id} data-testid="chat-user-message">{message.text}</div>
            }
            if (message.kind === 'weather') {
              const rainy = message.text.toLowerCase().includes('дождь')
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-weather">
                  <span className="message-number">СВОДКА ПОГОДЫ · OPEN-METEO</span>
                  <p className="weather-line">{rainy ? <CloudRain size={15} /> : <Sun size={15} />} {message.text}</p>
                </div>
              )
            }
            if (message.kind === 'filters' && message.filters) {
              const contract = message.filters
              const budget = contract.hard_filters.budget
              // A party total lives in `total`; older responses only carry the
              // per-person figure.
              const budgetAmount = budget?.basis === 'total'
                ? budget.total ?? budget.max_price_per_person
                : budget?.max_price_per_person
              const when = formatWhen(contract.hard_filters.datetime)
              const partySize = contract.hard_filters.party_size
              const hasParty = typeof partySize === 'number'
              const categories = contract.hard_filters.category ?? []
              const location = contract.hard_filters.location
              const negative = contract.negative_filters
              const hasExceptions = Boolean(
                negative?.exclude_tags?.length
                || negative?.exclude_categories?.length
                || negative?.exclude_districts?.length,
              )
              const eventCount = contract.hard_filters.event_count
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-filters">
                  <span className="message-number">КОНТРАКТ ДИАЛОГА · ШАГ {contract.context_state.turn_count}</span>
                  <p>{message.text}</p>
                  <div className="filter-chips" data-testid="chat-hard-filters">
                    {when
                      ? <span className="chip chip-dark">когда: {when}</span>
                      : <span className="chip chip-muted" title="по умолчанию">когда: ближайшие</span>}
                    {location?.any
                      ? <span className="chip chip-dark">где: любой город</span>
                      : location?.city
                        ? <span className="chip chip-dark">где: {location.city}</span>
                        : <span className="chip chip-muted" title="по умолчанию">где: {CITIES}</span>}
                    {categories.length
                      ? categories.map((cat) => <span className="chip chip-dark" key={cat}>тип: {cat}</span>)
                      : <span className="chip chip-muted" title="по умолчанию">тип: любые</span>}
                    {contract.hard_filters.themes?.map((theme) => <span className="chip chip-dark" key={theme}>тема: {THEME_LABELS[theme] ?? theme}</span>)}
                    {contract.intent?.startsWith('find_venue') && <span className="chip chip-dark">раздел: места</span>}
                    {contract.intent === 'both' && <span className="chip chip-dark">раздел: события и места</span>}
                    {partySize === 0
                      ? <span className="chip chip-dark">нас: любое</span>
                      : hasParty
                        ? <span className="chip chip-dark">нас: {partySize}</span>
                        : <span className="chip chip-muted" title="по умолчанию">нас: не указано</span>}
                    {budget?.any
                      ? <span className="chip chip-dark">цена: любая</span>
                      : budgetAmount != null
                        ? (
                          <span className="chip chip-dark">
                            до {budgetAmount} руб.
                            {budget?.basis === 'total' ? ' на всех' : ''}
                          </span>
                        )
                        : <span className="chip chip-muted" title="по умолчанию">цена: без ограничений</span>}
                    {contract.hard_filters.min_rating != null
                      ? <span className="chip chip-dark">рейтинг: от {contract.hard_filters.min_rating}</span>
                      : <span className="chip chip-muted" title="по умолчанию">рейтинг: любой</span>}
                    {contract.hard_filters.age_max != null
                      ? <span className="chip chip-dark">{ageLabel(contract.hard_filters.age_max)}</span>
                      : <span className="chip chip-muted" title="по умолчанию">возраст: любой</span>}
                    {eventCount != null && (
                      <span className="chip chip-dark">событий в плане: {eventCount}</span>
                    )}
                    {hasExceptions ? (
                      <>
                        {negative?.exclude_tags?.map((tag) => <span className="chip chip-neg" key={tag}>без {tag}</span>)}
                        {negative?.exclude_categories?.map((cat) => <span className="chip chip-neg" key={cat}>кроме {cat}</span>)}
                        {negative?.exclude_districts?.map((district) => <span className="chip chip-neg" key={district}>не {district}</span>)}
                      </>
                    ) : (
                      <span className="chip chip-muted" title="по умолчанию">исключений нет</span>
                    )}
                  </div>
                </div>
              )
            }
            if (message.kind === 'results' && message.results) {
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-results">
                  <span className="message-number">РЕЗУЛЬТАТЫ</span>
                  <p>{message.text}</p>
                  <div className="result-cards">
                    {message.results.map((result) => {
                      const detailHref = result.kind === 'venue'
                        ? `/places/detail?id=${encodeURIComponent(result.detail_id ?? '')}`
                        : `/events/detail?id=${encodeURIComponent(result.detail_id ?? '')}`
                      const rating = ratingValue(result.rating)
                      const reviews = typeof result.review_count === 'number' ? result.review_count : null
                      const statusText = statusLabel(result.status)
                      const seats = typeof result.seats_left === 'number' ? result.seats_left : null
                      const partySize = activeChat?.contract?.hard_filters.party_size
                      const noSeats = result.fits_party === false && partySize && partySize > 0
                        ? `на ${partySize} ${plural(partySize, ['человека', 'человек', 'человек'])} нет мест`
                        : null
                      // The backend already puts the run/showtime into `meta`;
                      // structured film fields only fill what it omitted.
                      const sessionTime = filmSessionTime(result)
                      const showSession = Boolean(sessionTime) && !result.meta.includes(sessionTime)
                      const facts = filmFacts(result).filter((fact) => !result.meta.includes(fact))
                      const card = (
                        <>
                          {(rating !== null || statusText) && (
                            <div className="result-badges">
                              {rating !== null && (
                                <span className="place-rating"><Star size={13} /> {rating.toFixed(1)}</span>
                              )}
                              {rating !== null && reviews !== null && (
                                <span className="result-reviews">
                                  {reviews} {plural(reviews, ['отзыв', 'отзыва', 'отзывов'])}
                                </span>
                              )}
                              {statusText && <span className="chip chip-neg">{statusText}</span>}
                            </div>
                          )}
                          <h3>{result.title}</h3>
                          <p>{result.meta}</p>
                          {showSession && (
                            <p className="result-film" data-testid="chat-result-film-session">
                              {filmSessionLabel(result)}
                            </p>
                          )}
                          {facts.length > 0 && (
                            <p className="result-film" data-testid="chat-result-film-facts">
                              {facts.join(' · ')}
                            </p>
                          )}
                          {result.address && <p>{result.address}</p>}
                          {result.hours && <p>Часы: {result.hours}</p>}
                          {noSeats && <p className="result-availability">{noSeats}</p>}
                          {!noSeats && seats !== null && (
                            <p className="result-availability">мест: {seats}</p>
                          )}
                          {result.price && <strong>{result.price}</strong>}
                          {result.source && (
                            <span className="result-source">Источник: {sourceLabel(result.source)}</span>
                          )}
                        </>
                      )
                      return (
                        <article className="result-card" key={`${result.title}-${result.event_id ?? ''}`} data-testid="chat-result-card">
                          {isDetailId(result.detail_id) ? (
                            <Link
                              href={detailHref}
                              className="result-card-link"
                              data-testid="chat-result-link"
                            >
                              {card}
                            </Link>
                          ) : (
                            <div className="result-card-link">{card}</div>
                          )}
                          {isBookable(result.event_id) && (
                            <button
                              className="apply-button"
                              disabled={busy || !!statusText}
                              onClick={() => void selectResult(activeChat?.id ?? '', result)}
                              data-testid="chat-result-select"
                              title={statusText ?? undefined}
                            >
                              Выбрать
                            </button>
                          )}
                        </article>
                      )
                    })}
                  </div>
                </div>
              )
            }
            if (message.kind === 'plan' && message.plan) {
              const planBookable = message.plan.some((step) => step.bookable)
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-plan">
                  <span className="message-number">{planLabel(activeChat?.contract ?? undefined, message.plan)}</span>
                  <p>{message.text}</p>
                  <ol className="plan-steps">
                    {message.plan.map((step) => {
                      const href = step.detail_id
                        ? (step.kind === 'venue'
                          ? `/places/detail?id=${encodeURIComponent(step.detail_id)}`
                          : `/events/detail?id=${encodeURIComponent(step.detail_id)}`)
                        : null
                      const rating = ratingValue(step.rating)
                      const statusText = statusLabel(step.status)
                      return (
                        <li key={`${step.time}-${step.title}`} data-testid="chat-plan-step">
                          <strong>{step.time}</strong>
                          <div>
                            {(rating !== null || statusText) && (
                              <div className="result-badges">
                                {rating !== null && (
                                  <span className="place-rating"><Star size={12} /> {rating.toFixed(1)}</span>
                                )}
                                {statusText && <span className="chip chip-neg">{statusText}</span>}
                              </div>
                            )}
                            <h3>
                              {href ? <Link href={href}>{step.title}</Link> : step.title}
                            </h3>
                            <p>{step.detail}</p>
                            <span>Источник: {sourceLabel(step.source)}</span>
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                  <div className="plan-actions">
                    <button
                      className="apply-button"
                      disabled={busy || !planBookable}
                      onClick={() => void confirmPlan(activeChat?.id ?? '', message)}
                      data-testid="chat-plan-confirm"
                      title={planBookable
                        ? 'Забронировать события плана на 10 минут'
                        : 'В плане нет событий с онлайн-бронью'}
                    >
                      <CheckCircle2 size={15} /> Подтвердить план
                    </button>
                    {!planBookable && (
                      <p className="side-hint">В плане нет событий с онлайн-бронью — откройте карточки по ссылкам.</p>
                    )}
                    <button
                      className="reset-button"
                      onClick={() => dismissPlan(activeChat?.id ?? '', message.id)}
                      data-testid="chat-plan-edit"
                    >
                      <RefreshCcw size={13} /> Изменить условия
                    </button>
                  </div>
                </div>
              )
            }
            return (
              <div className="assistant-message" key={message.id} data-testid={message.error ? 'chat-error' : undefined}>
                {message.error && <span className="message-number">ОШИБКА</span>}
                <p>{message.text}</p>
                {mock && (
                <div className="quick-replies" data-testid="chat-quick-replies">
                  {Object.keys(SCENARIOS).map((label) => (
                    <button key={label} onClick={() => activeChat && pushScenario(activeChat.id, label)}>{label}</button>
                  ))}
                </div>
                )}
              </div>
            )
          })}
          {thinking !== null && (
            <div className="assistant-message" data-testid="chat-thinking">
              <span className="message-number">АССИСТЕНТ ОБРАБАТЫВАЕТ ЗАПРОС</span>
              <p>Печатает… {thinking} с</p>
            </div>
          )}
          {planThinking !== null && (
            <div className="assistant-message" data-testid="chat-plan-thinking">
              <span className="message-number">СОБИРАЮ ПЛАН</span>
              <p>Строю маршрут по найденным событиям… {planThinking} с</p>
            </div>
          )}
          <div ref={endRef} />
        </div>
        <div className="chat-plan-row">
          <button
            type="button"
            className="reset-button"
            disabled={busy}
            onClick={() => void buildPlan()}
            data-testid="chat-plan-request"
            title="Собрать план вечера (может занять пару минут)"
          >
            Собрать план вечера
          </button>
        </div>
        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
        >
          <input
            placeholder="Напишите свой запрос…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            data-testid="chat-input"
          />
          <button aria-label="Отправить" type="submit" disabled={busy} data-testid="chat-send"><ArrowRight size={18} /></button>
        </form>
          </>
        )}
      </section>
    </div>
  )
}
