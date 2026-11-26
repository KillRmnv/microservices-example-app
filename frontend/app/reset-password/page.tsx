'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'
import { api } from '@/lib/api'

export default function Page() {
  const router = useRouter()
  const [token, setToken] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setNotice('')
    if (password !== confirm) {
      setError('Пароли не совпадают')
      return
    }
    setBusy(true)
    try {
      const valid = await api.validateResetToken(token.trim())
      if (!valid) {
        setError('Ссылка недействительна или срок её истёк')
        setBusy(false)
        return
      }
      await api.resetPassword(token.trim(), password)
      router.push('/login')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сбросить пароль')
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
        <h1>Новый пароль</h1>
        <p className="auth-note">Вставьте код из письма и задайте новый пароль.</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            Код из письма
            <input required value={token} onChange={(e) => setToken(e.target.value)} data-testid="reset-token" />
          </label>
          <label>
            Новый пароль
            <input required type="password" autoComplete="new-password" minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} data-testid="reset-password" />
          </label>
          <label>
            Повтор пароля
            <input required type="password" autoComplete="new-password" minLength={6} value={confirm} onChange={(e) => setConfirm(e.target.value)} data-testid="reset-confirm" />
          </label>
          {notice && <p className="auth-switch">{notice}</p>}
          {error && <p className="auth-error">{error}</p>}
          <button className="apply-button" disabled={busy} data-testid="reset-submit">{busy ? 'Сохраняем…' : 'Сохранить пароль'}</button>
        </form>
        <p className="auth-switch"><Link href="/login">Вернуться ко входу</Link></p>
      </div>
    </main>
  )
}
