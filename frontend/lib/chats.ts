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
  plan?: { time: string; title: string; detail: string; source: string; kind?: 'event' | 'venue'; detail_id?: string; event_id?: string; bookable?: boolean }[]
  holdId?: string
  error?: boolean
}

export interface Chat {
  id: string
  number: number
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
  contract: StateContract | null
}

const CHATS_KEY = 'dosugChats.v1'
const ACTIVE_KEY = 'dosugActiveChat'
const SEQUENCE_KEY = 'dosugChatSequence'
const LEGACY_CONTRACT_KEY = 'dosugDialogue'
const MAX_CHATS = 20
const MAX_MESSAGES = 200
const NEW_TITLE = 'Новый чат'

export const WELCOME =
  'Добрый вечер. Что ищем сегодня — событие, место или готовый план прогулки?'

export function welcomeMessage(): ChatMessage {
  return { id: 1, kind: 'assistant', text: WELCOME }
}

export function createChat(contract: StateContract | null = null,
                           number = 1): Chat {
  const now = Date.now()
  return {
    id: `chat_${now}_${Math.floor(Math.random() * 10000)}`,
    number,
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
    number: typeof raw.number === 'number' && raw.number > 0
      ? raw.number : 0,
    title: typeof raw.title === 'string' ? raw.title : NEW_TITLE,
    createdAt: typeof raw.createdAt === 'number' ? raw.createdAt : Date.now(),
    updatedAt: typeof raw.updatedAt === 'number' ? raw.updatedAt : Date.now(),
    messages: messages.length ? messages : [welcomeMessage()],
    contract: asContract(raw.contract),
  }
}

function readSequence(): number {
  try {
    const value = Number(localStorage.getItem(SEQUENCE_KEY) ?? 0)
    return Number.isFinite(value) && value > 0 ? value : 0
  } catch {
    return 0
  }
}

function writeSequence(value: number): void {
  try {
    localStorage.setItem(SEQUENCE_KEY, String(value))
  } catch {
    /* ignore */
  }
}

/** Give every chat a permanent number; older chats are numbered oldest-first. */
function normalizeNumbers(list: Chat[]): Chat[] {
  const result = [...list]
  const used = new Set<number>()
  let max = readSequence()
  for (const chat of result) {
    if (chat.number > 0) {
      used.add(chat.number)
      max = Math.max(max, chat.number)
    }
  }
  // The list is newest-first, so walk it backwards: the oldest chat gets 1.
  for (let index = result.length - 1; index >= 0; index -= 1) {
    if (result[index].number > 0) continue
    let candidate = max + 1
    while (used.has(candidate)) candidate += 1
    used.add(candidate)
    max = candidate
    result[index] = { ...result[index], number: candidate }
  }
  writeSequence(max)
  return result
}

/** Next permanent chat number: never reused after deletion. */
export function nextChatNumber(chats: Chat[]): number {
  let max = readSequence()
  for (const chat of chats) max = Math.max(max, chat.number || 0)
  const next = max + 1
  writeSequence(next)
  return next
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
    if (list.length) return normalizeNumbers(list).slice(0, MAX_CHATS)
    // One-time migration: keep the old single dialogue as the first chat.
    const legacy = readLegacyContract()
    return normalizeNumbers([createChat(legacy)])
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
    const max = trimmed.reduce((acc, chat) => Math.max(acc, chat.number || 0), readSequence())
    writeSequence(max)
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
