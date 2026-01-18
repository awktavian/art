/**
 * Real-Time State Management — 鏡 Kagami
 *
 * Ultra-low-latency state synchronization with the Kagami backend.
 * Uses Tauri events for instant UI updates.
 *
 * Performance targets:
 * - State update rendering: < 16ms (60fps)
 * - Event propagation: < 50ms
 * - Memory footprint: < 10MB
 *
 * Colony: Nexus (e₄) × Flow (e₃) → Crystal (e₇)
 * η → s → μ → a → η′
 */

// Check if running in Tauri
const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// State store with immutable updates
class RealtimeStore {
    constructor() {
        this.state = {
            connected: false,
            registered: false,
            safety_score: null,
            active_colonies: [],
            api_uptime_ms: null,
            home_status: null,
            training_status: null,
            latency_ms: 0,
            last_update: 0,
            // Context from Kagami (Dec 30, 2025)
            situation_phase: 'unknown',
            wakefulness_level: 'alert',
            suggested_action: null,
            // Health data (Dec 30, 2025)
            health_status: null,  // Aggregated health from all devices
            // Connection status (Jan 2026)
            connectionStatus: 'disconnected', // 'connected' | 'disconnected' | 'connecting' | 'reconnecting'
            reconnectAttempt: 0,
            reconnectCountdown: 0,
            lastError: null,
        };

        this.listeners = new Map();
        this.colony_activity_buffer = [];
        this.MAX_ACTIVITY_BUFFER = 100;

        // Performance metrics
        this.metrics = {
            updates: 0,
            renders: 0,
            avg_render_ms: 0,
            last_render_ms: 0,
        };
    }

    // Subscribe to state changes
    subscribe(key, callback) {
        if (!this.listeners.has(key)) {
            this.listeners.set(key, new Set());
        }
        this.listeners.get(key).add(callback);

        // Return unsubscribe function
        return () => {
            this.listeners.get(key)?.delete(callback);
        };
    }

    // Update state and notify listeners (batched for performance)
    update(partial) {
        const start = performance.now();

        // Immutable update
        this.state = { ...this.state, ...partial, last_update: Date.now() };
        this.metrics.updates++;

        // Batch notifications with requestAnimationFrame
        if (!this._pendingNotify) {
            this._pendingNotify = true;
            requestAnimationFrame(() => {
                this._notifyListeners(Object.keys(partial));
                this._pendingNotify = false;

                // Track render time
                const elapsed = performance.now() - start;
                this.metrics.last_render_ms = elapsed;
                this.metrics.avg_render_ms =
                    (this.metrics.avg_render_ms * this.metrics.renders + elapsed) /
                    (this.metrics.renders + 1);
                this.metrics.renders++;
            });
        }
    }

    _notifyListeners(changedKeys) {
        // Notify specific key listeners
        for (const key of changedKeys) {
            const listeners = this.listeners.get(key);
            if (listeners) {
                for (const callback of listeners) {
                    try {
                        callback(this.state[key], key);
                    } catch (e) {
                        console.error('Listener error:', e);
                    }
                }
            }
        }

        // Notify global listeners
        const globalListeners = this.listeners.get('*');
        if (globalListeners) {
            for (const callback of globalListeners) {
                try {
                    callback(this.state, changedKeys);
                } catch (e) {
                    console.error('Global listener error:', e);
                }
            }
        }
    }

    // Add colony activity with circular buffer
    addActivity(activity) {
        this.colony_activity_buffer.push(activity);
        if (this.colony_activity_buffer.length > this.MAX_ACTIVITY_BUFFER) {
            this.colony_activity_buffer.shift();
        }

        // Update active colonies
        if (!this.state.active_colonies.includes(activity.colony)) {
            this.update({
                active_colonies: [...this.state.active_colonies, activity.colony]
            });
        }
    }

    // Get state (read-only)
    getState() {
        return { ...this.state };
    }

    // Get performance metrics
    getMetrics() {
        return { ...this.metrics };
    }
}

// Global store instance
const store = new RealtimeStore();

// ═══════════════════════════════════════════════════════════════
// TAURI EVENT HANDLERS
// ═══════════════════════════════════════════════════════════════

async function initTauriEvents() {
    if (!isTauri) {
        console.log('Not in Tauri environment, using mock updates');
        initMockUpdates();
        return;
    }

    const { listen } = await import('@tauri-apps/api/event');
    const { invoke } = await import('@tauri-apps/api/core');

    // Full state sync
    await listen('kagami-state', (event) => {
        store.update(event.payload);
    });

    // Connection events
    await listen('kagami-connected', () => {
        store.update({
            connected: true,
            connectionStatus: 'connected',
            reconnectAttempt: 0,
            reconnectCountdown: 0,
            lastError: null,
        });
        showConnectionToast('Connected to Kagami', 'success');
    });

    await listen('kagami-disconnected', () => {
        store.update({
            connected: false,
            registered: false,
            connectionStatus: 'disconnected',
        });
        showConnectionToast('Disconnected from Kagami', 'warning');
    });

    // Reconnection events
    await listen('kagami-reconnecting', (event) => {
        const data = event.payload || {};
        store.update({
            connectionStatus: 'reconnecting',
            reconnectAttempt: data.attempt || 0,
            reconnectCountdown: data.delay_ms || 0,
        });
        startReconnectCountdown(data.delay_ms || 3000);
    });

    await listen('kagami-error', (event) => {
        store.update({
            lastError: event.payload?.error || 'Unknown error',
        });
    });

    // Client registration events (Dec 30, 2025)
    await listen('kagami-registered', (event) => {
        store.update({ registered: true });
        console.log('📱 Registered with Kagami:', event.payload);
    });

    // Context updates from Kagami (Dec 30, 2025)
    await listen('context-update', (event) => {
        const data = event.payload;
        store.update({
            situation_phase: data.situation_phase || 'unknown',
            wakefulness_level: data.wakefulness || 'alert',
            safety_score: data.safety_score ?? store.state.safety_score,
        });
    });

    // Suggestion from Kagami (Dec 30, 2025)
    await listen('suggestion', (event) => {
        store.update({ suggested_action: event.payload });
    });

    // Health status updates (Dec 30, 2025)
    await listen('health-update', (event) => {
        store.update({ health_status: event.payload });
    });

    // Brand activity
    await listen('colony-activity', (event) => {
        store.addActivity(event.payload);
    });

    // Training updates
    await listen('training-update', (event) => {
        store.update({ training_status: event.payload });
    });

    // Home updates
    await listen('home-update', (event) => {
        store.update({ home_status: event.payload });
    });

    // Safety updates
    await listen('safety-update', (event) => {
        store.update({ safety_score: event.payload.h_x });
    });

    // Connect to real-time backend
    try {
        await invoke('connect_realtime');
        console.log('✓ Connected to real-time backend');
    } catch (e) {
        console.error('Failed to connect to real-time:', e);
    }

    // Start health polling (fetches aggregated health from Kagami)
    startHealthPolling();
}

// Health polling - fetch aggregated health data periodically
async function startHealthPolling() {
    const { invoke } = await import('@tauri-apps/api/core');

    const pollHealth = async () => {
        try {
            const health = await invoke('fetch_health_status');
            store.update({ health_status: health });
        } catch (e) {
            console.debug('Health poll failed:', e);
        }
    };

    // Initial poll
    await pollHealth();

    // Poll every 30 seconds
    setInterval(pollHealth, 30000);
}

// Mock updates for browser preview
function initMockUpdates() {
    store.update({ connected: true, safety_score: 0.85 });

    // Simulate periodic updates
    setInterval(() => {
        const colonies = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];
        const randomColony = colonies[Math.floor(Math.random() * colonies.length)];

        store.addActivity({
            colony: randomColony,
            action: 'processing',
            timestamp_ms: Date.now(),
        });

        // Vary safety score slightly
        const currentSafety = store.state.safety_score || 0.85;
        const newSafety = Math.max(0.5, Math.min(1.0, currentSafety + (Math.random() - 0.5) * 0.05));
        store.update({ safety_score: newSafety });
    }, 3000);
}

// ═══════════════════════════════════════════════════════════════
// CONNECTION STATUS UI
// ═══════════════════════════════════════════════════════════════

let reconnectInterval = null;

/**
 * Show a connection status toast notification
 * @param {string} message - Toast message
 * @param {'success' | 'warning' | 'error'} type - Toast type
 */
function showConnectionToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('connection-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'connection-toast-container';
        container.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 8px;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `connection-toast connection-toast-${type}`;
    toast.style.cssText = `
        background: ${type === 'success' ? '#10B981' : type === 'warning' ? '#F59E0B' : '#EF4444'};
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        pointer-events: auto;
        opacity: 0;
        transform: translateX(20px);
        transition: opacity 0.3s ease, transform 0.3s ease;
    `;
    toast.textContent = message;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    });

    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(20px)';
        setTimeout(() => toast.remove(), 233);  // standard timing
    }, 3000);
}

/**
 * Start reconnect countdown display
 * @param {number} delayMs - Delay in milliseconds
 */
function startReconnectCountdown(delayMs) {
    if (reconnectInterval) {
        clearInterval(reconnectInterval);
    }

    let remaining = Math.ceil(delayMs / 1000);
    store.update({ reconnectCountdown: remaining });

    // Update countdown toast
    const updateToast = () => {
        const toastEl = document.getElementById('reconnect-countdown-toast');
        if (toastEl) {
            toastEl.textContent = `Reconnecting in ${remaining}s...`;
        }
    };

    // Create countdown toast
    let container = document.getElementById('connection-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'connection-toast-container';
        container.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            display: flex;
            flex-direction: column;
            gap: 8px;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }

    // Remove existing countdown toast
    const existingToast = document.getElementById('reconnect-countdown-toast');
    if (existingToast) existingToast.remove();

    const toast = document.createElement('div');
    toast.id = 'reconnect-countdown-toast';
    toast.style.cssText = `
        background: #374151;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        pointer-events: auto;
        display: flex;
        align-items: center;
        gap: 10px;
    `;
    toast.innerHTML = `
        <span class="reconnect-spinner" style="
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        "></span>
        <span>Reconnecting in ${remaining}s...</span>
    `;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    // Add spinner animation if not present
    if (!document.getElementById('reconnect-spinner-style')) {
        const style = document.createElement('style');
        style.id = 'reconnect-spinner-style';
        style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
        document.head.appendChild(style);
    }

    container.appendChild(toast);

    reconnectInterval = setInterval(() => {
        remaining--;
        store.update({ reconnectCountdown: remaining });

        if (remaining <= 0) {
            clearInterval(reconnectInterval);
            reconnectInterval = null;
            toast.remove();
        } else {
            const span = toast.querySelector('span:last-child');
            if (span) span.textContent = `Reconnecting in ${remaining}s...`;
        }
    }, 1000);
}

// ═══════════════════════════════════════════════════════════════
// UI BINDINGS
// ═══════════════════════════════════════════════════════════════

// Bind to DOM elements with data-bind attribute
function bindUI() {
    // API Status
    store.subscribe('connected', (connected) => {
        const el = document.getElementById('api-status');
        if (el) {
            el.textContent = connected ? 'Connected' : 'Disconnected';
            el.classList.toggle('connected', connected);
        }
    });

    // Connection status - fade controls when offline
    store.subscribe('connectionStatus', (status) => {
        // Find all control elements and adjust opacity
        const controlElements = document.querySelectorAll(
            '.control-card, .room-control, .device-control, .scene-button, ' +
            '.light-slider, .shade-control, .climate-control'
        );

        const isOffline = status === 'disconnected' || status === 'reconnecting';

        controlElements.forEach(el => {
            el.style.opacity = isOffline ? '0.5' : '1';
            el.style.pointerEvents = isOffline ? 'none' : 'auto';
            el.setAttribute('aria-disabled', isOffline ? 'true' : 'false');
        });

        // Update body class for CSS hooks
        document.body.classList.toggle('kagami-offline', isOffline);
        document.body.classList.toggle('kagami-online', !isOffline);

        // Update connection indicator if present
        const indicator = document.getElementById('connection-indicator');
        if (indicator) {
            indicator.className = `connection-indicator connection-${status}`;
            indicator.setAttribute('aria-label', `Connection status: ${status}`);
        }
    });

    // Safety Score
    store.subscribe('safety_score', (score) => {
        const el = document.getElementById('safety-value');
        if (el && score !== null) {
            el.textContent = score >= 0.5 ? 'All Good' : score >= 0 ? 'Attention' : 'Alert';

            // Update class based on value
            el.classList.remove('safety-ok', 'safety-caution', 'safety-violation');
            if (score >= 0.5) {
                el.classList.add('safety-ok');
                el.textContent += ' ✓';
            } else if (score >= 0) {
                el.classList.add('safety-caution');
                el.textContent += ' ⚠';
            } else {
                el.classList.add('safety-violation');
                el.textContent += ' ✗';
            }
        }

        const healthEl = document.getElementById('api-health');
        if (healthEl && score !== null) {
            healthEl.textContent = score >= 0.5 ? '● Good' : score >= 0 ? '● Caution' : '● Alert';
        }
    });

    // Active Colonies
    store.subscribe('active_colonies', (colonies) => {
        // Update colony display elements
        document.querySelectorAll('.colony').forEach(el => {
            const colony = el.dataset.colony;
            const statusEl = el.querySelector('.colony-status');

            if (colonies.includes(colony)) {
                el.classList.add('active');
                if (statusEl) statusEl.textContent = 'active';
            } else {
                el.classList.remove('active');
                if (statusEl) statusEl.textContent = 'idle';
            }
        });
    });

    // Training Status
    store.subscribe('training_status', (status) => {
        const el = document.getElementById('training-status');
        if (el && status) {
            if (status.running) {
                el.textContent = `Epoch ${status.epoch} (${(status.progress * 100).toFixed(1)}%)`;
            } else {
                el.textContent = 'Idle';
            }
        }

        const progressEl = document.getElementById('training-progress');
        if (progressEl && status?.loss) {
            progressEl.textContent = `Loss: ${status.loss.toFixed(4)}`;
        }
    });

    // Home Status
    store.subscribe('home_status', (status) => {
        const el = document.getElementById('home-status');
        if (el && status) {
            const parts = [];
            if (status.movie_mode) parts.push('🎬 Movie');
            if (status.fireplace_on) parts.push('🔥');
            if (status.temperature) parts.push(`${status.temperature}°F`);
            el.textContent = parts.join(' ') || 'Ready';
        }

        const detailEl = document.getElementById('home-detail');
        if (detailEl && status?.occupied_rooms?.length > 0) {
            detailEl.textContent = `Occupied: ${status.occupied_rooms.join(', ')}`;
        }
    });

    // Latency indicator
    store.subscribe('latency_ms', (latency) => {
        const el = document.getElementById('latency');
        if (el) {
            el.textContent = `${latency}ms`;
            el.classList.toggle('high-latency', latency > 100);
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// OPTIMIZED ANIMATION FRAME LOOP
// ═══════════════════════════════════════════════════════════════

let lastFrameTime = 0;
const TARGET_FPS = 60;
const FRAME_BUDGET_MS = 1000 / TARGET_FPS;

function optimizedRenderLoop(timestamp) {
    const elapsed = timestamp - lastFrameTime;

    // Only update if we have budget
    if (elapsed >= FRAME_BUDGET_MS) {
        lastFrameTime = timestamp - (elapsed % FRAME_BUDGET_MS);

        // Update any animations here
        updateColonyPulse(timestamp);
        updateParticles(timestamp);
    }

    requestAnimationFrame(optimizedRenderLoop);
}

function updateColonyPulse(timestamp) {
    const activeColonies = store.state.active_colonies;

    document.querySelectorAll('.colony').forEach(el => {
        const colony = el.dataset.colony;
        if (activeColonies.includes(colony)) {
            // Subtle pulse animation
            const pulse = Math.sin(timestamp / 500) * 0.1 + 1;
            el.style.transform = `scale(${pulse})`;
        } else {
            el.style.transform = '';
        }
    });
}

function updateParticles(timestamp) {
    // Particle updates handled by CSS animations for performance
    // Only update if special effects needed
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

async function init() {
    console.log('🔗 Initializing real-time state management...');

    await initTauriEvents();
    bindUI();

    // Start render loop
    requestAnimationFrame(optimizedRenderLoop);

    console.log('✓ Real-time initialized');
    console.log('  State updates will render at 60fps');
    console.log('  Try: Realtime.getState() or Realtime.getMetrics()');
}

// Auto-init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const Realtime = {
    store,
    subscribe: (key, cb) => store.subscribe(key, cb),
    getState: () => store.getState(),
    getMetrics: () => store.getMetrics(),

    // Direct state access
    get connected() { return store.state.connected; },
    get registered() { return store.state.registered; },
    get safetyScore() { return store.state.safety_score; },
    get activeColonies() { return store.state.active_colonies; },
    get latency() { return store.state.latency_ms; },

    // Context (Dec 30, 2025)
    get situationPhase() { return store.state.situation_phase; },
    get wakefulnessLevel() { return store.state.wakefulness_level; },
    get suggestedAction() { return store.state.suggested_action; },

    // Health (Dec 30, 2025)
    get healthStatus() { return store.state.health_status; },

    // Connection status (Jan 2026)
    get connectionStatus() { return store.state.connectionStatus; },
    get reconnectAttempt() { return store.state.reconnectAttempt; },
    get reconnectCountdown() { return store.state.reconnectCountdown; },
    get lastError() { return store.state.lastError; },
    get isOffline() { return store.state.connectionStatus !== 'connected'; },
};

window.Realtime = Realtime;

/*
 * 鏡
 * η → s → μ → a → η′
 * Real-time is presence. Latency is distance.
 */
