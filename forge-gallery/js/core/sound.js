// ═══════════════════════════════════════════════════════════════════════════
// FORGE SOUND SYSTEM
// ⚒️ Metallic, industrial, rhythmic
// Crystal-verified: Web Audio API implementation
// ═══════════════════════════════════════════════════════════════════════════

export class ForgeSoundSystem {
    constructor() {
        this.context = null;
        this.initialized = false;
        this.enabled = true;
        this.masterGain = null;
        this.compressor = null;
    }
    
    async init() {
        if (this.initialized) return;
        
        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            
            // Master chain
            this.compressor = this.context.createDynamicsCompressor();
            this.compressor.threshold.value = -24;
            this.compressor.knee.value = 30;
            this.compressor.ratio.value = 12;
            this.compressor.attack.value = 0.003;
            this.compressor.release.value = 0.25;
            
            this.masterGain = this.context.createGain();
            this.masterGain.gain.value = 0.6;
            
            this.masterGain.connect(this.compressor);
            this.compressor.connect(this.context.destination);
            
            this.initialized = true;
            console.log('⚒️ Forge Sound System initialized');
        } catch (e) {
            console.warn('Forge Sound System failed to initialize:', e);
        }
    }
    
    // Hammer strike on anvil
    playStrike() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Impact noise
        const noiseBuffer = this.createNoiseBuffer(0.15);
        const noiseSource = this.context.createBufferSource();
        noiseSource.buffer = noiseBuffer;
        
        const noiseFilter = this.context.createBiquadFilter();
        noiseFilter.type = 'bandpass';
        noiseFilter.frequency.value = 2000;
        noiseFilter.Q.value = 1;
        
        const noiseGain = this.context.createGain();
        noiseGain.gain.setValueAtTime(0.4, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
        
        noiseSource.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(this.masterGain);
        noiseSource.start(now);
        
        // Metal ring
        const ringFreqs = [800, 1600, 2400, 3200];
        ringFreqs.forEach((freq, i) => {
            const osc = this.context.createOscillator();
            osc.type = 'sine';
            osc.frequency.value = freq + Math.random() * 50;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.15 / (i + 1), now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8 - i * 0.1);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            osc.start(now);
            osc.stop(now + 1);
        });
    }
    
    // Metal pour sound
    playPour() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Rushing liquid sound (filtered noise)
        const noiseBuffer = this.createNoiseBuffer(2);
        const noiseSource = this.context.createBufferSource();
        noiseSource.buffer = noiseBuffer;
        
        const filter = this.context.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(500, now);
        filter.frequency.linearRampToValueAtTime(2000, now + 0.5);
        filter.frequency.linearRampToValueAtTime(800, now + 2);
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.3, now + 0.2);
        gain.gain.linearRampToValueAtTime(0.2, now + 1.5);
        gain.gain.linearRampToValueAtTime(0, now + 2);
        
        noiseSource.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        noiseSource.start(now);
        noiseSource.stop(now + 2);
    }
    
    // Quench/cooling sound
    playQuench() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Steam hiss
        const noiseBuffer = this.createNoiseBuffer(1.5);
        const noiseSource = this.context.createBufferSource();
        noiseSource.buffer = noiseBuffer;
        
        const filter = this.context.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.value = 3000;
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.5, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 1.5);
        
        noiseSource.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        noiseSource.start(now);
        noiseSource.stop(now + 1.5);
    }
    
    // Cusp transition sound
    playCuspTransition(param) {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        const freq = 200 + (param + 2) * 150; // Map param to frequency
        
        const osc = this.context.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(freq, now);
        osc.frequency.exponentialRampToValueAtTime(freq * 0.5, now + 0.3);
        
        const filter = this.context.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 1000;
        filter.Q.value = 5;
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        
        osc.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        osc.start(now);
        osc.stop(now + 0.4);
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
    
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

