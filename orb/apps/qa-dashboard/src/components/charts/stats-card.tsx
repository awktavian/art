'use client'

import { cn, getColonyHex } from '@/lib/utils'
import type { ColonyColor } from '@/types'
import { Card } from '@/components/ui'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface StatsCardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  color?: ColonyColor
  icon?: React.ReactNode
  className?: string
}

export function StatsCard({
  title,
  value,
  change,
  changeLabel,
  color = 'crystal',
  icon,
  className,
}: StatsCardProps) {
  const trendDirection = change ? (change > 0 ? 'up' : change < 0 ? 'down' : 'stable') : 'stable'
  const trendColor =
    trendDirection === 'up' ? 'grove' : trendDirection === 'down' ? 'spark' : 'crystal'

  const TrendIcon =
    trendDirection === 'up'
      ? TrendingUp
      : trendDirection === 'down'
        ? TrendingDown
        : Minus

  return (
    <Card
      variant="colony"
      colonyColor={color}
      className={cn('relative overflow-hidden', className)}
      asMotion
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-white/60 mb-1">{title}</p>
          <motion.p
            className="text-3xl font-bold tabular-nums"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: TIMING.normal / 1000, delay: TIMING.micro / 1000 }}
            style={{ color: getColonyHex(color) }}
          >
            {value}
          </motion.p>
        </div>
        {icon && (
          <div
            className="p-2 rounded-lg bg-white/5"
            style={{ color: getColonyHex(color) }}
          >
            {icon}
          </div>
        )}
      </div>

      {change !== undefined && (
        <motion.div
          className="flex items-center gap-1 mt-3 text-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: TIMING.fast / 1000, delay: TIMING.fast / 1000 }}
        >
          <TrendIcon
            className="w-4 h-4"
            style={{ color: getColonyHex(trendColor) }}
          />
          <span style={{ color: getColonyHex(trendColor) }}>
            {change > 0 ? '+' : ''}
            {change}%
          </span>
          {changeLabel && <span className="text-white/40">{changeLabel}</span>}
        </motion.div>
      )}

      {/* Decorative glow */}
      <div
        className="absolute -top-12 -right-12 w-24 h-24 rounded-full opacity-20 blur-2xl"
        style={{ backgroundColor: getColonyHex(color) }}
      />
    </Card>
  )
}

// Compact stats row for inline display
export function StatRow({
  label,
  value,
  color,
  className,
}: {
  label: string
  value: string | number
  color?: ColonyColor
  className?: string
}) {
  return (
    <div className={cn('flex items-center justify-between py-2', className)}>
      <span className="text-sm text-white/60">{label}</span>
      <span
        className="text-sm font-semibold tabular-nums"
        style={color ? { color: getColonyHex(color) } : undefined}
      >
        {value}
      </span>
    </div>
  )
}

// Stats grid for multiple metrics
export function StatsGrid({
  stats,
  columns = 4,
  className,
}: {
  stats: StatsCardProps[]
  columns?: 2 | 3 | 4
  className?: string
}) {
  const gridCols = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  }

  return (
    <div className={cn('grid gap-4', gridCols[columns], className)}>
      {stats.map((stat, index) => (
        <StatsCard key={index} {...stat} />
      ))}
    </div>
  )
}
