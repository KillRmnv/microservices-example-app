'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { ArrowRight, CheckCircle2, CloudRain, MessageCircle, MessageSquare, Plus, RefreshCcw, Sun, Trash2, X } from 'lucide-react'
import type { StateContract } from '@/lib/types'
import { api } from '@/lib/api'
import { sourceLabel } from '@/lib/catalog'
import {
  confirmHold,
  createHold,
  isMockMode,
  requestPlan,
  sendDialogue,
  structureQuery,
  type DialogMessage,
} from '@/lib/assistant'
import { contractFromParsed, mergeContracts, parseQuery } from '@/lib/dialogue'
import {
  type Chat,
  type ChatMessage,
  createChat,
  loadActiveChatId,
  loadChats,
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

const CITIES = 'Минск'
const THEME_LABELS: Record<string, string> = {
  classical: 'классика',
  jazz: 'джаз',
  rock: 'рок',
  beer: 'пиво',
  kids: 'детям',
}

function baseContract(): StateContract {
  return {
    dialogue_action: 'search',
    needs_clarification: false,
    clarification_prompt: null,
    hard_filters: {
      location: { city: CITIES },
      party_size: 2,
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
  const endRef = useRef<HTMLDivElement | null>(null)
  const mock = isMockMode()

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

  const nextId = () => Date.now() + Math.floor(Math.random() * 1000)

  const updateChat = (chatId: string, update: (chat: Chat) => Chat) => {
    setChats((prev) => prev.map((chat) => (
      chat.id === chatId ? { ...update(chat), updatedAt: Date.now() } : chat
    )))
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

  const startNewChat = (): Chat => {
    const chat = createChat()
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
      const fresh = createChat()
      setChats([fresh])
      setActiveChatId(fresh.id)
      return
    }
    setChats(rest)
    if (chatId === activeChatId) setActiveChatId(rest[0].id)
  }

  const openChatList = () => setListOpen((value) => !value)

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
        contract = mergeContracts(remote.contract, contract, parsed)
      } catch {
        /* model backend down: keep the local contract */
      }
      const response = await sendDialogue(contract)
      const incoming = response.messages.length
        ? response.messages.map((message: DialogMessage, index: number) => ({
            id: nextId() + index,
            kind: message.kind,
            text: message.text,
            results: message.results,
            weather: message.weather,
            plan: message.plan,
            filters: message.kind === 'filters' ? response.contract : undefined,
          }))
        : [{
            id: nextId(),
            kind: 'assistant' as const,
            text: response.contract.clarification_prompt
              || 'Уточните запрос — например, дату и время.',
          }]
      updateChat(chatId, (chat) => ({
        ...chat,
        contract: response.contract,
        messages: [...chat.messages, ...incoming],
      }))
    } catch (e) {
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
    addUserMessage(activeChat.id, 'Собери план вечера')
    setBusy(true)
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      setPlanThinking(Math.floor((Date.now() - startedAt) / 1000))
    }, 1000)
    setPlanThinking(0)
    try {
      const response = await requestPlan(contract)
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
    const chat = chats.find((item) => item.id === chatId)
    const contract = chat?.contract
    const sessionId = contract?.context_state.session_id ?? `web_${Date.now()}`
    const partySize = contract?.hard_filters.party_size ?? 2
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
      pushError(e instanceof Error ? `Не удалось оформить бронь: ${e.message}` : 'Не удалось оформить бронь.', chatId)
    } finally {
      setBusy(false)
    }
  }

  const confirmPlan = async (chatId: string, message: ChatMessage) => {
    if (!message.holdId) return
    setBusy(true)
    try {
      const hold = await confirmHold(message.holdId)
      appendToChat(chatId, [{
        id: nextId(),
        kind: 'assistant',
        text: `Готово! Бронь №${hold.id} подтверждена: событие ${hold.event_id}, зона ${hold.zone}, ${hold.price} руб.`,
      }])
      const confirmedId = message.id
      updateChat(chatId, (chat) => ({
        ...chat,
        messages: chat.messages.map((item) =>
          item.id === confirmedId ? { ...item, holdId: undefined } : item),
      }))
    } catch (e) {
      pushError(e instanceof Error ? `Не удалось подтвердить: ${e.message}` : 'Не удалось подтвердить бронь.', chatId)
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

  return (
    <div className="chat-overlay" onClick={onClose} data-testid="chat-overlay">
      <section className="chat-panel" onClick={(e) => e.stopPropagation()} data-testid="chat-panel">
        <header>
          <div>
            <div className="kicker">СПРАВКА РЕДАКЦИИ · {mock ? 'РЕЖИМ ДЕМО' : 'ОНЛАЙН'}</div>
            <h2>Ваш помощник</h2>
          </div>
          <div className="chat-header-actions">
            <button onClick={openChatList} aria-label="Чаты" data-testid="chat-list-toggle"><MessageSquare size={18} /></button>
            <button onClick={() => { startNewChat() }} aria-label="Новый чат" data-testid="chat-new"><Plus size={19} /></button>
            <button onClick={onClose} aria-label="Закрыть" data-testid="chat-close"><X size={19} /></button>
          </div>
        </header>
        {listOpen && (
          <div className="chat-list" data-testid="chat-list">
            <div className="chat-list-head">
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
        )}
        <div className="chat-body">
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
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-filters">
                  <span className="message-number">КОНТРАКТ ДИАЛОГА · ШАГ {contract.context_state.turn_count}</span>
                  <p>{message.text}</p>
                  <div className="filter-chips" data-testid="chat-hard-filters">
                    {contract.hard_filters.datetime?.raw_expression && <span className="chip chip-dark">когда: {contract.hard_filters.datetime.raw_expression}</span>}
                    {contract.hard_filters.datetime?.start && !contract.hard_filters.datetime.raw_expression && <span className="chip chip-dark">когда: выходные</span>}
                    {contract.hard_filters.location?.city && <span className="chip chip-dark">где: {contract.hard_filters.location.city}</span>}
                    {contract.hard_filters.category?.map((cat) => <span className="chip chip-dark" key={cat}>тип: {cat}</span>)}
                    {contract.hard_filters.themes?.map((theme) => <span className="chip chip-dark" key={theme}>тема: {THEME_LABELS[theme] ?? theme}</span>)}
                    {contract.intent === 'find_venues' && <span className="chip chip-dark">раздел: места</span>}
                    {contract.hard_filters.party_size && <span className="chip chip-dark">нас: {contract.hard_filters.party_size}</span>}
                    {contract.negative_filters?.exclude_tags?.map((tag) => <span className="chip chip-neg" key={tag}>без {tag}</span>)}
                    {contract.negative_filters?.exclude_categories?.map((cat) => <span className="chip chip-neg" key={cat}>кроме {cat}</span>)}
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
                      const card = (
                        <>
                          <h3>{result.title}</h3>
                          <p>{result.meta}</p>
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
                              disabled={busy}
                              onClick={() => void selectResult(activeChat?.id ?? '', result)}
                              data-testid="chat-result-select"
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
              return (
                <div className="assistant-message" key={message.id} data-testid="chat-plan">
                  <span className="message-number">ПЛАН ДОСУГА · НА ПОДТВЕРЖДЕНИЕ</span>
                  <p>{message.text}</p>
                  <ol className="plan-steps">
                    {message.plan.map((step) => (
                      <li key={step.time} data-testid="chat-plan-step">
                        <strong>{step.time}</strong>
                        <div>
                          <h3>{step.title}</h3>
                          <p>{step.detail}</p>
                          <span>Источник: {sourceLabel(step.source)}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <div className="plan-actions">
                    <button
                      className="apply-button"
                      disabled={busy || !message.holdId}
                      onClick={() => void confirmPlan(activeChat?.id ?? '', message)}
                      data-testid="chat-plan-confirm"
                    >
                      <CheckCircle2 size={15} /> Подтвердить план
                    </button>
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
                <span className="message-number">СВОДКА № 001 · ТОЛЬКО ЧТО</span>
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
      </section>
    </div>
  )
}
