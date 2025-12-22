// ═══════════════════════════════════════════════════════════════════════════
// FLOW SOUND SYSTEM
// 🌊 Fluid, ambient, healing
// Crystal-verified: Web Audio API implementation
// ═══════════════════════════════════════════════════════════════════════════

export class FlowSoundSystem {
    constructor() {
        this.context = null;
        this.initialized = false;
        this.enabled = true;
        this.masterGain = null;
        this.reverb = null;
    }
    
    async init() {
        if (this.initialized) return;
        
        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create reverb
            this.reverb = this.context.createConvolver();
            this.reverb.buffer = this.createReverbBuffer(3);
            
            const reverbGain = this.context.createGain();
            reverbGain.gain.value = 0.4;
            
            // Master chain
            this.masterGain = this.context.createGain();
            this.masterGain.gain.value = 0.5;
            
            // Dry/wet mix
            this.masterGain.connect(this.context.destination);
            this.masterGain.connect(this.reverb);
            this.reverb.connect(reverbGain);
            reverbGain.connect(this.context.destination);
            
            this.initialized = true;
            console.log('🌊 Flow Sound System initialized');
        } catch (e) {
            console.warn('Flow Sound System failed to initialize:', e);
        }
    }
    
    // Water droplet sound
    playDroplet() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        const baseFreq = 800 + Math.random() * 400;
        
        const osc = this.context.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(baseFreq, now);
        osc.frequency.exponentialRampToValueAtTime(baseFreq * 0.3, now + 0.15);
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.25, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
        
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.25);
    }
    
    // Error spawn sound
    playError() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Dissonant chord
        const freqs = [200, 283, 350]; // Minor second intervals
        freqs.forEach((freq, i) => {
            const osc = this.context.createOscillator();
            osc.type = 'square';
            osc.frequency.value = freq;
            
            const filter = this.context.createBiquadFilter();
            filter.type = 'lowpass';
            filter.frequency.value = 800;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
            
            osc.connect(filter);
            filter.connect(gain);
            gain.connect(this.masterGain);
            osc.start(now);
            osc.stop(now + 0.35);
        });
    }
    
    // Healing/fix sound
    playHeal() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Ascending arpeggio (major chord)
        const freqs = [262, 330, 392, 523]; // C major + octave
        freqs.forEach((freq, i) => {
            const osc = this.context.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = freq;
            
            const gain = this.context.createGain();
            const startTime = now + i * 0.08;
            gain.gain.setValueAtTime(0, startTime);
            gain.gain.linearRampToValueAtTime(0.2, startTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.5);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            osc.start(startTime);
            osc.stop(startTime + 0.6);
        });
    }
    
    // Flowing water ambient
    playFlow() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Filtered noise for water
        const noiseBuffer = this.createNoiseBuffer(2);
        const noiseSource = this.context.createBufferSource();
        noiseSource.buffer = noiseBuffer;
        
        const filter = this.context.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 400;
        filter.Q.value = 0.5;
        
        // LFO for movement
        const lfo = this.context.createOscillator();
        lfo.frequency.value = 0.3;
        const lfoGain = this.context.createGain();
        lfoGain.gain.value = 200;
        lfo.connect(lfoGain);
        lfoGain.connect(filter.frequency);
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.15, now + 0.5);
        gain.gain.linearRampToValueAtTime(0.1, now + 1.5);
        gain.gain.linearRampToValueAtTime(0, now + 2);
        
        noiseSource.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        
        lfo.start(now);
        noiseSource.start(now);
        noiseSource.stop(now + 2);
        lfo.stop(now + 2);
    }
    
    // Swallowtail transition
    playSwallowtailTransition(params) {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        const { a, b, c } = params;
        
        // Map parameters to frequencies
        const freq1 = 300 + (a + 2) * 100;
        const freq2 = 400 + (b + 2) * 80;
        const freq3 = 500 + (c + 2) * 60;
        
        [freq1, freq2, freq3].forEach((freq, i) => {
            const osc = this.context.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = freq;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            osc.start(now);
            osc.stop(now + 0.25);
        });
    }
    
    createNoiseBuffer(duration) {
        const sampleRate = this.context.sampleRate;
        const bufferSize = sampleRate * duration;
        const buffer = this.context.createBuffer(1, bufferSize, sampleRate);
        const data = buffer.getChannelData(0);
        
        for (let i = 0; i < bufferSize; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        
        return buffer;
    }
    
    createReverbBuffer(duration) {
        const sampleRate = this.context.sampleRate;
        const bufferSize = sampleRate * duration;
        const buffer = this.context.createBuffer(2, bufferSize, sampleRate);
        
        for (let channel = 0; channel < 2; channel++) {
            const data = buffer.getChannelData(channel);
            for (let i = 0; i < bufferSize; i++) {
                data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (sampleRate * 0.5));
            }
        }
        
        return buffer;
    }
    
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

