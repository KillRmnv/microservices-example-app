'use client'

import { useState, type ReactNode } from 'react'
import { AssistantFab, ChatPanel } from '@/components/chat-panel'
import { SiteFooter } from '@/components/site-footer'

/** Global page chrome: assistant FAB/panel and the newspaper footer. */
export function SiteChrome({ children }: { children: ReactNode }) {
  const [chatOpen, setChatOpen] = useState(false)
  return (
    <div className="site-shell">
      <div className="site-main">{children}</div>
      <SiteFooter />
      <AssistantFab onOpen={() => setChatOpen(true)} />
      <ChatPanel open={chatOpen} onClose={() => setChatOpen(false)} />
    </div>
  )
}
