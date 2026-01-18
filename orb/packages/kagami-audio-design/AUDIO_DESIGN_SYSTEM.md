# Kagami Unified Audio Design System

**Colony: Crystal (e7) — Verification & Polish**

```
    ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫
   ╔═══════════════════════════════════════════════════╗
   ║  Every sound carries meaning. Every touch speaks. ║
   ║  Same experience. Every platform. Every person.   ║
   ╚═══════════════════════════════════════════════════╝
    ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫
```

This document defines the canonical audio/haptic feedback patterns across all Kagami platforms.
All platforms MUST implement these standardized patterns for cross-device consistency.

**h(x) >= 0. For EVERYONE.**

---

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Quick Start by Platform](#quick-start-by-platform)
3. [ADSR Envelopes Explained](#adsr-envelopes-explained)
4. [Musical Theory for Engineers](#musical-theory-for-engineers)
5. [Semantic Feedback Categories](#semantic-feedback-categories)
6. [Platform Implementation Matrix](#platform-implementation-matrix)
7. [Canonical Patterns](#canonical-patterns)
8. [visionOS Spatial Audio Guidelines](#visionos-spatial-audio-guidelines)
9. [Persona-Specific Adaptations](#persona-specific-adaptations)
10. [Accessibility Requirements](#accessibility-requirements)
11. [Testing Standards](#testing-standards)

---

## Design Philosophy

### Core Principles

1. **Semantic Consistency** — Same meaning, same pattern everywhere
2. **Platform-Native Feel** — Adapt to each platform's strengths
3. **Graceful Degradation** — Always provide feedback, even without audio
4. **Accessibility First** — Patterns must work for all users
5. **Non-Intrusive** — Feedback should inform, not distract

### The Feedback Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│  1. Haptic (primary where available)                    │
│  2. Audio (complement or fallback)                      │
│  3. Visual (always present as confirmation)             │
└─────────────────────────────────────────────────────────┘
```

Users receive feedback through available channels. If haptics are disabled,
audio plays. If audio is muted, visual feedback is always shown.

### Fibonacci Timing Philosophy

**Why Fibonacci? Because nature figured this out millions of years ago.**

```
┌────────────────────────────────────────────────────────────────────┐
│  FIBONACCI SEQUENCE: 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144... │
│                                                                    │
│  In milliseconds for audio design:                                 │
│                                                                    │
│    34ms  → Instantaneous (click)                                   │
│    55ms  → Quick tap                                               │
│    89ms  → Micro-interaction      ← Selection, navigation         │
│    144ms → Button response        ← Confirmation                   │
│    233ms → Short feedback         ← Notification                   │
│    377ms → Standard feedback      ← Success, error                 │
│    610ms → Rich feedback          ← Scene changes                  │
│    987ms → Ambient transitions    ← Wake/sleep                     │
│                                                                    │
│  Why it feels right: Golden ratio (φ ≈ 1.618) creates natural     │
│  progressions that human perception evolved to find pleasing.      │
└────────────────────────────────────────────────────────────────────┘
```

Our pattern durations approximate these values because arbitrary round numbers
(100ms, 200ms, 500ms) feel mechanical. Fibonacci feels *organic*.

---

## Quick Start by Platform

### iOS (Swift)

```swift
import UIKit
import AVFoundation
import CoreHaptics

// MARK: - Quick Start: iOS Audio/Haptic Feedback

class KagamiFeedback {
    static let shared = KagamiFeedback()

    private var hapticEngine: CHHapticEngine?
    private let audioEngine = AVAudioEngine()

    init() {
        setupHaptics()
        setupAudio()
    }

    // MARK: - Haptic Setup
    private func setupHaptics() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else { return }
        do {
            hapticEngine = try CHHapticEngine()
            try hapticEngine?.start()
        } catch {
            print("Haptic engine failed: \(error)")
        }
    }

    // MARK: - Play Success Pattern (C major chord = happy!)
    func playSuccess() {
        // C-E-G ascending = major chord = triumph!
        playToneSequence([
            (freq: 523, duration: 0.1),  // C5
            (freq: 659, duration: 0.1),  // E5
            (freq: 784, duration: 0.15)  // G5
        ], envelope: .soft)

        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }

    // MARK: - Play Error Pattern (descending = sad)
    func playError() {
        // A-F descending = minor feel = something's wrong
        playToneSequence([
            (freq: 440, duration: 0.15),  // A4
            (freq: 349, duration: 0.2)    // F4
        ], envelope: .harsh)

        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.error)
    }

    // MARK: - Play Emergency Pattern (URGENT!)
    func playEmergency() {
        // Alternating high frequencies + aggressive timing
        // This MUST cut through everything
        playToneSequence([
            (freq: 1047, duration: 0.15), // C6
            (freq: 880, duration: 0.15),  // A5
            (freq: 1047, duration: 0.15), // C6
            (freq: 880, duration: 0.15)   // A5
        ], envelope: .harsh, repeat: 5)

        // Maximum haptic intensity
        let generator = UINotificationFeedbackGenerator()
        for _ in 0..<5 {
            generator.notificationOccurred(.error)
            Thread.sleep(forTimeInterval: 0.3)
        }
    }

    // MARK: - Tone Generation
    private func playToneSequence(_ tones: [(freq: Float, duration: Double)],
                                   envelope: Envelope,
                                   repeat count: Int = 1) {
        // Implementation uses AVAudioEngine with oscillator node
        // See full implementation in KagamiAudioEngine.swift
    }
}

// Usage:
// KagamiFeedback.shared.playSuccess()
// KagamiFeedback.shared.playError()
// KagamiFeedback.shared.playEmergency()  // Fire, intrusion, medical
```

### Android (Kotlin)

```kotlin
package com.kagami.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import kotlin.math.PI
import kotlin.math.sin

/**
 * Kagami Audio/Haptic Feedback - Quick Start
 *
 * Musical hint: C-E-G = C major chord = HAPPY!
 *               A-F descending = sadness/error
 */
class KagamiFeedback(private val context: Context) {

    private val vibrator: Vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        val manager = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
        manager.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
    }

    // MARK: - Success Pattern (C major arpeggio = triumph!)
    fun playSuccess() {
        // C5 -> E5 -> G5: Rising major chord = success!
        playToneSequence(
            listOf(
                Tone(523f, 100),  // C5
                Tone(659f, 100),  // E5
                Tone(784f, 150)   // G5
            ),
            Envelope.SOFT
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Double click for success confirmation
            vibrator.vibrate(
                VibrationEffect.createComposition()
                    .addPrimitive(VibrationEffect.Composition.PRIMITIVE_CLICK)
                    .addPrimitive(VibrationEffect.Composition.PRIMITIVE_CLICK)
                    .compose()
            )
        } else {
            vibrator.vibrate(VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE))
        }
    }

    // MARK: - Error Pattern (descending = something went wrong)
    fun playError() {
        // A4 -> F4: Descending = disappointment
        playToneSequence(
            listOf(
                Tone(440f, 150),  // A4
                Tone(349f, 200)   // F4
            ),
            Envelope.HARSH
        )

        vibrator.vibrate(VibrationEffect.createOneShot(100, 255))
    }

    // MARK: - Emergency Pattern (CRITICAL - must cut through!)
    fun playEmergency() {
        // Alternating C6-A5 at max volume, repeated
        // This pattern must be unmissable
        repeat(5) {
            playToneSequence(
                listOf(
                    Tone(1047f, 150),  // C6 - piercing high
                    Tone(880f, 150)    // A5
                ),
                Envelope.HARSH
            )

            vibrator.vibrate(
                VibrationEffect.createWaveform(
                    longArrayOf(0, 200, 100, 200),
                    intArrayOf(255, 0, 255, 0),
                    -1
                )
            )
            Thread.sleep(300)
        }
    }

    // MARK: - Thermostat Up (warm rising tone)
    fun playThermostatUp() {
        playToneSequence(
            listOf(
                Tone(440f, 100),  // A4
                Tone(523f, 100),  // C5
                Tone(659f, 100)   // E5 (rising = warming)
            ),
            Envelope.SOFT
        )
        vibrator.vibrate(VibrationEffect.createOneShot(50, 128))
    }

    // MARK: - Thermostat Down (cool falling tone)
    fun playThermostatDown() {
        playToneSequence(
            listOf(
                Tone(659f, 100),  // E5
                Tone(523f, 100),  // C5
                Tone(440f, 100)   // A4 (falling = cooling)
            ),
            Envelope.SOFT
        )
        vibrator.vibrate(VibrationEffect.createOneShot(50, 128))
    }

    // MARK: - Tone Generation
    private fun playToneSequence(tones: List<Tone>, envelope: Envelope) {
        // Generate samples for each tone with ADSR envelope
        // See full implementation in KagamiAudioEngine.kt
    }

    data class Tone(val frequency: Float, val durationMs: Int)
    enum class Envelope { SHARP, SOFT, HARSH, AMBIENT }
}

// Usage:
// val feedback = KagamiFeedback(context)
// feedback.playSuccess()
// feedback.playEmergency()  // Fire, intrusion, medical
```

### Hub (Rust)

```rust
//! Kagami Audio Feedback - Hub Implementation
//!
//! Musical theory reminder:
//!   C-E-G (523-659-784 Hz) = C major chord = HAPPY!
//!   Descending intervals = sadness/concern
//!   High frequencies (>800 Hz) = attention/urgency

use rodio::{OutputStream, Sink, Source};
use std::time::Duration;

/// Envelope shapes for audio synthesis
#[derive(Clone, Copy)]
pub enum Envelope {
    /// Quick attack, full sustain, fast release (clicks)
    Sharp { attack_ms: u32, decay_ms: u32, release_ms: u32 },
    /// Gentle fade in/out (pleasant tones)
    Soft { attack_ms: u32, decay_ms: u32, release_ms: u32 },
    /// Instant attack, harsh sound (alerts)
    Harsh { attack_ms: u32, decay_ms: u32, release_ms: u32 },
}

impl Default for Envelope {
    fn default() -> Self {
        Envelope::Soft { attack_ms: 50, decay_ms: 100, release_ms: 100 }
    }
}

/// A single tone in a pattern
pub struct Tone {
    pub frequency: f32,
    pub duration_ms: u32,
}

/// Kagami audio feedback system
pub struct KagamiFeedback {
    _stream: OutputStream,
    sink: Sink,
}

impl KagamiFeedback {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let (stream, stream_handle) = OutputStream::try_default()?;
        let sink = Sink::try_new(&stream_handle)?;
        Ok(Self { _stream: stream, sink })
    }

    /// Success pattern: C-E-G ascending (major chord = triumph!)
    pub fn play_success(&self) {
        self.play_sequence(&[
            Tone { frequency: 523.0, duration_ms: 100 },  // C5
            Tone { frequency: 659.0, duration_ms: 100 },  // E5
            Tone { frequency: 784.0, duration_ms: 150 },  // G5
        ], Envelope::default());
    }

    /// Error pattern: A-F descending (minor feel = problem)
    pub fn play_error(&self) {
        self.play_sequence(&[
            Tone { frequency: 440.0, duration_ms: 150 },  // A4
            Tone { frequency: 349.0, duration_ms: 200 },  // F4
        ], Envelope::Harsh { attack_ms: 2, decay_ms: 20, release_ms: 50 });
    }

    /// Emergency pattern: CRITICAL - fire, intrusion, medical
    /// This MUST cut through everything. Repeat until acknowledged.
    pub fn play_emergency(&self) {
        for _ in 0..5 {
            self.play_sequence(&[
                Tone { frequency: 1047.0, duration_ms: 150 },  // C6 - piercing
                Tone { frequency: 880.0, duration_ms: 150 },   // A5
            ], Envelope::Harsh { attack_ms: 2, decay_ms: 10, release_ms: 30 });
            std::thread::sleep(Duration::from_millis(300));
        }
    }

    /// Safety alert: h(x) < 0 warning
    pub fn play_safety_alert(&self) {
        for _ in 0..3 {
            self.play_sequence(&[
                Tone { frequency: 880.0, duration_ms: 200 },  // A5
            ], Envelope::Harsh { attack_ms: 2, decay_ms: 20, release_ms: 50 });
            std::thread::sleep(Duration::from_millis(100));
        }
    }

    /// Thermostat up: warming tone (ascending)
    pub fn play_thermostat_up(&self) {
        self.play_sequence(&[
            Tone { frequency: 440.0, duration_ms: 100 },  // A4
            Tone { frequency: 523.0, duration_ms: 100 },  // C5
            Tone { frequency: 659.0, duration_ms: 100 },  // E5
        ], Envelope::default());
    }

    /// Thermostat down: cooling tone (descending)
    pub fn play_thermostat_down(&self) {
        self.play_sequence(&[
            Tone { frequency: 659.0, duration_ms: 100 },  // E5
            Tone { frequency: 523.0, duration_ms: 100 },  // C5
            Tone { frequency: 440.0, duration_ms: 100 },  // A4
        ], Envelope::default());
    }

    fn play_sequence(&self, tones: &[Tone], envelope: Envelope) {
        // Implementation generates sine waves with ADSR envelope
        // See full implementation in kagami_audio/src/synthesis.rs
    }
}

// Usage:
// let feedback = KagamiFeedback::new()?;
// feedback.play_success();
// feedback.play_emergency();  // Fire, intrusion, medical
```

### Desktop (TypeScript + Web Audio API)

```typescript
/**
 * Kagami Audio Feedback - Desktop (Tauri + Web Audio API)
 *
 * Musical theory reminder:
 *   C-E-G (523-659-784 Hz) = C major chord = HAPPY!
 *   Descending intervals = sadness/error
 *   High frequencies (>800 Hz) = attention/urgency
 */

class KagamiFeedback {
  private audioContext: AudioContext;

  constructor() {
    this.audioContext = new AudioContext();
  }

  // MARK: - Success Pattern (C major arpeggio = triumph!)
  async playSuccess(): Promise<void> {
    await this.playToneSequence([
      { freq: 523, durationMs: 100 },  // C5 - root
      { freq: 659, durationMs: 100 },  // E5 - major third
      { freq: 784, durationMs: 150 },  // G5 - perfect fifth
    ], 'soft');
  }

  // MARK: - Error Pattern (descending = disappointment)
  async playError(): Promise<void> {
    await this.playToneSequence([
      { freq: 440, durationMs: 150 },  // A4 - starts confident
      { freq: 349, durationMs: 200 },  // F4 - drops down (sad)
    ], 'harsh');
  }

  // MARK: - Emergency Pattern (CRITICAL - must cut through!)
  async playEmergency(): Promise<void> {
    for (let i = 0; i < 5; i++) {
      await this.playToneSequence([
        { freq: 1047, durationMs: 150 },  // C6 - piercing
        { freq: 880, durationMs: 150 },   // A5
      ], 'harsh');
      await this.sleep(300);
    }
  }

  // MARK: - Thermostat Up (warm rising tone)
  async playThermostatUp(): Promise<void> {
    await this.playToneSequence([
      { freq: 440, durationMs: 100 },  // A4 (warm base)
      { freq: 523, durationMs: 100 },  // C5 (rising)
      { freq: 659, durationMs: 100 },  // E5 (warm peak)
    ], 'soft');
  }

  // MARK: - Thermostat Down (cool falling tone)
  async playThermostatDown(): Promise<void> {
    await this.playToneSequence([
      { freq: 659, durationMs: 100 },  // E5 (start high)
      { freq: 523, durationMs: 100 },  // C5 (falling)
      { freq: 440, durationMs: 100 },  // A4 (cool base)
    ], 'soft');
  }

  // MARK: - ADSR Envelope Application
  private applyEnvelope(
    gainNode: GainNode,
    envelope: 'sharp' | 'soft' | 'harsh' | 'ambient',
    startTime: number,
    durationMs: number
  ): void {
    const envelopes = {
      sharp: { attack: 0.005, decay: 0.01, sustain: 1.0, release: 0.02 },
      soft: { attack: 0.05, decay: 0.1, sustain: 0.8, release: 0.1 },
      harsh: { attack: 0.002, decay: 0.02, sustain: 0.9, release: 0.05 },
      ambient: { attack: 0.3, decay: 0.2, sustain: 0.5, release: 0.3 },
    };

    const env = envelopes[envelope];
    const durationSec = durationMs / 1000;

    gainNode.gain.setValueAtTime(0, startTime);
    gainNode.gain.linearRampToValueAtTime(1.0, startTime + env.attack);
    gainNode.gain.linearRampToValueAtTime(env.sustain, startTime + env.attack + env.decay);
    gainNode.gain.setValueAtTime(env.sustain, startTime + durationSec - env.release);
    gainNode.gain.linearRampToValueAtTime(0, startTime + durationSec);
  }

  // MARK: - Tone Sequence Generation
  private async playToneSequence(
    tones: Array<{ freq: number; durationMs: number }>,
    envelope: 'sharp' | 'soft' | 'harsh' | 'ambient'
  ): Promise<void> {
    let currentTime = this.audioContext.currentTime;

    for (const tone of tones) {
      const oscillator = this.audioContext.createOscillator();
      const gainNode = this.audioContext.createGain();

      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(tone.freq, currentTime);

      oscillator.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      this.applyEnvelope(gainNode, envelope, currentTime, tone.durationMs);

      oscillator.start(currentTime);
      oscillator.stop(currentTime + tone.durationMs / 1000);

      currentTime += tone.durationMs / 1000;
    }

    // Wait for sequence to complete
    await this.sleep(tones.reduce((sum, t) => sum + t.durationMs, 0));
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Tauri integration: Invoke from Rust backend
// window.__TAURI__.invoke('play_feedback', { pattern: 'success' });

// Usage:
// const feedback = new KagamiFeedback();
// await feedback.playSuccess();
// await feedback.playEmergency();  // Fire, intrusion, medical
```

---

## ADSR Envelopes Explained

**ADSR = Attack, Decay, Sustain, Release**

Every sound has a shape. ADSR defines that shape.

```
       SHARP Envelope               SOFT Envelope                HARSH Envelope
       (clicks, taps)               (pleasant tones)             (alerts, warnings)

    A │    ╱╲                    A │      ╱‾‾‾╲                A │╱╲
    m │   ╱  ╲                   m │     ╱     ╲               m ││ ╲
    p │  ╱    ╲                  p │    ╱       ╲              p ││  ╲
    l │ ╱      ╲                 l │   ╱         ╲             l ││   ╲
      │╱        ╲                  │  ╱           ╲              │╱     ╲
      └──────────────→           └────────────────────→        └────────────→
       A  D  S   R                 A    D   S     R              A D  S   R

       Attack:  5ms               Attack:  50ms                Attack:  2ms
       Decay:  10ms               Decay:  100ms                Decay:  20ms
       Sustain: 100%              Sustain: 80%                 Sustain: 90%
       Release: 20ms              Release: 100ms               Release: 50ms

       Feel: Instant, precise     Feel: Warm, organic          Feel: Urgent, sharp
       Use: Selection, nav        Use: Success, scenes         Use: Errors, alerts


       AMBIENT Envelope
       (background, transitions)

    A │          ╱‾‾‾‾‾‾‾╲
    m │         ╱         ╲
    p │        ╱           ╲
    l │       ╱             ╲
      │      ╱               ╲
      └────────────────────────────→
             A      D   S       R

       Attack:  300ms
       Decay:   200ms
       Sustain: 50%
       Release: 300ms

       Feel: Ethereal, gradual
       Use: Wake/sleep, ambient
```

### Why Envelopes Matter

A 440Hz tone with SHARP envelope feels like a tap.
The same 440Hz tone with SOFT envelope feels like a notification.
With HARSH envelope, it feels like a warning.

**The frequency is the WHAT. The envelope is the HOW.**

### Envelope Formulas

```
Given: total_duration_ms, envelope_type

For SHARP (total 50ms):
  - Time 0-5ms:     amplitude rises 0 → 1.0 (attack)
  - Time 5-15ms:    amplitude holds at 1.0 (decay/sustain)
  - Time 15-35ms:   amplitude at 1.0 (sustain)
  - Time 35-50ms:   amplitude falls 1.0 → 0 (release)

For SOFT (total 350ms):
  - Time 0-50ms:    amplitude rises 0 → 1.0 (attack)
  - Time 50-150ms:  amplitude falls 1.0 → 0.8 (decay)
  - Time 150-250ms: amplitude at 0.8 (sustain)
  - Time 250-350ms: amplitude falls 0.8 → 0 (release)
```

### Duration Calculation with Repeat

```
Pattern: safety_alert
Sequence: [880Hz:200ms] + [rest:100ms] + [880Hz:200ms]
Base duration: 500ms
Repeat: 3

total_duration_ms = base_duration * repeat
                  = 500ms * 3
                  = 1500ms (1.5 seconds total)

Timeline:
  0ms────500ms────1000ms────1500ms
  │ beep beep │ beep beep │ beep beep │
```

---

## Musical Theory for Engineers

### The C Major Chord: Your Best Friend

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   C MAJOR CHORD = HAPPY / SUCCESS / TRIUMPH                        │
│                                                                    │
│   Notes: C - E - G                                                 │
│   Frequencies: 262 - 330 - 392 Hz (octave 4)                       │
│                523 - 659 - 784 Hz (octave 5) ← We use this one     │
│                                                                    │
│   ♪ Play C5-E5-G5 ascending = "We did it!"                         │
│   ♪ Play C5-E5-G5 together = Triumphant chord                      │
│                                                                    │
│   Piano visualization:                                             │
│   ┌─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┐                                    │
│   │ │█│ │█│ │ │█│ │█│ │█│ │ │ │                                    │
│   │ └┬┘ └┬┘ │ └┬┘ └┬┘ └┬┘ │ │                                    │
│   │ C│ D│ E│ F│ G│ A│ B│ C│                                       │
│   │  │  │▲ │  │▲ │  │  │  │                                       │
│   │  │  │E │  │G │  │  │  │                                       │
│   │  ▲                    │                                       │
│   │  C                    │                                       │
│   └──────────────────────────┘                                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Minor Intervals: For Errors and Sadness

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   DESCENDING = SAD / ERROR / CONCERN                               │
│                                                                    │
│   A → F (descending minor)                                         │
│   Frequencies: 440 → 349 Hz                                        │
│                                                                    │
│   ♪ Higher note to lower = "Something went wrong"                  │
│   ♪ The drop in pitch signals disappointment                       │
│                                                                    │
│   Visual:                                                          │
│           ●  A4 (440 Hz)                                           │
│          ╱                                                         │
│         ╱                                                          │
│        ●  F4 (349 Hz)                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### High Frequencies: Attention and Urgency

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│   HIGH FREQ (>800 Hz) = ATTENTION / URGENT / ALERT                 │
│                                                                    │
│   A5 (880 Hz) = Warning tone                                       │
│   C6 (1047 Hz) = Piercing alert                                    │
│                                                                    │
│   Why high frequencies grab attention:                             │
│   - Evolutionarily significant (baby cries, alarms)                │
│   - Cuts through ambient noise                                     │
│   - Hard to ignore                                                 │
│                                                                    │
│   Emergency pattern: C6-A5 alternating                             │
│   ♪ 1047-880-1047-880 Hz = "DANGER! PAY ATTENTION!"               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Pattern Psychology Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────┐
│  PATTERN              │ NOTES      │ EMOTION                    │
├───────────────────────┼────────────┼────────────────────────────┤
│  Ascending major      │ C-E-G ↑    │ Success, triumph, joy      │
│  Descending           │ A-F ↓      │ Error, sadness, concern    │
│  Single high tone     │ A5         │ Attention, notification    │
│  Repeated high tones  │ A5-A5-A5   │ Warning, urgency           │
│  Alternating high     │ C6-A5-C6   │ EMERGENCY, critical        │
│  Rising warmth        │ E4-A4-C5 ↑ │ Cozy, warming (fireplace)  │
│  Falling cool         │ C5-A4-C4 ↓ │ Cooling, dimming           │
│  Firm double tap      │ E5-A5      │ Secure, locked, confirmed  │
│  Rising sweep         │ G4-C5 ↑    │ Opening, revealing         │
│  Falling sweep        │ C5-C4 ↓    │ Closing, hiding            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Semantic Feedback Categories

### Primary Feedback (P0)

| Semantic | Meaning | Use Case |
|----------|---------|----------|
| `success` | Action completed positively | Scene activated, command executed |
| `error` | Action failed | Request denied, connection lost |
| `warning` | Attention needed | Safety alert, low battery |
| `notification` | New information | Message arrived, status change |

### Interaction Feedback (P1)

| Semantic | Meaning | Use Case |
|----------|---------|----------|
| `selection` | Item selected | Button tap, list row tap |
| `navigation_up` | Moving up in UI | Scroll up, previous item |
| `navigation_down` | Moving down in UI | Scroll down, next item |
| `confirmation` | Action confirmed | Double-tap, long press completion |

### Home Control Feedback (P1)

| Semantic | Meaning | Use Case |
|----------|---------|----------|
| `light_on` | Lights turning on | Rising brightness |
| `light_off` | Lights turning off | Falling brightness |
| `light_dim` | Lights dimming | Intermediate state |
| `shades_open` | Shades opening | Rising sweep |
| `shades_close` | Shades closing | Falling sweep |
| `fireplace_on` | Fireplace igniting | Warm rising pattern |
| `fireplace_off` | Fireplace extinguishing | Cool falling pattern |
| `lock_engaged` | Lock securing | Firm double tap |
| `scene_activated` | Scene change | Triple ascending |
| `tv_raise` | TV mount rising | Ascending pattern |
| `tv_lower` | TV mount lowering | Descending pattern |
| `thermostat_up` | Temperature increasing | Warm ascending |
| `thermostat_down` | Temperature decreasing | Cool descending |

### Safety Feedback (P0) - CRITICAL

| Semantic | Meaning | Use Case | Urgency |
|----------|---------|----------|---------|
| `safety_alert` | h(x) < 0 warning | Safety constraint violation | HIGH |
| `emergency` | Life/property threat | Fire, intrusion, medical | **CRITICAL** |
| `boundary_reached` | Limit hit | Scroll end, max/min value | LOW |

```
┌────────────────────────────────────────────────────────────────────┐
│  URGENCY ESCALATION                                                │
│                                                                    │
│  LOW ────────────────────────────────────────────────────► CRITICAL│
│                                                                    │
│  boundary_reached    warning    safety_alert         emergency     │
│       ●               ●             ●                    ★         │
│    (single tap)   (attention)  (h(x) < 0!)        (LIFE THREAT!)  │
│                                                                    │
│  • Longer duration as urgency increases                            │
│  • Higher frequencies as urgency increases                         │
│  • More repetitions as urgency increases                           │
│  • Emergency MUST repeat until acknowledged                        │
└────────────────────────────────────────────────────────────────────┘
```

---

## Platform Implementation Matrix

### Haptic Implementations

| Platform | Engine | Strengths | Limitations |
|----------|--------|-----------|-------------|
| iOS | Core Haptics + UIFeedbackGenerator | Rich patterns, intensity control | Phone only |
| watchOS | WKInterfaceDevice | Battery efficient | Limited patterns |
| visionOS | N/A | — | No haptics |
| Android | VibrationEffect | Wide support | Device-dependent |
| Hub | N/A | — | No haptics |
| Desktop | N/A | — | No haptics |

### Audio Implementations

| Platform | Engine | Capabilities |
|----------|--------|--------------|
| iOS | AVAudioEngine | Stereo, synthesized tones |
| watchOS | WKInterfaceDevice (system sounds) | Limited playback |
| visionOS | PHASE + AVAudioEngine | Full 3D spatial audio |
| Android | SoundPool | Stereo audio clips |
| Hub | rodio/cpal | Mono/stereo synthesis |
| Desktop | Tauri + Web Audio API | Stereo web audio |

---

## Canonical Patterns

### Audio Frequencies (Hz)

Standard tone frequencies based on musical intervals for pleasant sound:

```
┌────────────────────────────────────────────────────────────────┐
│  MUSICAL FREQUENCY REFERENCE                                   │
│                                                                │
│  Octave 3 (low, warm)          Octave 4 (mid, natural)        │
│  ─────────────────────         ─────────────────────          │
│  B3  = 247 Hz                  C4  = 262 Hz  ← Middle C       │
│                                D4  = 294 Hz                    │
│                                E4  = 330 Hz  ← Warm third     │
│                                F4  = 349 Hz  ← Error descent  │
│                                G4  = 392 Hz  ← Fifth          │
│                                A4  = 440 Hz  ← Concert pitch  │
│                                B4  = 494 Hz                    │
│                                                                │
│  Octave 5 (bright, clear)      Octave 6 (piercing, alert)     │
│  ─────────────────────         ─────────────────────          │
│  C5  = 523 Hz  ← Success base  C6  = 1047 Hz ← Emergency!     │
│  D5  = 587 Hz                                                  │
│  E5  = 659 Hz  ← Success mid                                   │
│  F5  = 698 Hz  ← Light on                                      │
│  G5  = 784 Hz  ← Success top                                   │
│  A5  = 880 Hz  ← Warning tone                                  │
│  B5  = 988 Hz                                                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Pattern Definitions

#### success

**Musical hint: C major arpeggio ascending = "We did it!"**

```yaml
audio:
  sequence:
    - { freq: 523, duration_ms: 100 }  # C5 - root
    - { freq: 659, duration_ms: 100 }  # E5 - major third
    - { freq: 784, duration_ms: 150 }  # G5 - perfect fifth
  envelope: soft
  total_duration_ms: 350

haptic:
  ios: UINotificationFeedbackGenerator.success
  watchos: WKHapticType.success
  android: VibrationEffect.createComposition()
            .addPrimitive(PRIMITIVE_CLICK)
            .addPrimitive(PRIMITIVE_CLICK)
```

#### error

**Musical hint: Descending interval = disappointment**

```yaml
audio:
  sequence:
    - { freq: 440, duration_ms: 150 }  # A4 - starts confident
    - { freq: 349, duration_ms: 200 }  # F4 - drops down (sad)
  envelope: harsh
  total_duration_ms: 350

haptic:
  ios: UINotificationFeedbackGenerator.error
  watchos: WKHapticType.failure
  android: VibrationEffect.EFFECT_DOUBLE_CLICK
```

#### warning

**Musical hint: Single sustained high note = attention**

```yaml
audio:
  sequence:
    - { freq: 880, duration_ms: 200 }  # A5 - attention-grabbing
  envelope: soft
  total_duration_ms: 200

haptic:
  ios: UINotificationFeedbackGenerator.warning
  watchos: WKHapticType.notification
  android: VibrationEffect.EFFECT_HEAVY_CLICK
```

#### emergency

**CRITICAL: This pattern MUST cut through everything. Life/property at stake.**

```yaml
audio:
  sequence:
    - { freq: 1047, duration_ms: 150 }  # C6 - piercing high
    - { rest: 50 }
    - { freq: 880, duration_ms: 150 }   # A5
    - { rest: 50 }
    - { freq: 1047, duration_ms: 150 }  # C6
    - { rest: 50 }
    - { freq: 880, duration_ms: 150 }   # A5
  envelope: harsh
  total_duration_ms: 750  # 150+50+150+50+150+50+150 = 750ms
  repeat: 5
  repeat_gap_ms: 300
  # Total with repeats: 5 * 750ms + 4 * 300ms = 4950ms minimum
  # Pattern continues until acknowledged!
  overrides_user_volume: true  # MUST play even if user has muted

haptic:
  ios:
    - UINotificationFeedbackGenerator.error (continuous until ack)
  watchos:
    - WKHapticType.failure × continuous
  android:
    pattern: [0, 200, 100, 200, 100, 200, 100, 200]
    amplitudes: [255, 0, 255, 0, 255, 0, 255]
    repeat: 0  # Repeat indefinitely

visual:  # For deaf users - CRITICAL
  screen_flash:
    color: "#FF0000"
    frequency_hz: 2
    duration: until_acknowledged
  persistent_banner:
    background: "#FF0000"
    text: "#FFFFFF"
    contrast_ratio: 21:1
  led_indicator:
    pattern: rapid_blink
    color: "#FF0000"
```

#### safety_alert

**h(x) < 0 detected — Safety constraint violation**

```yaml
audio:
  sequence:
    - { freq: 880, duration_ms: 200 }  # A5
    - { rest: 100 }
    - { freq: 880, duration_ms: 200 }  # A5 (repeat for attention)
  envelope: harsh
  total_duration_ms: 500
  repeat: 3
  # Total with repeats: 3 * 500ms = 1500ms

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .heavy) × 3 (150ms apart)
    - UINotificationFeedbackGenerator.error
  watchos: WKHapticType.notification + WKHapticType.failure × 3
  android: VibrationEffect.EFFECT_HEAVY_CLICK × 3
```

#### notification

```yaml
audio:
  sequence:
    - { freq: 784, duration_ms: 100 }  # G5
    - { freq: 1047, duration_ms: 150 } # C6
  envelope: soft
  total_duration_ms: 250

haptic:
  ios: UIImpactFeedbackGenerator(style: .light)
  watchos: WKHapticType.click
  android: VibrationEffect.EFFECT_TICK
```

#### selection

```yaml
audio:
  sequence:
    - { freq: 880, duration_ms: 50 }   # A5 (brief)
  envelope: sharp
  total_duration_ms: 50

haptic:
  ios: UISelectionFeedbackGenerator.selectionChanged
  watchos: WKHapticType.click
  android: VibrationEffect.EFFECT_TICK
```

#### thermostat_up

**Musical hint: Ascending warmth = temperature rising**

```yaml
audio:
  sequence:
    - { freq: 440, duration_ms: 100 }  # A4 (warm base)
    - { freq: 523, duration_ms: 100 }  # C5 (rising)
    - { freq: 659, duration_ms: 100 }  # E5 (warm peak)
  envelope: soft
  total_duration_ms: 300

haptic:
  ios: UIImpactFeedbackGenerator(style: .light, intensity: 0.6)
  watchos: WKHapticType.directionUp
  android: VibrationEffect.EFFECT_CLICK
```

#### thermostat_down

**Musical hint: Descending cool = temperature falling**

```yaml
audio:
  sequence:
    - { freq: 659, duration_ms: 100 }  # E5 (start high)
    - { freq: 523, duration_ms: 100 }  # C5 (falling)
    - { freq: 440, duration_ms: 100 }  # A4 (cool base)
  envelope: soft
  total_duration_ms: 300

haptic:
  ios: UIImpactFeedbackGenerator(style: .soft, intensity: 0.6)
  watchos: WKHapticType.directionDown
  android: VibrationEffect.EFFECT_TICK
```

#### light_on

```yaml
audio:
  sequence:
    - { freq: 698, duration_ms: 100 }  # F5 (rising feel)
  envelope: soft
  total_duration_ms: 100

haptic:
  ios: UIImpactFeedbackGenerator(style: .light, intensity: 0.7)
  watchos: WKHapticType.directionUp + WKHapticType.success
  android: VibrationEffect.EFFECT_CLICK
```

#### light_off

```yaml
audio:
  sequence:
    - { freq: 349, duration_ms: 100 }  # F4 (falling feel)
  envelope: soft
  total_duration_ms: 100

haptic:
  ios: UIImpactFeedbackGenerator(style: .soft, intensity: 0.5)
  watchos: WKHapticType.directionDown + WKHapticType.click
  android: VibrationEffect.EFFECT_TICK
```

#### shades_open

```yaml
audio:
  sequence:
    - { freq: 392, duration_ms: 100 }  # G4
    - { freq: 523, duration_ms: 100 }  # C5
  envelope: soft
  total_duration_ms: 200

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .light) × 2 (100ms apart)
  watchos: WKHapticType.directionUp × 2
  android: VibrationEffect pattern [0, 50, 50, 50]
```

#### shades_close

```yaml
audio:
  sequence:
    - { freq: 523, duration_ms: 100 }  # C5
    - { freq: 262, duration_ms: 100 }  # C4
  envelope: soft
  total_duration_ms: 200

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .soft) × 2 (100ms apart)
  watchos: WKHapticType.directionDown × 2
  android: VibrationEffect pattern [0, 50, 50, 50]
```

#### fireplace_on

```yaml
audio:
  sequence:
    - { freq: 330, duration_ms: 150 }  # E4 (warm)
    - { freq: 440, duration_ms: 150 }  # A4
    - { freq: 523, duration_ms: 200 }  # C5
  envelope: soft
  total_duration_ms: 500

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .light) × 3 (150ms apart)
    - UINotificationFeedbackGenerator.success
  watchos: WKHapticType.directionUp × 3 + WKHapticType.success
  android: VibrationEffect pattern [0, 75, 75, 75, 75, 100]
```

#### fireplace_off

```yaml
audio:
  sequence:
    - { freq: 523, duration_ms: 150 }  # C5
    - { freq: 440, duration_ms: 150 }  # A4
    - { freq: 262, duration_ms: 200 }  # C4 (cool down)
  envelope: soft
  total_duration_ms: 500

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .soft) × 3 (150ms apart)
    - UISelectionFeedbackGenerator.selectionChanged
  watchos: WKHapticType.directionDown × 3 + WKHapticType.click
  android: VibrationEffect pattern [0, 75, 75, 75, 75, 100]
```

#### lock_engaged

```yaml
audio:
  sequence:
    - { freq: 659, duration_ms: 50 }   # E5
    - { rest: 30 }
    - { freq: 880, duration_ms: 100 }  # A5 (firm)
  envelope: sharp
  total_duration_ms: 180

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .rigid)
    - delay 100ms
    - UIImpactFeedbackGenerator(style: .heavy)
  watchos: WKHapticType.click + WKHapticType.retry
  android: VibrationEffect.EFFECT_DOUBLE_CLICK
```

#### scene_activated

```yaml
audio:
  sequence:
    - { freq: 523, duration_ms: 100 }  # C5
    - { freq: 659, duration_ms: 100 }  # E5
    - { freq: 784, duration_ms: 150 }  # G5 (triumphant)
  envelope: soft
  total_duration_ms: 350

haptic:
  ios:
    - UIImpactFeedbackGenerator(style: .medium)
    - delay 100ms
    - UIImpactFeedbackGenerator(style: .light)
    - delay 100ms
    - UINotificationFeedbackGenerator.success
  watchos: WKHapticType.start + WKHapticType.click + WKHapticType.success
  android: VibrationEffect pattern [0, 50, 100, 50, 100, 75]
```

---

## visionOS Spatial Audio Guidelines

**visionOS brings audio into 3D space. Use it wisely.**

### Spatial Positioning Zones

```
                         TOP VIEW (User looking forward)

                                    ↑ Front
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    │   ┌───────────┼───────────────┐
                    │   │           │           │   │
           Left ←───┼───┤  INTIMATE │ PERSONAL  ├───┼───→ Right
                    │   │  (<0.5m)  │ (0.5-1.5m)│   │
                    │   │   ●User   │           │   │
                    │   └───────────┼───────────────┘
                    │               │               │
                    │       ┌───────┴───────┐       │
                    │       │    SOCIAL     │       │
                    │       │  (1.5-3.5m)   │       │
                    │       └───────────────┘       │
                    │                               │
                    │           PUBLIC              │
                    │          (>3.5m)              │
                    └───────────────────────────────┘
```

### Positioning by Semantic Category

| Category | Zone | Distance | Reasoning |
|----------|------|----------|-----------|
| `success` | Intimate | 0.3m center | Personal achievement, close |
| `error` | Personal | 1.0m center | Needs attention but not alarming |
| `emergency` | Intimate | 0.2m + surrounds | MUST be unavoidable |
| `notification` | Personal | 1.0m slightly right | Natural notification position |
| `light_on/off` | Social | 2.0m at light position | Matches physical location |
| `scene_activated` | Social | Surrounds user | Immersive scene change |

### Spatial Audio Implementation (visionOS)

```swift
import PHASE

/// Kagami Spatial Audio for visionOS
class KagamiSpatialAudio {
    private let engine: PHASEEngine
    private var sources: [String: PHASESource] = [:]

    init() throws {
        engine = PHASEEngine(updateMode: .automatic)
        engine.defaultReverbPreset = .smallRoom
        try engine.start()
    }

    /// Position audio at semantic location
    func play(pattern: String, at position: SpatialPosition) {
        let source = createSource(at: position)

        switch pattern {
        case "success":
            // Close and centered - personal achievement
            source.transform = simd_float4x4(
                translation: SIMD3<Float>(0, 0, -0.3)  // 30cm in front
            )

        case "emergency":
            // Surround the user - cannot be ignored
            playSurroundEmergency()
            return

        case "notification":
            // Slightly right, natural notification position
            source.transform = simd_float4x4(
                translation: SIMD3<Float>(0.5, 0.2, -1.0)  // Right, up, 1m front
            )

        case "light_on", "light_off":
            // Position at the actual light location if known
            if let lightPosition = getLightPosition() {
                source.transform = simd_float4x4(
                    translation: lightPosition
                )
            }

        default:
            // Default: 1m in front
            source.transform = simd_float4x4(
                translation: SIMD3<Float>(0, 0, -1.0)
            )
        }

        playPattern(pattern, through: source)
    }

    /// Emergency: Audio from all directions
    private func playSurroundEmergency() {
        let positions = [
            SIMD3<Float>(0, 0, -0.2),    // Front
            SIMD3<Float>(0, 0, 0.2),     // Back
            SIMD3<Float>(-0.2, 0, 0),    // Left
            SIMD3<Float>(0.2, 0, 0),     // Right
            SIMD3<Float>(0, 0.2, 0),     // Above
        ]

        for position in positions {
            let source = createSource(at: .custom(position))
            playPattern("emergency", through: source)
        }
    }
}
```

### Spatial Audio Best Practices

```
┌────────────────────────────────────────────────────────────────────┐
│  DO:                                                               │
│  ✓ Use intimate zone (< 0.5m) for personal feedback               │
│  ✓ Match physical locations (light sound from light direction)    │
│  ✓ Use surround for emergency (unavoidable)                       │
│  ✓ Consider head-locked audio for critical alerts                 │
│  ✓ Attenuate with distance for immersion                          │
│                                                                    │
│  DON'T:                                                            │
│  ✗ Place all audio at same position (loses spatial benefit)       │
│  ✗ Use public zone (>3.5m) for important feedback (too far)       │
│  ✗ Ignore physical context (lights, doors, windows)               │
│  ✗ Make emergency audio positional only (surround it!)            │
└────────────────────────────────────────────────────────────────────┘
```

---

## Persona-Specific Adaptations

### Tim (Baseline Persona)

```yaml
name: Tim Jacoby
role: Primary user, household owner
adaptations:
  volume_multiplier: 1.0          # Standard volume
  duration_multiplier: 1.0        # Standard timing
  haptic_intensity_multiplier: 1.0
  prefer_audio: true              # Appreciates audio feedback
  spatial_audio: true             # Full visionOS spatial
  fibonacci_timing: true          # Natural timing enabled
notes: |
  Tim is a tech-forward user who appreciates craft and detail.
  He can handle fast feedback (193 WPM speech pace).
  Prefers "feeling" quality over "seeing" explanations.
  Audio feedback should be satisfying but not excessive.
```

### Ingrid (Solo Senior, 78yo)

```yaml
adaptations:
  volume_multiplier: 1.25         # Hearing may be reduced
  duration_multiplier: 1.5        # Slower perception
  haptic_intensity_multiplier: 1.25  # May need stronger feedback
  prefer_audio: true              # Audio over haptic
notes: |
  Extended durations give more time to perceive.
  Higher volume compensates for age-related hearing changes.
  Clear, distinct patterns over subtle ones.
```

### Michael (Blind User, 42yo)

```yaml
adaptations:
  volume_multiplier: 1.0          # Excellent hearing
  spatial_audio: true             # 3D positioning CRITICAL
  spoken_feedback: true           # Voice descriptions enabled
  haptic_intensity_multiplier: 1.0
  prefer_audio: true              # Primary feedback channel
notes: |
  Spatial audio positioning conveys UI location.
  Distinct patterns for each semantic category.
  Audio is primary - not a fallback.
```

### Maria (Motor Limited, 35yo)

```yaml
adaptations:
  volume_multiplier: 1.0
  duration_multiplier: 1.25       # Extra time to perceive
  haptic_intensity_multiplier: 1.5  # Stronger haptic
  prefer_audio: false             # Haptic may be more useful
notes: |
  Strong haptic feedback compensates for motor challenges.
  Extended durations for confirmation.
```

### Patel Family (Multigenerational)

```yaml
adaptations:
  # Per-member profiles loaded dynamically
  grandparents:
    volume_multiplier: 1.25
    duration_multiplier: 1.5
  parents:
    volume_multiplier: 1.0
    duration_multiplier: 1.0
  children:
    volume_multiplier: 1.0
    duration_multiplier: 1.0
    safety_sounds_enhanced: true  # More prominent safety alerts
notes: |
  Different family members have different needs.
  System identifies user and applies appropriate profile.
  Children get enhanced safety sounds.
```

### Tokyo Roommates

```yaml
adaptations:
  volume_multiplier: 0.75         # Privacy/quiet living
  privacy_mode: true              # Haptic-only option
  prefer_audio: false             # Prefer haptic to respect others
notes: |
  Quiet environment requires reduced audio.
  Haptic feedback respects shared space.
  Late-night mode further reduces.
```

### Jordan & Sam (LGBTQ+ Parents)

```yaml
adaptations:
  volume_multiplier: 1.0
  child_safety_enhanced: true     # Prominent alerts for child-related safety
  custom_roles: true              # Role-specific sounds for each parent
notes: |
  Child safety alerts are prominently enhanced.
  Custom role assignments enable personalized feedback.
```

### David (Deaf User, 38yo)

```yaml
adaptations:
  volume_multiplier: 0             # No audio
  prefer_audio: false              # Haptic and visual PRIMARY
  haptic_intensity_multiplier: 1.75
  haptic_duration_multiplier: 1.5
  visual_alerts_primary: true
  safety_haptic_enhanced: true
  emergency_visual_mode: full_screen_flash

haptic_pattern_complexity:
  success: double_tap_pause_tap    # •• _ •
  error: long_short_long           # — • —
  warning: triple_pulse            # • • •
  emergency: continuous_escalating # Increasing intensity
  safety_alert: staccato_burst_x5  # ••••• (rapid)

notes: |
  Haptic and visual are PRIMARY channels — audio is OFF.
  Emergency patterns use full-screen flash + enhanced haptic.
  All feedback must be perceivable without audio.
  Haptic patterns use Morse-like complexity for semantic distinction.
```

### Sarah (Low Vision, 52yo)

```yaml
adaptations:
  volume_multiplier: 1.15          # Audio is primary
  prefer_audio: true
  haptic_intensity_multiplier: 1.25
  high_contrast_visual: true       # 21:1 minimum contrast
  large_visual_alerts: true        # Oversized visual elements
notes: |
  Audio is primary navigation channel.
  Visual alerts must be high contrast (21:1 minimum) and large.
  Haptic reinforces audio for confirmation.
```

---

## Accessibility Requirements

### WCAG Audio Requirements

1. **Volume Control** — User MUST be able to adjust all audio feedback
2. **Mute Option** — MUST provide global mute
3. **Visual Alternative** — MUST show visual feedback alongside audio
4. **No Auto-Play > 3 seconds** — Sounds must be brief
5. **Captions/Transcripts** — Spoken feedback must have text equivalent

### Haptic Accessibility

1. **Intensity Control** — User MUST be able to adjust intensity
2. **Disable Option** — MUST respect system haptic settings
3. **Alternative Feedback** — When haptics disabled, use audio

### Audio-Only Navigation Mode

For blind users (Michael persona):
- All UI elements must have audio feedback
- Spatial audio for element positions (visionOS)
- Spoken labels for unlabeled elements
- Navigation sounds for direction

### Haptic-Only Navigation Mode

For deaf users:
- All feedback via haptic patterns
- Morse encoding available for text
- Distinct patterns for each semantic category
- Pattern preview in settings

---

## Testing Standards

### Unit Tests Required

Each platform MUST have tests for:
1. All semantic patterns play correctly
2. Volume/intensity controls work
3. Mute respects preferences
4. Accessibility settings honored
5. Pattern timing is accurate (±10ms)

### Integration Tests Required

1. Cross-platform pattern recognition (record audio, verify frequencies)
2. Haptic pattern verification (where testable)
3. Accessibility mode transitions
4. Persona adaptation loading

### E2E Tests Required

1. User perceives feedback for all actions
2. Accessibility modes work end-to-end
3. Persona adaptations apply correctly
4. Volume/intensity persist across sessions

### Test File Locations

| Platform | Test File |
|----------|-----------|
| iOS | `Tests/KagamiIOSTests/AudioDesignTests.swift` |
| watchOS | `Tests/KagamiWatchTests/HapticNavigationTests.swift` |
| visionOS | `Tests/KagamiVisionTests/SpatialAudioTests.swift` |
| Android | `.maestro/audio_feedback_test.yaml` |
| Hub | `tests/feedback_test.rs` |
| Desktop | `tests/e2e/audio-feedback.spec.ts` |

---

## Implementation Checklist

### Per Platform

- [ ] Implement all semantic patterns from this spec
- [ ] Map patterns to platform-native APIs
- [ ] Implement volume/intensity controls
- [ ] Implement mute functionality
- [ ] Respect system accessibility settings
- [ ] Implement persona adaptations
- [ ] Add unit tests for all patterns
- [ ] Add E2E tests for feedback

### Cross-Platform

- [ ] Verify pattern recognition (same meaning = same experience)
- [ ] Test persona adaptations across platforms
- [ ] Validate accessibility compliance
- [ ] Run Byzantine audit on implementation

---

```
    ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫
   ╔═══════════════════════════════════════════════════╗
   ║  Mirror: Every sound and touch carries meaning.   ║
   ║  h(x) >= 0. For EVERYONE.                         ║
   ╚═══════════════════════════════════════════════════╝
    ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫ ♪ ♫
```
