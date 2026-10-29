'use client'

import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, CloudRain, MessageCircle, RefreshCcw, Sun, X } from 'lucide-react'
import type { StateContract } from '@/lib/types'
import { api } from '@/lib/api'
import {
  clearContract,
  confirmHold,
  createHold,
  isMockMode,
  loadContract,
  requestPlan,
  saveContract,
  sendDialogue,
  structureQuery,
  type DialogMessage,
} from '@/lib/assistant'
import { contractFromParsed, mergeContracts, parseQuery } from '@/lib/dialogue'

interface ChatMessage {
  id: number
  kind: 'user' | 'assistant' | 'filters' | 'results' | 'plan' | 'weather'
  text: string
  filters?: StateContract
  results?: { title: string; meta: string; price: string; event_id?: string }[]
  plan?: { time: string; title: string; detail: string; source: string }[]
  holdId?: string
  error?: boolean
}

function isBookable(eventId: string | undefined): eventId is string {
  return !!eventId && /^\d+$/.test(eventId)
}

const CITIES = 'Минск'

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
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 1,
      kind: 'assistant',
      text: 'Добрый вечер. Что ищем сегодня — событие, место или готовый план прогулки?',
    },
  ])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState<number | null>(null)
  const mock = isMockMode()

  const nextId = () => Date.now() + Math.floor(Math.random() * 1000)

  const pushError = (text: string) => {
    setMessages((prev) => [...prev, { id: nextId(), kind: 'assistant', text, error: true }])
  }

  const sendLive = async (text: string) => {
    setBusy(true)
    // "Thinking" indicator appears only on slow turns (reasoning lane);
    // fast turns resolve before the first tick.
    const startedAt = Date.now()
    const timer = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000)
      if (elapsed >= 4) setThinking(elapsed)
    }, 1000)
    try {
      const stored = loadContract() ?? undefined
      const parsed = parseQuery(text)
      let contract = contractFromParsed(parsed, stored)
      try {
        // Model fills semantic slots; deterministic parser keeps RU dates.
        const remote = await structureQuery(text, contract.semantic_payload.language || 'ru',
          stored?.context_state.session_id)
        contract = mergeContracts(remote.contract, contract)
      } catch {
        /* model backend down: keep the local contract */
      }
      const response = await sendDialogue(contract)
      saveContract(response.contract)
      setMessages((prev) => [
        ...prev,
        ...response.messages.map((message: DialogMessage, index: number) => ({
          id: nextId() + index,
          kind: message.kind,
          text: message.text,
          results: message.results,
          weather: message.weather,
          plan: message.plan,
          filters: message.kind === 'filters' ? response.contract : undefined,
        })),
      ])
    } catch (e) {
      pushError(e instanceof Error ? `Не получилось связаться с ассистентом: ${e.message}` : 'Не получилось связаться с ассистентом.')
    } finally {
      window.clearInterval(timer)
      setThinking(null)
      setBusy(false)
    }
  }

  const buildPlan = async () => {
    const contract = loadContract()
    if (!contract) {
      pushError('Сначала опишите, что ищете, — тогда соберу план вечера.')
      return
    }
    setBusy(true)
    try {
      const response = await requestPlan(contract)
      saveContract(response.contract)
      setMessages((prev) => [
        ...prev,
        ...response.messages.map((message: DialogMessage, index: number) => ({
          id: nextId() + index,
          kind: message.kind,
          text: message.text,
          results: message.results,
          weather: message.weather,
          plan: message.plan,
        })),
      ])
    } catch (e) {
      pushError(e instanceof Error ? `Не получилось собрать план: ${e.message}` : 'Не получилось собрать план.')
    } finally {
      setBusy(false)
    }
  }

  const selectResult = async (result: { title: string; meta: string; price: string; event_id?: string }) => {
    if (!isBookable(result.event_id)) return
    const contract = loadContract()
    const sessionId = contract?.context_state.session_id ?? `web_${Date.now()}`
    const partySize = contract?.hard_filters.party_size ?? 2
    setBusy(true)
    try {
      const tickets = await api.getTickets(Number(result.event_id))
      const active = tickets.filter((ticket) => ticket.active)
      if (!active.length) {
        pushError('Похоже, билеты разобрали — выберите другое событие.')
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
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          kind: 'plan',
          text: `Держу для вас: ${result.title} — ${cheapest.zone}, ${cheapest.price} руб. Бронь сгорит через 10 минут.`,
          plan: [{ time: 'hold', title: result.title, detail: `${result.meta} · ${result.price}`, source: 'assistant' }],
          holdId: hold.id,
        },
      ])
    } catch (e) {
      pushError(e instanceof Error ? `Не удалось оформить бронь: ${e.message}` : 'Не удалось оформить бронь.')
    } finally {
      setBusy(false)
    }
  }

  const confirmPlan = async (message: ChatMessage) => {
    if (!message.holdId) return
    setBusy(true)
    try {
      const hold = await confirmHold(message.holdId)
      setMessages((prev) => [
        ...prev,
        {
          id: nextId(),
          kind: 'assistant',
          text: `Готово! Бронь №${hold.id} подтверждена: событие ${hold.event_id}, зона ${hold.zone}, ${hold.price} руб.`,
        },
      ])
      const confirmedId = message.id
      setMessages((prev) => prev.map((item) =>
        item.id === confirmedId ? { ...item, holdId: undefined } : item))
    } catch (e) {
      pushError(e instanceof Error ? `Не удалось подтвердить: ${e.message}` : 'Не удалось подтвердить бронь.')
    } finally {
      setBusy(false)
    }
  }

  const dismissPlan = (messageId: number) => {
    clearContract()
    setMessages((prev) => prev.filter((item) => item.id !== messageId))
  }

  useEffect(() => {
    if (open) {
      setMessages([
        { id: 1, kind: 'assistant', text: 'Добрый вечер. Что ищем сегодня — событие, место или готовый план прогулки?' },
      ])
    }
  }, [open])

  if (!open) return null

  const pushScenario = (label: string) => {
    const script = SCENARIOS[label]
    if (!script) return
    setMessages((prev) => [
      ...prev,
      { id: prev.length * 10 + 1, kind: 'user', text: label },
      ...script.map((message, index) => ({ ...message, id: (prev.length * 10 + 2) * 100 + index })),
    ])
  }

  const send = () => {
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    setMessages((prev) => [...prev, { id: nextId(), kind: 'user', text }])
    if (!mock) {
      void sendLive(text)
      return
    }
    const known = Object.keys(SCENARIOS).find((key) =>
      key.toLowerCase().split(' ').some((word) => word.length > 3 && text.toLowerCase().includes(word)),
    );
    setTimeout(() => {
      if (known) {
        pushScenario(known)
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            kind: 'assistant',
            text: 'Уточню: вас интересует событие на конкретную дату или место для вечера? Напишите, сколько вас будет и какой бюджет на человека.',
          },
        ])
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
          <button onClick={onClose} aria-label="Закрыть" data-testid="chat-close"><X size={19} /></button>
        </header>
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
                    {message.results.map((result) => (
                      <article className="result-card" key={`${result.title}-${result.event_id ?? ''}`} data-testid="chat-result-card">
                        <h3>{result.title}</h3>
                        <p>{result.meta}</p>
                        <strong>{result.price}</strong>
                        {isBookable(result.event_id) && (
                          <button
                            className="apply-button"
                            disabled={busy}
                            onClick={() => void selectResult(result)}
                            data-testid="chat-result-select"
                          >
                            Выбрать
                          </button>
                        )}
                      </article>
                    ))}
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
                          <span>Источник: {step.source}</span>
                        </div>
                      </li>
                    ))}
                  </ol>
                  <div className="plan-actions">
                    <button
                      className="apply-button"
                      disabled={busy || !message.holdId}
                      onClick={() => void confirmPlan(message)}
                      data-testid="chat-plan-confirm"
                    >
                      <CheckCircle2 size={15} /> Подтвердить план
                    </button>
                    <button
                      className="reset-button"
                      onClick={() => dismissPlan(message.id)}
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
                    <button key={label} onClick={() => pushScenario(label)}>{label}</button>
                  ))}
                </div>
                )}
              </div>
            )
          })}
          {thinking !== null && (
            <div className="assistant-message" data-testid="chat-thinking">
              <span className="message-number">АССИСТЕНТ ДУМАЕТ</span>
              <p>Размышляю над запросом… {thinking} с</p>
            </div>
          )}
        </div>
        <div className="chat-plan-row">
          <button
            type="button"
            className="reset-button"
            disabled={busy || mock}
            onClick={() => void buildPlan()}
            data-testid="chat-plan-request"
            title={mock ? 'План доступен в онлайн-режиме' : 'Собрать план вечера (может занять пару минут)'}
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
