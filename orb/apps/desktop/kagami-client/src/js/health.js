/**
 * 鏡 Kagami — Health Data Integration
 *
 * Focus:
 *
 * Provides health data from:
 * - Apple Watch (via HealthKit → Kagami API)
 * - Android (via Health Connect → Kagami API)
 * - Local cache (when offline)
 *
 * η → s → μ → a → η′
 */

const { invoke } = window.__TAURI__.core;

/**
 * Health metrics structure
 * @typedef {Object} HealthMetrics
 * @property {number|null} heart_rate - Current heart rate (BPM)
 * @property {number|null} resting_heart_rate - Resting heart rate (BPM)
 * @property {number|null} hrv - Heart rate variability (ms)
 * @property {number|null} steps - Steps today
 * @property {number|null} active_calories - Active calories burned
 * @property {number|null} exercise_minutes - Exercise minutes today
 * @property {number|null} blood_oxygen - Blood oxygen percentage
 * @property {number|null} sleep_hours - Sleep duration (hours)
 */

/**
 * Health service for the Kagami client
 */
class HealthService {
    constructor() {
        this.metrics = null;
        this.lastFetch = null;
        this.listeners = new Set();
        this.pollInterval = null;
        this.pollIntervalMs = 30000; // 30 seconds
    }

    /**
     * Check if native health API is available on this platform
     * @returns {Promise<boolean>}
     */
    async isAvailable() {
        try {
            return await invoke('health_available');
        } catch (e) {
            console.warn('Health availability check failed:', e);
            return false;
        }
    }

    /**
     * Get the platform's health API name
     * @returns {Promise<string>}
     */
    async getPlatformName() {
        try {
            return await invoke('health_platform_name');
        } catch (e) {
            return 'Unknown';
        }
    }

    /**
     * Check if health is authorized
     * @returns {Promise<boolean>}
     */
    async isAuthorized() {
        try {
            return await invoke('is_health_authorized');
        } catch (e) {
            return false;
        }
    }

    /**
     * Fetch current health metrics from Kagami API
     * @returns {Promise<HealthMetrics>}
     */
    async fetchMetrics() {
        try {
            this.metrics = await invoke('fetch_health_status');
            this.lastFetch = new Date();
            this.notifyListeners();
            return this.metrics;
        } catch (e) {
            console.warn('Failed to fetch health metrics:', e);
            return this.metrics || {};
        }
    }

    /**
     * Get cached health metrics (from local state)
     * @returns {Promise<HealthMetrics>}
     */
    async getCachedMetrics() {
        try {
            return await invoke('get_health_metrics');
        } catch (e) {
            return this.metrics || {};
        }
    }

    /**
     * Sync health data to Kagami API
     * @param {HealthMetrics} metrics
     * @returns {Promise<void>}
     */
    async syncMetrics(metrics) {
        try {
            await invoke('sync_health_data', { metrics });
            this.metrics = metrics;
            this.notifyListeners();
        } catch (e) {
            console.error('Failed to sync health metrics:', e);
            throw e;
        }
    }

    /**
     * Start polling for health updates
     * @param {number} intervalMs - Poll interval in milliseconds (default 30s)
     */
    startPolling(intervalMs = 30000) {
        this.pollIntervalMs = intervalMs;
        this.stopPolling(); // Clear any existing interval

        // Initial fetch
        this.fetchMetrics();

        // Set up polling
        this.pollInterval = setInterval(() => {
            this.fetchMetrics();
        }, this.pollIntervalMs);

        console.log(`✅ Health polling started (${intervalMs}ms interval)`);
    }

    /**
     * Stop polling for health updates
     */
    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
            console.log('Health polling stopped');
        }
    }

    /**
     * Add a listener for health data changes
     * @param {function(HealthMetrics): void} callback
     */
    addListener(callback) {
        this.listeners.add(callback);
    }

    /**
     * Remove a listener
     * @param {function(HealthMetrics): void} callback
     */
    removeListener(callback) {
        this.listeners.delete(callback);
    }

    /**
     * Notify all listeners of data change
     */
    notifyListeners() {
        for (const listener of this.listeners) {
            try {
                listener(this.metrics);
            } catch (e) {
                console.error('Health listener error:', e);
            }
        }
    }

    /**
     * Get a formatted summary of health metrics
     * @returns {string}
     */
    getSummary() {
        if (!this.metrics) return 'No health data';

        const parts = [];

        if (this.metrics.heart_rate) {
            parts.push(`❤️ ${Math.round(this.metrics.heart_rate)} BPM`);
        }

        if (this.metrics.steps) {
            parts.push(`👟 ${this.metrics.steps.toLocaleString()} steps`);
        }

        if (this.metrics.active_calories) {
            parts.push(`🔥 ${this.metrics.active_calories} kcal`);
        }

        if (this.metrics.sleep_hours) {
            const hours = Math.floor(this.metrics.sleep_hours);
            const mins = Math.round((this.metrics.sleep_hours - hours) * 60);
            parts.push(`😴 ${hours}h ${mins}m`);
        }

        return parts.length > 0 ? parts.join(' • ') : 'No metrics available';
    }

    /**
     * Get health score based on metrics
     * @returns {number} 0-100 score
     */
    getHealthScore() {
        if (!this.metrics) return 50;

        let score = 50; // Base score

        // Heart rate in healthy range (50-90 for resting)
        if (this.metrics.resting_heart_rate) {
            const rhr = this.metrics.resting_heart_rate;
            if (rhr >= 50 && rhr <= 70) score += 10;
            else if (rhr >= 40 && rhr <= 90) score += 5;
        }

        // HRV bonus (higher is generally better)
        if (this.metrics.hrv && this.metrics.hrv > 40) {
            score += 10;
        }

        // Steps bonus
        if (this.metrics.steps) {
            if (this.metrics.steps >= 10000) score += 15;
            else if (this.metrics.steps >= 5000) score += 10;
            else if (this.metrics.steps >= 2000) score += 5;
        }

        // Sleep bonus (7-9 hours ideal)
        if (this.metrics.sleep_hours) {
            if (this.metrics.sleep_hours >= 7 && this.metrics.sleep_hours <= 9) score += 15;
            else if (this.metrics.sleep_hours >= 6) score += 10;
        }

        // Blood oxygen (normal is 95-100)
        if (this.metrics.blood_oxygen && this.metrics.blood_oxygen >= 95) {
            score += 5;
        }

        return Math.min(100, Math.max(0, score));
    }
}

// Singleton instance
const healthService = new HealthService();

// Auto-start polling when module loads (if in Tauri context)
if (window.__TAURI__) {
    healthService.startPolling();
}

export { healthService, HealthService };

/*
 * 鏡
 *
 */
