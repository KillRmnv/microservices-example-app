'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { LogOut, MapPin, MessageCircle, Search, UserRound, ChevronDown } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { mastheadDate } from '@/lib/format'

interface NewspaperHeaderProps {
  returnLink?: { href: string; label: string }
  onChatOpen?: () => void
  dark?: boolean
  onThemeToggle?: () => void
}

export function NewspaperHeader({ returnLink, onChatOpen, dark, onThemeToggle }: NewspaperHeaderProps) {
  const auth = useAuth()
  const [cityOpen, setCityOpen] = useState(false)
  const [city, setCity] = useState('МИНСК')

  return (
    <header className="masthead-wrap">
      <div className="topline">
        <span>{mastheadDate()}</span>
        <span>№ 014 · {city.length > 0 ? city : 'МИНСК'}</span>
        <span className="topline-right">Свежий выпуск <span className="red-dot" /></span>
      </div>
      <div className="masthead">
        {returnLink ? (
          <Link href={returnLink.href} className="edition" data-testid="masthead-return-link">
            ВЕРНУТЬСЯ<br /><strong>НА ГЛАВНУЮ</strong>
          </Link>
        ) : (
          <div className="edition-holder" />
        )}
        <div className="brand">
          <div className="brand-kicker">ГОРОДСКАЯ ГАЗЕТА О ДОСУГЕ</div>
          <h1><Link href="/">ДОСУГ</Link></h1>
          <div className="brand-sub">СОБЫТИЯ · МЕСТА · ВПЕЧАТЛЕНИЯ</div>
        </div>
        <div className="mast-actions">
          <Link href="/events" aria-label="Поиск" data-testid="masthead-search"><Search size={18} /></Link>
          {auth.user ? (
            <>
              <Link href="/profile" aria-label="Личный кабинет" data-testid="masthead-profile"><UserRound size={18} /></Link>
              <button aria-label="Выйти" onClick={() => auth.logout()} data-testid="masthead-logout"><LogOut size={17} /></button>
            </>
          ) : (
            <>
              <Link href="/login" aria-label="Войти" data-testid="masthead-login"><UserRound size={18} /></Link>
              {onChatOpen && <button aria-label="Ассистент" onClick={onChatOpen} data-testid="masthead-assistant"><MessageCircle size={18} /></button>}
            </>
          )}
          {onThemeToggle && (
            <button aria-label="Ночная тема" onClick={onThemeToggle} className="theme-toggle" data-testid="theme-toggle">
              {dark ? '☼' : '☾'}
            </button>
          )}
        </div>
      </div>
      <nav className="navline" data-testid="newspaper-nav">
        <Link href="/" className="active" data-testid="nav-home">ГЛАВНАЯ</Link>
        <Link href="/events" data-testid="nav-events">СОБЫТИЯ</Link>
        <Link href="/places" data-testid="nav-places">МЕСТА</Link>
        <Link href="/profile" data-testid="nav-profile">ЛИЧНЫЙ КАБИНЕТ</Link>
        <Link href="/about" data-testid="nav-about">О ПРОЕКТЕ</Link>
        {auth.isManager && <Link href="/manager" data-testid="nav-manager">МЕНЕДЖЕР</Link>}
        {auth.isAdmin && <Link href="/admin" data-testid="nav-admin">АДМИНКА</Link>}
        <div className="city-picker">
          <button className="city" onClick={() => setCityOpen(!cityOpen)} aria-expanded={cityOpen} data-testid="city-picker">
            <MapPin size={14} /> {city} <ChevronDown size={14} />
          </button>
          {cityOpen && (
            <div className="city-menu">
              {['МИНСК', 'БРЕСТ', 'ГРОДНО'].map((option) => (
                <button key={option} onClick={() => { setCity(option); setCityOpen(false) }}>{option}</button>
              ))}
            </div>
          )}
        </div>
      </nav>
    </header>
  )
}

export function RuleTitle({ children }: { children: React.ReactNode }) {
  return <div className="rule-title"><span>{children}</span></div>
}
