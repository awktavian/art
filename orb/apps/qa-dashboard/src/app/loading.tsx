'use client'

import { motion } from 'framer-motion'
import { TIMING } from '@/types'

export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
      <motion.div
        className="flex flex-col items-center"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: TIMING.normal / 1000 }}
      >
        {/* Animated loading rings */}
        <div className="relative w-16 h-16">
          <motion.div
            className="absolute inset-0 rounded-full border-2 border-colony-crystal/30"
            animate={{ rotate: 360 }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'linear',
            }}
          />
          <motion.div
            className="absolute inset-2 rounded-full border-2 border-t-colony-crystal border-r-transparent border-b-transparent border-l-transparent"
            animate={{ rotate: -360 }}
            transition={{
              duration: 1.5,
              repeat: Infinity,
              ease: 'linear',
            }}
          />
          <motion.div
            className="absolute inset-4 rounded-full border-2 border-t-transparent border-r-colony-crystal border-b-transparent border-l-transparent"
            animate={{ rotate: 360 }}
            transition={{
              duration: 1,
              repeat: Infinity,
              ease: 'linear',
            }}
          />
        </div>

        <motion.p
          className="text-white/60 mt-4 text-sm"
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: TIMING.fast / 1000, delay: TIMING.fast / 1000 }}
        >
          Loading...
        </motion.p>
      </motion.div>
    </div>
  )
}
