/**
 * Kagami Sound System — Composable Audio for Web
 * 
 * A cross-platform sound library using Web Audio API for guaranteed playback.
 * Works on desktop, mobile, and embedded contexts.
 * 
 * Features:
 * - Web Audio API for precise timing and reliable playback
 * - Automatic AudioContext unlock on first user gesture
 * - Polyphonic playback (multiple sounds simultaneously)
 * - Volume control per-sound and master
 * - Spatial panning support
 * - Preloading with progress callbacks
 * 
 * Usage:
 * ```javascript
 * const sounds = new KagamiSounds({
 *   basePath: './sounds/',
 *   sounds: {
 *     hover: { file: 'hover.mp3', volume: 0.4 },
 *     click: { file: 'click.mp3', volume: 0.5 },
 *   }
 * });
 * 
 * await sounds.init();
 * sounds.play('hover');
 * ```
 * 
 * @author Kagami (鏡)
 * @version 1.0.0
 * @license MIT
 */

class KagamiSounds {
    constructor(config = {}) {
        this.config = {
            basePath: config.basePath || './',
            sounds: config.sounds || {},
            masterVolume: config.masterVolume ?? 0.8,
            debug: config.debug ?? false,
        };
        
        this.audioContext = null;
        this.buffers = new Map();
        this.gainNodes = new Map();
        this.masterGain = null;
        this.unlocked = false;
        this.muted = false;
        this.initialized = false;
        
        // Bind methods
        this._unlock = this._unlock.bind(this);
    }
    
    /**
     * Initialize the sound system.
     * Call this before playing any sounds.
     */
    async init() {
        if (this.initialized) return this;
        
        // Create AudioContext
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) {
            console.warn('KagamiSounds: Web Audio API not supported');
            return this;
        }
        
        this.audioContext = new AudioContextClass();
        
        // Create master gain
        this.masterGain = this.audioContext.createGain();
        this.masterGain.gain.value = this.config.masterVolume;
        this.masterGain.connect(this.audioContext.destination);
        
        // Setup unlock listeners for iOS/Safari
        this._setupUnlock();
        
        // Preload all sounds
        await this._preloadAll();
        
        this.initialized = true;
        this._log('Sound system initialized');
        
        return this;
    }
    
    /**
     * Play a sound by name.
     * @param {string} name - Sound name from config
     * @param {object} options - Optional overrides { volume, pan, rate }
     * @returns {object} Control object with stop() method
     */
    play(name, options = {}) {
        if (!this.initialized || this.muted) return { stop: () => {} };
        
        const soundConfig = this.config.sounds[name];
        if (!soundConfig) {
            this._log(`Sound not found: ${name}`, 'warn');
            return { stop: () => {} };
        }
        
        const buffer = this.buffers.get(name);
        if (!buffer) {
            this._log(`Buffer not loaded: ${name}`, 'warn');
            return { stop: () => {} };
        }
        
        // Resume context if suspended (iOS requirement)
        if (this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
        
        // Create nodes
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.playbackRate.value = options.rate ?? soundConfig.rate ?? 1.0;
        
        // Create gain for this instance
        const gain = this.audioContext.createGain();
        gain.gain.value = options.volume ?? soundConfig.volume ?? 1.0;
        
        // Create panner if needed
        let lastNode = gain;
        if (options.pan !== undefined || soundConfig.pan !== undefined) {
            const panner = this.audioContext.createStereoPanner();
            panner.pan.value = options.pan ?? soundConfig.pan ?? 0;
            gain.connect(panner);
            lastNode = panner;
        }
        
        // Connect chain
        source.connect(gain);
        lastNode.connect(this.masterGain);
        
        // Play
        source.start(0);
        
        this._log(`Playing: ${name}`);
        
        return {
            source,
            stop: () => {
                try {
                    source.stop();
                } catch (e) {
                    // Already stopped
                }
            }
        };
    }
    
    /**
     * Toggle mute state.
     * @returns {boolean} New muted state
     */
    toggleMute() {
        this.muted = !this.muted;
        if (this.masterGain) {
            this.masterGain.gain.value = this.muted ? 0 : this.config.masterVolume;
        }
        this._log(`Muted: ${this.muted}`);
        return this.muted;
    }
    
    /**
     * Set master volume.
     * @param {number} volume - 0.0 to 1.0
     */
    setVolume(volume) {
        this.config.masterVolume = Math.max(0, Math.min(1, volume));
        if (this.masterGain && !this.muted) {
            this.masterGain.gain.value = this.config.masterVolume;
        }
    }
    
    /**
     * Check if sound system is ready.
     */
    get ready() {
        return this.initialized && this.unlocked;
    }
    
    // === Private Methods ===
    
    async _preloadAll() {
        const loadPromises = Object.entries(this.config.sounds).map(
            async ([name, config]) => {
                try {
                    let arrayBuffer;
                    
                    // Check for embedded data URI first (SOUND_DATA global)
                    if (typeof SOUND_DATA !== 'undefined' && SOUND_DATA[name]) {
                        const dataUri = SOUND_DATA[name];
                        const base64 = dataUri.split(',')[1];
                        const binary = atob(base64);
                        const bytes = new Uint8Array(binary.length);
                        for (let i = 0; i < binary.length; i++) {
                            bytes[i] = binary.charCodeAt(i);
                        }
                        arrayBuffer = bytes.buffer;
                        this._log(`Loading ${name} from embedded data`);
                    } else {
                        // Fall back to fetch
                        const url = this.config.basePath + (config.file || `${name}.mp3`);
                        const response = await fetch(url);
                        if (!response.ok) throw new Error(`HTTP ${response.status}`);
                        arrayBuffer = await response.arrayBuffer();
                    }
                    
                    const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
                    this.buffers.set(name, audioBuffer);
                    this._log(`Loaded: ${name} (${audioBuffer.duration.toFixed(2)}s)`);
                } catch (e) {
                    this._log(`Failed to load ${name}: ${e.message}`, 'error');
                }
            }
        );
        
        await Promise.all(loadPromises);
        this._log(`Preloaded ${this.buffers.size}/${Object.keys(this.config.sounds).length} sounds`);
    }
    
    _setupUnlock() {
        // iOS and Safari require user gesture to unlock AudioContext
        const events = ['touchstart', 'touchend', 'mousedown', 'keydown', 'click'];
        events.forEach(event => {
            document.addEventListener(event, this._unlock, { once: false, passive: true });
        });
    }
    
    _unlock() {
        if (this.unlocked) return;
        
        if (this.audioContext && this.audioContext.state === 'suspended') {
            this.audioContext.resume().then(() => {
                this.unlocked = true;
                this._log('AudioContext unlocked');
                
                // Remove listeners
                ['touchstart', 'touchend', 'mousedown', 'keydown', 'click'].forEach(event => {
                    document.removeEventListener(event, this._unlock);
                });
            });
        } else {
            this.unlocked = true;
        }
    }
    
    _log(msg, level = 'log') {
        if (this.config.debug || level === 'error') {
            console[level](`🎵 KagamiSounds: ${msg}`);
        }
    }
}

/**
 * Create a pre-configured instance for the /art/ directory.
 * This is the main export for quick use.
 */
function createKagamiSounds(customSounds = {}) {
    const defaultSounds = {
        hover: { file: 'hover.mp3', volume: 0.4 },
        click: { file: 'click.mp3', volume: 0.5 },
        chime: { file: 'chime.mp3', volume: 0.3 },
        welcome: { file: 'welcome.mp3', volume: 0.35 },
    };
    
    return new KagamiSounds({
        basePath: './sounds/',
        sounds: { ...defaultSounds, ...customSounds },
        masterVolume: 0.8,
        debug: false,
    });
}

// Export for ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { KagamiSounds, createKagamiSounds };
}

// Global export for script tag usage
if (typeof window !== 'undefined') {
    window.KagamiSounds = KagamiSounds;
    window.createKagamiSounds = createKagamiSounds;
}
