'use client'

import Link from 'next/link'
import { useState } from 'react'
import { LogOut, MapPin, Search, UserRound, ChevronDown } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { mastheadDate } from '@/lib/format'
import { useTheme } from '@/lib/theme'
import { CITY_OPTIONS, useCity } from '@/lib/city'
import { usePathname } from 'next/navigation'

interface NewspaperHeaderProps {
  returnLink?: { href: string; label: string }
}

export function NewspaperHeader({ returnLink }: NewspaperHeaderProps) {
  const auth = useAuth()
  const { theme, toggle } = useTheme()
  const pathname = usePathname()
  const isActive = (href: string) => (href === '/' ? pathname === '/' : pathname.startsWith(href))
  const [cityOpen, setCityOpen] = useState(false)
  const { cityLabel, setCity } = useCity()

  return (
    <header className="masthead-wrap">
      <div className="topline">
        <span>{mastheadDate()}</span>
        <span>№ 014 · {cityLabel}</span>
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
            <Link href="/login" aria-label="Войти" data-testid="masthead-login"><UserRound size={18} /></Link>
          )}
          <button aria-label="Ночная тема" onClick={toggle} className="theme-toggle" data-testid="theme-toggle">
            {theme === 'dark' ? '☼' : '☾'}
          </button>
        </div>
      </div>
      <nav className="navline" data-testid="newspaper-nav">
        <Link href="/" className={isActive('/') ? 'active' : undefined} data-testid="nav-home">ГЛАВНАЯ</Link>
        <Link href="/events" className={isActive('/events') ? 'active' : undefined} data-testid="nav-events">СОБЫТИЯ</Link>
        <Link href="/places" className={isActive('/places') ? 'active' : undefined} data-testid="nav-places">МЕСТА</Link>
        <Link href="/profile" className={isActive('/profile') ? 'active' : undefined} data-testid="nav-profile">ЛИЧНЫЙ КАБИНЕТ</Link>
        <Link href="/about" className={isActive('/about') ? 'active' : undefined} data-testid="nav-about">О ПРОЕКТЕ</Link>
        {auth.isManager && <Link href="/manager" data-testid="nav-manager">МЕНЕДЖЕР</Link>}
        {auth.isAdmin && <Link href="/admin" data-testid="nav-admin">АДМИНКА</Link>}
        <div className="city-picker">
          <button className="city" onClick={() => setCityOpen(!cityOpen)} aria-expanded={cityOpen} data-testid="city-picker">
            <MapPin size={14} /> {cityLabel} <ChevronDown size={14} />
          </button>
          {cityOpen && (
            <div className="city-menu" data-testid="nav-city-options">
              {CITY_OPTIONS.map((option) => (
                <button key={option.value} onClick={() => { setCity(option.value); setCityOpen(false) }}>{option.label}</button>
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
