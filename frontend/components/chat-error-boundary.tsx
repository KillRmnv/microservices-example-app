'use client'

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/** Keep a render error inside the assistant instead of a blank panel. */
export class ChatErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('chat panel crashed', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="chat-overlay" data-testid="chat-error-boundary">
          <section className="chat-panel">
            <header>
              <div>
                <div className="kicker">СПРАВКА РЕДАКЦИИ · ОШИБКА</div>
                <h2>Панель не открылась</h2>
              </div>
            </header>
            <div className="chat-body">
              <div className="assistant-message">
                <span className="message-number">СБОЙ ИНТЕРФЕЙСА</span>
                <p>Обновите страницу — после обновления чат откроется с сохранённой историей.</p>
              </div>
            </div>
            <button className="apply-button" onClick={() => window.location.reload()}>
              Обновить страницу
            </button>
          </section>
        </div>
      )
    }
    return this.props.children
  }
}
