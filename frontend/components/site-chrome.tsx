'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { AssistantFab, ChatPanel } from '@/components/chat-panel'
import { ChatErrorBoundary } from '@/components/chat-error-boundary'
import { SiteFooter } from '@/components/site-footer'

function useStaleChunkReload() {
  useEffect(() => {
    if (typeof window === 'undefined') return
    let reloading = false
    const reloadOnce = (reason: string) => {
      if (reloading) return
      const last = Number(sessionStorage.getItem('dosugChunkReload') || 0)
      if (Date.now() - last < 10000) return
      reloading = true
      sessionStorage.setItem('dosugChunkReload', String(Date.now()))
      console.warn('stale frontend asset, reloading', reason)
      window.location.reload()
    }
    const onError = (event: Event) => {
      const target = event.target as HTMLElement | null
      if (target?.tagName === 'SCRIPT' || target?.tagName === 'LINK') {
        reloadOnce('asset load error')
      }
    }
    const onRejection = (event: PromiseRejectionEvent) => {
      const message = String(event.reason?.message || event.reason || '')
      if (/ChunkLoadError|Loading chunk|dynamically imported module/i.test(message)) {
        reloadOnce(message)
      }
    }
    window.addEventListener('error', onError, true)
    window.addEventListener('unhandledrejection', onRejection)
    return () => {
      window.removeEventListener('error', onError, true)
      window.removeEventListener('unhandledrejection', onRejection)
    }
  }, [])
}

/** Global page chrome: assistant FAB/panel and the newspaper footer. */
export function SiteChrome({ children }: { children: ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  useStaleChunkReload()
  return (
    <div className="site-shell">
      <div className="site-main">{children}</div>
      <SiteFooter />
      <AssistantFab onOpen={() => setChatOpen(true)} />
      <ChatErrorBoundary>
        <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
      </ChatErrorBoundary>
    </div>
  )
}
