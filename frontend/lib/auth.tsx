'use client'

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, tokenStore } from './api'
import type { User } from './types'

interface AuthContextValue {
  ready: boolean
  user: User | null
  refresh: () => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, username: string) => Promise<void>
  logout: () => void
  isManager: boolean
  isAdmin: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [user, setUser] = useState<User | null>(null)

  const refresh = useCallback(async () => {
    if (!tokenStore.token || !tokenStore.email) {
      setUser(null)
      setReady(true)
      return
    }
    try {
      const found = await api.getCurrentUser(tokenStore.email)
      setUser(found)
    } catch {
      tokenStore.clear()
      setUser(null)
    }
    setReady(true)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.login(email, password)
      tokenStore.setSession(response, email)
      const found = await api.getCurrentUser(email)
      setUser(found)
    },
    [],
  )

  const register = useCallback(async (email: string, password: string, username: string) => {
    await api.register(email, password, username, 'CUSTOMER')
    await login(email, password)
  }, [login])

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const role = (user?.role ?? tokenStore.role ?? '').toString().toUpperCase()

  return (
    <AuthContext.Provider
      value={{
        ready,
        user,
        refresh,
        login,
        register,
        logout,
        isManager: role === 'EVENT_MANAGER' || role === 'ADMIN',
        isAdmin: role === 'ADMIN',
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
