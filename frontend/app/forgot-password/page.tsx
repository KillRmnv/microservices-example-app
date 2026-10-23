'use client'

import Link from 'next/link'
import { useState, type FormEvent } from 'react'
import { api } from '@/lib/api'

export default function Page() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.forgetPassword(email.trim())
      setDone(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось отправить заявку')
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
        <h1>Восстановление подписки</h1>
        {done ? (
          <>
            <p className="auth-note">Заявка принята. Ссылку для сброса пароля отправили на вашу почту.</p>
            <Link href="/reset-password" className="apply-button centered" data-testid="go-to-reset">Перейти к сбросу пароля</Link>
          </>
        ) : (
          <form onSubmit={submit} className="auth-form">
            <label>
              Электронная почта
              <input required type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="forgot-email" />
            </label>
            {error && <p className="auth-error">{error}</p>}
            <button className="apply-button" disabled={busy} data-testid="forgot-submit">{busy ? 'Отправляем…' : 'Отправить ссылку'}</button>
          </form>
        )}
        <p className="auth-switch">Помните пароль? <Link href="/login">Войти</Link></p>
      </div>
    </main>
  )
}
