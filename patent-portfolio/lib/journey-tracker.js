/**
 * Journey Tracker - Visitor Experience Persistence
 * 
 * Tracks visitor progress, discoveries, preferences, and enables
 * emergent personalized experiences across sessions.
 */

const STORAGE_KEY = 'kagami-museum';
const SAVE_THROTTLE_MS = 5000;  // Save at most every 5 seconds
const MAX_SESSIONS = 10;
const MAX_PATH_LENGTH = 100;

// Colony order for consistency
const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

/**
 * Default journey state for new visitors
 */
function getDefaultState() {
    return {
        // Metadata
        version: 1,
        firstVisit: Date.now(),
        totalVisits: 1,
        totalTimeSeconds: 0,
        
        // Position (restored on return)
        currentPosition: { x: 0, y: 1.6, z: 8 },  // Starting position
        cameraRotation: { x: 0, y: 0 },
        
        // Discovery tracking
        visitedWings: {
            spark: false,
            forge: false,
            flow: false,
            nexus: false,
            beacon: false,
            grove: false,
            crystal: false,
            rotunda: true  // Start here
        },
        viewedPatents: [],
        discoveredSecrets: [],
        
        // Interaction counts
        interactions: {
            click: 0,
            dwell: 0,
            gesture: 0,
            teleport: 0
        },
        
        // Time spent in each wing (seconds)
        wingTime: {
            spark: 0,
            forge: 0,
            flow: 0,
            nexus: 0,
            beacon: 0,
            grove: 0,
            crystal: 0,
            rotunda: 0
        },
        
        // Emergent preferences (computed)
        favoriteWing: null,
        interactionStyle: 'explorer',  // 'explorer' | 'reader' | 'interactor'
        preferredPace: 'medium',       // 'slow' | 'medium' | 'fast'
        
        // Session history
        sessions: [],
        currentSession: {
            start: Date.now(),
            path: ['rotunda'],
            patentsViewed: 0,
            secretsFound: 0
        }
    };
}

/**
 * JourneyTracker class
 */
export class JourneyTracker {
    constructor() {
        this.state = null;
        this.currentZone = 'rotunda';
        this.zoneEntryTime = Date.now();
        this._saveTimeout = null;
        this._lastSaveTime = 0;
        this._listeners = new Map();
        
        this.load();
    }
    
    // ========================================================================
    // PERSISTENCE
    // ========================================================================
    
    /**
     * Load state from localStorage
     */
    load() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                // Merge with defaults to handle new fields
                this.state = {
                    ...getDefaultState(),
                    ...parsed,
                    // Always start a new session
                    currentSession: {
                        start: Date.now(),
                        path: [parsed.currentZone || 'rotunda'],
                        patentsViewed: 0,
                        secretsFound: 0
                    }
                };
                this.state.totalVisits++;
                console.log(`🎫 Welcome back! Visit #${this.state.totalVisits}`);
            } else {
                this.state = getDefaultState();
                console.log('🎫 First visit to the museum');
            }
        } catch (err) {
            console.warn('Journey tracker: failed to load state', err);
            this.state = getDefaultState();
        }
        
        // Restore current zone
        this.currentZone = this.state.currentSession?.path?.slice(-1)[0] || 'rotunda';
        this.zoneEntryTime = Date.now();
    }
    
    /**
     * Save state to localStorage (throttled)
     */
    save() {
        const now = Date.now();
        
        // Clear any pending save
        if (this._saveTimeout) {
            clearTimeout(this._saveTimeout);
            this._saveTimeout = null;
        }
        
        // Throttle saves
        const timeSinceLastSave = now - this._lastSaveTime;
        if (timeSinceLastSave < SAVE_THROTTLE_MS) {
            this._saveTimeout = setTimeout(() => this._doSave(), SAVE_THROTTLE_MS - timeSinceLastSave);
            return;
        }
        
        this._doSave();
    }
    
    _doSave() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
            this._lastSaveTime = Date.now();
        } catch (err) {
            console.warn('Journey tracker: failed to save state', err);
        }
    }
    
    /**
     * Clear all stored data
     */
    clearAll() {
        try {
            localStorage.removeItem(STORAGE_KEY);
            localStorage.removeItem('museum-settings');
            localStorage.removeItem('museum-accessibility');
            this.state = getDefaultState();
            console.log('🗑️ Journey data cleared');
            return true;
        } catch (err) {
            console.warn('Journey tracker: failed to clear data', err);
            return false;
        }
    }
    
    // ========================================================================
    // POSITION TRACKING
    // ========================================================================
    
    /**
     * Update current position (called from render loop, throttled internally)
     */
    updatePosition(camera) {
        if (!camera) return;
        
        this.state.currentPosition = {
            x: Math.round(camera.position.x * 100) / 100,
            y: Math.round(camera.position.y * 100) / 100,
            z: Math.round(camera.position.z * 100) / 100
        };
        
        this.state.cameraRotation = {
            x: Math.round(camera.rotation.x * 100) / 100,
            y: Math.round(camera.rotation.y * 100) / 100
        };
        
        // Determine current zone from position
        this._updateZoneFromPosition(camera.position);
        
        // Throttled save
        this.save();
    }
    
    /**
     * Get saved position for restoring
     */
    getSavedPosition() {
        return {
            position: this.state.currentPosition,
            rotation: this.state.cameraRotation
        };
    }
    
    /**
     * Determine which zone the player is in based on position
     */
    _updateZoneFromPosition(pos) {
        const distFromCenter = Math.sqrt(pos.x * pos.x + pos.z * pos.z);
        
        // In rotunda
        if (distFromCenter < 15) {
            this._setCurrentZone('rotunda');
            return;
        }
        
        // In a wing - determine which one
        const angle = Math.atan2(pos.z, pos.x);
        const normalizedAngle = ((angle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
        const wingIndex = Math.round(normalizedAngle / (Math.PI * 2 / 7)) % 7;
        const colony = COLONY_ORDER[wingIndex];
        
        this._setCurrentZone(colony);
    }
    
    _setCurrentZone(zone) {
        if (zone === this.currentZone) return;
        
        // Record time in previous zone
        const timeInZone = (Date.now() - this.zoneEntryTime) / 1000;
        if (this.currentZone && this.state.wingTime[this.currentZone] !== undefined) {
            this.state.wingTime[this.currentZone] += timeInZone;
        }
        
        // Update current zone
        const previousZone = this.currentZone;
        this.currentZone = zone;
        this.zoneEntryTime = Date.now();
        
        // Mark as visited
        if (this.state.visitedWings[zone] !== undefined) {
            this.state.visitedWings[zone] = true;
        }
        
        // Add to session path (avoid duplicates)
        const path = this.state.currentSession.path;
        if (path[path.length - 1] !== zone) {
            path.push(zone);
            if (path.length > MAX_PATH_LENGTH) {
                path.shift();
            }
        }
        
        // Emit event
        this._emit('zoneChange', { from: previousZone, to: zone });
        
        // Recompute preferences
        this._updatePreferences();
    }
    
    // ========================================================================
    // DISCOVERY TRACKING
    // ========================================================================
    
    /**
     * Record viewing a patent
     */
    viewPatent(patentId) {
        if (!patentId) return;
        
        if (!this.state.viewedPatents.includes(patentId)) {
            this.state.viewedPatents.push(patentId);
            this.state.currentSession.patentsViewed++;
            this._emit('patentViewed', { patentId, total: this.state.viewedPatents.length });
        }
        
        this.save();
    }
    
    /**
     * Check if a patent has been viewed
     */
    hasViewedPatent(patentId) {
        return this.state.viewedPatents.includes(patentId);
    }
    
    /**
     * Record discovering a secret
     */
    discoverSecret(secretId) {
        if (!secretId) return;
        
        if (!this.state.discoveredSecrets.includes(secretId)) {
            this.state.discoveredSecrets.push(secretId);
            this.state.currentSession.secretsFound++;
            this._emit('secretDiscovered', { secretId, total: this.state.discoveredSecrets.length });
            console.log(`✨ Secret discovered: ${secretId}`);
        }
        
        this.save();
    }
    
    /**
     * Check if a secret has been discovered
     */
    hasDiscoveredSecret(secretId) {
        return this.state.discoveredSecrets.includes(secretId);
    }
    
    /**
     * Record an interaction
     */
    recordInteraction(type) {
        if (this.state.interactions[type] !== undefined) {
            this.state.interactions[type]++;
        }
        this._updatePreferences();
        this.save();
    }
    
    // ========================================================================
    // PREFERENCES & PERSONALIZATION
    // ========================================================================
    
    /**
     * Compute emergent preferences from behavior
     */
    _updatePreferences() {
        // Favorite wing (most time spent)
        let maxTime = 0;
        let favorite = null;
        for (const [wing, time] of Object.entries(this.state.wingTime)) {
            if (wing !== 'rotunda' && time > maxTime) {
                maxTime = time;
                favorite = wing;
            }
        }
        this.state.favoriteWing = favorite;
        
        // Interaction style
        const { click, dwell, gesture } = this.state.interactions;
        const total = click + dwell + gesture;
        if (total > 10) {
            if (dwell > click && dwell > gesture) {
                this.state.interactionStyle = 'reader';
            } else if (click > dwell * 2) {
                this.state.interactionStyle = 'interactor';
            } else {
                this.state.interactionStyle = 'explorer';
            }
        }
        
        // Pace (based on session path length vs time)
        const sessionDuration = (Date.now() - this.state.currentSession.start) / 1000;
        const pathLength = this.state.currentSession.path.length;
        if (sessionDuration > 60) {
            const pace = pathLength / (sessionDuration / 60);  // zones per minute
            if (pace < 0.5) {
                this.state.preferredPace = 'slow';
            } else if (pace > 2) {
                this.state.preferredPace = 'fast';
            } else {
                this.state.preferredPace = 'medium';
            }
        }
    }
    
    /**
     * Get personalization hints for UI
     */
    getPersonalization() {
        return {
            favoriteWing: this.state.favoriteWing,
            interactionStyle: this.state.interactionStyle,
            preferredPace: this.state.preferredPace,
            isReturningVisitor: this.state.totalVisits > 1,
            discoveryCount: this.state.discoveredSecrets.length,
            patentsViewed: this.state.viewedPatents.length,
            totalPatents: 54,
            completionPercent: Math.round((this.state.viewedPatents.length / 54) * 100),
            visitedWingCount: Object.values(this.state.visitedWings).filter(v => v).length,
            totalWings: 8  // Including rotunda
        };
    }
    
    /**
     * Get exploration progress per wing
     */
    getWingProgress() {
        // Patent distribution per wing (approximate)
        const patentsPerWing = {
            spark: 8,
            forge: 8,
            flow: 7,
            nexus: 8,
            beacon: 8,
            grove: 8,
            crystal: 7
        };
        
        const progress = {};
        for (const wing of COLONY_ORDER) {
            const wingPatents = this.state.viewedPatents.filter(id => {
                // Simple heuristic: patent wing from ID or random assignment
                return id.includes(wing.charAt(0).toUpperCase());
            });
            progress[wing] = {
                visited: this.state.visitedWings[wing],
                timeSpent: Math.round(this.state.wingTime[wing]),
                patentsViewed: wingPatents.length,
                totalPatents: patentsPerWing[wing],
                percent: Math.round((wingPatents.length / patentsPerWing[wing]) * 100)
            };
        }
        return progress;
    }
    
    // ========================================================================
    // SESSION MANAGEMENT
    // ========================================================================
    
    /**
     * End current session (call on page unload)
     */
    endSession() {
        // Record time in current zone
        const timeInZone = (Date.now() - this.zoneEntryTime) / 1000;
        if (this.currentZone && this.state.wingTime[this.currentZone] !== undefined) {
            this.state.wingTime[this.currentZone] += timeInZone;
        }
        
        // Update total time
        const sessionDuration = (Date.now() - this.state.currentSession.start) / 1000;
        this.state.totalTimeSeconds += sessionDuration;
        
        // Save session to history
        this.state.sessions.push({
            start: this.state.currentSession.start,
            end: Date.now(),
            duration: Math.round(sessionDuration),
            path: this.state.currentSession.path.slice(0, 20),  // Truncate for storage
            patentsViewed: this.state.currentSession.patentsViewed,
            secretsFound: this.state.currentSession.secretsFound
        });
        
        // Keep only last N sessions
        if (this.state.sessions.length > MAX_SESSIONS) {
            this.state.sessions = this.state.sessions.slice(-MAX_SESSIONS);
        }
        
        // Force save
        this._doSave();
    }
    
    /**
     * Get journey statistics
     */
    getStats() {
        return {
            totalVisits: this.state.totalVisits,
            totalTime: formatDuration(this.state.totalTimeSeconds),
            firstVisit: new Date(this.state.firstVisit).toLocaleDateString(),
            patentsViewed: this.state.viewedPatents.length,
            secretsDiscovered: this.state.discoveredSecrets.length,
            wingsExplored: Object.values(this.state.visitedWings).filter(v => v).length,
            favoriteWing: this.state.favoriteWing,
            interactionStyle: this.state.interactionStyle
        };
    }
    
    // ========================================================================
    // EVENTS
    // ========================================================================
    
    /**
     * Subscribe to journey events
     */
    on(event, callback) {
        if (!this._listeners.has(event)) {
            this._listeners.set(event, []);
        }
        this._listeners.get(event).push(callback);
    }
    
    /**
     * Unsubscribe from journey events
     */
    off(event, callback) {
        const listeners = this._listeners.get(event);
        if (listeners) {
            const idx = listeners.indexOf(callback);
            if (idx >= 0) listeners.splice(idx, 1);
        }
    }
    
    _emit(event, data) {
        const listeners = this._listeners.get(event);
        if (listeners) {
            listeners.forEach(cb => {
                try {
                    cb(data);
                } catch (err) {
                    console.warn(`Journey event handler error (${event}):`, err);
                }
            });
        }
    }
}

// ============================================================================
// UTILITIES
// ============================================================================

function formatDuration(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    const hours = Math.floor(seconds / 3600);
    const mins = Math.round((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
}

// ============================================================================
// SINGLETON INSTANCE
// ============================================================================

let instance = null;

export function getJourneyTracker() {
    if (!instance) {
        instance = new JourneyTracker();
        
        // Save on page unload
        window.addEventListener('beforeunload', () => {
            instance.endSession();
        });
        
        // Also save on visibility change (mobile)
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') {
                instance._doSave();
            }
        });
    }
    return instance;
}

export default JourneyTracker;
