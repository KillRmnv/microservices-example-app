'use client'

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export const CITY_OPTIONS = [
  { label: 'МИНСК', value: 'Минск' },
  { label: 'БРЕСТ', value: 'Брест' },
  { label: 'ГРОДНО', value: 'Гродно' },
] as const

export type CityValue = (typeof CITY_OPTIONS)[number]['value']

interface CityContextValue {
  city: CityValue
  cityLabel: string
  setCity: (city: CityValue) => void
}

const CityContext = createContext<CityContextValue>({
  city: 'Минск',
  cityLabel: 'МИНСК',
  setCity: () => {},
})

const STORAGE_KEY = 'dosugCity'

export function CityProvider({ children }: { children: ReactNode }) {
  const [city, setCityState] = useState<CityValue>('Минск')

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as CityValue | null
      if (saved && CITY_OPTIONS.some((option) => option.value === saved)) {
        setCityState(saved)
      }
    } catch {
      /* storage disabled */
    }
  }, [])

  const setCity = (next: CityValue) => {
    setCityState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* storage disabled */
    }
  }

  const cityLabel = CITY_OPTIONS.find((option) => option.value === city)?.label ?? 'МИНСК'
  return <CityContext.Provider value={{ city, cityLabel, setCity }}>{children}</CityContext.Provider>
}

export function useCity(): CityContextValue {
  return useContext(CityContext)
}
