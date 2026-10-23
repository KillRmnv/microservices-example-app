'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { useAuth } from '@/lib/auth'

export default function Page() {
  const auth = useAuth()
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Пароли не совпадают')
      return
    }
    setBusy(true)
    try {
      await auth.register(email.trim(), password, username.trim())
      router.push('/profile')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось зарегистрироваться')
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
        <h1>Подписка для новых читателей</h1>
        <p className="auth-note">Создайте личный кабинет, чтобы хранить избранные события, покупать билеты и допланировать досуг.</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            Имя читателя
            <input required autoComplete="name" value={username} onChange={(e) => setUsername(e.target.value)} data-testid="register-name" />
          </label>
          <label>
            Электронная почта
            <input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="register-email" />
          </label>
          <label>
            Пароль
            <input required type="password" autoComplete="new-password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} data-testid="register-password" />
          </label>
          <label>
            Повтор пароля
            <input required type="password" autoComplete="new-password" minLength={6} value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="register-confirm" />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <button className="apply-button" disabled={busy} data-testid="register-submit">{busy ? 'Создаём…' : 'Зарегистрироваться'}</button>
        </form>
        <p className="auth-switch">Уже есть подписка? <Link href="/login">Войти в кабинет</Link></p>
        <Link href="/forgot-password" className="back-link">Забыли пароль?</Link>
      </div>
    </main>
  )
}
