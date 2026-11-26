// Pure mapping for assistant-call failures shown in the chat.
// No React/network imports, so node tests can exercise it directly.

/** HTTP 429 is a temporary throttle, not an assistant outage. */
export const RATE_LIMIT_MESSAGE = 'Слишком много запросов — подождите немного и повторите.'

interface StatusCarrier {
  status?: unknown
}

/** True for HTTP 429 without depending on the concrete ApiError class. */
export function isRateLimited(error: unknown): boolean {
  return typeof error === 'object' && error !== null
    && (error as StatusCarrier).status === 429
}
