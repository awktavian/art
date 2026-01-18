'use client'

import { useEffect, useState, type ReactNode } from 'react'

interface LiveRegionProps {
  /** The message to announce to screen readers */
  message: string | null
  /** Politeness level for the announcement */
  politeness?: 'polite' | 'assertive'
  /** Clear the message after this many milliseconds */
  clearAfter?: number
  /** ID for the live region */
  id?: string
}

/**
 * LiveRegion - Announce dynamic content changes to screen readers
 *
 * Use 'polite' for non-urgent updates (default) - waits for user to finish current task
 * Use 'assertive' for critical updates - interrupts current task
 */
export function LiveRegion({
  message,
  politeness = 'polite',
  clearAfter = 5000,
  id = 'live-region',
}: LiveRegionProps) {
  const [announcement, setAnnouncement] = useState<string | null>(null)

  useEffect(() => {
    if (message) {
      setAnnouncement(message)

      if (clearAfter > 0) {
        const timer = setTimeout(() => {
          setAnnouncement(null)
        }, clearAfter)

        return () => clearTimeout(timer)
      }
    }
  }, [message, clearAfter])

  return (
    <div
      id={id}
      role="status"
      aria-live={politeness}
      aria-atomic="true"
      className="sr-only"
    >
      {announcement}
    </div>
  )
}

interface StatusAnnouncerProps {
  /** Children to render */
  children: ReactNode
}

/**
 * StatusAnnouncer - Wrapper that provides global status announcements
 *
 * Place at the root of your app to provide a global announcement system.
 */
export function StatusAnnouncer({ children }: StatusAnnouncerProps) {
  return (
    <>
      {children}
      {/* Global live regions for different urgency levels */}
      <div className="sr-only">
        <div
          id="status-announcer-polite"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        />
        <div
          id="status-announcer-assertive"
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
        />
      </div>
    </>
  )
}

/**
 * Announce a message to screen readers
 *
 * @param message The message to announce
 * @param politeness 'polite' for non-urgent, 'assertive' for critical
 */
export function announce(message: string, politeness: 'polite' | 'assertive' = 'polite') {
  const regionId = politeness === 'assertive'
    ? 'status-announcer-assertive'
    : 'status-announcer-polite'

  const region = document.getElementById(regionId)
  if (region) {
    // Clear first to ensure re-announcement of same message
    region.textContent = ''

    // Small delay to ensure screen reader picks up the change
    requestAnimationFrame(() => {
      region.textContent = message
    })
  }
}
