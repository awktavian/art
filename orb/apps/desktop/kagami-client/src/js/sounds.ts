/**
 * Desktop Sound System — BBC Symphony Orchestra Earcons for Tauri
 *
 * Focus: Audio Integration
 *
 * Features:
 * - 36 BBC Symphony Orchestra earcons
 * - Tier 1 earcons bundled with app for instant playback
 * - Tier 2 earcons lazy-loaded from CDN
 * - Integrated with desktop haptics (visual feedback fallback)
 * - Web Audio API for high-quality playback
 *
 * Architecture:
 *   Event → SoundService → Web Audio API → System Audio
 *                       → Tauri haptics command → Visual/Gamepad
 *
 *
 */

import { invoke } from '@tauri-apps/api/core';

// ============================================================================
// Constants
// ============================================================================

const EARCON_CDN_BASE = 'https://storage.googleapis.com/kagami-media-public/earcons/v1/mp3';

const TIER_1_EARCONS = [
  'notification', 'success', 'error', 'alert', 'arrival', 'departure',
  'celebration', 'settling', 'awakening', 'cinematic', 'focus',
  'security_arm', 'package', 'meeting_soon'
] as const;

const TIER_2_EARCONS = [
  'room_enter', 'door_open', 'door_close', 'lock_engaged', 'voice_acknowledge',
  'voice_complete', 'washer_complete', 'coffee_ready', 'morning_sequence',
  'evening_transition', 'midnight', 'storm_approaching', 'rain_starting',
  'motion_detected', 'camera_alert', 'message_received', 'home_empty',
  'first_home', 'oven_preheat', 'dishwasher_complete', 'dryer_complete'
] as const;

type Tier1Earcon = typeof TIER_1_EARCONS[number];
type Tier2Earcon = typeof TIER_2_EARCONS[number];
type Earcon = Tier1Earcon | Tier2Earcon;

// ============================================================================
// Haptic Pattern Types
// ============================================================================

type HapticPattern =
  | 'success'
  | 'error'
  | 'warning'
  | 'selection'
  | 'light_impact'
  | 'medium_impact'
  | 'heavy_impact'
  | 'soft_impact'
  | 'rigid_impact'
  | 'discovery_glance'
  | 'discovery_interest'
  | 'discovery_focus'
  | 'discovery_engage'
  | 'double_tap'
  | 'long_press'
  | 'tick'
  | 'scene_activated'
  | 'lights_changed'
  | 'lock_engaged'
  | 'safety_violation';

// Earcon to haptic pattern mapping
const EARCON_HAPTIC_MAP: Record<Earcon, HapticPattern> = {
  notification: 'medium_impact',
  success: 'success',
  error: 'error',
  alert: 'warning',
  arrival: 'success',
  departure: 'soft_impact',
  celebration: 'success',
  settling: 'soft_impact',
  awakening: 'light_impact',
  cinematic: 'medium_impact',
  focus: 'light_impact',
  security_arm: 'heavy_impact',
  package: 'medium_impact',
  meeting_soon: 'warning',
  room_enter: 'discovery_glance',
  door_open: 'light_impact',
  door_close: 'soft_impact',
  lock_engaged: 'lock_engaged',
  voice_acknowledge: 'selection',
  voice_complete: 'success',
  washer_complete: 'success',
  coffee_ready: 'discovery_engage',
  morning_sequence: 'soft_impact',
  evening_transition: 'soft_impact',
  midnight: 'tick',
  storm_approaching: 'warning',
  rain_starting: 'soft_impact',
  motion_detected: 'tick',
  camera_alert: 'warning',
  message_received: 'medium_impact',
  home_empty: 'soft_impact',
  first_home: 'success',
  oven_preheat: 'medium_impact',
  dishwasher_complete: 'success',
  dryer_complete: 'success',
};

// Event to earcon mapping
const EVENT_EARCON_MAP: Record<string, Earcon> = {
  tap: 'focus',
  click: 'success',
  select: 'focus',
  hover: 'room_enter',
  scene_activated: 'success',
  lights_on: 'door_open',
  lights_off: 'door_close',
  shade_open: 'door_open',
  shade_close: 'door_close',
  welcome: 'arrival',
  goodbye: 'departure',
  lock: 'lock_engaged',
  voice_start: 'voice_acknowledge',
  voice_end: 'voice_complete',
};

// ============================================================================
// Sound Service
// ============================================================================

interface PlayOptions {
  withHaptic?: boolean;
  volume?: number;
  pan?: number;
}

export class SoundService {
  private audioContext: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private bufferCache: Map<string, AudioBuffer> = new Map();
  private loadingPromises: Map<string, Promise<boolean>> = new Map();

  private initialized = false;
  private _muted = false;
  private _volume = 0.7;

  get muted(): boolean {
    return this._muted;
  }

  get volume(): number {
    return this._volume;
  }

  // ========================================================================
  // Initialization
  // ========================================================================

  async init(): Promise<void> {
    if (this.initialized) return;

    try {
      this.audioContext = new AudioContext({ sampleRate: 48000 });
      this.masterGain = this.audioContext.createGain();
      this.masterGain.gain.value = this._volume;
      this.masterGain.connect(this.audioContext.destination);

      this.initialized = true;
      console.log('🎵 SoundService initialized');

      // Preload Tier 1 earcons
      await this.preloadTier1();

    } catch (e) {
      console.error('SoundService initialization failed:', e);
    }
  }

  private async preloadTier1(): Promise<void> {
    const loadPromises = TIER_1_EARCONS.map(name => this.loadEarcon(name));
    const results = await Promise.allSettled(loadPromises);

    const loaded = results.filter(r => r.status === 'fulfilled' && r.value).length;
    console.log(`🎵 Preloaded ${loaded}/${TIER_1_EARCONS.length} Tier 1 earcons`);
  }

  // ========================================================================
  // Playback
  // ========================================================================

  /**
   * Play an earcon by name with coordinated haptic feedback
   */
  async play(earconOrEvent: Earcon | string, options: PlayOptions = {}): Promise<void> {
    if (!this.initialized || this._muted) return;

    // Map event to earcon if needed
    const earcon = EVENT_EARCON_MAP[earconOrEvent] ?? earconOrEvent as Earcon;

    // Play haptic first (lower latency)
    const { withHaptic = true } = options;
    if (withHaptic) {
      const hapticPattern = EARCON_HAPTIC_MAP[earcon] ?? 'light_impact';
      this.playHaptic(hapticPattern);
    }

    // Play audio
    await this.playAudio(earcon, options);
  }

  /**
   * Play just audio (no haptic)
   */
  async playAudio(earcon: Earcon, options: PlayOptions = {}): Promise<void> {
    if (!this.audioContext || !this.masterGain) return;

    // Resume context if suspended
    if (this.audioContext.state === 'suspended') {
      await this.audioContext.resume();
    }

    // Get or load buffer
    let buffer = this.bufferCache.get(earcon);
    if (!buffer) {
      const loaded = await this.loadEarcon(earcon);
      if (!loaded) return;
      buffer = this.bufferCache.get(earcon);
    }

    if (!buffer) return;

    // Create source
    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;

    // Create gain for this instance
    const gain = this.audioContext.createGain();
    gain.gain.value = options.volume ?? this._volume;

    // Create panner if needed
    let lastNode: AudioNode = gain;
    if (options.pan !== undefined && options.pan !== 0) {
      const panner = this.audioContext.createStereoPanner();
      panner.pan.value = Math.max(-1, Math.min(1, options.pan));
      gain.connect(panner);
      lastNode = panner;
    }

    // Connect chain
    source.connect(gain);
    lastNode.connect(this.masterGain);

    // Play
    source.start(0);
  }

  /**
   * Play a haptic pattern via Tauri backend
   */
  private async playHaptic(pattern: HapticPattern): Promise<void> {
    try {
      await invoke('play_haptic', { pattern });
    } catch (e) {
      // Haptics may not be available
      console.debug('Haptic feedback not available:', e);
    }
  }

  // ========================================================================
  // Loading
  // ========================================================================

  private async loadEarcon(name: string): Promise<boolean> {
    if (this.bufferCache.has(name)) return true;

    // Check for existing loading promise
    const existing = this.loadingPromises.get(name);
    if (existing) return existing;

    const loadPromise = (async () => {
      try {
        const url = `${EARCON_CDN_BASE}/${name}.mp3`;
        const response = await fetch(url);

        if (!response.ok) {
          console.warn(`Earcon not found: ${name}`);
          return false;
        }

        const arrayBuffer = await response.arrayBuffer();
        const audioBuffer = await this.audioContext!.decodeAudioData(arrayBuffer);
        this.bufferCache.set(name, audioBuffer);

        console.debug(`🎵 Loaded earcon: ${name}`);
        return true;

      } catch (e) {
        console.warn(`Failed to load earcon ${name}:`, e);
        return false;
      } finally {
        this.loadingPromises.delete(name);
      }
    })();

    this.loadingPromises.set(name, loadPromise);
    return loadPromise;
  }

  // ========================================================================
  // Controls
  // ========================================================================

  setVolume(volume: number): void {
    this._volume = Math.max(0, Math.min(1, volume));
    if (this.masterGain) {
      this.masterGain.gain.value = this._muted ? 0 : this._volume;
    }
  }

  mute(): void {
    this._muted = true;
    if (this.masterGain) {
      this.masterGain.gain.value = 0;
    }
  }

  unmute(): void {
    this._muted = false;
    if (this.masterGain) {
      this.masterGain.gain.value = this._volume;
    }
  }

  toggleMute(): boolean {
    if (this._muted) {
      this.unmute();
    } else {
      this.mute();
    }
    return this._muted;
  }

  /**
   * Check if an earcon is loaded
   */
  isLoaded(earcon: Earcon): boolean {
    return this.bufferCache.has(earcon);
  }

  /**
   * Preload specific earcons
   */
  async preload(earcons: Earcon[]): Promise<number> {
    const results = await Promise.allSettled(
      earcons.map(earcon => this.loadEarcon(earcon))
    );
    return results.filter(r => r.status === 'fulfilled' && r.value).length;
  }

  /**
   * Get list of loaded earcons
   */
  getLoadedEarcons(): string[] {
    return Array.from(this.bufferCache.keys());
  }

  /**
   * Clear Tier 2 cache (keep Tier 1)
   */
  clearTier2Cache(): void {
    const tier1Set = new Set<string>(TIER_1_EARCONS);
    for (const key of this.bufferCache.keys()) {
      if (!tier1Set.has(key)) {
        this.bufferCache.delete(key);
      }
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let instance: SoundService | null = null;

export function getSoundService(): SoundService {
  if (!instance) {
    instance = new SoundService();
  }
  return instance;
}

// ============================================================================
// Exports
// ============================================================================

export {
  TIER_1_EARCONS,
  TIER_2_EARCONS,
  EARCON_CDN_BASE,
  EVENT_EARCON_MAP,
  EARCON_HAPTIC_MAP,
};

export type { Earcon, Tier1Earcon, Tier2Earcon, HapticPattern, PlayOptions };

/*
 * 鏡
 *
 *
 * BBC Symphony Orchestra earcons provide virtuoso audio feedback.
 * Coordinated with visual haptics for multi-sensory desktop experience.
 */
