'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/lib/utils'
import { Button, IconButton } from '@/components/ui'
import { ConnectionStatus } from '@/components/connection-status'
import { motion, AnimatePresence } from 'framer-motion'
import { TIMING } from '@/types'
import {
  LayoutDashboard,
  Activity,
  FileText,
  Settings,
  Sun,
  Moon,
  Bell,
  Menu,
  X,
} from 'lucide-react'
import { useTheme } from '@/hooks/use-theme'

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/analysis', label: 'Analysis', icon: Activity },
  { href: '/reports', label: 'Reports', icon: FileText },
]

export function Header() {
  const pathname = usePathname()
  const { theme, toggleTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 w-full bg-void/80 backdrop-blur-md">
      {/* Skip link for accessibility */}
      <a
        href="#main-content"
        className="skip-link"
      >
        Skip to main content
      </a>

      {/* Gold accent line at top - inspired by ~/projects/art/catastrophes.html */}
      <div
        className="h-[2px] bg-gradient-to-r from-transparent via-gold to-transparent opacity-60"
        aria-hidden="true"
      />

      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo and nav */}
        <div className="flex items-center gap-8">
          <Link
            href="/"
            className="group flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-colony-crystal rounded-md px-2 py-1"
          >
            {/* Display typography for brand */}
            <span className="font-display text-2xl font-semibold tracking-wide text-gold group-hover:text-gold-light transition-colors duration-fast">
              Kagami
            </span>
            <span className="text-lg font-light text-white/40 tracking-widest uppercase">
              QA
            </span>
          </Link>

          {/* Desktop navigation */}
          <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
            {navItems.map((item) => {
              const isActive = pathname === item.href ||
                (item.href !== '/' && pathname.startsWith(item.href))
              const Icon = item.icon

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'relative flex items-center gap-2 px-3 py-2 text-sm font-medium rounded-md',
                    'transition-colors duration-fast',
                    'focus-visible:ring-2 focus-visible:ring-colony-crystal focus-visible:ring-offset-2 focus-visible:ring-offset-void',
                    isActive
                      ? 'text-colony-crystal'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                  )}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                  {isActive && (
                    <motion.div
                      layoutId="nav-indicator"
                      className="absolute bottom-0 left-0 right-0 h-0.5 bg-colony-crystal"
                      transition={{ duration: TIMING.fast / 1000 }}
                    />
                  )}
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Connection status - full on desktop, compact on tablet, hidden on mobile */}
          <ConnectionStatus
            variant="full"
            className="hidden lg:flex"
            showReconnectProgress={true}
          />
          <ConnectionStatus
            variant="compact"
            className="hidden sm:flex lg:hidden"
          />

          {/* Notifications */}
          <div className="relative">
            <IconButton
              icon={<Bell className="w-5 h-5" />}
              label="Notifications"
            />
            {/* Notification dot */}
            <span className="absolute top-1 right-1 w-2 h-2 bg-colony-spark rounded-full pointer-events-none" />
          </div>

          {/* Theme toggle */}
          <IconButton
            icon={theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            onClick={toggleTheme}
          />

          {/* Settings */}
          <IconButton
            icon={<Settings className="w-5 h-5" />}
            label="Settings"
            className="hidden sm:flex"
          />

          {/* Mobile menu button */}
          <IconButton
            icon={mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden"
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-menu"
          />
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.nav
            id="mobile-menu"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: TIMING.normal / 1000 }}
            className="md:hidden border-t border-white/10 bg-void overflow-hidden"
            aria-label="Mobile navigation"
          >
            <div className="container mx-auto px-4 py-4 space-y-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href ||
                  (item.href !== '/' && pathname.startsWith(item.href))
                const Icon = item.icon

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      'flex items-center gap-3 px-3 py-2.5 rounded-md',
                      'transition-colors duration-fast',
                      isActive
                        ? 'bg-colony-crystal/10 text-colony-crystal'
                        : 'text-white/60 hover:text-white hover:bg-white/5'
                    )}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <Icon className="w-5 h-5" />
                    {item.label}
                  </Link>
                )
              })}

              <div className="pt-4 border-t border-white/10">
                <Link
                  href="/settings"
                  onClick={() => setMobileMenuOpen(false)}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-md text-white/60 hover:text-white hover:bg-white/5"
                >
                  <Settings className="w-5 h-5" />
                  Settings
                </Link>
              </div>
            </div>
          </motion.nav>
        )}
      </AnimatePresence>

      {/* Bottom border with subtle gold shimmer */}
      <div
        className="h-px bg-gradient-to-r from-white/5 via-gold/20 to-white/5"
        aria-hidden="true"
      />
    </header>
  )
}
