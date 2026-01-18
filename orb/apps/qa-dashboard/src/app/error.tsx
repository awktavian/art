'use client'

import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import { Button } from '@/components/ui'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import Link from 'next/link'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to an error reporting service
    console.error('Application error:', error)
  }, [error])

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] p-6">
      <motion.div
        className="text-center max-w-md"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: TIMING.normal / 1000 }}
      >
        <div className="w-16 h-16 rounded-full bg-colony-spark/20 flex items-center justify-center mx-auto mb-6">
          <AlertTriangle className="w-8 h-8 text-colony-spark" />
        </div>

        <h1 className="text-2xl font-bold mb-2">Something went wrong</h1>
        <p className="text-white/60 mb-6">
          An unexpected error occurred. Please try again or return to the dashboard.
        </p>

        {error.digest && (
          <p className="text-xs text-white/40 mb-6 font-mono">
            Error ID: {error.digest}
          </p>
        )}

        <div className="flex gap-3 justify-center">
          <Button
            variant="secondary"
            leftIcon={<RefreshCw className="w-4 h-4" />}
            onClick={reset}
          >
            Try Again
          </Button>
          <Link href="/">
            <Button leftIcon={<Home className="w-4 h-4" />}>
              Go to Dashboard
            </Button>
          </Link>
        </div>
      </motion.div>
    </div>
  )
}
