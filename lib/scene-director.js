/**
 * Scene Director Client — AI-Driven Scene Control
 * ================================================
 * Connects to the Claude proxy and drives autonomous character behavior.
 *
 * Usage:
 *   const director = new SceneDirector({
 *     proxyUrl: 'ws://localhost:8767',
 *     onAction: (action) => { ... },
 *     onTitleCard: (text, speaker) => { ... },
 *     onAudioCue: (cue) => { ... },
 *     onBeatComplete: (beat) => { ... },
 *   });
 *   await director.connect();
 *   director.start(sceneState);  // begin autonomous loop
 *   director.addEvent({ type: 'user_click', target: 'willie' });
 *   director.stop();
 */

'use strict';

class SceneDirector {
  constructor(opts = {}) {
    this.proxyUrl = opts.proxyUrl || 'ws://localhost:8767';

    // Callbacks
    this.onAction = opts.onAction || (() => {});
    this.onTitleCard = opts.onTitleCard || (() => {});
    this.onAudioCues = opts.onAudioCues || (() => {});
    this.onCamera = opts.onCamera || (() => {});
    this.onBeatComplete = opts.onBeatComplete || (() => {});
    this.onError = opts.onError || ((e) => console.error('[SceneDirector]', e));
    this.onStateChange = opts.onStateChange || (() => {});

    // Timing
    this.tickIntervalMs = opts.tickIntervalMs || 4000; // AI decides every 4 seconds
    this.minTickMs = 2000; // Don't tick faster than this

    // State
    this.ws = null;
    this.state = 'disconnected'; // disconnected | connecting | ready | running
    this.tickNumber = 0;
    this.startTime = 0;
    this.pendingEvents = [];
    this._tickTimer = null;
    this._lastTickTime = 0;
    this._currentSceneState = null;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // CONNECTION
  // ═══════════════════════════════════════════════════════════════════════

  async connect() {
    if (this.ws) return;
    this._setState('connecting');

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.proxyUrl);

      this.ws.onopen = () => {
        console.log('[SceneDirector] Connected to proxy');
        this._setState('ready');
        resolve();
      };

      this.ws.onmessage = (event) => {
        this._handleMessage(JSON.parse(event.data));
      };

      this.ws.onclose = () => {
        console.log('[SceneDirector] Disconnected');
        this._setState('disconnected');
        this.stop();
      };

      this.ws.onerror = (e) => {
        this.onError(e);
        reject(e);
      };

      // Timeout
      setTimeout(() => {
        if (this.state === 'connecting') {
          reject(new Error('Connection timeout'));
          this.disconnect();
        }
      }, 10000);
    });
  }

  disconnect() {
    this.stop();
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this._setState('disconnected');
  }

  // ═══════════════════════════════════════════════════════════════════════
  // SCENE CONTROL
  // ═══════════════════════════════════════════════════════════════════════

  start(initialSceneState) {
    if (this.state !== 'ready') {
      console.warn('[SceneDirector] Cannot start - not ready');
      return;
    }

    this._currentSceneState = initialSceneState;
    this.startTime = Date.now();
    this.tickNumber = 0;
    this._setState('running');

    // First tick immediately
    this._doTick();
  }

  stop() {
    if (this._tickTimer) {
      clearTimeout(this._tickTimer);
      this._tickTimer = null;
    }
    if (this.state === 'running') {
      this._setState('ready');
    }
  }

  pause() {
    if (this._tickTimer) {
      clearTimeout(this._tickTimer);
      this._tickTimer = null;
    }
  }

  resume() {
    if (this.state === 'running' && !this._tickTimer) {
      this._scheduleNextTick();
    }
  }

  // Update scene state from renderer
  updateSceneState(newState) {
    this._currentSceneState = newState;
  }

  // Add an event to be sent with next tick
  addEvent(event) {
    this.pendingEvents.push({
      ...event,
      timestamp: Date.now()
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // TICK LOOP
  // ═══════════════════════════════════════════════════════════════════════

  _doTick() {
    if (this.state !== 'running' || !this.ws) return;

    const now = Date.now();
    const elapsed = now - this.startTime;

    // Don't tick too fast
    if (now - this._lastTickTime < this.minTickMs) {
      this._scheduleNextTick();
      return;
    }

    this.tickNumber++;
    this._lastTickTime = now;

    // Build tick message
    const tickMsg = {
      type: 'scene_tick',
      tick_number: this.tickNumber,
      elapsed_ms: elapsed,
      scene_state: this._currentSceneState,
      events: [...this.pendingEvents]
    };

    // Clear pending events
    this.pendingEvents = [];

    // Send to proxy
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(tickMsg));
    }

    // Note: next tick is scheduled when beat_complete is received
    // This ensures we wait for AI to finish before asking for more
  }

  _scheduleNextTick() {
    if (this._tickTimer) clearTimeout(this._tickTimer);
    this._tickTimer = setTimeout(() => this._doTick(), this.tickIntervalMs);
  }

  // ═══════════════════════════════════════════════════════════════════════
  // MESSAGE HANDLING
  // ═══════════════════════════════════════════════════════════════════════

  _handleMessage(msg) {
    switch (msg.type) {
      case 'action':
        this.onAction({
          character: msg.character,
          action: msg.action,
          emotion: msg.emotion,
          dialogue: msg.dialogue,
          targetX: msg.target_x,
          targetY: msg.target_y
        });
        break;

      case 'audio_cues':
        if (msg.cues && msg.cues.length > 0) {
          this.onAudioCues(msg.cues);
        }
        break;

      case 'title_card':
        this.onTitleCard(msg.text, msg.speaker);
        break;

      case 'camera':
        this.onCamera({
          focus: msg.focus,
          shake: msg.shake
        });
        break;

      case 'beat_complete':
        this.onBeatComplete(msg.scene_beat, msg.tick);
        // Schedule next tick now that this one is done
        if (this.state === 'running') {
          this._scheduleNextTick();
        }
        break;

      case 'error':
        this.onError(new Error(msg.message));
        // Still schedule next tick to keep going
        if (this.state === 'running') {
          this._scheduleNextTick();
        }
        break;
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STATE
  // ═══════════════════════════════════════════════════════════════════════

  _setState(s) {
    if (this.state === s) return;
    this.state = s;
    this.onStateChange(s);
  }
}

// Export
if (typeof window !== 'undefined') {
  window.SceneDirector = SceneDirector;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { SceneDirector };
}
