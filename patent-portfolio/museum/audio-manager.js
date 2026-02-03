/**
 * Audio Manager
 * =============
 * 
 * Spatial audio and ambient sounds for the museum.
 * Each wing has its own sonic atmosphere.
 * 
 * h(x) ≥ 0 always
 */

// ═══════════════════════════════════════════════════════════════════════════
// COLONY AUDIO PROFILES
// ═══════════════════════════════════════════════════════════════════════════

const COLONY_AUDIO_PROFILES = {
    spark: {
        name: 'Spark Wing',
        ambient: 'creative-hum',
        characteristics: {
            frequency: 440, // A4
            waveform: 'sine',
            modulation: 8,
            volume: 0.1
        }
    },
    forge: {
        name: 'Forge Wing',
        ambient: 'industrial-warmth',
        characteristics: {
            frequency: 220, // A3
            waveform: 'sawtooth',
            modulation: 2,
            volume: 0.08
        }
    },
    flow: {
        name: 'Flow Wing',
        ambient: 'gentle-waves',
        characteristics: {
            frequency: 330, // E4
            waveform: 'sine',
            modulation: 0.5,
            volume: 0.12
        }
    },
    nexus: {
        name: 'Nexus Wing',
        ambient: 'network-pulse',
        characteristics: {
            frequency: 392, // G4
            waveform: 'triangle',
            modulation: 4,
            volume: 0.09
        }
    },
    beacon: {
        name: 'Beacon Wing',
        ambient: 'market-hum',
        characteristics: {
            frequency: 294, // D4
            waveform: 'sine',
            modulation: 6,
            volume: 0.07
        }
    },
    grove: {
        name: 'Grove Wing',
        ambient: 'organic-growth',
        characteristics: {
            frequency: 262, // C4
            waveform: 'sine',
            modulation: 1,
            volume: 0.11
        }
    },
    crystal: {
        name: 'Crystal Wing',
        ambient: 'crystalline-resonance',
        characteristics: {
            frequency: 528, // C5 (solfeggio)
            waveform: 'sine',
            modulation: 3,
            volume: 0.1
        }
    },
    rotunda: {
        name: 'Central Rotunda',
        ambient: 'sacred-geometry',
        characteristics: {
            frequency: 396, // G4 (solfeggio)
            waveform: 'sine',
            modulation: 0.25,
            volume: 0.08
        }
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// AUDIO MANAGER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class AudioManager {
    constructor() {
        this.audioContext = null;
        this.masterGain = null;
        this.isEnabled = false;
        this.currentZone = 'rotunda';
        
        // Active sound nodes
        this.ambientOscillators = new Map();
        this.spatialSources = new Map();
        
        // Settings
        this.masterVolume = 0.5;
        this.crossfadeDuration = 2; // seconds
        
        // Interaction sounds
        this.interactionSounds = {
            hover: { frequency: 880, duration: 0.1 },
            click: { frequency: 1760, duration: 0.15 },
            teleport: { frequency: 440, duration: 0.5, sweep: true }
        };
    }
    
    /**
     * Initialize the audio system (must be called after user interaction)
     */
    async init() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create master gain
            this.masterGain = this.audioContext.createGain();
            this.masterGain.gain.value = this.masterVolume;
            this.masterGain.connect(this.audioContext.destination);
            
            // Create analyzer for visualizations
            this.analyzer = this.audioContext.createAnalyser();
            this.analyzer.fftSize = 256;
            this.masterGain.connect(this.analyzer);
            
            this.isEnabled = true;
            console.log('🔊 Audio system initialized');
            
            // Start ambient sound for current zone
            this.setZone(this.currentZone);
            
            return true;
        } catch (error) {
            console.warn('Audio initialization failed:', error);
            return false;
        }
    }
    
    /**
     * Resume audio context (required after page interaction)
     */
    async resume() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
    }
    
    /**
     * Set the current zone and transition ambient sounds
     */
    setZone(zoneName) {
        if (!this.isEnabled || !this.audioContext) return;
        if (zoneName === this.currentZone && this.ambientOscillators.has(zoneName)) return;
        
        const profile = COLONY_AUDIO_PROFILES[zoneName];
        if (!profile) return;
        
        // Fade out current ambient
        this.fadeOutCurrentAmbient();
        
        // Create new ambient for this zone
        this.createAmbientForZone(zoneName, profile);
        
        this.currentZone = zoneName;
    }
    
    /**
     * Fade out current ambient sounds
     */
    fadeOutCurrentAmbient() {
        this.ambientOscillators.forEach((nodes, zone) => {
            const { oscillator, gain, lfo } = nodes;
            
            // Fade out
            gain.gain.linearRampToValueAtTime(
                0,
                this.audioContext.currentTime + this.crossfadeDuration
            );
            
            // Stop after fade
            setTimeout(() => {
                try {
                    oscillator.stop();
                    if (lfo) lfo.stop();
                } catch (e) {}
            }, this.crossfadeDuration * 1000 + 100);
        });
        
        this.ambientOscillators.clear();
    }
    
    /**
     * Create ambient sound for a zone
     */
    createAmbientForZone(zoneName, profile) {
        const { frequency, waveform, modulation, volume } = profile.characteristics;
        
        // Main oscillator
        const oscillator = this.audioContext.createOscillator();
        oscillator.type = waveform;
        oscillator.frequency.value = frequency;
        
        // Gain for this zone
        const gain = this.audioContext.createGain();
        gain.gain.value = 0;
        
        // LFO for subtle modulation
        const lfo = this.audioContext.createOscillator();
        lfo.type = 'sine';
        lfo.frequency.value = modulation;
        
        const lfoGain = this.audioContext.createGain();
        lfoGain.gain.value = frequency * 0.02; // Subtle frequency modulation
        
        // Connect LFO
        lfo.connect(lfoGain);
        lfoGain.connect(oscillator.frequency);
        
        // Connect main chain
        oscillator.connect(gain);
        gain.connect(this.masterGain);
        
        // Start oscillators
        oscillator.start();
        lfo.start();
        
        // Fade in
        gain.gain.linearRampToValueAtTime(
            volume * this.masterVolume,
            this.audioContext.currentTime + this.crossfadeDuration
        );
        
        // Store references
        this.ambientOscillators.set(zoneName, { oscillator, gain, lfo, lfoGain });
    }
    
    /**
     * Play an interaction sound
     */
    playInteraction(type) {
        if (!this.isEnabled || !this.audioContext) return;
        
        const config = this.interactionSounds[type];
        if (!config) return;
        
        const oscillator = this.audioContext.createOscillator();
        oscillator.type = 'sine';
        
        const gain = this.audioContext.createGain();
        gain.gain.value = 0.1 * this.masterVolume;
        
        oscillator.connect(gain);
        gain.connect(this.masterGain);
        
        if (config.sweep) {
            // Frequency sweep (for teleport)
            oscillator.frequency.setValueAtTime(config.frequency * 2, this.audioContext.currentTime);
            oscillator.frequency.exponentialRampToValueAtTime(
                config.frequency / 2,
                this.audioContext.currentTime + config.duration
            );
        } else {
            oscillator.frequency.value = config.frequency;
        }
        
        // Envelope
        gain.gain.setValueAtTime(0.1 * this.masterVolume, this.audioContext.currentTime);
        gain.gain.exponentialRampToValueAtTime(
            0.001,
            this.audioContext.currentTime + config.duration
        );
        
        oscillator.start();
        oscillator.stop(this.audioContext.currentTime + config.duration + 0.1);
    }
    
    /**
     * Play hover sound
     */
    playHover() {
        this.playInteraction('hover');
    }
    
    /**
     * Play click sound
     */
    playClick() {
        this.playInteraction('click');
    }
    
    /**
     * Play teleport sound
     */
    playTeleport() {
        this.playInteraction('teleport');
    }
    
    /**
     * Set master volume
     */
    setVolume(value) {
        this.masterVolume = Math.max(0, Math.min(1, value));
        if (this.masterGain) {
            this.masterGain.gain.linearRampToValueAtTime(
                this.masterVolume,
                this.audioContext.currentTime + 0.1
            );
        }
        
        // Update ambient volumes
        this.ambientOscillators.forEach((nodes, zone) => {
            const profile = COLONY_AUDIO_PROFILES[zone];
            if (profile) {
                nodes.gain.gain.linearRampToValueAtTime(
                    profile.characteristics.volume * this.masterVolume,
                    this.audioContext.currentTime + 0.1
                );
            }
        });
    }
    
    /**
     * Toggle audio on/off
     */
    toggle() {
        if (this.isEnabled) {
            this.setVolume(this.masterVolume > 0 ? 0 : 0.5);
        } else {
            this.init();
        }
    }
    
    /**
     * Get frequency data for visualizations
     */
    getFrequencyData() {
        if (!this.analyzer) return null;
        
        const dataArray = new Uint8Array(this.analyzer.frequencyBinCount);
        this.analyzer.getByteFrequencyData(dataArray);
        return dataArray;
    }
    
    /**
     * Update based on player position
     */
    updateListenerPosition(position, forward) {
        if (!this.audioContext?.listener) return;
        
        const listener = this.audioContext.listener;
        
        if (listener.positionX) {
            listener.positionX.setValueAtTime(position.x, this.audioContext.currentTime);
            listener.positionY.setValueAtTime(position.y, this.audioContext.currentTime);
            listener.positionZ.setValueAtTime(position.z, this.audioContext.currentTime);
            
            if (forward) {
                listener.forwardX.setValueAtTime(forward.x, this.audioContext.currentTime);
                listener.forwardY.setValueAtTime(forward.y, this.audioContext.currentTime);
                listener.forwardZ.setValueAtTime(forward.z, this.audioContext.currentTime);
            }
        } else {
            listener.setPosition(position.x, position.y, position.z);
            if (forward) {
                listener.setOrientation(forward.x, forward.y, forward.z, 0, 1, 0);
            }
        }
    }
    
    /**
     * Dispose audio resources
     */
    dispose() {
        this.fadeOutCurrentAmbient();
        
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        this.isEnabled = false;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createAudioManager() {
    return new AudioManager();
}

export default AudioManager;
