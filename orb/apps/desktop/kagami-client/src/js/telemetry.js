/**
 * Kagami Telemetry Module
 *
 * Structured event tracking with privacy-first local storage.
 * Features:
 * - Feature usage analytics
 * - Command frequency histograms
 * - Voice activation metrics
 * - Session duration tracking
 * - Privacy-respecting: all data stays local unless explicitly exported
 *
 * Focus:
 *
 *
 */

// ============================================================================
// CONSTANTS
// ============================================================================

const STORAGE_KEY = 'kagami-telemetry';
const MAX_EVENTS = 10000;
const MAX_HISTOGRAM_BUCKETS = 1000;
const FLUSH_INTERVAL_MS = 30000; // 30 seconds
const SESSION_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

// Event categories
const EventCategory = {
    COMMAND: 'command',
    VOICE: 'voice',
    NAVIGATION: 'navigation',
    SCENE: 'scene',
    ERROR: 'error',
    PERFORMANCE: 'performance',
    SESSION: 'session',
    FEATURE: 'feature',
    INTERACTION: 'interaction',
};

// ============================================================================
// TELEMETRY SERVICE
// ============================================================================

class TelemetryService {
    constructor() {
        this.events = [];
        this.histograms = new Map();
        this.sessionId = null;
        this.sessionStart = null;
        this.lastActivity = null;
        this.enabled = true;
        this.flushTimer = null;

        this._loadFromStorage();
        this._startSession();
        this._setupFlushTimer();
        this._setupActivityTracking();
    }

    // ========================================================================
    // SESSION MANAGEMENT
    // ========================================================================

    /**
     * Start a new session or resume existing one
     */
    _startSession() {
        const now = Date.now();

        // Check if we should resume existing session
        if (this.sessionId && this.lastActivity) {
            const timeSinceActivity = now - this.lastActivity;
            if (timeSinceActivity < SESSION_TIMEOUT_MS) {
                // Resume session
                this.lastActivity = now;
                console.log('[Telemetry] Resumed session:', this.sessionId);
                return;
            }
        }

        // End previous session if exists
        if (this.sessionId) {
            this._endSession();
        }

        // Start new session
        this.sessionId = this._generateSessionId();
        this.sessionStart = now;
        this.lastActivity = now;

        this.track(EventCategory.SESSION, 'session_start', {
            sessionId: this.sessionId,
            userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : 'unknown',
            platform: typeof navigator !== 'undefined' ? navigator.platform : 'unknown',
            language: typeof navigator !== 'undefined' ? navigator.language : 'en',
            screenWidth: typeof screen !== 'undefined' ? screen.width : 0,
            screenHeight: typeof screen !== 'undefined' ? screen.height : 0,
        });

        console.log('[Telemetry] Started session:', this.sessionId);
    }

    /**
     * End current session
     */
    _endSession() {
        if (!this.sessionId) return;

        const duration = Date.now() - this.sessionStart;
        this.track(EventCategory.SESSION, 'session_end', {
            sessionId: this.sessionId,
            durationMs: duration,
            durationFormatted: this._formatDuration(duration),
        });

        this.sessionId = null;
        this.sessionStart = null;
    }

    /**
     * Generate unique session ID
     */
    _generateSessionId() {
        return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }

    /**
     * Format duration in human-readable format
     */
    _formatDuration(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);

        if (hours > 0) {
            return `${hours}h ${minutes % 60}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${seconds % 60}s`;
        }
        return `${seconds}s`;
    }

    // ========================================================================
    // EVENT TRACKING
    // ========================================================================

    /**
     * Track an event
     * @param {string} category - Event category
     * @param {string} action - Event action name
     * @param {Object} data - Additional event data
     */
    track(category, action, data = {}) {
        if (!this.enabled) return;

        const event = {
            id: this._generateEventId(),
            sessionId: this.sessionId,
            category,
            action,
            data,
            timestamp: Date.now(),
            timestampIso: new Date().toISOString(),
        };

        this.events.push(event);
        this.lastActivity = Date.now();

        // Update histogram
        this._updateHistogram(category, action);

        // Trim events if over limit
        if (this.events.length > MAX_EVENTS) {
            this.events = this.events.slice(-MAX_EVENTS);
        }

        console.debug('[Telemetry]', category, action, data);
    }

    /**
     * Track a command execution
     * @param {string} command - Command name
     * @param {Object} params - Command parameters
     * @param {boolean} success - Whether command succeeded
     * @param {number} durationMs - Execution duration
     */
    trackCommand(command, params = {}, success = true, durationMs = 0) {
        this.track(EventCategory.COMMAND, command, {
            params: this._sanitizeParams(params),
            success,
            durationMs,
        });

        // Update command frequency histogram
        this.incrementHistogram('commands', command);

        // Track latency percentiles
        if (durationMs > 0) {
            this.recordValue('command_latency', durationMs);
        }
    }

    /**
     * Track voice activation
     * @param {string} action - Voice action (start, end, error)
     * @param {Object} data - Additional data
     */
    trackVoice(action, data = {}) {
        this.track(EventCategory.VOICE, action, data);
        this.incrementHistogram('voice_actions', action);
    }

    /**
     * Track scene execution
     * @param {string} scene - Scene name
     * @param {boolean} success - Whether execution succeeded
     */
    trackScene(scene, success = true) {
        this.track(EventCategory.SCENE, 'execute', { scene, success });
        this.incrementHistogram('scenes', scene);
    }

    /**
     * Track navigation
     * @param {string} from - Source page/view
     * @param {string} to - Destination page/view
     */
    trackNavigation(from, to) {
        this.track(EventCategory.NAVIGATION, 'navigate', { from, to });
        this.incrementHistogram('navigation', `${from} -> ${to}`);
    }

    /**
     * Track feature usage
     * @param {string} feature - Feature name
     * @param {Object} data - Feature-specific data
     */
    trackFeature(feature, data = {}) {
        this.track(EventCategory.FEATURE, feature, data);
        this.incrementHistogram('features', feature);
    }

    /**
     * Track user interaction
     * @param {string} element - UI element name
     * @param {string} action - Interaction type (click, hover, etc.)
     */
    trackInteraction(element, action) {
        this.track(EventCategory.INTERACTION, action, { element });
        this.incrementHistogram('interactions', `${element}:${action}`);
    }

    /**
     * Track error
     * @param {string} error - Error message
     * @param {string} context - Error context
     * @param {Object} data - Additional error data
     */
    trackError(error, context = 'unknown', data = {}) {
        this.track(EventCategory.ERROR, 'error', {
            error: String(error).substring(0, 500),
            context,
            ...data,
        });
        this.incrementHistogram('errors', context);
    }

    /**
     * Track performance metric
     * @param {string} metric - Metric name
     * @param {number} value - Metric value
     * @param {string} unit - Unit of measurement
     */
    trackPerformance(metric, value, unit = 'ms') {
        this.track(EventCategory.PERFORMANCE, metric, { value, unit });
        this.recordValue(`perf_${metric}`, value);
    }

    // ========================================================================
    // HISTOGRAMS
    // ========================================================================

    /**
     * Increment histogram counter
     * @param {string} name - Histogram name
     * @param {string} bucket - Bucket key
     */
    incrementHistogram(name, bucket) {
        if (!this.histograms.has(name)) {
            this.histograms.set(name, new Map());
        }

        const histogram = this.histograms.get(name);

        // Limit buckets to prevent memory issues
        if (histogram.size >= MAX_HISTOGRAM_BUCKETS && !histogram.has(bucket)) {
            // Remove least frequent bucket
            let minKey = null;
            let minValue = Infinity;
            for (const [k, v] of histogram.entries()) {
                if (v < minValue) {
                    minValue = v;
                    minKey = k;
                }
            }
            if (minKey) histogram.delete(minKey);
        }

        histogram.set(bucket, (histogram.get(bucket) || 0) + 1);
    }

    /**
     * Record a numeric value for statistical analysis
     * @param {string} name - Metric name
     * @param {number} value - Value to record
     */
    recordValue(name, value) {
        const key = `_values_${name}`;
        if (!this.histograms.has(key)) {
            this.histograms.set(key, []);
        }

        const values = this.histograms.get(key);
        values.push(value);

        // Keep only last 1000 values
        if (values.length > 1000) {
            values.shift();
        }
    }

    /**
     * Get histogram data
     * @param {string} name - Histogram name
     * @returns {Object} Histogram data as object
     */
    getHistogram(name) {
        const histogram = this.histograms.get(name);
        if (!histogram) return {};

        const result = {};
        for (const [key, value] of histogram.entries()) {
            result[key] = value;
        }
        return result;
    }

    /**
     * Get top N items from histogram
     * @param {string} name - Histogram name
     * @param {number} n - Number of top items
     * @returns {Array} Array of [key, count] pairs
     */
    getTopN(name, n = 10) {
        const histogram = this.histograms.get(name);
        if (!histogram) return [];

        return Array.from(histogram.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, n);
    }

    /**
     * Get statistics for recorded values
     * @param {string} name - Metric name
     * @returns {Object} Statistics (min, max, avg, p50, p90, p99)
     */
    getStatistics(name) {
        const key = `_values_${name}`;
        const values = this.histograms.get(key);
        if (!values || values.length === 0) {
            return { count: 0, min: 0, max: 0, avg: 0, p50: 0, p90: 0, p99: 0 };
        }

        const sorted = [...values].sort((a, b) => a - b);
        const sum = sorted.reduce((a, b) => a + b, 0);

        return {
            count: sorted.length,
            min: sorted[0],
            max: sorted[sorted.length - 1],
            avg: Math.round(sum / sorted.length),
            p50: sorted[Math.floor(sorted.length * 0.5)],
            p90: sorted[Math.floor(sorted.length * 0.9)],
            p99: sorted[Math.floor(sorted.length * 0.99)],
        };
    }

    // ========================================================================
    // ANALYTICS QUERIES
    // ========================================================================

    /**
     * Get events by category
     * @param {string} category - Event category
     * @param {number} limit - Maximum events to return
     * @returns {Array} Events
     */
    getEventsByCategory(category, limit = 100) {
        return this.events
            .filter(e => e.category === category)
            .slice(-limit);
    }

    /**
     * Get events in time range
     * @param {number} startTime - Start timestamp
     * @param {number} endTime - End timestamp
     * @returns {Array} Events
     */
    getEventsInRange(startTime, endTime = Date.now()) {
        return this.events.filter(e =>
            e.timestamp >= startTime && e.timestamp <= endTime
        );
    }

    /**
     * Get command frequency report
     * @returns {Object} Command frequency data
     */
    getCommandReport() {
        return {
            topCommands: this.getTopN('commands', 20),
            totalCommands: this.events.filter(e => e.category === EventCategory.COMMAND).length,
            latencyStats: this.getStatistics('command_latency'),
        };
    }

    /**
     * Get voice usage report
     * @returns {Object} Voice usage data
     */
    getVoiceReport() {
        const voiceEvents = this.events.filter(e => e.category === EventCategory.VOICE);
        const starts = voiceEvents.filter(e => e.action === 'start').length;
        const successes = voiceEvents.filter(e => e.action === 'end' && e.data?.success).length;

        return {
            totalActivations: starts,
            successRate: starts > 0 ? (successes / starts * 100).toFixed(1) + '%' : '0%',
            actionBreakdown: this.getHistogram('voice_actions'),
        };
    }

    /**
     * Get feature usage report
     * @returns {Object} Feature usage data
     */
    getFeatureReport() {
        return {
            topFeatures: this.getTopN('features', 20),
            topScenes: this.getTopN('scenes', 10),
            navigationPaths: this.getTopN('navigation', 10),
        };
    }

    /**
     * Get session analytics
     * @returns {Object} Session data
     */
    getSessionReport() {
        const sessionEvents = this.events.filter(e => e.category === EventCategory.SESSION);
        const ends = sessionEvents.filter(e => e.action === 'session_end');

        const durations = ends.map(e => e.data?.durationMs || 0).filter(d => d > 0);
        const avgDuration = durations.length > 0
            ? durations.reduce((a, b) => a + b, 0) / durations.length
            : 0;

        return {
            currentSession: this.sessionId,
            sessionStart: this.sessionStart ? new Date(this.sessionStart).toISOString() : null,
            currentDuration: this.sessionStart
                ? this._formatDuration(Date.now() - this.sessionStart)
                : null,
            totalSessions: sessionEvents.filter(e => e.action === 'session_start').length,
            averageSessionDuration: this._formatDuration(avgDuration),
        };
    }

    /**
     * Get comprehensive analytics report
     * @returns {Object} Full analytics report
     */
    getFullReport() {
        return {
            generated: new Date().toISOString(),
            session: this.getSessionReport(),
            commands: this.getCommandReport(),
            voice: this.getVoiceReport(),
            features: this.getFeatureReport(),
            errors: {
                count: this.events.filter(e => e.category === EventCategory.ERROR).length,
                topErrors: this.getTopN('errors', 10),
            },
            performance: {
                commandLatency: this.getStatistics('command_latency'),
            },
            totalEvents: this.events.length,
        };
    }

    // ========================================================================
    // PERSISTENCE
    // ========================================================================

    /**
     * Load telemetry data from storage
     */
    _loadFromStorage() {
        try {
            const data = localStorage.getItem(STORAGE_KEY);
            if (data) {
                const parsed = JSON.parse(data);
                this.events = parsed.events || [];
                this.sessionId = parsed.sessionId || null;
                this.sessionStart = parsed.sessionStart || null;
                this.lastActivity = parsed.lastActivity || null;
                this.enabled = parsed.enabled !== false;

                // Restore histograms
                if (parsed.histograms) {
                    for (const [name, hist] of Object.entries(parsed.histograms)) {
                        if (Array.isArray(hist)) {
                            this.histograms.set(name, hist);
                        } else {
                            this.histograms.set(name, new Map(Object.entries(hist)));
                        }
                    }
                }

                console.log('[Telemetry] Loaded', this.events.length, 'events from storage');
            }
        } catch (e) {
            console.warn('[Telemetry] Failed to load from storage:', e);
        }
    }

    /**
     * Save telemetry data to storage
     */
    _saveToStorage() {
        try {
            const histogramsObj = {};
            for (const [name, hist] of this.histograms.entries()) {
                if (hist instanceof Map) {
                    histogramsObj[name] = Object.fromEntries(hist);
                } else {
                    histogramsObj[name] = hist;
                }
            }

            const data = {
                events: this.events,
                histograms: histogramsObj,
                sessionId: this.sessionId,
                sessionStart: this.sessionStart,
                lastActivity: this.lastActivity,
                enabled: this.enabled,
                savedAt: Date.now(),
            };

            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch (e) {
            console.warn('[Telemetry] Failed to save to storage:', e);
        }
    }

    /**
     * Setup periodic flush timer
     */
    _setupFlushTimer() {
        this.flushTimer = setInterval(() => {
            this._saveToStorage();
        }, FLUSH_INTERVAL_MS);

        // Save on page unload
        if (typeof window !== 'undefined') {
            window.addEventListener('beforeunload', () => {
                this._endSession();
                this._saveToStorage();
            });

            window.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'hidden') {
                    this._saveToStorage();
                }
            });
        }
    }

    /**
     * Setup activity tracking for session management
     */
    _setupActivityTracking() {
        if (typeof document === 'undefined') return;

        const updateActivity = () => {
            const now = Date.now();
            const timeSinceActivity = now - (this.lastActivity || 0);

            // Check if session timed out
            if (this.sessionId && timeSinceActivity > SESSION_TIMEOUT_MS) {
                this._startSession(); // This will end old session and start new
            } else {
                this.lastActivity = now;
            }
        };

        // Track user activity
        ['click', 'keydown', 'scroll', 'touchstart'].forEach(event => {
            document.addEventListener(event, updateActivity, { passive: true });
        });
    }

    // ========================================================================
    // UTILITIES
    // ========================================================================

    /**
     * Generate unique event ID
     */
    _generateEventId() {
        return `${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
    }

    /**
     * Sanitize parameters to remove sensitive data
     */
    _sanitizeParams(params) {
        const sanitized = {};
        const sensitiveKeys = ['password', 'token', 'secret', 'key', 'auth', 'credential'];

        for (const [key, value] of Object.entries(params)) {
            const lowerKey = key.toLowerCase();
            if (sensitiveKeys.some(s => lowerKey.includes(s))) {
                sanitized[key] = '[REDACTED]';
            } else if (typeof value === 'object') {
                sanitized[key] = this._sanitizeParams(value);
            } else {
                sanitized[key] = value;
            }
        }

        return sanitized;
    }

    // ========================================================================
    // PUBLIC API
    // ========================================================================

    /**
     * Enable telemetry
     */
    enable() {
        this.enabled = true;
        this._saveToStorage();
        console.log('[Telemetry] Enabled');
    }

    /**
     * Disable telemetry
     */
    disable() {
        this.enabled = false;
        this._saveToStorage();
        console.log('[Telemetry] Disabled');
    }

    /**
     * Clear all telemetry data
     */
    clear() {
        this.events = [];
        this.histograms.clear();
        localStorage.removeItem(STORAGE_KEY);
        console.log('[Telemetry] Cleared all data');
    }

    /**
     * Export telemetry data as JSON
     * @returns {string} JSON string
     */
    export() {
        return JSON.stringify(this.getFullReport(), null, 2);
    }

    /**
     * Destroy the service
     */
    destroy() {
        if (this.flushTimer) {
            clearInterval(this.flushTimer);
        }
        this._endSession();
        this._saveToStorage();
    }
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

const telemetry = new TelemetryService();

// Export for global access
if (typeof window !== 'undefined') {
    window.KagamiTelemetry = telemetry;
}

export { telemetry, TelemetryService, EventCategory };

/*
 * Grove watches. Grove learns. Grove grows.
 *
 */
