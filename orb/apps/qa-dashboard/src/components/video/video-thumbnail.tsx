'use client'

import { cn, formatDuration } from '@/lib/utils'
import type { TestStatus } from '@/types'
import { StatusBadge } from '@/components/ui'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import { Play } from 'lucide-react'
import Image from 'next/image'

interface VideoThumbnailProps {
  src: string
  alt: string
  duration: number
  status?: TestStatus
  onClick?: () => void
  className?: string
  priority?: boolean
}

export function VideoThumbnail({
  src,
  alt,
  duration,
  status,
  onClick,
  className,
  priority = false,
}: VideoThumbnailProps) {
  return (
    <motion.button
      className={cn(
        'relative w-full overflow-hidden rounded-md bg-void-lighter',
        'group cursor-pointer',
        'focus-visible:ring-2 focus-visible:ring-colony-crystal focus-visible:ring-offset-2 focus-visible:ring-offset-void',
        className
      )}
      style={{ aspectRatio: '16 / 9' }}
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ duration: TIMING.micro / 1000 }}
      aria-label={`Play video: ${alt}`}
    >
      {/* Thumbnail image */}
      <div className="absolute inset-0">
        {src ? (
          <Image
            src={src}
            alt={alt}
            fill
            className="object-cover transition-transform duration-medium group-hover:scale-105"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
            priority={priority}
          />
        ) : (
          <div className="w-full h-full bg-void-lighter flex items-center justify-center">
            <Play className="w-12 h-12 text-white/20" />
          </div>
        )}
      </div>

      {/* Hover overlay */}
      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors duration-fast flex items-center justify-center">
        <motion.div
          className="w-12 h-12 rounded-full bg-void/80 border-2 border-colony-crystal flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-fast"
          whileHover={{ scale: 1.1 }}
        >
          <Play className="w-5 h-5 text-colony-crystal ml-0.5" fill="currentColor" />
        </motion.div>
      </div>

      {/* Duration badge */}
      <div className="absolute bottom-2 right-2 px-1.5 py-0.5 bg-black/80 rounded text-xs font-medium tabular-nums">
        {formatDuration(duration)}
      </div>

      {/* Status badge */}
      {status && (
        <div className="absolute top-2 left-2">
          <StatusBadge status={status} size="sm" />
        </div>
      )}
    </motion.button>
  )
}

// Skeleton for loading state
export function VideoThumbnailSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'relative w-full overflow-hidden rounded-md bg-void-lighter animate-pulse',
        className
      )}
      style={{ aspectRatio: '16 / 9' }}
    >
      <div className="absolute bottom-2 right-2 w-12 h-5 bg-void rounded" />
      <div className="absolute top-2 left-2 w-16 h-5 bg-void rounded-full" />
    </div>
  )
}
