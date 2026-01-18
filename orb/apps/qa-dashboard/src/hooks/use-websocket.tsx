'use client'

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from 'react'
import type { TestUpdateEvent, ConnectionStatus, ConnectionState, WebSocketEventType } from '@/types'
import { TIMING } from '@/types'

interface WebSocketContextType {
  isConnected: boolean
  connectionStatus: ConnectionStatus
  lastEvent: TestUpdateEvent | null
  subscribe: (callback: (event: TestUpdateEvent) => void) => () => void
  sendMessage: (message: object) => void
}

const WebSocketContext = createContext<WebSocketContextType | null>(null)

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:3001'
const RECONNECT_BASE_DELAY = TIMING.slower // Fibonacci timing (987ms)
const MAX_RECONNECT_ATTEMPTS = 5
const PING_INTERVAL = 30000 // 30 seconds
const MAX_EVENT_QUEUE_SIZE = 100

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    state: 'disconnected',
    connected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: MAX_RECONNECT_ATTEMPTS,
  })
  const [lastEvent, setLastEvent] = useState<TestUpdateEvent | null>(null)

  // Use refs to avoid stale closures in WebSocket callbacks
  const subscribersRef = useRef<Set<(event: TestUpdateEvent) => void>>(new Set())
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>()
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | undefined>()
  const reconnectAttemptsRef = useRef(0)
  const eventQueueRef = useRef<TestUpdateEvent[]>([])
  const mountedRef = useRef(true)

  // Subscribe to events
  const subscribe = useCallback((callback: (event: TestUpdateEvent) => void) => {
    subscribersRef.current.add(callback)
    return () => {
      subscribersRef.current.delete(callback)
    }
  }, [])

  // Send message through WebSocket
  const sendMessage = useCallback((message: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    } else {
      console.warn('[WebSocket] Cannot send message - not connected')
    }
  }, [])

  // Process event and notify subscribers
  const processEvent = useCallback((event: TestUpdateEvent) => {
    setLastEvent(event)
    subscribersRef.current.forEach((cb) => {
      try {
        cb(event)
      } catch (e) {
        console.error('[WebSocket] Subscriber error:', e)
      }
    })
  }, [])

  // Flush queued events when reconnected
  const flushEventQueue = useCallback(() => {
    const queue = eventQueueRef.current
    if (queue.length > 0) {
      console.log(`[WebSocket] Flushing ${queue.length} queued events`)
      queue.forEach(processEvent)
      eventQueueRef.current = []
    }
  }, [processEvent])

  // Queue event during disconnection
  const queueEvent = useCallback((event: TestUpdateEvent) => {
    if (eventQueueRef.current.length < MAX_EVENT_QUEUE_SIZE) {
      eventQueueRef.current.push(event)
    } else {
      // Drop oldest events if queue is full
      eventQueueRef.current.shift()
      eventQueueRef.current.push(event)
      console.warn('[WebSocket] Event queue full, dropping oldest event')
    }
  }, [])

  // Update connection state
  const updateConnectionState = useCallback((state: ConnectionState, error?: string) => {
    if (!mountedRef.current) return

    setConnectionStatus((prev) => ({
      ...prev,
      state,
      connected: state === 'connected',
      reconnectAttempts: reconnectAttemptsRef.current,
      ...(error && { lastError: error }),
      ...(state === 'connected' && { lastError: undefined }),
    }))
  }, [])

  // WebSocket connection
  useEffect(() => {
    mountedRef.current = true

    const connect = () => {
      if (!mountedRef.current) return

      updateConnectionState('connecting')

      try {
        const ws = new WebSocket(WS_URL)
        wsRef.current = ws

        ws.onopen = () => {
          if (!mountedRef.current) {
            ws.close()
            return
          }

          console.log('[WebSocket] Connected to', WS_URL)
          reconnectAttemptsRef.current = 0
          updateConnectionState('connected')

          // Flush any queued events
          flushEventQueue()

          // Start ping interval to keep connection alive
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }))
            }
          }, PING_INTERVAL)
        }

        ws.onmessage = (event) => {
          if (!mountedRef.current) return

          try {
            const data = JSON.parse(event.data) as TestUpdateEvent

            // Handle pong messages separately
            if (data.type === 'pong') {
              setConnectionStatus((prev) => ({
                ...prev,
                lastPing: new Date().toISOString(),
              }))
              return
            }

            // Process the event
            processEvent(data)
          } catch (e) {
            console.error('[WebSocket] Failed to parse message:', e)
          }
        }

        ws.onclose = (event) => {
          if (!mountedRef.current) return

          console.log('[WebSocket] Disconnected:', event.code, event.reason)

          // Clear ping interval
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current)
            pingIntervalRef.current = undefined
          }

          // Attempt to reconnect with exponential backoff
          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttemptsRef.current++
            updateConnectionState('reconnecting')

            const delay = RECONNECT_BASE_DELAY * reconnectAttemptsRef.current
            console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`)

            reconnectTimeoutRef.current = setTimeout(connect, delay)
          } else {
            updateConnectionState('disconnected', 'Max reconnection attempts reached')
            console.error('[WebSocket] Max reconnection attempts reached')
          }
        }

        ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error)
          updateConnectionState('disconnected', 'Connection error')
        }
      } catch (error) {
        console.error('[WebSocket] Connection failed:', error)
        updateConnectionState('disconnected', 'Failed to create WebSocket connection')

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++
          const delay = RECONNECT_BASE_DELAY * reconnectAttemptsRef.current
          reconnectTimeoutRef.current = setTimeout(connect, delay)
        }
      }
    }

    connect()

    return () => {
      mountedRef.current = false

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (pingIntervalRef.current) {
        clearInterval(pingIntervalRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted')
        wsRef.current = null
      }
    }
  }, [updateConnectionState, processEvent, flushEventQueue])

  return (
    <WebSocketContext.Provider
      value={{
        isConnected: connectionStatus.connected,
        connectionStatus,
        lastEvent,
        subscribe,
        sendMessage,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocket() {
  const context = useContext(WebSocketContext)

  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider')
  }

  return context
}

// Hook for subscribing to specific event types
export function useTestUpdates(
  onEvent?: (event: TestUpdateEvent) => void,
  eventTypes?: WebSocketEventType[]
) {
  const { subscribe, lastEvent } = useWebSocket()

  useEffect(() => {
    if (!onEvent) return

    return subscribe((event) => {
      if (!eventTypes || eventTypes.includes(event.type)) {
        onEvent(event)
      }
    })
  }, [subscribe, onEvent, eventTypes])

  return lastEvent
}

// Hook for connection status only
export function useConnectionStatus() {
  const { connectionStatus } = useWebSocket()
  return connectionStatus
}
