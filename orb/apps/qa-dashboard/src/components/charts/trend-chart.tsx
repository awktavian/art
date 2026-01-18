'use client'

import { useMemo } from 'react'
import { cn, getColonyHex } from '@/lib/utils'
import type { ColonyColor } from '@/types'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Area,
  AreaChart,
} from 'recharts'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'

interface DataPoint {
  date: string
  [key: string]: number | string
}

interface TrendChartProps {
  data: DataPoint[]
  dataKey: string
  xAxisKey?: string
  title?: string
  color?: ColonyColor
  showArea?: boolean
  showGrid?: boolean
  height?: number
  className?: string
}

interface MultiLineChartProps {
  data: DataPoint[]
  lines: Array<{
    dataKey: string
    name: string
    color: ColonyColor
  }>
  xAxisKey?: string
  title?: string
  showGrid?: boolean
  height?: number
  className?: string
}

// Custom tooltip component
function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}) {
  if (!active || !payload?.length) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-void-light border border-white/10 rounded-md px-3 py-2 shadow-lg"
    >
      <p className="text-xs text-white/60 mb-1">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}
        </p>
      ))}
    </motion.div>
  )
}

export function TrendChart({
  data,
  dataKey,
  xAxisKey = 'date',
  title,
  color = 'crystal',
  showArea = true,
  showGrid = true,
  height = 200,
  className,
}: TrendChartProps) {
  const colorHex = getColonyHex(color)

  const ChartComponent = showArea ? AreaChart : LineChart

  return (
    <div className={cn('w-full', className)}>
      {title && (
        <h4 className="text-sm font-medium text-white/60 mb-3">{title}</h4>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ChartComponent data={data} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255, 255, 255, 0.05)"
              vertical={false}
            />
          )}
          <XAxis
            dataKey={xAxisKey}
            tick={{ fill: 'rgba(255, 255, 255, 0.4)', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
          />
          <YAxis
            tick={{ fill: 'rgba(255, 255, 255, 0.4)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          {showArea ? (
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={colorHex}
              strokeWidth={2}
              fill={`url(#gradient-${color})`}
              animationDuration={TIMING.slow}
            />
          ) : (
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={colorHex}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: colorHex }}
              animationDuration={TIMING.slow}
            />
          )}
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colorHex} stopOpacity={0.3} />
              <stop offset="100%" stopColor={colorHex} stopOpacity={0} />
            </linearGradient>
          </defs>
        </ChartComponent>
      </ResponsiveContainer>
    </div>
  )
}

export function MultiLineChart({
  data,
  lines,
  xAxisKey = 'date',
  title,
  showGrid = true,
  height = 200,
  className,
}: MultiLineChartProps) {
  return (
    <div className={cn('w-full', className)}>
      {title && (
        <h4 className="text-sm font-medium text-white/60 mb-3">{title}</h4>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          {showGrid && (
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255, 255, 255, 0.05)"
              vertical={false}
            />
          )}
          <XAxis
            dataKey={xAxisKey}
            tick={{ fill: 'rgba(255, 255, 255, 0.4)', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
          />
          <YAxis
            tick={{ fill: 'rgba(255, 255, 255, 0.4)', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{
              fontSize: '12px',
              color: 'rgba(255, 255, 255, 0.6)',
            }}
          />
          {lines.map((line) => (
            <Line
              key={line.dataKey}
              type="monotone"
              dataKey={line.dataKey}
              name={line.name}
              stroke={getColonyHex(line.color)}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: getColonyHex(line.color) }}
              animationDuration={TIMING.slow}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// Sparkline component for compact trend display
export function Sparkline({
  data,
  dataKey,
  color = 'crystal',
  width = 100,
  height = 32,
  className,
}: {
  data: DataPoint[]
  dataKey: string
  color?: ColonyColor
  width?: number
  height?: number
  className?: string
}) {
  const colorHex = getColonyHex(color)

  return (
    <div className={cn('inline-block', className)} style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={colorHex}
            strokeWidth={1.5}
            fill={colorHex}
            fillOpacity={0.2}
            animationDuration={TIMING.medium}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
