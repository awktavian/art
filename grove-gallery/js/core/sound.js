// Sound System - Web Audio API synthesis
// Musical Architecture: E minor pentatonic (mystical, grove-like)

export class SoundSystem {
    constructor() {
        this.context = null;
        this.initialized = false;
        this.enabled = true;
        this.reverb = null;
        this.masterVolume = 0.3; // Global volume control (30% of already quiet sounds)

        // E minor pentatonic scale (mystical, meditative)
        this.scale = {
            E2: 82.41,   // Root (bass drone)
            E3: 164.81,  // Root (main drone)
            G3: 196.00,  // Minor third
            A3: 220.00,  // Fourth
            B3: 246.94,  // Fifth
            D4: 293.66,  // Minor seventh
            E4: 329.63,  // Root (octave)
            G4: 392.00,  // Minor third (octave)
            A4: 440.00,  // Fourth (octave)
            B4: 493.88,  // Fifth (octave)
            D5: 587.33,  // Minor seventh (octave)
            E5: 659.25,  // Root (high)
        };

        // Colony-specific frequencies (7-note sequence for hall waves)
        this.colonyNotes = [
            this.scale.E3,  // Spark
            this.scale.G3,  // Forge
            this.scale.A3,  // Flow
            this.scale.B3,  // Nexus
            this.scale.D4,  // Beacon
            this.scale.E4,  // Grove
            this.scale.G4,  // Crystal
        ];
    }

    /**
     * Initialize Web Audio Context (must be called after user gesture)
     * @returns {Promise<void>}
     */
    async initialize() {
        if (this.initialized) return;

        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            this.reverb = this.createReverb();
            this.initialized = true;
            console.log('🔊 Sound system initialized (E minor pentatonic)');
        } catch (error) {
            console.warn('Web Audio API not supported:', error);
            this.enabled = false;
        }
    }

    /**
     * Create reverb convolver for spatial depth
     * @returns {ConvolverNode}
     */
    createReverb() {
        if (!this.context) return null;

        const convolver = this.context.createConvolver();
        const rate = this.context.sampleRate;
        const length = rate * 2.5; // 2.5 second reverb (mystical space)
        const impulse = this.context.createBuffer(2, length, rate);

        // Create impulse response (simulated cathedral reverb)
        for (let channel = 0; channel < 2; channel++) {
            const channelData = impulse.getChannelData(channel);
            for (let i = 0; i < length; i++) {
                // Exponential decay with random reflections
                const decay = Math.pow(1 - i / length, 2.5);
                channelData[i] = (Math.random() * 2 - 1) * decay;
            }
        }

        convolver.buffer = impulse;
        return convolver;
    }

    /**
     * Core musical phrase player with ADSR envelope and spatial audio
     * @param {number} frequency - Frequency in Hz
     * @param {number} pan - Stereo position (-1=left, 0=center, 1=right)
     * @param {number} duration - Duration in seconds
     * @param {Object} envelope - ADSR parameters {attack, decay, sustain, release}
     * @param {boolean} useReverb - Apply reverb effect
     * @param {string} waveform - Oscillator type ('sine', 'triangle', 'sawtooth', 'square')
     */
    playPhrase(
        frequency,
        pan = 0,
        duration = 1.0,
        envelope = { attack: 0.02, decay: 0.1, sustain: 0.7, release: 0.5 },
        useReverb = false,
        waveform = 'sine'
    ) {
        if (!this.enabled || !this.initialized) return;

        const now = this.context.currentTime;
        const { attack, decay, sustain, release } = envelope;

        // Oscillator
        const osc = this.context.createOscillator();
        osc.type = waveform;
        osc.frequency.value = frequency;

        // Stereo panning
        const panner = this.context.createStereoPanner();
        panner.pan.value = Math.max(-1, Math.min(1, pan));

        // Gain with ADSR envelope
        const gain = this.context.createGain();
        const peakLevel = 0.08 * this.masterVolume; // MUCH quieter (was 0.3)
        const sustainLevel = peakLevel * sustain;

        // ADSR envelope
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(peakLevel, now + attack);
        gain.gain.linearRampToValueAtTime(sustainLevel, now + attack + decay);
        gain.gain.setValueAtTime(sustainLevel, now + duration - release);
        gain.gain.exponentialRampToValueAtTime(0.001, now + duration);

        // Audio graph: osc → panner → (reverb?) → gain → destination
        osc.connect(panner);

        if (useReverb && this.reverb) {
            const dryGain = this.context.createGain();
            const wetGain = this.context.createGain();
            dryGain.gain.value = 0.88; // 88% dry (was 60%)
            wetGain.gain.value = 0.12; // 12% wet (was 40% - TOO MUCH)

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
    }

    /**
     * Play chord (multiple notes simultaneously)
     * @param {number[]} frequencies - Array of frequencies
     * @param {number} pan - Stereo position
     * @param {number} duration - Duration in seconds
     * @param {boolean} useReverb - Apply reverb
     */
    playChord(frequencies, pan = 0, duration = 1.5, useReverb = true) {
        frequencies.forEach(freq => {
            this.playPhrase(freq, pan, duration, {
                attack: 0.03,
                decay: 0.15,
                sustain: 0.6,
                release: 0.8
            }, useReverb);
        });
    }

    /**
     * Play arpeggio (notes in sequence)
     * @param {number[]} frequencies - Array of frequencies
     * @param {number} pan - Stereo position
     * @param {number} noteGap - Time between notes (seconds)
     */
    playArpeggio(frequencies, pan = 0, noteGap = 0.15) {
        frequencies.forEach((freq, i) => {
            setTimeout(() => {
                this.playPhrase(freq, pan, 0.8, {
                    attack: 0.01,
                    decay: 0.05,
                    sustain: 0.5,
                    release: 0.4
                }, true);
            }, i * noteGap * 1000);
        });
    }

    /**
     * ENTRANCE: Glyph appears - E minor chord (E + G + B)
     */
    playBellChime(duration = 2) {
        if (!this.enabled || !this.initialized) return;
        this.playChord([this.scale.E3, this.scale.G3, this.scale.B3], 0, duration, true);
    }

    /**
     * ENTRANCE: Light burst - Perfect fifth (E + B) with shimmer
     */
    playWindWhoosh(duration = 2) {
        if (!this.enabled || !this.initialized) return;

        // Perfect fifth for mystical energy
        this.playChord([this.scale.E4, this.scale.B4], 0, duration, true);

        // Add shimmer (high harmonics)
        setTimeout(() => {
            this.playPhrase(this.scale.E5, 0.3, 0.8, {
                attack: 0.1,
                decay: 0.2,
                sustain: 0.4,
                release: 0.5
            }, true);
        }, 300);

        setTimeout(() => {
            this.playPhrase(this.scale.E5, -0.3, 0.8, {
                attack: 0.1,
                decay: 0.2,
                sustain: 0.4,
                release: 0.5
            }, true);
        }, 500);
    }

    /**
     * ENTRANCE: Title cascade - E minor arpeggio (E → G → B → D → E)
     */
    playTextChime() {
        if (!this.enabled || !this.initialized) return;
        this.playArpeggio([
            this.scale.E4,
            this.scale.G4,
            this.scale.B4,
            this.scale.D5,
            this.scale.E5
        ], 0, 0.12);
    }

    /**
     * Resume context (required after page load on some browsers)
     */
    resume() {
        if (this.context && this.context.state === 'suspended') {
            this.context.resume();
        }
    }

    /**
     * SANCTUARY: Ambient drone - E + B fifth (meditative)
     * @returns {Object} - { sources, gain } for control
     */
    playRustlingLeaves() {
        if (!this.enabled || !this.initialized) return null;

        const now = this.context.currentTime;

        // E drone (root)
        const osc1 = this.context.createOscillator();
        osc1.type = 'sine';
        osc1.frequency.value = this.scale.E2; // Deep bass drone

        // B drone (fifth)
        const osc2 = this.context.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.value = this.scale.B3;

        // Master gain
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.001, now);

        // Connect both through reverb for atmosphere
        if (this.reverb) {
            const dryGain = this.context.createGain();
            const wetGain = this.context.createGain();
            dryGain.gain.value = 0.8; // 80% dry (was 30%)
            wetGain.gain.value = 0.2; // 20% wet (was 70% - WAY TOO MUCH)

            osc1.connect(dryGain);
            osc2.connect(dryGain);
            osc1.connect(this.reverb);
            osc2.connect(this.reverb);
            this.reverb.connect(wetGain);

            dryGain.connect(gain);
            wetGain.connect(gain);
        } else {
            osc1.connect(gain);
            osc2.connect(gain);
        }

        gain.connect(this.context.destination);

        osc1.start(now);
        osc2.start(now);

        return { sources: [osc1, osc2], gain };
    }

    /**
     * SANCTUARY: Detail open - E major resolution (success)
     */
    playSoftChime() {
        if (!this.enabled || !this.initialized) return;
        // E major chord (E + G# + B) - resolution, positive
        const G_sharp = 207.65; // G# for major third
        this.playChord([this.scale.E4, G_sharp, this.scale.B4], 0, 1.5, true);
    }

    /**
     * ENTRANCE: Particle spawn - Random pentatonic note with spatial audio
     * @param {number} pan - Stereo position based on particle location
     */
    playParticleSpawn(pan = 0) {
        if (!this.enabled || !this.initialized) return;

        // Throttle: only play if enough time has passed
        const now = Date.now();
        if (!this.lastParticleSound) this.lastParticleSound = 0;
        if (now - this.lastParticleSound < 300) return; // Max once per 300ms
        this.lastParticleSound = now;

        // Random note from E minor pentatonic scale
        const notes = [
            this.scale.E4, this.scale.G4, this.scale.A4,
            this.scale.B4, this.scale.D5, this.scale.E5
        ];
        const frequency = notes[Math.floor(Math.random() * notes.length)];

        this.playPhrase(frequency, pan, 0.15, {
            attack: 0.005,
            decay: 0.02,
            sustain: 0.3,
            release: 0.1
        }, false, 'triangle');
    }

    /**
     * COLONIES HALL: Wave pulse - Play colony-specific note
     * @param {number} colonyIndex - Index (0-6) for colony
     * @param {number} pan - Stereo position
     */
    playColonyWave(colonyIndex, pan = 0) {
        if (!this.enabled || !this.initialized) return;
        const frequency = this.colonyNotes[colonyIndex % 7];
        this.playPhrase(frequency, pan, 0.6, {
            attack: 0.02,
            decay: 0.08,
            sustain: 0.5,
            release: 0.4
        }, true);
    }

    /**
     * FANO 3D: Pluck line - String vibration with overtones
     * @param {number[]} colonyIndices - Three colony indices on Fano line
     */
    playFanoLine(colonyIndices) {
        if (!this.enabled || !this.initialized) return;
        const frequencies = colonyIndices.map(i => this.colonyNotes[i % 7]);
        this.playChord(frequencies, 0, 1.2, true);
    }

    /**
     * WORKFLOW: Phase transitions
     * @param {string} phase - 'plan', 'execute', 'verify'
     */
    playWorkflowPhase(phase) {
        if (!this.enabled || !this.initialized) return;

        switch (phase) {
            case 'plan':
                // E + G (opening, questioning)
                this.playChord([this.scale.E3, this.scale.G3], 0, 1.0, true);
                break;
            case 'execute':
                // A + D (tension, action)
                this.playChord([this.scale.A3, this.scale.D4], 0, 1.0, true);
                break;
            case 'verify':
                // E major chord (resolution, success)
                const G_sharp = 207.65;
                this.playChord([this.scale.E3, G_sharp, this.scale.B3], 0, 2.0, true);
                break;
        }
    }

    /**
     * FOUNDATIONS: E8 lattice - Full pentatonic scale
     */
    playE8Lattice() {
        if (!this.enabled || !this.initialized) return;
        this.playArpeggio([
            this.scale.E3, this.scale.G3, this.scale.A3,
            this.scale.B3, this.scale.D4, this.scale.E4
        ], 0, 0.1);
    }

    /**
     * CBF DEMO: Safety state sonification
     * @param {number} hValue - CBF value (0-1, where >0.5 is safe)
     */
    playCBFState(hValue) {
        if (!this.enabled || !this.initialized) return;

        if (hValue > 0.5) {
            // Safe: Consonant E minor chord
            this.playChord([this.scale.E3, this.scale.G3, this.scale.B3], 0, 0.5, false);
        } else if (hValue > 0) {
            // Caution: Tension (A + D, no resolution)
            this.playChord([this.scale.A3, this.scale.D4], 0, 0.5, false);
        } else {
            // Danger: Dissonant tritone
            const F_sharp = 185.00; // Tritone from C
            this.playChord([this.scale.E3, F_sharp], 0, 0.8, false);
        }
    }

    /**
     * EPILOGUE: Seven-part harmony (all colonies)
     */
    playEpilogue() {
        if (!this.enabled || !this.initialized) return;

        // Seven orbs ascending
        this.colonyNotes.forEach((freq, i) => {
            setTimeout(() => {
                this.playPhrase(freq, (i - 3) * 0.3, 2.0, {
                    attack: 0.05,
                    decay: 0.2,
                    sustain: 0.7,
                    release: 1.0
                }, true);
            }, i * 200);
        });

        // Final E major resolution at 1.4s
        setTimeout(() => {
            const G_sharp = 207.65;
            this.playChord([this.scale.E3, G_sharp, this.scale.B3, this.scale.E4], 0, 4.0, true);
        }, 1400);
    }
}
