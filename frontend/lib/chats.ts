/** Local chat history: several assistant dialogues, one contract per chat. */
import type { StateContract } from './types'

export interface ChatResult {
  title: string
  meta: string
  price: string
  event_id?: string
  detail_id?: string
  source?: string
  kind?: 'event' | 'venue'
}

export interface ChatMessage {
  id: number
  kind: 'user' | 'assistant' | 'filters' | 'results' | 'plan' | 'weather'
  text: string
  filters?: StateContract
  results?: ChatResult[]
  plan?: { time: string; title: string; detail: string; source: string }[]
  holdId?: string
  error?: boolean
}

export interface Chat {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
  contract: StateContract | null
}

const CHATS_KEY = 'dosugChats.v1'
const ACTIVE_KEY = 'dosugActiveChat'
const LEGACY_CONTRACT_KEY = 'dosugDialogue'
const MAX_CHATS = 20
const MAX_MESSAGES = 200
const NEW_TITLE = 'Новый чат'

export const WELCOME =
  'Добрый вечер. Что ищем сегодня — событие, место или готовый план прогулки?'

export function welcomeMessage(): ChatMessage {
  return { id: 1, kind: 'assistant', text: WELCOME }
}

export function createChat(contract: StateContract | null = null): Chat {
  const now = Date.now()
  return {
    id: `chat_${now}_${Math.floor(Math.random() * 10000)}`,
    title: NEW_TITLE,
    createdAt: now,
    updatedAt: now,
    messages: [welcomeMessage()],
    contract,
  }
}

export function titleFromMessage(text: string): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length > 42 ? `${clean.slice(0, 41)}…` : clean || NEW_TITLE
}

const MESSAGE_KINDS = new Set([
  'user', 'assistant', 'filters', 'results', 'plan', 'weather',
])

function asMessage(value: unknown): ChatMessage | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Partial<ChatMessage>
  if (!MESSAGE_KINDS.has(String(raw.kind)) || typeof raw.text !== 'string') {
    return null
  }
  return {
    ...raw,
    id: typeof raw.id === 'number' && Number.isFinite(raw.id)
      ? raw.id : Date.now() + Math.floor(Math.random() * 1000),
    kind: raw.kind as ChatMessage['kind'],
    text: raw.text,
  }
}

function asContract(value: unknown): StateContract | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Partial<StateContract>
  if (!raw.hard_filters || !raw.semantic_payload || !raw.context_state) {
    return null
  }
  return raw as StateContract
}

function asChat(value: unknown): Chat | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Partial<Chat>
  if (typeof raw.id !== 'string' || !Array.isArray(raw.messages)) return null
  const messages = raw.messages
    .map(asMessage)
    .filter((message): message is ChatMessage => message !== null)
    .slice(-MAX_MESSAGES)
  return {
    id: raw.id,
    title: typeof raw.title === 'string' ? raw.title : NEW_TITLE,
    createdAt: typeof raw.createdAt === 'number' ? raw.createdAt : Date.now(),
    updatedAt: typeof raw.updatedAt === 'number' ? raw.updatedAt : Date.now(),
    messages: messages.length ? messages : [welcomeMessage()],
    contract: asContract(raw.contract),
  }
}

function readLegacyContract(): StateContract | null {
  try {
    const raw = localStorage.getItem(LEGACY_CONTRACT_KEY)
    return raw ? (JSON.parse(raw) as StateContract) : null
  } catch {
    return null
  }
}

export function loadChats(): Chat[] {
  try {
    const raw = localStorage.getItem(CHATS_KEY)
    const parsed = raw ? (JSON.parse(raw) as unknown) : null
    const list = Array.isArray(parsed)
      ? parsed.map(asChat).filter((chat): chat is Chat => chat !== null)
      : []
    if (list.length) return list.slice(0, MAX_CHATS)
    // One-time migration: keep the old single dialogue as the first chat.
    const legacy = readLegacyContract()
    return [createChat(legacy)]
  } catch {
    return [createChat()]
  }
}

export function saveChats(chats: Chat[]): void {
  try {
    const trimmed = chats.slice(0, MAX_CHATS).map((chat) => ({
      ...chat,
      messages: chat.messages.slice(-MAX_MESSAGES),
    }))
    localStorage.setItem(CHATS_KEY, JSON.stringify(trimmed))
  } catch {
    /* private mode / quota: dialogue works in memory */
  }
}

export function loadActiveChatId(chats: Chat[]): string {
  try {
    const saved = localStorage.getItem(ACTIVE_KEY)
    if (saved && chats.some((chat) => chat.id === saved)) return saved
  } catch {
    /* ignore */
  }
  return chats[0]?.id ?? ''
}

export function saveActiveChatId(id: string): void {
  try {
    localStorage.setItem(ACTIVE_KEY, id)
  } catch {
    /* ignore */
  }
}
