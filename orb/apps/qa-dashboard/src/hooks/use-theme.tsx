'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { ThemeMode, ThemeContext as ThemeContextType } from '@/types'

const ThemeContext = createContext<ThemeContextType | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>('dark')
  const [resolvedMode, setResolvedMode] = useState<'dark' | 'light'>('dark')

  // Initialize from localStorage and system preference
  useEffect(() => {
    const stored = localStorage.getItem('kagami-qa-theme') as ThemeMode | null
    if (stored) {
      setMode(stored)
    } else {
      setMode('system')
    }
  }, [])

  // Resolve system preference
  useEffect(() => {
    const resolveTheme = () => {
      if (mode === 'system') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
        setResolvedMode(prefersDark ? 'dark' : 'light')
      } else {
        setResolvedMode(mode as 'dark' | 'light')
      }
    }

    resolveTheme()

    // Listen for system preference changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      if (mode === 'system') {
        setResolvedMode(mediaQuery.matches ? 'dark' : 'light')
      }
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [mode])

  // Apply theme class to document
  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('dark', 'light')
    root.classList.add(resolvedMode)

    // Update meta theme-color for browser chrome
    const metaTheme = document.querySelector('meta[name="theme-color"]')
    if (metaTheme) {
      metaTheme.setAttribute(
        'content',
        resolvedMode === 'dark' ? '#0A0A0F' : '#FAFAFC'
      )
    }
  }, [resolvedMode])

  // Save to localStorage when mode changes
  useEffect(() => {
    localStorage.setItem('kagami-qa-theme', mode)
  }, [mode])

  return (
    <ThemeContext.Provider value={{ mode, resolvedMode, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)

  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }

  const { mode, resolvedMode, setMode } = context

  const toggleTheme = () => {
    setMode(resolvedMode === 'dark' ? 'light' : 'dark')
  }

  return {
    theme: resolvedMode,
    mode,
    setMode,
    toggleTheme,
    isDark: resolvedMode === 'dark',
  }
}
