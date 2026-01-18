/**
 * WebSocket client with automatic reconnection and error handling
 */

import type { RalphMessage } from '../types/agent';

export interface WebSocketConfig {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export type MessageHandler = (message: RalphMessage) => void;
export type ErrorHandler = (error: Error) => void;
export type ConnectionHandler = (connected: boolean) => void;

export class RalphWebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private isIntentionallyClosed = false;

  private readonly config: Required<WebSocketConfig>;
  private readonly messageHandlers: Set<MessageHandler> = new Set();
  private readonly errorHandlers: Set<ErrorHandler> = new Set();
  private readonly connectionHandlers: Set<ConnectionHandler> = new Set();

  constructor(config: WebSocketConfig) {
    this.config = {
      reconnectInterval: config.reconnectInterval ?? 3000,
      maxReconnectAttempts: config.maxReconnectAttempts ?? 10,
      heartbeatInterval: config.heartbeatInterval ?? 30000,
      ...config,
    };
  }

  /**
   * Connect to WebSocket server
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    this.isIntentionallyClosed = false;

    try {
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        console.log('[Ralph WS] Connected');
        this.reconnectAttempts = 0;
        this.notifyConnectionHandlers(true);
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: RalphMessage = JSON.parse(event.data);
          this.notifyMessageHandlers(message);
        } catch (error) {
          this.notifyErrorHandlers(
            new Error(`Failed to parse message: ${error}`)
          );
        }
      };

      this.ws.onerror = (event) => {
        console.error('[Ralph WS] Error:', event);
        this.notifyErrorHandlers(new Error('WebSocket error'));
      };

      this.ws.onclose = () => {
        console.log('[Ralph WS] Disconnected');
        this.stopHeartbeat();
        this.notifyConnectionHandlers(false);

        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        }
      };
    } catch (error) {
      this.notifyErrorHandlers(
        error instanceof Error ? error : new Error(String(error))
      );
      this.scheduleReconnect();
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.isIntentionallyClosed = true;
    this.clearReconnectTimer();
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send message to server
   */
  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      this.notifyErrorHandlers(new Error('WebSocket not connected'));
    }
  }

  /**
   * Check if connected
   */
  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Register message handler
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /**
   * Register error handler
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  /**
   * Register connection state handler
   */
  onConnection(handler: ConnectionHandler): () => void {
    this.connectionHandlers.add(handler);
    return () => this.connectionHandlers.delete(handler);
  }

  private scheduleReconnect(): void {
    if (
      this.reconnectAttempts >= this.config.maxReconnectAttempts ||
      this.isIntentionallyClosed
    ) {
      console.log('[Ralph WS] Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(
      `[Ralph WS] Reconnecting in ${this.config.reconnectInterval}ms (attempt ${this.reconnectAttempts})`
    );

    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, this.config.reconnectInterval);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.send({ type: 'ping', timestamp: Date.now() });
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private notifyMessageHandlers(message: RalphMessage): void {
    this.messageHandlers.forEach((handler) => {
      try {
        handler(message);
      } catch (error) {
        console.error('[Ralph WS] Message handler error:', error);
      }
    });
  }

  private notifyErrorHandlers(error: Error): void {
    this.errorHandlers.forEach((handler) => {
      try {
        handler(error);
      } catch (err) {
        console.error('[Ralph WS] Error handler error:', err);
      }
    });
  }

  private notifyConnectionHandlers(connected: boolean): void {
    this.connectionHandlers.forEach((handler) => {
      try {
        handler(connected);
      } catch (error) {
        console.error('[Ralph WS] Connection handler error:', error);
      }
    });
  }
}
