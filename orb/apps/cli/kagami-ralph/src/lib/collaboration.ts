/**
 * Real-time collaboration for 111/100 Crystal polish
 * 
 * Multi-user cursors and presence indicators.
 */

export interface CollaboratorCursor {
  userId: string;
  userName: string;
  x: number;
  y: number;
  color: string;
  lastSeen: number;
}

export class CollaborationManager {
  private collaborators: Map<string, CollaboratorCursor> = new Map();
  private readonly localUserId: string;
  private cursorElements: Map<string, HTMLElement> = new Map();
  
  constructor(userId?: string) {
    this.localUserId = userId || this.generateUserId();
    console.log(`[Collab] User ID: ${this.localUserId}`);
    this.startTrackingMouse();
    this.startPresenceHeartbeat();
  }
  
  private generateUserId(): string {
    return `user_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Track local mouse movements
   */
  private startTrackingMouse(): void {
    document.addEventListener('mousemove', (e) => {
      // Broadcast cursor position (would go via WebSocket)
      this.broadcastCursorPosition(e.clientX, e.clientY);
    });
  }
  
  /**
   * Send presence heartbeat
   */
  private startPresenceHeartbeat(): void {
    setInterval(() => {
      this.broadcastPresence();
    }, 5000);
  }
  
  /**
   * Broadcast cursor position
   */
  private broadcastCursorPosition(_x: number, _y: number): void {
    // In real implementation: wsClient.send({ type: 'cursor', x, y })
    // For now: local simulation
    // console.log(`[Collab] Cursor: ${x}, ${y}`);
  }
  
  /**
   * Broadcast presence
   */
  private broadcastPresence(): void {
    // In real implementation: wsClient.send({ type: 'presence', userId })
  }
  
  /**
   * Update collaborator cursor
   */
  updateCollaborator(cursor: CollaboratorCursor): void {
    this.collaborators.set(cursor.userId, {
      ...cursor,
      lastSeen: Date.now(),
    });
    
    this.renderCursor(cursor);
    this.pruneStale();
  }
  
  /**
   * Render cursor element
   */
  private renderCursor(cursor: CollaboratorCursor): void {
    let element = this.cursorElements.get(cursor.userId);
    
    if (!element) {
      element = document.createElement('div');
      element.className = 'collab-cursor';
      element.innerHTML = `
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
          <path d="M5 3L19 12L12 13L9 20L5 3Z" fill="${cursor.color}" stroke="white" stroke-width="1.5"/>
        </svg>
        <div class="collab-name">${cursor.userName}</div>
      `;
      document.body.appendChild(element);
      this.cursorElements.set(cursor.userId, element);
    }
    
    // Update position
    element.style.left = `${cursor.x}px`;
    element.style.top = `${cursor.y}px`;
  }
  
  /**
   * Remove stale cursors
   */
  private pruneStale(): void {
    const now = Date.now();
    const staleThreshold = 10000; // 10 seconds
    
    this.collaborators.forEach((cursor, userId) => {
      if (now - cursor.lastSeen > staleThreshold) {
        this.collaborators.delete(userId);
        const element = this.cursorElements.get(userId);
        if (element) {
          element.remove();
          this.cursorElements.delete(userId);
        }
      }
    });
  }
  
  /**
   * Get active collaborator count
   */
  getCollaboratorCount(): number {
    return this.collaborators.size;
  }
  
  destroy(): void {
    this.cursorElements.forEach(el => el.remove());
    this.cursorElements.clear();
    this.collaborators.clear();
  }
}
