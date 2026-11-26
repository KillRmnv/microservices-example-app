'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { FALLBACK_EVENT_IMAGE } from '@/lib/catalog'

interface EventImageProps {
  src?: string | null
  alt: string
  /** Extra class for the wrapper, e.g. `card-image` or `lead-image`. */
  className?: string
  loading?: 'lazy' | 'eager'
  /** Overlays such as captions or badges. */
  children?: ReactNode
}

/**
 * Shows the whole event poster (`contain`) over a blurred copy of the same
 * image, so tall flyers are never cropped by the card frame.
 */
export function EventImage({ src, alt, className, loading = 'lazy', children }: EventImageProps) {
  const initial = src?.trim() || FALLBACK_EVENT_IMAGE
  const [source, setSource] = useState(initial)

  useEffect(() => {
    setSource(initial)
  }, [initial])

  const fallback = () => {
    setSource((current) => (current === FALLBACK_EVENT_IMAGE ? current : FALLBACK_EVENT_IMAGE))
  }

  return (
    <div className={className ? `event-image ${className}` : 'event-image'}>
      <img
        className="event-image-backdrop"
        src={source}
        alt=""
        aria-hidden="true"
        loading={loading}
        onError={fallback}
      />
      <img
        className="event-image-foreground"
        src={source}
        alt={alt}
        loading={loading}
        onError={fallback}
      />
      {children}
    </div>
  )
}
