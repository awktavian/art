'use client'

import { motion } from 'framer-motion'
import { TIMING } from '@/types'
import { Button } from '@/components/ui'
import { FileQuestion, Home, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)] p-6">
      <motion.div
        className="text-center max-w-md"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: TIMING.normal / 1000 }}
      >
        <div className="w-16 h-16 rounded-full bg-colony-crystal/20 flex items-center justify-center mx-auto mb-6">
          <FileQuestion className="w-8 h-8 text-colony-crystal" />
        </div>

        <h1 className="text-4xl font-bold mb-2 text-colony-crystal">404</h1>
        <h2 className="text-xl font-semibold mb-2">Page Not Found</h2>
        <p className="text-white/60 mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>

        <div className="flex gap-3 justify-center">
          <Button
            variant="secondary"
            leftIcon={<ArrowLeft className="w-4 h-4" />}
            onClick={() => window.history.back()}
          >
            Go Back
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
