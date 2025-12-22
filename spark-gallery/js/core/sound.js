// ═══════════════════════════════════════════════════════════════════════════
// SPARK SOUND SYSTEM
// Aggressive, explosive, synthesized fire sounds
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
        }
    }
    
    // ─── IGNITION EXPLOSION ────────────────────────────────────────────────
    playIgnition() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // White noise burst
        const noiseBuffer = this.createNoiseBuffer(0.5);
        const noiseSource = this.context.createBufferSource();
        noiseSource.buffer = noiseBuffer;
        
        const noiseGain = this.context.createGain();
        noiseGain.gain.setValueAtTime(0.8, now);
        noiseGain.gain.exponentialDecayTo(0.01, now + 0.3);
        
        const noiseFilter = this.context.createBiquadFilter();
        noiseFilter.type = 'lowpass';
        noiseFilter.frequency.setValueAtTime(5000, now);
        noiseFilter.frequency.exponentialDecayTo(200, now + 0.3);
        
        noiseSource.connect(noiseFilter);
        noiseFilter.connect(noiseGain);
        noiseGain.connect(this.compressor);
        noiseSource.start(now);
        noiseSource.stop(now + 0.5);
        
        // Low boom
        const osc = this.context.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(150, now);
        osc.frequency.exponentialDecayTo(30, now + 0.4);
        
        const oscGain = this.context.createGain();
        oscGain.gain.setValueAtTime(0.6, now);
        oscGain.gain.exponentialDecayTo(0.01, now + 0.4);
        
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
            sizzleGain.gain.exponentialDecayTo(0.001, now + 0.3 + i * 0.05);
            
            sizzle.connect(sizzleGain);
            sizzleGain.connect(this.compressor);
            sizzle.start(now + i * 0.05);
            sizzle.stop(now + 0.4);
        }
    }
    
    // ─── IDEA SPAWN ────────────────────────────────────────────────────────
    playSpawn() {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Rising tone
        const osc = this.context.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(200, now);
        osc.frequency.exponentialRampToValueAtTime(800, now + 0.15);
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialDecayTo(0.01, now + 0.2);
        
        osc.connect(gain);
        gain.connect(this.compressor);
        osc.start(now);
        osc.stop(now + 0.2);
    }
    
    // ─── IDEA COLLISION ────────────────────────────────────────────────────
    playCollision() {
        if (!this.initialized || !this.enabled) return;
        
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
        gain.gain.setValueAtTime(0.3, now);
        gain.gain.exponentialDecayTo(0.01, now + 0.1);
        
        source.connect(filter);
        filter.connect(gain);
        gain.connect(this.compressor);
        source.start(now);
        source.stop(now + 0.1);
    }
    
    // ─── FOLD TRANSITION ───────────────────────────────────────────────────
    playFoldTransition(param) {
        if (!this.initialized || !this.enabled) return;
        
        const now = this.context.currentTime;
        
        // Map param (-2 to 2) to frequency
        const freq = 200 + (param + 2) * 150;
        
        const osc = this.context.createOscillator();
        osc.type = 'triangle';
        osc.frequency.value = freq;
        
        const gain = this.context.createGain();
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialDecayTo(0.01, now + 0.3);
        
        osc.connect(gain);
        gain.connect(this.compressor);
        osc.start(now);
        osc.stop(now + 0.3);
    }
    
    // ─── AMBIENT CRACKLE ───────────────────────────────────────────────────
    startAmbientCrackle() {
        if (!this.initialized || !this.enabled) return;
        
        const crackle = () => {
            if (!this.enabled) return;
            
            const now = this.context.currentTime;
            const noise = this.createNoiseBuffer(0.02);
            const source = this.context.createBufferSource();
            source.buffer = noise;
            
            const filter = this.context.createBiquadFilter();
            filter.type = 'highpass';
            filter.frequency.value = 5000 + Math.random() * 5000;
            
            const gain = this.context.createGain();
            gain.gain.setValueAtTime(0.02 + Math.random() * 0.03, now);
            gain.gain.exponentialDecayTo(0.001, now + 0.02);
            
            source.connect(filter);
            filter.connect(gain);
            gain.connect(this.compressor);
            source.start(now);
            source.stop(now + 0.02);
            
            // Random interval for next crackle
            setTimeout(crackle, 100 + Math.random() * 500);
        };
        
        crackle();
    }
    
    // ─── UTILITY: Create noise buffer ──────────────────────────────────────
    createNoiseBuffer(duration) {
        const sampleRate = this.context.sampleRate;
        const length = sampleRate * duration;
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

// Polyfill for exponentialDecayTo (not a real method, let's make it work)
GainNode.prototype.gain.exponentialDecayTo = function(value, endTime) {
    this.exponentialRampToValueAtTime(Math.max(value, 0.0001), endTime);
};

// Actually add this properly
if (typeof AudioParam !== 'undefined') {
    AudioParam.prototype.exponentialDecayTo = function(value, endTime) {
        this.exponentialRampToValueAtTime(Math.max(value, 0.0001), endTime);
    };
}

