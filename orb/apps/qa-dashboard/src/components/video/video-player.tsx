'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { cn, formatTimestamp, getColonyHex } from '@/lib/utils'
import type { Checkpoint, VideoPlayerState } from '@/types'
import { TIMING } from '@/types'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  SkipBack,
  SkipForward,
  Settings,
} from 'lucide-react'

interface VideoPlayerProps {
  src: string
  poster?: string
  checkpoints?: Checkpoint[]
  onCheckpointClick?: (checkpoint: Checkpoint) => void
  onTimeUpdate?: (time: number) => void
  className?: string
  autoPlay?: boolean
}

export function VideoPlayer({
  src,
  poster,
  checkpoints = [],
  onCheckpointClick,
  onTimeUpdate,
  className,
  autoPlay = false,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const progressRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<VideoPlayerState>({
    currentTime: 0,
    duration: 0,
    isPlaying: false,
    volume: 1,
    isMuted: false,
    playbackRate: 1,
    activeCheckpoint: null,
  })
  const [showControls, setShowControls] = useState(true)
  const [hoveredCheckpoint, setHoveredCheckpoint] = useState<Checkpoint | null>(null)
  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Handle video metadata loaded
  const handleLoadedMetadata = useCallback(() => {
    if (videoRef.current) {
      setState((s) => ({ ...s, duration: videoRef.current!.duration }))
    }
  }, [])

  // Handle time update
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime
      setState((s) => ({ ...s, currentTime }))
      onTimeUpdate?.(currentTime)

      // Check for active checkpoint
      const activeCheckpoint = checkpoints.find(
        (cp) =>
          currentTime >= cp.timestamp - 0.5 && currentTime <= cp.timestamp + 0.5
      )
      if (activeCheckpoint && activeCheckpoint.id !== state.activeCheckpoint?.id) {
        setState((s) => ({ ...s, activeCheckpoint }))
      }
    }
  }, [checkpoints, onTimeUpdate, state.activeCheckpoint?.id])

  // Toggle play/pause
  const togglePlay = useCallback(() => {
    if (videoRef.current) {
      if (state.isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setState((s) => ({ ...s, isPlaying: !s.isPlaying }))
    }
  }, [state.isPlaying])

  // Toggle mute
  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.muted = !state.isMuted
      setState((s) => ({ ...s, isMuted: !s.isMuted }))
    }
  }, [state.isMuted])

  // Seek to time
  const seekTo = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time
      setState((s) => ({ ...s, currentTime: time }))
    }
  }, [])

  // Handle progress bar click
  const handleProgressClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (progressRef.current && videoRef.current) {
        const rect = progressRef.current.getBoundingClientRect()
        const percent = (e.clientX - rect.left) / rect.width
        const time = percent * state.duration
        seekTo(time)
      }
    },
    [state.duration, seekTo]
  )

  // Skip forward/backward
  const skip = useCallback(
    (seconds: number) => {
      if (videoRef.current) {
        const newTime = Math.max(
          0,
          Math.min(state.duration, videoRef.current.currentTime + seconds)
        )
        seekTo(newTime)
      }
    },
    [state.duration, seekTo]
  )

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    if (containerRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen()
      } else {
        containerRef.current.requestFullscreen()
      }
    }
  }, [])

  // Handle checkpoint click
  const handleCheckpointClick = useCallback(
    (checkpoint: Checkpoint) => {
      seekTo(checkpoint.timestamp)
      onCheckpointClick?.(checkpoint)
    },
    [seekTo, onCheckpointClick]
  )

  // Handle mouse movement for controls visibility
  const handleMouseMove = useCallback(() => {
    setShowControls(true)
    if (controlsTimeoutRef.current) {
      clearTimeout(controlsTimeoutRef.current)
    }
    controlsTimeoutRef.current = setTimeout(() => {
      if (state.isPlaying) {
        setShowControls(false)
      }
    }, 3000)
  }, [state.isPlaying])

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      switch (e.key.toLowerCase()) {
        case ' ':
        case 'k':
          e.preventDefault()
          togglePlay()
          break
        case 'arrowleft':
        case 'j':
          e.preventDefault()
          skip(-10)
          break
        case 'arrowright':
        case 'l':
          e.preventDefault()
          skip(10)
          break
        case 'm':
          e.preventDefault()
          toggleMute()
          break
        case 'f':
          e.preventDefault()
          toggleFullscreen()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [togglePlay, skip, toggleMute, toggleFullscreen])

  // Progress percentage
  const progress = state.duration > 0 ? (state.currentTime / state.duration) * 100 : 0

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative w-full bg-black rounded-lg overflow-hidden group',
        'focus-visible:ring-2 focus-visible:ring-colony-crystal focus-visible:ring-offset-2',
        className
      )}
      style={{ aspectRatio: '16 / 9' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => state.isPlaying && setShowControls(false)}
      tabIndex={0}
      role="application"
      aria-label="Video player"
    >
      {/* Video element */}
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        className="w-full h-full object-contain"
        onLoadedMetadata={handleLoadedMetadata}
        onTimeUpdate={handleTimeUpdate}
        onPlay={() => setState((s) => ({ ...s, isPlaying: true }))}
        onPause={() => setState((s) => ({ ...s, isPlaying: false }))}
        onEnded={() => setState((s) => ({ ...s, isPlaying: false }))}
        autoPlay={autoPlay}
        playsInline
      />

      {/* Big play button overlay */}
      <AnimatePresence>
        {!state.isPlaying && (
          <motion.button
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: TIMING.fast / 1000 }}
            className={cn(
              'absolute inset-0 flex items-center justify-center',
              'bg-black/30 cursor-pointer'
            )}
            onClick={togglePlay}
            aria-label="Play video"
          >
            <div className="w-20 h-20 rounded-full bg-void/80 border-2 border-colony-crystal flex items-center justify-center transition-transform duration-fast hover:scale-110">
              <Play className="w-8 h-8 text-colony-crystal ml-1" fill="currentColor" />
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Controls overlay */}
      <AnimatePresence>
        {showControls && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: TIMING.fast / 1000 }}
            className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent pt-16 pb-3 px-4"
          >
            {/* Progress bar */}
            <div
              ref={progressRef}
              className="relative h-1.5 bg-white/20 rounded-full cursor-pointer mb-3 group/progress"
              onClick={handleProgressClick}
              role="slider"
              aria-label="Video progress"
              aria-valuenow={Math.round(state.currentTime)}
              aria-valuemin={0}
              aria-valuemax={Math.round(state.duration)}
            >
              {/* Progress fill */}
              <div
                className="absolute h-full bg-colony-crystal rounded-full transition-all duration-micro"
                style={{ width: `${progress}%` }}
              />

              {/* Checkpoint markers */}
              {checkpoints.map((checkpoint) => {
                const position =
                  state.duration > 0
                    ? (checkpoint.timestamp / state.duration) * 100
                    : 0
                const markerColor =
                  checkpoint.status === 'pass' ? 'grove' : 'spark'

                return (
                  <div
                    key={checkpoint.id}
                    className="absolute top-1/2 -translate-y-1/2 cursor-pointer z-10"
                    style={{ left: `${position}%` }}
                    onMouseEnter={() => setHoveredCheckpoint(checkpoint)}
                    onMouseLeave={() => setHoveredCheckpoint(null)}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleCheckpointClick(checkpoint)
                    }}
                  >
                    <div
                      className={cn(
                        'w-3 h-3 rounded-full transition-transform duration-fast',
                        'hover:scale-150 -translate-x-1/2'
                      )}
                      style={{ backgroundColor: getColonyHex(markerColor) }}
                    />

                    {/* Checkpoint tooltip */}
                    <AnimatePresence>
                      {hoveredCheckpoint?.id === checkpoint.id && (
                        <motion.div
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 8 }}
                          transition={{ duration: TIMING.micro / 1000 }}
                          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-void-light rounded text-xs whitespace-nowrap pointer-events-none"
                        >
                          {checkpoint.name}
                          <div className="text-white/60">
                            {formatTimestamp(checkpoint.timestamp)}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )
              })}

              {/* Scrubber handle */}
              <div
                className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-colony-crystal rounded-full shadow-lg opacity-0 group-hover/progress:opacity-100 transition-opacity duration-fast pointer-events-none"
                style={{ left: `${progress}%`, transform: 'translate(-50%, -50%)' }}
              />
            </div>

            {/* Control buttons */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {/* Play/Pause */}
                <button
                  onClick={togglePlay}
                  className="p-2 text-white/80 hover:text-white transition-colors duration-fast"
                  aria-label={state.isPlaying ? 'Pause' : 'Play'}
                >
                  {state.isPlaying ? (
                    <Pause className="w-5 h-5" />
                  ) : (
                    <Play className="w-5 h-5" fill="currentColor" />
                  )}
                </button>

                {/* Skip backward */}
                <button
                  onClick={() => skip(-10)}
                  className="p-2 text-white/80 hover:text-white transition-colors duration-fast"
                  aria-label="Skip back 10 seconds"
                >
                  <SkipBack className="w-4 h-4" />
                </button>

                {/* Skip forward */}
                <button
                  onClick={() => skip(10)}
                  className="p-2 text-white/80 hover:text-white transition-colors duration-fast"
                  aria-label="Skip forward 10 seconds"
                >
                  <SkipForward className="w-4 h-4" />
                </button>

                {/* Volume */}
                <button
                  onClick={toggleMute}
                  className="p-2 text-white/80 hover:text-white transition-colors duration-fast"
                  aria-label={state.isMuted ? 'Unmute' : 'Mute'}
                >
                  {state.isMuted ? (
                    <VolumeX className="w-5 h-5" />
                  ) : (
                    <Volume2 className="w-5 h-5" />
                  )}
                </button>

                {/* Time display */}
                <span className="text-sm text-white/80 tabular-nums ml-2">
                  {formatTimestamp(state.currentTime)} / {formatTimestamp(state.duration)}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {/* Playback speed */}
                <select
                  value={state.playbackRate}
                  onChange={(e) => {
                    const rate = parseFloat(e.target.value)
                    if (videoRef.current) {
                      videoRef.current.playbackRate = rate
                      setState((s) => ({ ...s, playbackRate: rate }))
                    }
                  }}
                  className="bg-transparent text-white/80 text-sm cursor-pointer focus:outline-none"
                  aria-label="Playback speed"
                >
                  <option value="0.5" className="bg-void">0.5x</option>
                  <option value="1" className="bg-void">1x</option>
                  <option value="1.5" className="bg-void">1.5x</option>
                  <option value="2" className="bg-void">2x</option>
                </select>

                {/* Fullscreen */}
                <button
                  onClick={toggleFullscreen}
                  className="p-2 text-white/80 hover:text-white transition-colors duration-fast"
                  aria-label="Toggle fullscreen"
                >
                  <Maximize className="w-5 h-5" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
