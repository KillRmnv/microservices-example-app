'use client'

import { useEffect, useRef, useState } from 'react'
import { MapPin } from 'lucide-react'
import { twoGisLink } from '@/lib/catalog'

declare global {
  interface Window {
    mapgl?: {
      Map: new (container: HTMLElement, options: Record<string, unknown>) => { destroy: () => void }
      Marker: new (map: unknown, options: Record<string, unknown>) => unknown
    }
  }
}

const MAP_KEY = process.env.NEXT_PUBLIC_2GIS_MAP_KEY
const MAP_SCRIPT = 'https://mapgl.2gis.com/api/js/v1'

let mapScriptPromise: Promise<void> | null = null

function loadMapScript(): Promise<void> {
  if (window.mapgl) return Promise.resolve()
  if (!mapScriptPromise) {
    mapScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = MAP_SCRIPT
      script.async = true
      script.onload = () => resolve()
      script.onerror = () => reject(new Error('2GIS map script failed'))
      document.head.appendChild(script)
    })
  }
  return mapScriptPromise
}

interface MapMarker {
  latitude: number
  longitude: number
  label: string
}

interface MapViewProps {
  latitude?: number
  longitude?: number
  markers?: MapMarker[]
  label: string
  address?: string | null
}

export function MapView({ latitude, longitude, markers, label, address }: MapViewProps) {
  const container = useRef<HTMLDivElement | null>(null)
  const [failed, setFailed] = useState(false)
  const points = markers?.length
    ? markers
    : latitude != null && longitude != null
      ? [{ latitude, longitude, label }]
      : []
  const center = points[0]
  const link = center ? twoGisLink(center.latitude, center.longitude) : '#'
  const pointsKey = points.map((point) => `${point.latitude},${point.longitude}`).join('|')

  useEffect(() => {
    if (!MAP_KEY || !center) {
      setFailed(true)
      return
    }
    let map: { destroy: () => void } | undefined
    let cancelled = false
    ;(async () => {
      try {
        await loadMapScript()
        if (cancelled || !container.current || !window.mapgl) return
        map = new window.mapgl.Map(container.current, {
          key: MAP_KEY,
          center: [center.longitude, center.latitude],
          zoom: points.length > 1 ? 12 : 16,
        })
        for (const point of points) {
          new window.mapgl.Marker(map, { coordinates: [point.longitude, point.latitude] })
        }
      } catch {
        if (!cancelled) setFailed(true)
      }
    })()
    return () => {
      cancelled = true
      map?.destroy()
    }
  }, [pointsKey, center?.latitude, center?.longitude, points.length])

  if (failed) {
    return (
      <div className="map-skeleton" data-testid="venue-map-placeholder">
        <MapPin size={26} />
        <strong>{label}</strong>
        {address && <p>{address}</p>}
        <p>
          Координаты: {center?.latitude.toFixed(5)}, {center?.longitude.toFixed(5)} ·{' '}
          <a href={link} target="_blank" rel="noreferrer">открыть в 2ГИС</a>
        </p>
      </div>
    )
  }

  return (
    <div className="map-view" data-testid="venue-map">
      <div ref={container} className="map-view-canvas" />
      <div className="map-view-caption">
        <strong>{label}</strong>
        {address && <span>{address}</span>}
      </div>
      <a className="map-view-link" href={link} target="_blank" rel="noreferrer">Открыть в 2ГИС</a>
    </div>
  )
}
