// Crystal Sound System - Web Audio API synthesis
// Musical Architecture: Crystal resonance (glass harmonics, pure tones, overtones)
// Based on Grove's sound.js but tuned for crystalline aesthetics

export class CrystalSoundSystem {
    constructor() {
        this.context = null;
        this.initialized = false;
        this.enabled = true;
        this.reverb = null;
        this.masterVolume = 0.25; // Crystalline: precise, not overwhelming
        
        // Crystal harmonic series - overtone-rich frequencies
        // Based on glass resonance (approximately G major with raised 4th for brightness)
        this.frequencies = {
            // Fundamental tones (glass bowl frequencies)
            C4: 261.63,
            D4: 293.66,
            E4: 329.63,
            F_sharp4: 369.99, // Raised 4th (lydian brightness)
            G4: 392.00,
            A4: 440.00,
            B4: 493.88,
            C5: 523.25,
            D5: 587.33,
            E5: 659.25,
            G5: 783.99,
            C6: 1046.50,
            
            // Very high crystalline shimmer
            E6: 1318.51,
            G6: 1567.98,
            C7: 2093.00,
        };
        
        // Spectrum colors mapped to frequencies (dispersion sonification)
        this.spectrumTones = {
            red: this.frequencies.C4,      // Lowest frequency light = lowest tone
            orange: this.frequencies.D4,
            yellow: this.frequencies.E4,
            green: this.frequencies.G4,
            cyan: this.frequencies.A4,
            blue: this.frequencies.B4,
            violet: this.frequencies.D5,   // Highest frequency light = higher tone
        };
        
        // Colony frequencies (same as Grove for consistency, but will sound different)
        this.colonyTones = [
            this.frequencies.C4,  // Spark
            this.frequencies.D4,  // Forge
            this.frequencies.E4,  // Flow
            this.frequencies.G4,  // Nexus
            this.frequencies.A4,  // Beacon
            this.frequencies.B4,  // Grove
            this.frequencies.D5,  // Crystal
        ];
    }
    
    async initialize() {
        if (this.initialized) return;
        
        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            this.reverb = this.createCrystalReverb();
            this.initialized = true;
            console.log('💎 Crystal Sound: Resonance initialized');
        } catch (error) {
            console.warn('Web Audio API not supported:', error);
            this.enabled = false;
        }
    }
    
    /**
     * Create reverb tailored for crystalline space
     * Short, bright reflections (like inside a crystal cave)
     */
    createCrystalReverb() {
        if (!this.context) return null;
        
        const convolver = this.context.createConvolver();
        const rate = this.context.sampleRate;
        const length = rate * 1.8; // Shorter than Grove (crystalline, not cathedral)
        const impulse = this.context.createBuffer(2, length, rate);
        
        for (let channel = 0; channel < 2; channel++) {
            const channelData = impulse.getChannelData(channel);
            for (let i = 0; i < length; i++) {
                // Sharp initial reflections, then fast decay (crystal = hard surfaces)
                const decay = Math.pow(1 - i / length, 3.5); // Faster decay than Grove
                // Add some discrete reflection spikes (crystal facets)
                const spikes = (i % Math.floor(rate * 0.05) < 50) ? 1.5 : 1;
                channelData[i] = (Math.random() * 2 - 1) * decay * spikes;
            }
        }
        
        convolver.buffer = impulse;
        return convolver;
    }
    
    /**
     * Play a crystalline tone (pure with slight overtones)
     */
    playTone(frequency, pan = 0, duration = 1.0, options = {}) {
        if (!this.enabled || !this.initialized) return;
        
        const {
            attack = 0.005,  // Crystal: very fast attack (glass strike)
            decay = 0.1,
            sustain = 0.4,
            release = 0.8,   // Long release (resonance)
            useReverb = true,
            waveform = 'sine',
            addOvertones = true,
        } = options;
        
        const now = this.context.currentTime;
        
        // Main oscillator
        const osc = this.context.createOscillator();
        osc.type = waveform;
        osc.frequency.value = frequency;
        
        // Stereo panning
        const panner = this.context.createStereoPanner();
        panner.pan.value = Math.max(-1, Math.min(1, pan));
        
        // Gain envelope
        const gain = this.context.createGain();
        const peakLevel = 0.06 * this.masterVolume;
        const sustainLevel = peakLevel * sustain;
        
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(peakLevel, now + attack);
        gain.gain.linearRampToValueAtTime(sustainLevel, now + attack + decay);
        gain.gain.setValueAtTime(sustainLevel, now + duration - release);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        
        osc.connect(panner);
        
        if (useReverb && this.reverb) {
            const dryGain = this.context.createGain();
            const wetGain = this.context.createGain();
            dryGain.gain.value = 0.75;
            wetGain.gain.value = 0.25;
            
            panner.connect(dryGain);
            panner.connect(this.reverb);
            this.reverb.connect(wetGain);
            
            dryGain.connect(gain);
            wetGain.connect(gain);
        } else {
            panner.connect(gain);
        }
        
        gain.connect(this.context.destination);
        
        osc.start(now);
        osc.stop(now + duration);
        
        // Add overtones for crystalline shimmer
        if (addOvertones) {
            this.playOvertone(frequency * 2, pan, duration * 0.7, 0.3);
            this.playOvertone(frequency * 3, pan, duration * 0.5, 0.15);
            this.playOvertone(frequency * 4, pan, duration * 0.3, 0.08);
        }
    }
    
    /**
     * Play an overtone (helper for crystalline shimmer)
     */
    playOvertone(frequency, pan, duration, volumeScale) {
        if (!this.enabled || !this.initialized) return;
        
        const now = this.context.currentTime;
        
        const osc = this.context.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = frequency;
        
        const panner = this.context.createStereoPanner();
        panner.pan.value = pan;
        
        const gain = this.context.createGain();
        const level = 0.03 * this.masterVolume * volumeScale;
        
        gain.gain.setValueAtTime(level, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
        
        osc.connect(panner);
        panner.connect(gain);
        gain.connect(this.context.destination);
        
        osc.start(now);
        osc.stop(now + duration);
    }
    
    /**
     * PRISM ROOM: Light entering prism - single white tone
     */
    playLightEnter() {
        if (!this.enabled || !this.initialized) return;
        // High, pure tone (white light = all frequencies, represented by fundamental)
        this.playTone(this.frequencies.C5, 0, 1.5, {
            attack: 0.1,
            sustain: 0.6,
            release: 0.8,
            addOvertones: true,
        });
    }
    
    /**
     * PRISM ROOM: Dispersion - spectrum cascade
     */
    playDispersion() {
        if (!this.enabled || !this.initialized) return;
        
        const colors = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'violet'];
        const pans = [-0.8, -0.5, -0.2, 0, 0.2, 0.5, 0.8]; // Spread across stereo field
        
        colors.forEach((color, i) => {
            setTimeout(() => {
                this.playTone(this.spectrumTones[color], pans[i], 1.2, {
                    attack: 0.01,
                    decay: 0.1,
                    sustain: 0.5,
                    release: 0.6,
                    addOvertones: false, // Keep spectrum tones pure
                });
            }, i * 80); // Staggered for cascade effect
        });
    }
    
    /**
     * PRISM ROOM: Rotate prism - glass scraping sound
     */
    playPrismRotate(direction = 1) {
        if (!this.enabled || !this.initialized) return;
        
        // Throttle
        const now = Date.now();
        if (!this.lastPrismRotate) this.lastPrismRotate = 0;
        if (now - this.lastPrismRotate < 200) return;
        this.lastPrismRotate = now;
        
        // Subtle high-frequency whisper
        this.playTone(this.frequencies.G6, direction * 0.3, 0.2, {
            attack: 0.02,
            decay: 0.05,
            sustain: 0.2,
            release: 0.1,
            addOvertones: false,
        });
    }
    
    /**
     * LATTICE ROOM: Node hover - single ping
     */
    playNodeHover() {
        if (!this.enabled || !this.initialized) return;
        
        // Throttle
        const now = Date.now();
        if (!this.lastNodeHover) this.lastNodeHover = 0;
        if (now - this.lastNodeHover < 100) return;
        this.lastNodeHover = now;
        
        this.playTone(this.frequencies.E5, 0, 0.2, {
            attack: 0.005,
            decay: 0.03,
            sustain: 0.3,
            release: 0.15,
            addOvertones: true,
        });
    }
    
    /**
     * LATTICE ROOM: Node click - confirmation chime
     */
    playNodeClick() {
        if (!this.enabled || !this.initialized) return;
        
        // Two-note confirmation (perfect fifth = verified/resolved)
        this.playTone(this.frequencies.C5, -0.2, 0.8, { addOvertones: true });
        setTimeout(() => {
            this.playTone(this.frequencies.G5, 0.2, 0.6, { addOvertones: true });
        }, 100);
    }
    
    /**
     * LATTICE ROOM: E8 lattice visualization - full arpeggio
     */
    playLatticeActivate() {
        if (!this.enabled || !this.initialized) return;
        
        const notes = [
            this.frequencies.C4,
            this.frequencies.E4,
            this.frequencies.G4,
            this.frequencies.B4,
            this.frequencies.D5,
            this.frequencies.G5,
            this.frequencies.C6,
        ];
        
        notes.forEach((freq, i) => {
            setTimeout(() => {
                this.playTone(freq, (i - 3) * 0.2, 0.8, {
                    attack: 0.01,
                    decay: 0.08,
                    sustain: 0.4,
                    release: 0.5,
                    addOvertones: true,
                });
            }, i * 100);
        });
    }
    
    /**
     * REFLECTION ROOM: Mirror activation - ethereal chord
     */
    playMirrorActivate() {
        if (!this.enabled || !this.initialized) return;
        
        // C major 7 chord (dreamy, reflective)
        const chord = [
            this.frequencies.C4,
            this.frequencies.E4,
            this.frequencies.G4,
            this.frequencies.B4,
        ];
        
        chord.forEach((freq, i) => {
            this.playTone(freq, (i - 1.5) * 0.3, 2.0, {
                attack: 0.05,
                decay: 0.2,
                sustain: 0.6,
                release: 1.0,
                addOvertones: true,
            });
        });
    }
    
    /**
     * REFLECTION ROOM: Typing in verify input - keypress sound
     */
    playKeypress() {
        if (!this.enabled || !this.initialized) return;
        
        // Throttle heavily
        const now = Date.now();
        if (!this.lastKeypress) this.lastKeypress = 0;
        if (now - this.lastKeypress < 50) return;
        this.lastKeypress = now;
        
        // Random high frequency for variety
        const freqs = [this.frequencies.G5, this.frequencies.C6, this.frequencies.E6];
        const freq = freqs[Math.floor(Math.random() * freqs.length)];
        
        this.playTone(freq, (Math.random() - 0.5) * 0.4, 0.08, {
            attack: 0.003,
            decay: 0.02,
            sustain: 0.2,
            release: 0.05,
            addOvertones: false,
        });
    }
    
    /**
     * REFLECTION ROOM: Verification result - success/failure
     */
    playVerificationResult(success) {
        if (!this.enabled || !this.initialized) return;
        
        if (success) {
            // C major triad - resolution
            const chord = [this.frequencies.C5, this.frequencies.E5, this.frequencies.G5];
            chord.forEach((freq, i) => {
                setTimeout(() => {
                    this.playTone(freq, (i - 1) * 0.3, 1.5, { addOvertones: true });
                }, i * 80);
            });
        } else {
            // Minor second - dissonance (unverified)
            this.playTone(this.frequencies.E4, 0, 0.8, { addOvertones: false });
            setTimeout(() => {
                this.playTone(this.frequencies.E4 * 1.059, 0, 0.8, { addOvertones: false }); // Minor 2nd
            }, 50);
        }
    }
    
    /**
     * INFINITE REFLECTION: Recursive mirror sound (delay-based)
     */
    playInfiniteReflection() {
        if (!this.enabled || !this.initialized) return;
        
        const now = this.context.currentTime;
        const baseFreq = this.frequencies.C5;
        
        // Create echo effect manually (sound bouncing between mirrors)
        for (let i = 0; i < 8; i++) {
            setTimeout(() => {
                const volumeDecay = Math.pow(0.7, i);
                const pan = Math.sin(i * 0.8) * 0.6; // Bounce left-right
                const freq = baseFreq * Math.pow(1.02, i); // Slight pitch rise (Doppler-ish)
                
                this.playTone(freq, pan, 0.3, {
                    attack: 0.005,
                    decay: 0.05,
                    sustain: 0.3 * volumeDecay,
                    release: 0.2,
                    addOvertones: i < 3, // Only first few have overtones
                });
            }, i * 120);
        }
    }
    
    /**
     * Gallery entrance - grand crystalline chord
     */
    playGalleryEnter() {
        if (!this.enabled || !this.initialized) return;
        
        // Staggered chord for grandeur
        const frequencies = [
            this.frequencies.C4,
            this.frequencies.G4,
            this.frequencies.C5,
            this.frequencies.E5,
            this.frequencies.G5,
        ];
        
        frequencies.forEach((freq, i) => {
            setTimeout(() => {
                this.playTone(freq, 0, 3.0, {
                    attack: 0.1,
                    decay: 0.3,
                    sustain: 0.5,
                    release: 1.5,
                    addOvertones: true,
                });
            }, i * 150);
        });
    }
    
    /**
     * Resume context after user gesture
     */
    resume() {
        if (this.context && this.context.state === 'suspended') {
            this.context.resume();
        }
    }
}

