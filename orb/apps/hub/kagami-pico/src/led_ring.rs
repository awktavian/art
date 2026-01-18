//! 鏡 Kagami Pico LED Ring — WS2812 via PIO
//!
//! Real-time LED ring control using the RP2040's Programmable I/O.
//! This provides deterministic, microsecond-precise timing that
//! Linux cannot achieve.
//!
//! Features:
//! - 60fps animation loop
//! - 7 LEDs (one per colony)
//! - Prismorphism-inspired patterns
//! - No jitter, no frame drops
//!
//! Colony colors follow the Fano plane basis:
//! - e₁ Spark: Red (#FF4136)
//! - e₂ Forge: Orange (#FF851B)
//! - e₃ Flow: Yellow (#FFDC00)
//! - e₄ Nexus: Green (#2ECC40)
//! - e₅ Beacon: Cyan (#00D4FF)
//! - e₆ Grove: Blue (#0074D9)
//! - e₇ Crystal: Violet (#B10DC9)
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use embassy_rp::pio::{Common, Instance, PioPin, StateMachine};
use embassy_time::Instant;
use fixed::types::U24F8;
use smart_leds::RGB8;

/// Apply brightness to a color (standalone function to avoid borrow conflicts)
#[inline]
fn apply_brightness_to(color: RGB8, brightness: u8) -> RGB8 {
    let scale = brightness as u16;
    RGB8::new(
        ((color.r as u16 * scale) / 255) as u8,
        ((color.g as u16 * scale) / 255) as u8,
        ((color.b as u16 * scale) / 255) as u8,
    )
}

// ============================================================================
// Colony Colors (Spectral Order)
// ============================================================================

/// Colony colors in spectral order (red to violet)
pub const COLONY_COLORS: [RGB8; 7] = [
    RGB8::new(0xFF, 0x41, 0x36), // e₁ Spark: Red (620nm)
    RGB8::new(0xFF, 0x85, 0x1B), // e₂ Forge: Orange (590nm)
    RGB8::new(0xFF, 0xDC, 0x00), // e₃ Flow: Yellow (570nm)
    RGB8::new(0x2E, 0xCC, 0x40), // e₄ Nexus: Green (510nm)
    RGB8::new(0x00, 0xD4, 0xFF), // e₅ Beacon: Cyan (475nm)
    RGB8::new(0x00, 0x74, 0xD9), // e₆ Grove: Blue (445nm)
    RGB8::new(0xB1, 0x0D, 0xC9), // e₇ Crystal: Violet (400nm)
];

/// Safety colors
pub const SAFE_COLOR: RGB8 = RGB8::new(0x00, 0xFF, 0x88);    // Green
pub const CAUTION_COLOR: RGB8 = RGB8::new(0xFF, 0xD7, 0x00); // Yellow
pub const VIOLATION_COLOR: RGB8 = RGB8::new(0xFF, 0x44, 0x44); // Red

// ============================================================================
// Animation Patterns
// ============================================================================

/// Animation patterns
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum AnimationPattern {
    Idle = 0,
    Breathing = 1,
    Spin = 2,
    Pulse = 3,
    Cascade = 4,
    Flash = 5,
    ErrorFlash = 6,
    Rainbow = 7,
    Spectral = 8,
    FanoPulse = 9,
    SpectralSweep = 10,
    ChromaticSuccess = 11,
    ChromaticError = 12,
    SafetySafe = 13,
    SafetyCaution = 14,
    SafetyViolation = 15,
}

impl AnimationPattern {
    pub fn from_u8(n: u8) -> Self {
        match n {
            0 => Self::Idle,
            1 => Self::Breathing,
            2 => Self::Spin,
            3 => Self::Pulse,
            4 => Self::Cascade,
            5 => Self::Flash,
            6 => Self::ErrorFlash,
            7 => Self::Rainbow,
            8 => Self::Spectral,
            9 => Self::FanoPulse,
            10 => Self::SpectralSweep,
            11 => Self::ChromaticSuccess,
            12 => Self::ChromaticError,
            13 => Self::SafetySafe,
            14 => Self::SafetyCaution,
            15 => Self::SafetyViolation,
            _ => Self::Idle,
        }
    }
}

// ============================================================================
// LED Ring Controller
// ============================================================================

/// LED ring controller using PIO
pub struct LedRing<'d, PIO: Instance, const SM: usize> {
    /// State machine (not used directly after init, but kept for ownership)
    _sm: StateMachine<'d, PIO, SM>,

    /// Current animation pattern
    pattern: AnimationPattern,

    /// Global brightness (0-255)
    brightness: u8,

    /// Animation start time
    start_time: Instant,

    /// Frame counter
    frame_count: u32,

    /// Override color (if set, all LEDs show this color)
    override_color: Option<RGB8>,

    /// LED buffer
    leds: [RGB8; 7],
}

impl<'d, PIO: Instance, const SM: usize> LedRing<'d, PIO, SM> {
    /// Create a new LED ring controller
    ///
    /// Note: In production, this would initialize the PIO state machine
    /// with the WS2812 program. For now, we stub this out.
    pub fn new<P: PioPin>(
        _common: Common<'d, PIO>,
        sm: StateMachine<'d, PIO, SM>,
        _pin: P,
    ) -> Self {
        // In production:
        // 1. Load WS2812 PIO program
        // 2. Configure state machine for 800kHz timing
        // 3. Set up DMA for LED data transfer

        Self {
            _sm: sm,
            pattern: AnimationPattern::Breathing,
            brightness: 128,
            start_time: Instant::now(),
            frame_count: 0,
            override_color: None,
            leds: [RGB8::default(); 7],
        }
    }

    /// Set the animation pattern
    pub fn set_pattern(&mut self, pattern: AnimationPattern) {
        if self.pattern != pattern {
            self.pattern = pattern;
            self.start_time = Instant::now();
            self.frame_count = 0;
        }
    }

    /// Get current pattern
    pub fn current_pattern(&self) -> AnimationPattern {
        self.pattern
    }

    /// Set global brightness
    pub fn set_brightness(&mut self, level: u8) {
        self.brightness = level;
    }

    /// Get current brightness
    pub fn brightness(&self) -> u8 {
        self.brightness
    }

    /// Get frame count
    pub fn frame_count(&self) -> u32 {
        self.frame_count
    }

    /// Set override color
    pub fn set_override_color(&mut self, color: Option<(u8, u8, u8)>) {
        self.override_color = color.map(|(r, g, b)| RGB8::new(r, g, b));
    }

    /// Render next frame
    pub fn render_frame(&mut self) {
        let elapsed_ms = self.start_time.elapsed().as_millis() as u32;

        // Calculate frame colors
        if let Some(color) = self.override_color {
            // Override: all LEDs same color
            for led in &mut self.leds {
                *led = apply_brightness_to(color, self.brightness);
            }
        } else {
            // Pattern-based animation
            self.calculate_pattern(elapsed_ms);
        }

        // Write to hardware (stubbed for now)
        self.write_leds();

        self.frame_count = self.frame_count.wrapping_add(1);
    }

    /// Calculate pattern colors
    fn calculate_pattern(&mut self, elapsed_ms: u32) {
        match self.pattern {
            AnimationPattern::Idle => self.pattern_idle(),
            AnimationPattern::Breathing => self.pattern_breathing(elapsed_ms),
            AnimationPattern::Spin => self.pattern_spin(elapsed_ms),
            AnimationPattern::Pulse => self.pattern_pulse(elapsed_ms),
            AnimationPattern::Cascade => self.pattern_cascade(elapsed_ms),
            AnimationPattern::Flash => self.pattern_flash(elapsed_ms),
            AnimationPattern::ErrorFlash => self.pattern_error_flash(elapsed_ms),
            AnimationPattern::Rainbow => self.pattern_rainbow(elapsed_ms),
            AnimationPattern::Spectral => self.pattern_spectral(elapsed_ms),
            AnimationPattern::FanoPulse => self.pattern_fano_pulse(elapsed_ms),
            AnimationPattern::SpectralSweep => self.pattern_spectral_sweep(elapsed_ms),
            AnimationPattern::ChromaticSuccess => self.pattern_chromatic(elapsed_ms, true),
            AnimationPattern::ChromaticError => self.pattern_chromatic(elapsed_ms, false),
            AnimationPattern::SafetySafe => self.pattern_safety(SAFE_COLOR),
            AnimationPattern::SafetyCaution => self.pattern_safety(CAUTION_COLOR),
            AnimationPattern::SafetyViolation => self.pattern_safety(VIOLATION_COLOR),
        }
    }

    // ========================================================================
    // Pattern Implementations
    // ========================================================================

    fn pattern_idle(&mut self) {
        for (i, led) in self.leds.iter_mut().enumerate() {
            *led = apply_brightness_to(COLONY_COLORS[i], self.brightness);
        }
    }

    fn pattern_breathing(&mut self, elapsed_ms: u32) {
        // 4-second breathing cycle
        let phase = (elapsed_ms % 4000) as f32 / 4000.0;
        let breath = 0.4 + 0.6 * sin_approx(phase * core::f32::consts::TAU);

        for (i, led) in self.leds.iter_mut().enumerate() {
            let c = COLONY_COLORS[i];
            *led = RGB8::new(
                scale_u8(c.r, breath),
                scale_u8(c.g, breath),
                scale_u8(c.b, breath),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_spin(&mut self, elapsed_ms: u32) {
        let position = ((elapsed_ms % 800) as f32 / 800.0) * 7.0;

        for (i, led) in self.leds.iter_mut().enumerate() {
            let dist = ((i as f32 - position).abs()).min((i as f32 + 7.0 - position).abs());
            let factor = if dist < 1.0 { 1.0 - dist * 0.3 }
                        else if dist < 2.0 { 0.7 - (dist - 1.0) * 0.5 }
                        else { 0.1 };

            let c = COLONY_COLORS[4]; // Beacon cyan for processing
            *led = RGB8::new(
                scale_u8(c.r, factor),
                scale_u8(c.g, factor),
                scale_u8(c.b, factor),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_pulse(&mut self, elapsed_ms: u32) {
        let phase = (elapsed_ms % 500) as f32 / 500.0;
        let pulse = 0.3 + 0.7 * sin_approx(phase * core::f32::consts::TAU).abs();

        let c = COLONY_COLORS[2]; // Flow yellow for listening
        let pulsed = RGB8::new(
            scale_u8(c.r, pulse),
            scale_u8(c.g, pulse),
            scale_u8(c.b, pulse),
        );

        for led in &mut self.leds {
            *led = apply_brightness_to(pulsed, self.brightness);
        }
    }

    fn pattern_cascade(&mut self, elapsed_ms: u32) {
        let wave_pos = ((elapsed_ms % 600) as f32 / 600.0) * 4.0;
        let center = 3;

        for (i, led) in self.leds.iter_mut().enumerate() {
            let dist = (i as i32 - center).abs() as f32;
            let intensity = if (wave_pos - dist).abs() < 1.0 {
                1.0 - (wave_pos - dist).abs()
            } else { 0.15 };

            let c = COLONY_COLORS[i];
            *led = RGB8::new(
                scale_u8(c.r, intensity),
                scale_u8(c.g, intensity),
                scale_u8(c.b, intensity),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_flash(&mut self, elapsed_ms: u32) {
        let on = (elapsed_ms / 100) % 4 < 2 && elapsed_ms < 600;
        let c = if on { SAFE_COLOR } else { RGB8::default() };

        for led in &mut self.leds {
            *led = apply_brightness_to(c, self.brightness);
        }
    }

    fn pattern_error_flash(&mut self, elapsed_ms: u32) {
        let cycle = elapsed_ms / 200;
        let on = cycle % 2 == 0 && cycle < 6;
        let c = if on { VIOLATION_COLOR } else {
            RGB8::new(VIOLATION_COLOR.r / 10, VIOLATION_COLOR.g / 10, VIOLATION_COLOR.b / 10)
        };

        for led in &mut self.leds {
            *led = apply_brightness_to(c, self.brightness);
        }
    }

    fn pattern_rainbow(&mut self, elapsed_ms: u32) {
        let base_hue = (elapsed_ms % 1500) as f32 / 1500.0;

        for (i, led) in self.leds.iter_mut().enumerate() {
            let hue = (base_hue + (i as f32 / 7.0)) % 1.0;
            *led = apply_brightness_to(hsv_to_rgb(hue, 1.0, 1.0), self.brightness);
        }
    }

    fn pattern_spectral(&mut self, elapsed_ms: u32) {
        let progress = (elapsed_ms % 8000) as f32 / 8000.0;

        for (i, led) in self.leds.iter_mut().enumerate() {
            let phase = (progress + (i as f32 / 7.0)) % 1.0;
            let idx = (phase * 7.0) as usize;
            let frac = (phase * 7.0) - idx as f32;

            let c1 = COLONY_COLORS[idx % 7];
            let c2 = COLONY_COLORS[(idx + 1) % 7];

            *led = RGB8::new(
                lerp_u8(c1.r, c2.r, frac),
                lerp_u8(c1.g, c2.g, frac),
                lerp_u8(c1.b, c2.b, frac),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_fano_pulse(&mut self, elapsed_ms: u32) {
        let base_phase = (elapsed_ms % 6000) as f32 / 6000.0 * core::f32::consts::TAU;

        for (i, led) in self.leds.iter_mut().enumerate() {
            let offset = (i as f32 / 7.0) * core::f32::consts::TAU;
            let intensity = 0.3 + 0.7 * ((sin_approx(base_phase + offset) + 1.0) * 0.5);

            let c = COLONY_COLORS[i];
            *led = RGB8::new(
                scale_u8(c.r, intensity),
                scale_u8(c.g, intensity),
                scale_u8(c.b, intensity),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_spectral_sweep(&mut self, elapsed_ms: u32) {
        let progress = (elapsed_ms % 2000) as f32 / 1000.0; // 0 to 2 (forward then back)
        let sweep = if progress <= 1.0 { progress } else { 2.0 - progress };

        for (i, led) in self.leds.iter_mut().enumerate() {
            let delay_ms = i as u32 * 8; // 8ms spectral delay
            let delayed = elapsed_ms.saturating_sub(delay_ms);
            let led_progress = (delayed % 2000) as f32 / 1000.0;
            let led_sweep = if led_progress <= 1.0 { led_progress } else { 2.0 - led_progress };

            let idx = (led_sweep * 6.0) as usize;
            let frac = (led_sweep * 6.0) - idx as f32;

            let c1 = COLONY_COLORS[idx.min(6)];
            let c2 = COLONY_COLORS[(idx + 1).min(6)];

            *led = RGB8::new(
                lerp_u8(c1.r, c2.r, frac),
                lerp_u8(c1.g, c2.g, frac),
                lerp_u8(c1.b, c2.b, frac),
            );
            *led = apply_brightness_to(*led, self.brightness);
        }
    }

    fn pattern_chromatic(&mut self, elapsed_ms: u32, success: bool) {
        let progress = (elapsed_ms % 610) as f32 / 610.0;
        let wave_radius = progress * 4.0;
        let center = 3;

        let colors = if success {
            [COLONY_COLORS[0], COLONY_COLORS[1], COLONY_COLORS[2]] // Warm
        } else {
            [COLONY_COLORS[6], COLONY_COLORS[5], COLONY_COLORS[4]] // Cool
        };

        let brightness = self.brightness as u16;
        for (i, led) in self.leds.iter_mut().enumerate() {
            let dist = (i as i32 - center).abs() as f32;
            let intensity = if dist <= wave_radius {
                let rel = 1.0 - (wave_radius - dist) / wave_radius.max(0.1);
                if success { smooth_step(1.0 - rel * 0.5) }
                else { (1.0 - rel) * (1.0 - rel) }
            } else { 0.1 };

            let hue_idx = ((progress * 2.0).min(2.0) as usize).min(2);
            let c = colors[hue_idx];

            let raw = RGB8::new(
                scale_u8(c.r, intensity),
                scale_u8(c.g, intensity),
                scale_u8(c.b, intensity),
            );
            // Inline apply_brightness to avoid borrow conflict
            *led = RGB8::new(
                ((raw.r as u16 * brightness) / 255) as u8,
                ((raw.g as u16 * brightness) / 255) as u8,
                ((raw.b as u16 * brightness) / 255) as u8,
            );
        }
    }

    fn pattern_safety(&mut self, color: RGB8) {
        let brightness = self.brightness as u16;
        for led in &mut self.leds {
            // Inline apply_brightness to avoid borrow conflict
            *led = RGB8::new(
                ((color.r as u16 * brightness) / 255) as u8,
                ((color.g as u16 * brightness) / 255) as u8,
                ((color.b as u16 * brightness) / 255) as u8,
            );
        }
    }

    // ========================================================================
    // Helper Methods
    // ========================================================================

    fn apply_brightness(&self, color: RGB8) -> RGB8 {
        let scale = self.brightness as u16;
        RGB8::new(
            ((color.r as u16 * scale) / 255) as u8,
            ((color.g as u16 * scale) / 255) as u8,
            ((color.b as u16 * scale) / 255) as u8,
        )
    }

    fn write_leds(&self) {
        // In production, this would use PIO/DMA to write to WS2812
        // For now, this is a stub
    }
}

// ============================================================================
// Math Helpers (no_std compatible)
// ============================================================================

/// Approximate sine using Taylor series (no_std compatible)
fn sin_approx(x: f32) -> f32 {
    // Normalize to [-π, π]
    let mut x = x % (2.0 * core::f32::consts::PI);
    if x > core::f32::consts::PI {
        x -= 2.0 * core::f32::consts::PI;
    }
    if x < -core::f32::consts::PI {
        x += 2.0 * core::f32::consts::PI;
    }

    // Taylor series approximation
    let x2 = x * x;
    let x3 = x2 * x;
    let x5 = x3 * x2;
    let x7 = x5 * x2;

    x - x3 / 6.0 + x5 / 120.0 - x7 / 5040.0
}

/// Scale a u8 by a float factor
fn scale_u8(v: u8, scale: f32) -> u8 {
    ((v as f32 * scale) as u16).min(255) as u8
}

/// Linear interpolation for u8
fn lerp_u8(a: u8, b: u8, t: f32) -> u8 {
    let t = t.max(0.0).min(1.0);
    ((a as f32 * (1.0 - t) + b as f32 * t) as u16).min(255) as u8
}

/// Smooth step function
fn smooth_step(x: f32) -> f32 {
    let x = x.max(0.0).min(1.0);
    x * x * (3.0 - 2.0 * x)
}

/// HSV to RGB conversion
fn hsv_to_rgb(h: f32, s: f32, v: f32) -> RGB8 {
    let h = h * 6.0;
    let i = h as u32;
    let f = h - i as f32;
    let p = v * (1.0 - s);
    let q = v * (1.0 - s * f);
    let t = v * (1.0 - s * (1.0 - f));

    let (r, g, b) = match i % 6 {
        0 => (v, t, p),
        1 => (q, v, p),
        2 => (p, v, t),
        3 => (p, q, v),
        4 => (t, p, v),
        _ => (v, p, q),
    };

    RGB8::new(
        (r * 255.0) as u8,
        (g * 255.0) as u8,
        (b * 255.0) as u8,
    )
}

/*
 * 鏡
 * Seven lights. Microsecond precision.
 * The LED ring breathes with the home.
 *
 * h(x) ≥ 0. Always.
 */
