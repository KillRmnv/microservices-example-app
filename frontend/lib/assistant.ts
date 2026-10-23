'use client'

// Assistant backend client. Same-origin calls: /assistant/* is proxied
// to the gateway by nginx (see frontend/nginx.conf).
// NEXT_PUBLIC_ASSISTANT_MOCK=true keeps the old demo scenarios.
import { ApiError } from './api'
import type { StateContract } from './types'

export interface DialogResultCard {
  event_id: string
  title: string
  meta: string
  price: string
}

export interface DialogMessage {
  kind: 'assistant' | 'filters' | 'results' | 'plan' | 'weather'
  text: string
  results?: DialogResultCard[]
  weather?: string
  plan?: Array<{ time: string; title: string; detail: string; source: string }>
}

export interface DialogResponse {
  contract: StateContract
  messages: DialogMessage[]
}

export interface Hold {
  id: string
  session_id: string
  event_id: number
  zone: string
  price: number
  party_size: number
  status: string
}

export function isMockMode(): boolean {
  return process.env.NEXT_PUBLIC_ASSISTANT_MOCK === 'true'
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    const data = await response.json().catch(() => null)
    if (data && typeof (data as { detail?: unknown }).detail === 'string') {
      message = (data as { detail: string }).detail
    } else if (data && typeof (data as { message?: unknown }).message === 'string') {
      message = (data as { message: string }).message
    }
    throw new ApiError(message, response.status)
  }
  return (await response.json()) as T
}

export function sendDialogue(contract: StateContract): Promise<DialogResponse> {
  return postJson<DialogResponse>('/assistant/dialogue/v2', contract)
}

export function createHold(input: {
  session_id: string
  event_id: number
  zone: string
  price: number
  party_size: number
}): Promise<Hold> {
  return postJson<Hold>('/assistant/holds', input)
}

export function confirmHold(holdId: string): Promise<Hold> {
  return postJson<Hold>(`/assistant/holds/${holdId}/confirm`, {})
}

const CONTRACT_KEY = 'dosugDialogue'

export function loadContract(): StateContract | null {
  try {
    const raw = sessionStorage.getItem(CONTRACT_KEY)
    return raw ? (JSON.parse(raw) as StateContract) : null
  } catch {
    return null
  }
}

export function saveContract(contract: StateContract): void {
  try {
    sessionStorage.setItem(CONTRACT_KEY, JSON.stringify(contract))
  } catch {
    /* private mode — dialogue simply won't persist */
  }
}

export function clearContract(): void {
  try {
    sessionStorage.removeItem(CONTRACT_KEY)
  } catch {
    /* ignore */
  }
}
