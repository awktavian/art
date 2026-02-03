/**
 * Museum Sound Design System
 * ==========================
 * 
 * Professional spatial audio for the Patent Museum.
 * 
 * Inspired by:
 * - ARTECHOUSE's multi-sensory integration
 * - Meow Wolf's environmental audio
 * - Film score techniques for emotional depth
 * 
 * Features:
 * - Spatial audio (3D positioned sounds)
 * - Wing-specific ambient soundscapes
 * - Interaction feedback sounds
 * - Dynamic music based on location
 * - Smooth crossfades between zones
 * 
 * h(x) ≥ 0 always
 */

import { AmbientPlayer } from './ambient-player.js';

// ═══════════════════════════════════════════════════════════════════════════
// AUDIO CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

// Colony audio profiles (frequencies in Hz, inspired by harmonic series)
const COLONY_AUDIO = {
    spark: {
        baseFreq: 523.25,    // C5
        harmonics: [1, 2, 3, 5],
        waveform: 'sawtooth',
        filterFreq: 2000,
        attack: 0.02,
        release: 0.3,
        character: 'bright'
    },
    forge: {
        baseFreq: 392.00,    // G4
        harmonics: [1, 2, 4],
        waveform: 'square',
        filterFreq: 1200,
        attack: 0.05,
        release: 0.5,
        character: 'warm'
    },
    flow: {
        baseFreq: 349.23,    // F4
        harmonics: [1, 3, 5, 7],
        waveform: 'sine',
        filterFreq: 800,
        attack: 0.1,
        release: 0.8,
        character: 'fluid'
    },
    nexus: {
        baseFreq: 440.00,    // A4
        harmonics: [1, 2, 3, 4, 5],
        waveform: 'triangle',
        filterFreq: 1500,
        attack: 0.03,
        release: 0.4,
        character: 'mysterious'
    },
    beacon: {
        baseFreq: 587.33,    // D5
        harmonics: [1, 2, 4, 8],
        waveform: 'sawtooth',
        filterFreq: 3000,
        attack: 0.01,
        release: 0.2,
        character: 'bold'
    },
    grove: {
        baseFreq: 329.63,    // E4
        harmonics: [1, 2, 3],
        waveform: 'sine',
        filterFreq: 600,
        attack: 0.15,
        release: 1.0,
        character: 'organic'
    },
    crystal: {
        baseFreq: 493.88,    // B4
        harmonics: [1, 3, 5, 7, 9],
        waveform: 'sine',
        filterFreq: 4000,
        attack: 0.005,
        release: 0.6,
        character: 'crystalline'
    },
    rotunda: {
        baseFreq: 261.63,    // C4 (middle C)
        harmonics: [1, 2, 3, 4, 5, 6, 7],
        waveform: 'sine',
        filterFreq: 1000,
        attack: 0.2,
        release: 2.0,
        character: 'majestic'
    }
};

// Interaction sound presets
const INTERACTION_SOUNDS = {
    hover: { freq: 880, duration: 0.05, type: 'sine', volume: 0.1 },
    click: { freq: 440, duration: 0.1, type: 'triangle', volume: 0.2 },
    success: { freqs: [523, 659, 784], duration: 0.3, type: 'sine', volume: 0.25 },
    error: { freq: 220, duration: 0.2, type: 'square', volume: 0.15 },
    discovery: { freqs: [523, 659, 784, 1047], duration: 0.5, type: 'sine', volume: 0.3 },
    consensus: { freqs: [261, 329, 392, 523, 659, 784, 987], duration: 1.0, type: 'sine', volume: 0.35 },
    teleport: { freqStart: 1000, freqEnd: 200, duration: 0.3, type: 'sine', volume: 0.2 }
};

// ═══════════════════════════════════════════════════════════════════════════
// SOUND DESIGN MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class SoundDesignManager {
    constructor() {
        this.audioContext = null;
        this.masterGain = null;
        this.compressor = null;
        this.reverb = null;
        
        // Ambient system
        this.ambientOscillators = new Map();
        this.ambientGains = new Map();
        this.currentZone = null;
        
        // Spatial audio
        this.listener = null;
        this.spatialSources = new Map();
        
        // State
        this.isInitialized = false;
        this.isMuted = false;
        this.masterVolume = 0.5;
        
        // Crossfade
        this.crossfadeDuration = 2.0;
    }
    
    async init() {
        if (this.isInitialized) return;
        
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Master chain: sources → compressor → master gain → destination
            this.compressor = this.audioContext.createDynamicsCompressor();
            this.compressor.threshold.value = -24;
            this.compressor.knee.value = 30;
            this.compressor.ratio.value = 4;
            this.compressor.attack.value = 0.003;
            this.compressor.release.value = 0.25;
            
            this.masterGain = this.audioContext.createGain();
            this.masterGain.gain.value = this.masterVolume;
            
            // Create reverb
            this.reverb = await this.createReverb(2.0, 0.3);
            
            // Connect chain
            this.compressor.connect(this.masterGain);
            this.masterGain.connect(this.audioContext.destination);
            
            // Create spatial listener
            this.listener = this.audioContext.listener;
            
            this.isInitialized = true;
            console.log('🔊 Sound Design initialized');
            
        } catch (error) {
            console.warn('Audio initialization failed:', error);
        }
    }
    
    async createReverb(duration = 2.0, decay = 0.3) {
        const sampleRate = this.audioContext.sampleRate;
        const length = sampleRate * duration;
        const impulse = this.audioContext.createBuffer(2, length, sampleRate);
        
        for (let channel = 0; channel < 2; channel++) {
            const channelData = impulse.getChannelData(channel);
            for (let i = 0; i < length; i++) {
                channelData[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay * 10);
            }
        }
        
        const convolver = this.audioContext.createConvolver();
        convolver.buffer = impulse;
        
        const reverbGain = this.audioContext.createGain();
        reverbGain.gain.value = 0.2;
        
        convolver.connect(reverbGain);
        reverbGain.connect(this.compressor);
        
        return { convolver, gain: reverbGain };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // AMBIENT SOUNDSCAPES
    // ═══════════════════════════════════════════════════════════════════════
    
    setZone(zoneName) {
        if (!this.isInitialized || zoneName === this.currentZone) return;
        
        const profile = COLONY_AUDIO[zoneName];
        if (!profile) return;
        
        // Crossfade from current to new zone
        this.crossfadeToZone(zoneName, profile);
        this.currentZone = zoneName;
    }
    
    crossfadeToZone(zoneName, profile) {
        const now = this.audioContext.currentTime;
        const fadeTime = this.crossfadeDuration;
        
        // Fade out current ambient
        this.ambientGains.forEach((gain, name) => {
            if (name !== zoneName) {
                gain.gain.setTargetAtTime(0, now, fadeTime / 3);
                
                // Clean up after fade
                setTimeout(() => {
                    const oscs = this.ambientOscillators.get(name);
                    if (oscs) {
                        oscs.forEach(osc => {
                            try { osc.stop(); } catch (e) {}
                        });
                        this.ambientOscillators.delete(name);
                        this.ambientGains.delete(name);
                    }
                }, fadeTime * 1000 + 500);
            }
        });
        
        // Create new ambient if not exists
        if (!this.ambientOscillators.has(zoneName)) {
            this.createAmbientForZone(zoneName, profile);
        }
        
        // Fade in new ambient
        const newGain = this.ambientGains.get(zoneName);
        if (newGain) {
            newGain.gain.setTargetAtTime(0.08, now, fadeTime / 3);
        }
    }
    
    createAmbientForZone(zoneName, profile) {
        const oscillators = [];
        const gainNode = this.audioContext.createGain();
        gainNode.gain.value = 0; // Start silent
        
        // Create filter for character
        const filter = this.audioContext.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = profile.filterFreq;
        filter.Q.value = 1;
        
        // Create oscillators for each harmonic
        profile.harmonics.forEach((harmonic, i) => {
            const osc = this.audioContext.createOscillator();
            osc.type = profile.waveform;
            osc.frequency.value = profile.baseFreq * harmonic;
            
            // Harmonic amplitude decreases with order
            const harmonicGain = this.audioContext.createGain();
            harmonicGain.gain.value = 0.15 / (i + 1);
            
            // Add slow modulation for organic feel
            const lfo = this.audioContext.createOscillator();
            lfo.type = 'sine';
            lfo.frequency.value = 0.1 + Math.random() * 0.2;
            
            const lfoGain = this.audioContext.createGain();
            lfoGain.gain.value = profile.baseFreq * 0.005; // Slight pitch wobble
            
            lfo.connect(lfoGain);
            lfoGain.connect(osc.frequency);
            lfo.start();
            
            osc.connect(harmonicGain);
            harmonicGain.connect(filter);
            osc.start();
            
            oscillators.push(osc);
            oscillators.push(lfo);
        });
        
        // Connect chain
        filter.connect(gainNode);
        gainNode.connect(this.compressor);
        
        // Also send to reverb
        gainNode.connect(this.reverb.convolver);
        
        this.ambientOscillators.set(zoneName, oscillators);
        this.ambientGains.set(zoneName, gainNode);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION SOUNDS
    // ═══════════════════════════════════════════════════════════════════════
    
    playInteraction(type) {
        if (!this.isInitialized || this.isMuted) return;
        
        const preset = INTERACTION_SOUNDS[type];
        if (!preset) return;
        
        if (preset.freqs) {
            // Chord (multiple frequencies)
            this.playChord(preset.freqs, preset.duration, preset.type, preset.volume);
        } else if (preset.freqStart && preset.freqEnd) {
            // Sweep
            this.playSweep(preset.freqStart, preset.freqEnd, preset.duration, preset.type, preset.volume);
        } else {
            // Single tone
            this.playTone(preset.freq, preset.duration, preset.type, preset.volume);
        }
    }
    
    playTone(frequency, duration, waveform = 'sine', volume = 0.2) {
        if (!this.isInitialized || this.isMuted) return;
        
        const now = this.audioContext.currentTime;
        
        const osc = this.audioContext.createOscillator();
        osc.type = waveform;
        osc.frequency.value = frequency;
        
        const gain = this.audioContext.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(volume, now + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        
        osc.connect(gain);
        gain.connect(this.compressor);
        gain.connect(this.reverb.convolver);
        
        osc.start(now);
        osc.stop(now + duration + 0.1);
    }
    
    playChord(frequencies, duration, waveform = 'sine', volume = 0.2) {
        if (!this.isInitialized || this.isMuted) return;
        
        const now = this.audioContext.currentTime;
        const volumePerNote = volume / Math.sqrt(frequencies.length);
        
        frequencies.forEach((freq, i) => {
            setTimeout(() => {
                this.playTone(freq, duration, waveform, volumePerNote);
            }, i * 30); // Slight arpeggio
        });
    }
    
    playSweep(startFreq, endFreq, duration, waveform = 'sine', volume = 0.2) {
        if (!this.isInitialized || this.isMuted) return;
        
        const now = this.audioContext.currentTime;
        
        const osc = this.audioContext.createOscillator();
        osc.type = waveform;
        osc.frequency.setValueAtTime(startFreq, now);
        osc.frequency.exponentialRampToValueAtTime(endFreq, now + duration);
        
        const gain = this.audioContext.createGain();
        gain.gain.setValueAtTime(volume, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        
        osc.connect(gain);
        gain.connect(this.compressor);
        
        osc.start(now);
        osc.stop(now + duration + 0.1);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // COLONY-SPECIFIC NOTES
    // ═══════════════════════════════════════════════════════════════════════
    
    playColonyNote(colonyName, volume = 0.2) {
        if (!this.isInitialized || this.isMuted) return;
        
        const profile = COLONY_AUDIO[colonyName];
        if (!profile) return;
        
        const now = this.audioContext.currentTime;
        
        // Create a richer sound with harmonics
        profile.harmonics.slice(0, 3).forEach((harmonic, i) => {
            const osc = this.audioContext.createOscillator();
            osc.type = profile.waveform;
            osc.frequency.value = profile.baseFreq * harmonic;
            
            const gain = this.audioContext.createGain();
            const noteVolume = volume / (i + 1);
            
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(noteVolume, now + profile.attack);
            gain.gain.exponentialRampToValueAtTime(0.001, now + profile.release);
            
            const filter = this.audioContext.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = profile.filterFreq;
            
            osc.connect(filter);
            filter.connect(gain);
            gain.connect(this.compressor);
            gain.connect(this.reverb.convolver);
            
            osc.start(now);
            osc.stop(now + profile.release + 0.1);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SPATIAL AUDIO
    // ═══════════════════════════════════════════════════════════════════════
    
    updateListenerPosition(position, forward, up) {
        if (!this.listener) return;
        
        if (this.listener.positionX) {
            // Modern API
            this.listener.positionX.setValueAtTime(position.x, this.audioContext.currentTime);
            this.listener.positionY.setValueAtTime(position.y, this.audioContext.currentTime);
            this.listener.positionZ.setValueAtTime(position.z, this.audioContext.currentTime);
            
            this.listener.forwardX.setValueAtTime(forward.x, this.audioContext.currentTime);
            this.listener.forwardY.setValueAtTime(forward.y, this.audioContext.currentTime);
            this.listener.forwardZ.setValueAtTime(forward.z, this.audioContext.currentTime);
            
            this.listener.upX.setValueAtTime(up.x, this.audioContext.currentTime);
            this.listener.upY.setValueAtTime(up.y, this.audioContext.currentTime);
            this.listener.upZ.setValueAtTime(up.z, this.audioContext.currentTime);
        } else {
            // Legacy API
            this.listener.setPosition(position.x, position.y, position.z);
            this.listener.setOrientation(forward.x, forward.y, forward.z, up.x, up.y, up.z);
        }
    }
    
    createSpatialSource(id, position) {
        if (!this.isInitialized) return null;
        
        const panner = this.audioContext.createPanner();
        panner.panningModel = 'HRTF';
        panner.distanceModel = 'inverse';
        panner.refDistance = 1;
        panner.maxDistance = 50;
        panner.rolloffFactor = 1;
        panner.coneInnerAngle = 360;
        panner.coneOuterAngle = 0;
        panner.coneOuterGain = 0;
        
        if (panner.positionX) {
            panner.positionX.value = position.x;
            panner.positionY.value = position.y;
            panner.positionZ.value = position.z;
        } else {
            panner.setPosition(position.x, position.y, position.z);
        }
        
        panner.connect(this.compressor);
        
        this.spatialSources.set(id, panner);
        return panner;
    }
    
    playSpatialSound(id, frequency, duration = 0.5, volume = 0.3) {
        const panner = this.spatialSources.get(id);
        if (!panner || !this.isInitialized || this.isMuted) return;
        
        const now = this.audioContext.currentTime;
        
        const osc = this.audioContext.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = frequency;
        
        const gain = this.audioContext.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(volume, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        
        osc.connect(gain);
        gain.connect(panner);
        
        osc.start(now);
        osc.stop(now + duration + 0.1);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTROLS
    // ═══════════════════════════════════════════════════════════════════════
    
    setVolume(volume) {
        this.masterVolume = Math.max(0, Math.min(1, volume));
        if (this.masterGain) {
            this.masterGain.gain.setTargetAtTime(
                this.masterVolume,
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
                this.masterVolume,
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
    
    suspend() {
        if (this.audioContext && this.audioContext.state === 'running') {
            this.audioContext.suspend();
        }
    }
    
    resume() {
        if (this.audioContext && this.audioContext.state === 'suspended') {
            this.audioContext.resume();
        }
    }
    
    dispose() {
        // Stop all oscillators
        this.ambientOscillators.forEach(oscs => {
            oscs.forEach(osc => {
                try { osc.stop(); } catch (e) {}
            });
        });
        
        // Close audio context
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// COMPLETE SOUND MANAGER (combines all audio systems)
// ═══════════════════════════════════════════════════════════════════════════

class CompleteSoundManager {
    /**
     * Unified sound manager that combines:
     * - SoundDesignManager (interaction sounds, colony notes)
     * - AmbientPlayer (background ambient music)
     */
    constructor() {
        this.soundDesign = new SoundDesignManager();
        this.ambientPlayer = new AmbientPlayer();
        this.isInitialized = false;
        this.masterVolume = 0.5;
    }
    
    async init() {
        if (this.isInitialized) return;
        
        await this.soundDesign.init();
        
        // Share audio context with ambient player
        this.ambientPlayer.audioContext = this.soundDesign.audioContext;
        await this.ambientPlayer.init();
        
        this.isInitialized = true;
        console.log('🔊 Complete Sound Manager initialized');
    }
    
    setZone(zoneName) {
        this.soundDesign.setZone(zoneName);
        this.ambientPlayer.setZone(zoneName);
    }
    
    playInteraction(type) {
        this.soundDesign.playInteraction(type);
    }
    
    playColonyNote(colonyName, volume) {
        this.soundDesign.playColonyNote(colonyName, volume);
    }
    
    updateListenerPosition(position, forward, up) {
        this.soundDesign.updateListenerPosition(position, forward, up);
    }
    
    setVolume(volume) {
        this.masterVolume = volume;
        this.soundDesign.setVolume(volume);
        this.ambientPlayer.setVolume(volume * 0.6);  // Ambient slightly quieter
    }
    
    toggle() {
        const enabled = this.soundDesign.toggle();
        if (enabled) {
            this.ambientPlayer.unmute();
        } else {
            this.ambientPlayer.mute();
        }
        return enabled;
    }
    
    get isMuted() {
        return this.soundDesign.isMuted;
    }
    
    dispose() {
        this.soundDesign.dispose();
        this.ambientPlayer.dispose();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export { COLONY_AUDIO, INTERACTION_SOUNDS, CompleteSoundManager };
