'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { useAuth } from '@/lib/auth'

export default function Page() {
  const auth = useAuth()
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await auth.login(email.trim(), password)
      const next = new URLSearchParams(window.location.search).get('next')
      router.push(next && next.startsWith('/') ? next : '/profile')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-kicker">ГОРОДСКАЯ ГАЗЕТА О ДОСУГЕ</div>
          <div className="auth-logo">ДОСУГ</div>
        </div>
        <h1>Вход для подписчиков</h1>
        <p className="auth-note">Войдите в личный кабинет, чтобы видеть ваши билеты, избранное и планы.</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            Электронная почта
            <input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" />
          </label>
          <label>
            Пароль
            <input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password" />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button className="apply-button" disabled={busy} data-testid="login-submit">{busy ? 'Проверяем…' : 'Войти'}</button>
        </form>
        <p className="auth-switch">Нет подписки? <Link href="/register">Оформить</Link></p>
        <Link href="/forgot-password" className="back-link">Забыли пароль?</Link>
      </div>
    </main>
  )
}
