// ═══════════════════════════════════════════════════════════════════════════
// SPARK SOUND SYSTEM
// Aggressive, explosive, synthesized fire sounds
// Crystal-verified: All audio methods use proper Web Audio API calls
// ═══════════════════════════════════════════════════════════════════════════

export class SparkSoundSystem {
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
            
            // Resume context if suspended (required by browsers)
            if (this.context.state === 'suspended') {
                await this.context.resume();
            }
            
            // Master gain
            this.masterGain = this.context.createGain();
            this.masterGain.gain.value = 0.3;
            
            // Compressor for punch
            this.compressor = this.context.createDynamicsCompressor();
            this.compressor.threshold.value = -24;
            this.compressor.knee.value = 30;
            this.compressor.ratio.value = 12;
            this.compressor.attack.value = 0.003;
            this.compressor.release.value = 0.25;
            
            this.compressor.connect(this.masterGain);
            this.masterGain.connect(this.context.destination);
            
            this.initialized = true;
            console.log('🔥 Spark Sound System initialized');
        } catch (e) {
            console.warn('Audio not available:', e);
            this.enabled = false;
        }
    }
    
    // Helper: exponential decay (replaces broken polyfill)
    expDecay(param, value, endTime) {
        param.exponentialRampToValueAtTime(Math.max(value, 0.0001), endTime);
    }
    
    // ─── IGNITION EXPLOSION ────────────────────────────────────────────────
    playIgnition() {
        if (!this.initialized || !this.enabled) return;
        
        try {
            const now = this.context.currentTime;
            
            // White noise burst
            const noiseBuffer = this.createNoiseBuffer(0.5);
            const noiseSource = this.context.createBufferSource();
            noiseSource.buffer = noiseBuffer;
            
            const noiseGain = this.context.createGain();
            noiseGain.gain.setValueAtTime(0.8, now);
            this.expDecay(noiseGain.gain, 0.01, now + 0.3);
            
            const noiseFilter = this.context.createBiquadFilter();
            noiseFilter.type = 'lowpass';
            noiseFilter.frequency.setValueAtTime(5000, now);
            this.expDecay(noiseFilter.frequency, 200, now + 0.3);
            
            noiseSource.connect(noiseFilter);
            noiseFilter.connect(noiseGain);
            noiseGain.connect(this.compressor);
            noiseSource.start(now);
            noiseSource.stop(now + 0.5);
            
            // Low boom
            const osc = this.context.createOscillator();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(150, now);
            this.expDecay(osc.frequency, 30, now + 0.4);
            
            const oscGain = this.context.createGain();
            oscGain.gain.setValueAtTime(0.6, now);
            this.expDecay(oscGain.gain, 0.01, now + 0.4);
            
            osc.connect(oscGain);
            oscGain.connect(this.compressor);
            osc.start(now);
            osc.stop(now + 0.5);
            
            // High sizzle
            for (let i = 0; i < 3; i++) {
                const sizzle = this.context.createOscillator();
                sizzle.type = 'sawtooth';
                sizzle.frequency.value = 2000 + Math.random() * 3000;
                
                const sizzleGain = this.context.createGain();
                sizzleGain.gain.setValueAtTime(0.1, now + i * 0.05);
                this.expDecay(sizzleGain.gain, 0.001, now + 0.3 + i * 0.05);
                
                sizzle.connect(sizzleGain);
                sizzleGain.connect(this.compressor);
                sizzle.start(now + i * 0.05);
                sizzle.stop(now + 0.4);
            }
        } catch (e) {
            console.warn('Ignition sound error:', e);
        }
    }
    
    // ─── IDEA SPAWN ────────────────────────────────────────────────────────
    playSpawn() {
        if (!this.initialized || !this.enabled) return;
        
        try {
            const now = this.context.currentTime;
            
            // Rising tone
            const osc = this.context.createOscillator();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(200, now);
            osc.frequency.exponentialRampToValueAtTime(800, now + 0.15);
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.15, now);
            this.expDecay(gain.gain, 0.01, now + 0.2);
            
            osc.connect(gain);
            gain.connect(this.compressor);
            osc.start(now);
            osc.stop(now + 0.2);
        } catch (e) {
            console.warn('Spawn sound error:', e);
        }
    }
    
    // ─── IDEA COLLISION ────────────────────────────────────────────────────
    playCollision() {
        if (!this.initialized || !this.enabled) return;
        
        try {
            const now = this.context.currentTime;
            
            // Crackle
            const noise = this.createNoiseBuffer(0.1);
            const source = this.context.createBufferSource();
            source.buffer = noise;
            
            const filter = this.context.createBiquadFilter();
            filter.type = 'bandpass';
            filter.frequency.value = 3000;
            filter.Q.value = 5;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.2, now);
            this.expDecay(gain.gain, 0.01, now + 0.1);
            
            source.connect(filter);
            filter.connect(gain);
            gain.connect(this.compressor);
            source.start(now);
            source.stop(now + 0.1);
        } catch (e) {
            console.warn('Collision sound error:', e);
        }
    }
    
    // ─── FOLD TRANSITION ───────────────────────────────────────────────────
    playFoldTransition(param) {
        if (!this.initialized || !this.enabled) return;
        
        try {
            const now = this.context.currentTime;
            
            // Map param (-2 to 2) to frequency
            const freq = 200 + (param + 2) * 150;
            
            const osc = this.context.createOscillator();
            osc.type = 'triangle';
            osc.frequency.value = freq;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.08, now);
            this.expDecay(gain.gain, 0.01, now + 0.3);
            
            osc.connect(gain);
            gain.connect(this.compressor);
            osc.start(now);
            osc.stop(now + 0.3);
        } catch (e) {
            console.warn('Fold sound error:', e);
        }
    }
    
    // ─── AMBIENT CRACKLE ───────────────────────────────────────────────────
    startAmbientCrackle() {
        if (!this.initialized || !this.enabled) return;
        
        const crackle = () => {
            if (!this.enabled || !this.initialized) return;
            
            try {
                const now = this.context.currentTime;
                const noise = this.createNoiseBuffer(0.02);
                const source = this.context.createBufferSource();
                source.buffer = noise;
                
                const filter = this.context.createBiquadFilter();
                filter.type = 'highpass';
                filter.frequency.value = 5000 + Math.random() * 5000;
                
                const gain = this.context.createGain();
                gain.gain.setValueAtTime(0.015 + Math.random() * 0.02, now);
                this.expDecay(gain.gain, 0.001, now + 0.02);
                
                source.connect(filter);
                filter.connect(gain);
                gain.connect(this.compressor);
                source.start(now);
                source.stop(now + 0.02);
            } catch (e) {
                // Silently fail for ambient sounds
            }
            
            // Random interval for next crackle
            setTimeout(crackle, 100 + Math.random() * 500);
        };
        
        crackle();
    }
    
    // ─── UTILITY: Create noise buffer ──────────────────────────────────────
    createNoiseBuffer(duration) {
        const sampleRate = this.context.sampleRate;
        const length = Math.floor(sampleRate * duration);
        const buffer = this.context.createBuffer(1, length, sampleRate);
        const data = buffer.getChannelData(0);
        
        for (let i = 0; i < length; i++) {
            data[i] = Math.random() * 2 - 1;
        }
        
        return buffer;
    }
    
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}
