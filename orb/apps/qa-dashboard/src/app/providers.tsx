'use client'

import { type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider, WebSocketProvider } from '@/hooks'
import { StatusAnnouncer } from '@/components/ui'

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60 * 1000, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <WebSocketProvider>
          <StatusAnnouncer>
            {children}
          </StatusAnnouncer>
        </WebSocketProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
