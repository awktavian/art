/**
 * Steamboat Audio — 1928 Sound Synthesis
 * ========================================
 * Clean Web Audio API implementation for Steamboat Willie.
 * All sounds are synthesized, no external files needed.
 *
 * Features:
 *   - Proper lifecycle management (start/stop)
 *   - Single AudioContext (created on first user gesture)
 *   - Authentic 1928-era sound design
 *
 * Usage:
 *   const audio = new SteamboatAudio();
 *   await audio.init();  // Call on user gesture
 *   audio.playWhistle();
 *   audio.playSquawk();
 *   audio.startAmbient();
 *   audio.stopAmbient();
 */

'use strict';

class SteamboatAudio {
  constructor() {
    this.ctx = null;
    this.masterGain = null;
    this.ambientNodes = [];
    this.isAmbientPlaying = false;
    this._initialized = false;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // INITIALIZATION
  // ═══════════════════════════════════════════════════════════════════════

  async init() {
    if (this._initialized) return true;

    try {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();

      // Master gain for global volume control
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = 0.7;
      this.masterGain.connect(this.ctx.destination);

      // Resume if suspended (iOS requirement)
      if (this.ctx.state === 'suspended') {
        await this.ctx.resume();
      }

      this._initialized = true;
      console.log('[SteamboatAudio] Initialized');
      return true;
    } catch (err) {
      console.error('[SteamboatAudio] Failed to initialize:', err);
      return false;
    }
  }

  _ensureInit() {
    if (!this._initialized) {
      console.warn('[SteamboatAudio] Not initialized. Call init() first.');
      return false;
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return true;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STEAMBOAT WHISTLE — Willie's signature sound
  // ═══════════════════════════════════════════════════════════════════════

  playWhistle(duration = 1.2) {
    if (!this._ensureInit()) return;

    const now = this.ctx.currentTime;
    const endTime = now + duration;

    // Three-note chord: A4, C#5, E5 (A major)
    const frequencies = [440, 554.37, 659.25];

    frequencies.forEach((freq, i) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const filter = this.ctx.createBiquadFilter();

      // Sawtooth for that brassy steamboat tone
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq * 0.5, now);
      osc.frequency.linearRampToValueAtTime(freq, now + 0.08);
      osc.frequency.setValueAtTime(freq, now + duration * 0.7);
      osc.frequency.linearRampToValueAtTime(freq * 0.97, endTime);

      // Warm lowpass
      filter.type = 'lowpass';
      filter.frequency.value = 2200;
      filter.Q.value = 1.5;

      // Envelope
      const baseGain = 0.12 - i * 0.025;
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(baseGain, now + 0.05);
      gain.gain.setValueAtTime(baseGain, now + duration * 0.75);
      gain.gain.exponentialRampToValueAtTime(0.001, endTime);

      // Connect
      osc.connect(filter);
      filter.connect(gain);
      gain.connect(this.masterGain);

      osc.start(now);
      osc.stop(endTime + 0.1);
    });

    // Steam hiss
    this._playNoise({
      duration: duration * 0.9,
      filterFreq: 4000,
      filterType: 'highpass',
      gainStart: 0.06,
      gainEnd: 0.02,
      delay: 0.05
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // PETE'S GRUMBLE — Low angry rumble
  // ═══════════════════════════════════════════════════════════════════════

  playGrumble(duration = 0.8) {
    if (!this._ensureInit()) return;

    const now = this.ctx.currentTime;
    const endTime = now + duration;

    // Low rumble with multiple oscillators
    [55, 82.5, 110].forEach((freq, i) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, now);
      osc.frequency.linearRampToValueAtTime(freq * 0.8, endTime);

      const baseGain = 0.08 - i * 0.02;
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(baseGain, now + 0.1);
      gain.gain.linearRampToValueAtTime(baseGain * 0.5, now + duration * 0.6);
      gain.gain.exponentialRampToValueAtTime(0.001, endTime);

      osc.connect(gain);
      gain.connect(this.masterGain);

      osc.start(now);
      osc.stop(endTime + 0.1);
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // PARROT SQUAWK — High-pitched bird sound
  // ═══════════════════════════════════════════════════════════════════════

  playSquawk(duration = 0.4) {
    if (!this._ensureInit()) return;

    const now = this.ctx.currentTime;

    // Two quick chirps
    [0, 0.15].forEach((delay) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'square';

      const startFreq = 800 + Math.random() * 400;
      const t = now + delay;
      osc.frequency.setValueAtTime(startFreq, t);
      osc.frequency.linearRampToValueAtTime(startFreq * 1.5, t + 0.05);
      osc.frequency.linearRampToValueAtTime(startFreq * 0.7, t + 0.15);

      gain.gain.setValueAtTime(0, t);
      gain.gain.linearRampToValueAtTime(0.1, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);

      osc.connect(gain);
      gain.connect(this.masterGain);

      osc.start(t);
      osc.stop(t + 0.2);
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STOMP — Heavy footstep
  // ═══════════════════════════════════════════════════════════════════════

  playStomp() {
    if (!this._ensureInit()) return;

    const now = this.ctx.currentTime;

    // Low thud
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(80, now);
    osc.frequency.exponentialRampToValueAtTime(40, now + 0.15);

    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

    osc.connect(gain);
    gain.connect(this.masterGain);

    osc.start(now);
    osc.stop(now + 0.25);

    // Add some noise for texture
    this._playNoise({
      duration: 0.1,
      filterFreq: 200,
      filterType: 'lowpass',
      gainStart: 0.1,
      gainEnd: 0.01
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // SPLASH — Water sound
  // ═══════════════════════════════════════════════════════════════════════

  playSplash() {
    if (!this._ensureInit()) return;

    this._playNoise({
      duration: 0.6,
      filterFreq: 800,
      filterType: 'bandpass',
      filterQ: 1,
      gainStart: 0.15,
      gainEnd: 0.01
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // STEAM PUFF — Short burst from smokestack
  // ═══════════════════════════════════════════════════════════════════════

  playSteam() {
    if (!this._ensureInit()) return;

    this._playNoise({
      duration: 0.3,
      filterFreq: 3000,
      filterType: 'highpass',
      gainStart: 0.08,
      gainEnd: 0.01
    });
  }

  // ═══════════════════════════════════════════════════════════════════════
  // AMBIENT ENGINE + WATER
  // ═══════════════════════════════════════════════════════════════════════

  startAmbient() {
    if (!this._ensureInit()) return;
    if (this.isAmbientPlaying) return;

    this.isAmbientPlaying = true;

    // Engine rumble
    const engineOsc = this.ctx.createOscillator();
    const engineGain = this.ctx.createGain();
    const engineFilter = this.ctx.createBiquadFilter();

    engineOsc.type = 'sawtooth';
    engineOsc.frequency.value = 38;

    engineFilter.type = 'lowpass';
    engineFilter.frequency.value = 120;

    // Subtle throb via LFO
    const lfo = this.ctx.createOscillator();
    const lfoGain = this.ctx.createGain();
    lfo.frequency.value = 0.7;
    lfoGain.gain.value = 4;
    lfo.connect(lfoGain);
    lfoGain.connect(engineOsc.frequency);
    lfo.start();

    engineGain.gain.value = 0.025;

    engineOsc.connect(engineFilter);
    engineFilter.connect(engineGain);
    engineGain.connect(this.masterGain);
    engineOsc.start();

    // Water noise
    const waterNoise = this.ctx.createBufferSource();
    const waterBuffer = this.ctx.createBuffer(1, this.ctx.sampleRate * 3, this.ctx.sampleRate);
    const waterData = waterBuffer.getChannelData(0);
    for (let i = 0; i < waterData.length; i++) {
      waterData[i] = (Math.random() * 2 - 1) * Math.sin(i * 0.0004) * 0.5;
    }
    waterNoise.buffer = waterBuffer;
    waterNoise.loop = true;

    const waterFilter = this.ctx.createBiquadFilter();
    waterFilter.type = 'bandpass';
    waterFilter.frequency.value = 350;
    waterFilter.Q.value = 0.4;

    const waterGain = this.ctx.createGain();
    waterGain.gain.value = 0.015;

    waterNoise.connect(waterFilter);
    waterFilter.connect(waterGain);
    waterGain.connect(this.masterGain);
    waterNoise.start();

    // Store for cleanup
    this.ambientNodes = [engineOsc, lfo, waterNoise];
  }

  stopAmbient() {
    if (!this.isAmbientPlaying) return;

    this.ambientNodes.forEach(node => {
      try {
        node.stop();
      } catch (e) { /* already stopped */ }
    });
    this.ambientNodes = [];
    this.isAmbientPlaying = false;
  }

  // ═══════════════════════════════════════════════════════════════════════
  // PLAY BY NAME — For AI-directed cues
  // ═══════════════════════════════════════════════════════════════════════

  play(cueName) {
    switch (cueName) {
      case 'whistle': this.playWhistle(); break;
      case 'grumble': this.playGrumble(); break;
      case 'squawk': this.playSquawk(); break;
      case 'stomp': this.playStomp(); break;
      case 'splash': this.playSplash(); break;
      case 'steam': this.playSteam(); break;
      default:
        console.warn(`[SteamboatAudio] Unknown cue: ${cueName}`);
    }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // HELPERS
  // ═══════════════════════════════════════════════════════════════════════

  _playNoise({ duration, filterFreq, filterType, filterQ = 1, gainStart, gainEnd, delay = 0 }) {
    const now = this.ctx.currentTime + delay;

    const noise = this.ctx.createBufferSource();
    const noiseBuffer = this.ctx.createBuffer(1, this.ctx.sampleRate * duration, this.ctx.sampleRate);
    const noiseData = noiseBuffer.getChannelData(0);
    for (let i = 0; i < noiseData.length; i++) {
      noiseData[i] = Math.random() * 2 - 1;
    }
    noise.buffer = noiseBuffer;

    const filter = this.ctx.createBiquadFilter();
    filter.type = filterType;
    filter.frequency.value = filterFreq;
    filter.Q.value = filterQ;

    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(gainStart, now);
    gain.gain.exponentialRampToValueAtTime(Math.max(gainEnd, 0.001), now + duration);

    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.masterGain);

    noise.start(now);
  }

  // ═══════════════════════════════════════════════════════════════════════
  // CLEANUP
  // ═══════════════════════════════════════════════════════════════════════

  dispose() {
    this.stopAmbient();
    if (this.ctx) {
      this.ctx.close().catch(() => {});
      this.ctx = null;
    }
    this._initialized = false;
  }
}

// Export
if (typeof window !== 'undefined') {
  window.SteamboatAudio = SteamboatAudio;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { SteamboatAudio };
}
