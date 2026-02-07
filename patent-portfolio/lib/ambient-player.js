/**
 * Museum Ambient Audio Player
 * ============================
 * 
 * Plays wing-specific ambient orchestral music.
 * Supports preloaded audio files or synthesized Web Audio fallback.
 * 
 * Features:
 * - Zone-based audio switching
 * - Smooth crossfades between zones
 * - Volume control
 * - Web Audio API synthesis fallback
 * 
 * h(x) ≥ 0 always
 */

// ═══════════════════════════════════════════════════════════════════════════
// COLONY MUSIC PROFILES (for Web Audio synthesis fallback)
// ═══════════════════════════════════════════════════════════════════════════

const COLONY_SYNTH_PROFILES = {
    spark: {
        baseFreq: 523.25,    // C5
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'bright',
        tempo: 90
    },
    forge: {
        baseFreq: 196.00,    // G3
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'warm',
        tempo: 72
    },
    flow: {
        baseFreq: 349.23,    // F4
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'fluid',
        tempo: 60
    },
    nexus: {
        baseFreq: 220.00,    // A3
        scale: [0, 2, 3, 5, 7, 8, 10],  // Minor
        character: 'mysterious',
        tempo: 66
    },
    beacon: {
        baseFreq: 293.66,    // D4
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'bold',
        tempo: 84
    },
    grove: {
        baseFreq: 329.63,    // E4
        scale: [0, 2, 3, 5, 7, 8, 10],  // Minor
        character: 'organic',
        tempo: 54
    },
    crystal: {
        baseFreq: 493.88,    // B4
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'crystalline',
        tempo: 72
    },
    rotunda: {
        baseFreq: 261.63,    // C4
        scale: [0, 2, 4, 5, 7, 9, 11],
        character: 'majestic',
        tempo: 66
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// AMBIENT PLAYER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class AmbientPlayer {
    constructor(audioContext = null) {
        this.audioContext = audioContext;
        this.masterGain = null;
        this.currentZone = null;
        this.isInitialized = false;
        this.isMuted = true;  // Start muted by default - let user enable
        this.volume = 0.08;   // Much quieter when enabled
        
        // Audio elements for each zone (preloaded files)
        this.audioElements = new Map();
        this.audioGains = new Map();
        
        // Synthesis fallback
        this.synthPlayers = new Map();
        this.useSynthesis = true;  // Use synthesis by default (no server)
        
        // Crossfade settings
        this.crossfadeDuration = 3.0;  // seconds
    }
    
    async init() {
        if (this.isInitialized) return;
        
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            
            // Master gain node
            this.masterGain = this.audioContext.createGain();
            this.masterGain.gain.value = this.volume;
            this.masterGain.connect(this.audioContext.destination);
            
            this.isInitialized = true;
            console.log('🎵 Ambient Player initialized');
            
        } catch (error) {
            console.warn('Ambient Player initialization failed:', error);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ZONE MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    async setZone(zoneName) {
        if (!this.isInitialized || zoneName === this.currentZone) return;
        
        const profile = COLONY_SYNTH_PROFILES[zoneName];
        if (!profile) return;
        
        console.log(`🎵 Switching ambient to: ${zoneName}`);
        
        // Crossfade from current to new zone
        await this.crossfade(this.currentZone, zoneName);
        this.currentZone = zoneName;
    }
    
    async crossfade(fromZone, toZone) {
        const now = this.audioContext.currentTime;
        
        // Fade out current zone
        if (fromZone) {
            const oldSynth = this.synthPlayers.get(fromZone);
            if (oldSynth) {
                oldSynth.gain.gain.setTargetAtTime(0, now, this.crossfadeDuration / 3);
                
                // Stop after fade
                setTimeout(() => {
                    this.stopSynthPlayer(fromZone);
                }, this.crossfadeDuration * 1000 + 500);
            }
        }
        
        // Create and fade in new zone
        if (toZone) {
            await this.startSynthPlayer(toZone);
            
            const newSynth = this.synthPlayers.get(toZone);
            if (newSynth) {
                newSynth.gain.gain.setValueAtTime(0, now);
                newSynth.gain.gain.setTargetAtTime(0.4, now, this.crossfadeDuration / 3);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // WEB AUDIO SYNTHESIS
    // ═══════════════════════════════════════════════════════════════════════
    
    async startSynthPlayer(zoneName) {
        if (this.synthPlayers.has(zoneName)) return;
        
        const profile = COLONY_SYNTH_PROFILES[zoneName];
        if (!profile) return;
        
        const gain = this.audioContext.createGain();
        gain.gain.value = 0;
        gain.connect(this.masterGain);
        
        const oscillators = [];
        const lfos = [];
        
        // Create pad oscillators based on character
        const chordNotes = this.getChordForProfile(profile);
        
        // Much gentler pad sounds - more musical and ambient
        for (const noteOffset of chordNotes) {
            const freq = profile.baseFreq * Math.pow(2, noteOffset / 12);
            
            // Main oscillator - always use sine for gentlest sound
            const osc = this.audioContext.createOscillator();
            osc.type = 'sine';  // Always sine for gentle ambient
            osc.frequency.value = freq;
            
            // Very slow pitch drift for organic feel
            const pitchLfo = this.audioContext.createOscillator();
            pitchLfo.type = 'sine';
            pitchLfo.frequency.value = 0.02 + Math.random() * 0.03;  // Very slow
            
            const pitchLfoGain = this.audioContext.createGain();
            pitchLfoGain.gain.value = freq * 0.001;  // Extremely subtle
            
            pitchLfo.connect(pitchLfoGain);
            pitchLfoGain.connect(osc.frequency);
            
            // Heavy filtering for warm pad sound
            const filter = this.audioContext.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = Math.min(this.getFilterFreq(profile.character), 600);  // More aggressive filtering
            filter.Q.value = 0.3;  // Low resonance
            
            // Slow breathing amplitude for meditation-like quality
            const ampLfo = this.audioContext.createOscillator();
            ampLfo.type = 'sine';
            ampLfo.frequency.value = 0.015 + Math.random() * 0.02;  // Very slow breath
            
            const ampLfoGain = this.audioContext.createGain();
            ampLfoGain.gain.value = 0.04;  // Subtle volume modulation
            
            const noteGain = this.audioContext.createGain();
            noteGain.gain.value = 0.025 / chordNotes.length;  // Much quieter
            
            ampLfo.connect(ampLfoGain);
            ampLfoGain.connect(noteGain.gain);
            
            osc.connect(filter);
            filter.connect(noteGain);
            noteGain.connect(gain);
            
            osc.start();
            pitchLfo.start();
            ampLfo.start();
            
            oscillators.push(osc, pitchLfo, ampLfo);
            lfos.push(pitchLfoGain, ampLfoGain);
        }
        
        // Add subtle reverb tail via convolver
        // (Skipped for simplicity - would need impulse response)
        
        this.synthPlayers.set(zoneName, {
            gain,
            oscillators,
            lfos
        });
    }
    
    stopSynthPlayer(zoneName) {
        const synth = this.synthPlayers.get(zoneName);
        if (!synth) return;
        
        for (const osc of synth.oscillators) {
            try { osc.stop(); } catch (e) {}
        }
        
        synth.gain.disconnect();
        this.synthPlayers.delete(zoneName);
    }
    
    getChordForProfile(profile) {
        // Return chord notes based on scale
        const scale = profile.scale;
        
        switch (profile.character) {
            case 'bright':
                return [scale[0], scale[2], scale[4], scale[6] || scale[0] + 12];  // Major 7th
            case 'warm':
                return [scale[0] - 12, scale[0], scale[2], scale[4]];  // Root doubling
            case 'fluid':
                return [scale[0], scale[2], scale[4], scale[0] + 12];  // Simple triad + octave
            case 'mysterious':
                return [scale[0], scale[2], scale[4], scale[6]];  // Minor 7th
            case 'bold':
                return [scale[0] - 12, scale[0], scale[4], scale[4] + 12];  // Power chord
            case 'organic':
                return [scale[0], scale[2], scale[4]];  // Simple triad
            case 'crystalline':
                return [scale[0], scale[4], scale[0] + 12, scale[4] + 12];  // Fifths
            case 'majestic':
                return [scale[0] - 12, scale[0], scale[2], scale[4], scale[0] + 12];  // Full spread
            default:
                return [scale[0], scale[2], scale[4]];
        }
    }
    
    getWaveformForCharacter(character) {
        switch (character) {
            case 'bright':
            case 'crystalline':
                return 'sine';
            case 'warm':
            case 'bold':
                return 'triangle';
            case 'mysterious':
            case 'organic':
                return 'sine';
            case 'fluid':
            case 'majestic':
                return 'triangle';
            default:
                return 'sine';
        }
    }
    
    getFilterFreq(character) {
        switch (character) {
            case 'bright':
            case 'crystalline':
                return 4000;
            case 'warm':
            case 'organic':
                return 800;
            case 'mysterious':
                return 1200;
            case 'bold':
            case 'majestic':
                return 2000;
            case 'fluid':
                return 1000;
            default:
                return 1500;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTROLS
    // ═══════════════════════════════════════════════════════════════════════
    
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        if (this.masterGain && !this.isMuted) {
            this.masterGain.gain.setTargetAtTime(
                this.volume,
                this.audioContext.currentTime,
                0.1
            );
        }
    }
    
    mute() {
        this.isMuted = true;
        if (this.masterGain) {
            this.masterGain.gain.setTargetAtTime(0, this.audioContext.currentTime, 0.1);
        }
    }
    
    unmute() {
        this.isMuted = false;
        if (this.masterGain) {
            this.masterGain.gain.setTargetAtTime(
                this.volume,
                this.audioContext.currentTime,
                0.1
            );
        }
    }
    
    toggle() {
        if (this.isMuted) {
            this.unmute();
        } else {
            this.mute();
        }
        return !this.isMuted;
    }
    
    dispose() {
        // Stop all synth players
        for (const zoneName of this.synthPlayers.keys()) {
            this.stopSynthPlayer(zoneName);
        }
        
        // Disconnect master
        if (this.masterGain) {
            this.masterGain.disconnect();
        }
    }
}

export { COLONY_SYNTH_PROFILES };
