/**
 * Museum State Machine
 * ====================
 * 
 * Formal state management for the Patent Museum:
 * - Application state tracking (loading, exploring, viewing, menu, etc.)
 * - Error recovery with exponential backoff
 * - Memory management and cleanup
 * - Event-driven state transitions
 * - Undo/redo capability for navigation
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// STATE DEFINITIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Application States
 */
export const AppState = {
    INITIALIZING: 'initializing',
    LOADING: 'loading',
    READY: 'ready',
    EXPLORING: 'exploring',
    VIEWING_ARTWORK: 'viewing_artwork',
    MENU_OPEN: 'menu_open',
    XR_SESSION: 'xr_session',
    ERROR: 'error',
    PAUSED: 'paused'
};

/**
 * Valid state transitions
 */
const STATE_TRANSITIONS = {
    [AppState.INITIALIZING]: [AppState.LOADING, AppState.ERROR],
    [AppState.LOADING]: [AppState.READY, AppState.ERROR],
    [AppState.READY]: [AppState.EXPLORING, AppState.ERROR],
    [AppState.EXPLORING]: [
        AppState.VIEWING_ARTWORK, 
        AppState.MENU_OPEN, 
        AppState.XR_SESSION, 
        AppState.PAUSED,
        AppState.ERROR
    ],
    [AppState.VIEWING_ARTWORK]: [
        AppState.EXPLORING, 
        AppState.MENU_OPEN, 
        AppState.PAUSED,
        AppState.ERROR
    ],
    [AppState.MENU_OPEN]: [
        AppState.EXPLORING, 
        AppState.VIEWING_ARTWORK, 
        AppState.PAUSED,
        AppState.ERROR
    ],
    [AppState.XR_SESSION]: [AppState.EXPLORING, AppState.ERROR],
    [AppState.ERROR]: [AppState.LOADING, AppState.READY, AppState.EXPLORING],
    [AppState.PAUSED]: [AppState.EXPLORING, AppState.VIEWING_ARTWORK, AppState.MENU_OPEN]
};

// ═══════════════════════════════════════════════════════════════════════════
// ERROR TYPES
// ═══════════════════════════════════════════════════════════════════════════

export const ErrorType = {
    INITIALIZATION: 'initialization',
    RESOURCE_LOAD: 'resource_load',
    WEBGL_CONTEXT_LOST: 'webgl_context_lost',
    XR_SESSION_ERROR: 'xr_session_error',
    MEMORY_PRESSURE: 'memory_pressure',
    AUDIO_ERROR: 'audio_error',
    NETWORK_ERROR: 'network_error',
    UNKNOWN: 'unknown'
};

/**
 * Error recovery strategies
 */
const ERROR_RECOVERY = {
    [ErrorType.INITIALIZATION]: {
        maxRetries: 3,
        baseDelay: 1000,
        strategy: 'exponential_backoff',
        fallback: 'show_error_screen'
    },
    [ErrorType.RESOURCE_LOAD]: {
        maxRetries: 5,
        baseDelay: 500,
        strategy: 'exponential_backoff',
        fallback: 'use_placeholder'
    },
    [ErrorType.WEBGL_CONTEXT_LOST]: {
        maxRetries: 2,
        baseDelay: 2000,
        strategy: 'full_reinit',
        fallback: 'show_error_screen'
    },
    [ErrorType.XR_SESSION_ERROR]: {
        maxRetries: 2,
        baseDelay: 1000,
        strategy: 'graceful_exit',
        fallback: 'continue_desktop'
    },
    [ErrorType.MEMORY_PRESSURE]: {
        maxRetries: 1,
        baseDelay: 0,
        strategy: 'reduce_quality',
        fallback: 'emergency_cleanup'
    },
    [ErrorType.AUDIO_ERROR]: {
        maxRetries: 3,
        baseDelay: 500,
        strategy: 'reinit_audio',
        fallback: 'disable_audio'
    },
    [ErrorType.NETWORK_ERROR]: {
        maxRetries: 3,
        baseDelay: 2000,
        strategy: 'exponential_backoff',
        fallback: 'offline_mode'
    },
    [ErrorType.UNKNOWN]: {
        maxRetries: 1,
        baseDelay: 1000,
        strategy: 'log_and_continue',
        fallback: 'show_error_screen'
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// STATE MACHINE CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class MuseumStateMachine {
    constructor() {
        this.currentState = AppState.INITIALIZING;
        this.previousState = null;
        this.stateHistory = [];
        this.maxHistorySize = 50;
        
        // Event listeners
        this.listeners = new Map();
        
        // Error tracking
        this.errorCounts = new Map();
        this.lastError = null;
        this.isRecovering = false;
        
        // State data storage
        this.stateData = new Map();
        
        // Performance tracking
        this.stateStartTime = performance.now();
        this.stateDurations = new Map();
        
        // Memory management
        this.disposables = new Set();
        this.memoryCheckInterval = null;
        this.memoryThreshold = 0.9; // 90% memory usage triggers cleanup
        
        this.init();
    }
    
    init() {
        // Start memory monitoring
        this.startMemoryMonitoring();
        
        // Listen for page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.pause();
            } else {
                this.resume();
            }
        });
        
        // Handle page unload
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // STATE MANAGEMENT
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Transition to a new state
     * @param {string} newState - Target state
     * @param {object} data - Optional state data
     * @returns {boolean} - Whether transition was successful
     */
    transition(newState, data = {}) {
        // Validate transition
        const allowedTransitions = STATE_TRANSITIONS[this.currentState];
        if (!allowedTransitions || !allowedTransitions.includes(newState)) {
            console.warn(`Invalid state transition: ${this.currentState} → ${newState}`);
            return false;
        }
        
        // Record state duration
        const duration = performance.now() - this.stateStartTime;
        this.stateDurations.set(this.currentState, 
            (this.stateDurations.get(this.currentState) || 0) + duration
        );
        
        // Save to history
        this.stateHistory.push({
            from: this.currentState,
            to: newState,
            timestamp: Date.now(),
            data: { ...data }
        });
        
        // Trim history if needed
        if (this.stateHistory.length > this.maxHistorySize) {
            this.stateHistory = this.stateHistory.slice(-this.maxHistorySize);
        }
        
        // Update state
        this.previousState = this.currentState;
        this.currentState = newState;
        this.stateStartTime = performance.now();
        
        // Store state data
        this.stateData.set(newState, data);
        
        // Emit transition event
        this.emit('stateChange', {
            from: this.previousState,
            to: newState,
            data
        });
        
        // State-specific handlers
        this.onStateEnter(newState, data);
        
        return true;
    }
    
    /**
     * Handle state entry
     */
    onStateEnter(state, data) {
        switch (state) {
            case AppState.ERROR:
                this.handleError(data.error, data.type);
                break;
            case AppState.PAUSED:
                this.onPause();
                break;
            case AppState.XR_SESSION:
                this.onXRSessionStart(data);
                break;
            case AppState.VIEWING_ARTWORK:
                this.onArtworkFocus(data.artwork);
                break;
        }
    }
    
    /**
     * Get current state
     */
    getState() {
        return this.currentState;
    }
    
    /**
     * Get state data
     */
    getStateData(state = this.currentState) {
        return this.stateData.get(state);
    }
    
    /**
     * Check if in specific state
     */
    isInState(state) {
        return this.currentState === state;
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // ERROR HANDLING
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Report and handle an error
     */
    handleError(error, type = ErrorType.UNKNOWN) {
        console.error(`Museum Error [${type}]:`, error);
        
        this.lastError = { error, type, timestamp: Date.now() };
        
        // Track error counts
        const count = (this.errorCounts.get(type) || 0) + 1;
        this.errorCounts.set(type, count);
        
        // Get recovery strategy
        const recovery = ERROR_RECOVERY[type] || ERROR_RECOVERY[ErrorType.UNKNOWN];
        
        // Attempt recovery
        if (count <= recovery.maxRetries && !this.isRecovering) {
            this.attemptRecovery(type, recovery, count);
        } else {
            this.executeFallback(type, recovery.fallback);
        }
        
        // Emit error event
        this.emit('error', { error, type, count });
    }
    
    /**
     * Attempt to recover from error
     */
    async attemptRecovery(type, recovery, attemptNumber) {
        this.isRecovering = true;
        
        // Calculate delay with exponential backoff
        const delay = recovery.strategy === 'exponential_backoff'
            ? recovery.baseDelay * Math.pow(2, attemptNumber - 1)
            : recovery.baseDelay;
        
        console.log(`Attempting recovery for ${type} (attempt ${attemptNumber}/${recovery.maxRetries}) in ${delay}ms`);
        
        await this.sleep(delay);
        
        try {
            switch (recovery.strategy) {
                case 'exponential_backoff':
                    this.emit('retryOperation', { type, attempt: attemptNumber });
                    break;
                    
                case 'full_reinit':
                    this.emit('reinitialize', { type });
                    break;
                    
                case 'graceful_exit':
                    this.emit('gracefulExit', { type });
                    break;
                    
                case 'reduce_quality':
                    this.emit('reduceQuality', { type });
                    break;
                    
                case 'reinit_audio':
                    this.emit('reinitAudio', { type });
                    break;
                    
                case 'log_and_continue':
                    // Just log and hope for the best
                    break;
            }
            
            // If we get here, recovery might have worked
            // Transition back to appropriate state
            if (this.previousState && this.previousState !== AppState.ERROR) {
                this.transition(this.previousState);
            } else {
                this.transition(AppState.EXPLORING);
            }
            
        } catch (e) {
            console.error('Recovery failed:', e);
            this.handleError(e, type);
        } finally {
            this.isRecovering = false;
        }
    }
    
    /**
     * Execute fallback when recovery fails
     */
    executeFallback(type, fallback) {
        console.warn(`Executing fallback for ${type}: ${fallback}`);
        
        switch (fallback) {
            case 'show_error_screen':
                this.emit('showErrorScreen', { type, error: this.lastError });
                break;
                
            case 'use_placeholder':
                this.emit('usePlaceholder', { type });
                break;
                
            case 'continue_desktop':
                this.transition(AppState.EXPLORING);
                break;
                
            case 'emergency_cleanup':
                this.emergencyCleanup();
                break;
                
            case 'disable_audio':
                this.emit('disableAudio', {});
                break;
                
            case 'offline_mode':
                this.emit('enableOfflineMode', {});
                break;
        }
    }
    
    /**
     * Reset error counts for a type
     */
    resetErrorCount(type) {
        this.errorCounts.set(type, 0);
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // MEMORY MANAGEMENT
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Register a disposable resource
     */
    registerDisposable(resource, metadata = {}) {
        this.disposables.add({
            resource,
            metadata,
            timestamp: Date.now()
        });
    }
    
    /**
     * Unregister a disposable resource
     */
    unregisterDisposable(resource) {
        for (const item of this.disposables) {
            if (item.resource === resource) {
                this.disposables.delete(item);
                break;
            }
        }
    }
    
    /**
     * Dispose a specific resource
     */
    disposeResource(resource) {
        if (!resource) return;
        
        try {
            if (typeof resource.dispose === 'function') {
                resource.dispose();
            } else if (resource instanceof THREE.Object3D) {
                this.disposeObject3D(resource);
            } else if (resource instanceof THREE.Material) {
                this.disposeMaterial(resource);
            } else if (resource instanceof THREE.Texture) {
                resource.dispose();
            } else if (resource instanceof THREE.BufferGeometry) {
                resource.dispose();
            }
            
            this.unregisterDisposable(resource);
        } catch (e) {
            console.warn('Error disposing resource:', e);
        }
    }
    
    /**
     * Recursively dispose a Three.js Object3D
     */
    disposeObject3D(object) {
        object.traverse((child) => {
            if (child.geometry) {
                child.geometry.dispose();
            }
            
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach(mat => this.disposeMaterial(mat));
                } else {
                    this.disposeMaterial(child.material);
                }
            }
        });
        
        if (object.parent) {
            object.parent.remove(object);
        }
    }
    
    /**
     * Dispose a material and its textures
     */
    disposeMaterial(material) {
        if (!material) return;
        
        // Dispose textures
        const textureProps = [
            'map', 'normalMap', 'roughnessMap', 'metalnessMap',
            'emissiveMap', 'envMap', 'alphaMap', 'aoMap',
            'bumpMap', 'displacementMap', 'lightMap'
        ];
        
        textureProps.forEach(prop => {
            if (material[prop]) {
                material[prop].dispose();
            }
        });
        
        material.dispose();
    }
    
    /**
     * Start memory monitoring
     */
    startMemoryMonitoring() {
        // Check memory every 30 seconds
        this.memoryCheckInterval = setInterval(() => {
            this.checkMemory();
        }, 30000);
    }
    
    /**
     * Check memory usage and trigger cleanup if needed
     */
    checkMemory() {
        if (!performance.memory) return; // Not available in all browsers
        
        const usage = performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit;
        
        if (usage > this.memoryThreshold) {
            console.warn(`Memory pressure detected: ${(usage * 100).toFixed(1)}% usage`);
            this.handleError(new Error('High memory usage'), ErrorType.MEMORY_PRESSURE);
        }
        
        this.emit('memoryCheck', {
            usage,
            used: performance.memory.usedJSHeapSize,
            total: performance.memory.jsHeapSizeLimit
        });
    }
    
    /**
     * Emergency cleanup when memory is critically low
     */
    emergencyCleanup() {
        console.warn('Emergency cleanup triggered');
        
        // Dispose oldest resources first
        const sortedDisposables = Array.from(this.disposables)
            .sort((a, b) => a.timestamp - b.timestamp);
        
        // Dispose up to 30% of resources
        const toDispose = Math.ceil(sortedDisposables.length * 0.3);
        
        for (let i = 0; i < toDispose; i++) {
            this.disposeResource(sortedDisposables[i].resource);
        }
        
        // Force garbage collection hint
        if (window.gc) {
            window.gc();
        }
        
        this.emit('emergencyCleanup', { disposed: toDispose });
    }
    
    /**
     * Full cleanup on shutdown
     */
    cleanup() {
        console.log('Museum state machine cleanup');
        
        // Stop memory monitoring
        if (this.memoryCheckInterval) {
            clearInterval(this.memoryCheckInterval);
        }
        
        // Dispose all registered resources
        for (const item of this.disposables) {
            this.disposeResource(item.resource);
        }
        this.disposables.clear();
        
        // Clear state data
        this.stateData.clear();
        this.stateHistory = [];
        this.errorCounts.clear();
        
        // Remove all listeners
        this.listeners.clear();
        
        this.emit('cleanup', {});
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // PAUSE / RESUME
    // ─────────────────────────────────────────────────────────────────────────
    
    pause() {
        if (this.currentState !== AppState.PAUSED) {
            this.transition(AppState.PAUSED);
        }
    }
    
    resume() {
        if (this.currentState === AppState.PAUSED && this.previousState) {
            this.transition(this.previousState);
        }
    }
    
    onPause() {
        this.emit('pause', {});
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // XR HANDLING
    // ─────────────────────────────────────────────────────────────────────────
    
    onXRSessionStart(data) {
        this.emit('xrSessionStart', data);
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // ARTWORK HANDLING
    // ─────────────────────────────────────────────────────────────────────────
    
    onArtworkFocus(artwork) {
        this.emit('artworkFocus', { artwork });
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // EVENT SYSTEM
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Subscribe to an event
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        
        // Return unsubscribe function
        return () => this.off(event, callback);
    }
    
    /**
     * Unsubscribe from an event
     */
    off(event, callback) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.delete(callback);
        }
    }
    
    /**
     * Emit an event
     */
    emit(event, data) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.forEach(callback => {
                try {
                    callback(data);
                } catch (e) {
                    console.error(`Error in event listener for ${event}:`, e);
                }
            });
        }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // NAVIGATION HISTORY
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Navigate to a location
     */
    navigateTo(location, data = {}) {
        this.emit('navigate', { location, data });
    }
    
    /**
     * Go back in navigation history
     */
    goBack() {
        // Find last navigation event
        for (let i = this.stateHistory.length - 1; i >= 0; i--) {
            const entry = this.stateHistory[i];
            if (entry.data?.location && entry.from === AppState.EXPLORING) {
                this.emit('navigateBack', entry.data);
                return true;
            }
        }
        return false;
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // DIAGNOSTICS
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Get diagnostic information
     */
    getDiagnostics() {
        const totalDuration = Array.from(this.stateDurations.values()).reduce((a, b) => a + b, 0);
        
        return {
            currentState: this.currentState,
            previousState: this.previousState,
            historyLength: this.stateHistory.length,
            errorCounts: Object.fromEntries(this.errorCounts),
            lastError: this.lastError,
            isRecovering: this.isRecovering,
            disposablesCount: this.disposables.size,
            stateDurations: Object.fromEntries(this.stateDurations),
            totalUptime: totalDuration,
            memoryUsage: performance.memory ? {
                used: performance.memory.usedJSHeapSize,
                total: performance.memory.jsHeapSizeLimit,
                percentage: (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit * 100).toFixed(1) + '%'
            } : 'not available'
        };
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // UTILITIES
    // ─────────────────────────────────────────────────────────────────────────
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SINGLETON INSTANCE
// ═══════════════════════════════════════════════════════════════════════════

let instance = null;

export function getStateMachine() {
    if (!instance) {
        instance = new MuseumStateMachine();
    }
    return instance;
}

export function resetStateMachine() {
    if (instance) {
        instance.cleanup();
        instance = null;
    }
}

export default {
    AppState,
    ErrorType,
    MuseumStateMachine,
    getStateMachine,
    resetStateMachine
};
