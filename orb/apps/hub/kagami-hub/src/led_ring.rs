//! LED Ring Controller — HAL 9000 Inspired
//!
//! 7 LEDs representing the seven colonies (Fano plane basis e₁-e₇).
//! Colors shift based on active colony, voice pipeline state, and safety status.
//!
//! Hardware: SK6812 RGBW LEDs
//! - 4 bytes per LED: Green, Red, Blue, White
//! - White channel used when R=G=B for efficiency and better color rendering
//! - Gamma correction (2.2) applied for perceptually linear brightness
//!
//! Prismorphism Integration (see PRISMORPHISM.md):
//! - FanoLine: Cycles through 3 colors of a Fano multiplication line
//! - SpectralSweep: Physics-accurate ROYGBIV wavelength order
//! - ChromaticPulse: Success/error feedback using colony colors
//! - DiscoveryGlow: Gradual brightness increase on sustained presence
//!
//! The 7 Fano Lines (octonion multiplication):
//! - (1,2,3): Spark-Forge-Flow (warm spectrum)
//! - (1,4,5): Spark-Nexus-Beacon (red-green-cyan diagonal)
//! - (1,7,6): Spark-Crystal-Grove (red-violet-blue harmonic)
//! - (2,4,6): Forge-Nexus-Grove (orange-green-blue triadic)
//! - (2,5,7): Forge-Beacon-Crystal (warm-to-cool transition)
//! - (3,4,7): Flow-Nexus-Crystal (yellow-green-violet path)
//! - (3,6,5): Flow-Grove-Beacon (yellow-blue-cyan arc)
//!
//! Voice Pipeline State Mapping:
//! - Idle: Breathing animation (all colonies)
//! - Listening: Pulsing cyan (Flow e₃)
//! - Processing: Spinning animation
//! - Executing: Cascade from center
//! - Speaking: Highlight Crystal (e₇)
//! - Error: Red flash
//!
//! Colony: All seven, unified through e₀

use anyhow::Result;
use std::sync::Mutex;
use std::time::Instant;
use tracing::{debug, info};

use crate::config::LEDRingConfig;

// Thread-safe lazy initialization for the singleton
use std::sync::OnceLock;
static LED_RING: OnceLock<Mutex<Option<LEDRing>>> = OnceLock::new();

fn get_led_ring() -> &'static Mutex<Option<LEDRing>> {
    LED_RING.get_or_init(|| Mutex::new(None))
}

// Import from generated design tokens
use crate::design_tokens_generated::colony;

// ============================================================================
// SK6812 RGBW Support
// ============================================================================

/// RGBW color for SK6812 LEDs (4 bytes per LED)
/// SK6812 uses GRBW byte order in hardware
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct RGBW {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub w: u8,
}

impl RGBW {
    /// Create a new RGBW color
    pub const fn new(r: u8, g: u8, b: u8, w: u8) -> Self {
        Self { r, g, b, w }
    }

    /// Convert RGB tuple to RGBW with automatic white channel extraction
    /// When R, G, B are similar, extract common component to white channel
    /// for better efficiency and color rendering on SK6812
    pub fn from_rgb(r: u8, g: u8, b: u8) -> Self {
        // Find the minimum component - this is the "white" portion
        let white = r.min(g).min(b);

        // Subtract white from RGB channels
        // This makes pure white (255,255,255) -> (0,0,0,255)
        // and colors like (255,128,128) -> (127,0,0,128)
        Self {
            r: r.saturating_sub(white),
            g: g.saturating_sub(white),
            b: b.saturating_sub(white),
            w: white,
        }
    }

    /// Convert RGB tuple to RGBW (convenience method)
    pub fn from_tuple(rgb: (u8, u8, u8)) -> Self {
        Self::from_rgb(rgb.0, rgb.1, rgb.2)
    }

    /// Get raw bytes in SK6812 GRBW order for SPI transmission
    pub fn to_grbw_bytes(&self) -> [u8; 4] {
        [self.g, self.r, self.b, self.w]
    }

    /// Get as RGB tuple (for backwards compatibility)
    pub fn to_rgb_tuple(&self) -> (u8, u8, u8) {
        // Recombine white back into RGB
        (
            self.r.saturating_add(self.w),
            self.g.saturating_add(self.w),
            self.b.saturating_add(self.w),
        )
    }
}

// ============================================================================
// Gamma Correction — Perceptually Linear Brightness
// ============================================================================

/// Standard gamma value for LED correction (sRGB standard)
const GAMMA: f32 = 2.2;

/// Apply gamma correction to a single color component
/// Converts linear brightness to perceptually linear brightness
///
/// LEDs respond linearly to PWM duty cycle, but human vision is non-linear.
/// Without gamma correction, 50% brightness looks much brighter than expected.
/// Gamma 2.2 matches sRGB standard and provides natural-looking dimming.
#[inline]
fn gamma_correct(value: u8) -> u8 {
    let normalized = value as f32 / 255.0;
    let corrected = normalized.powf(GAMMA);
    (corrected * 255.0) as u8
}

/// Apply gamma correction to RGB tuple
#[inline]
#[allow(dead_code)] // Available for direct RGB gamma correction if needed
fn gamma_correct_rgb(r: u8, g: u8, b: u8) -> (u8, u8, u8) {
    (gamma_correct(r), gamma_correct(g), gamma_correct(b))
}

/// Apply gamma correction to RGBW color
#[inline]
fn gamma_correct_rgbw(rgbw: RGBW) -> RGBW {
    RGBW {
        r: gamma_correct(rgbw.r),
        g: gamma_correct(rgbw.g),
        b: gamma_correct(rgbw.b),
        w: gamma_correct(rgbw.w),
    }
}

// ============================================================================
// Constants — Colony Colors from Design Tokens
// ============================================================================

/// Colony colors (RGB) - the seven aspects of Kagami (from design tokens)
pub const COLONY_COLORS: [(u8, u8, u8); 7] = [
    colony::SPARK_RGB,   // e₁: Energy, initiative
    colony::FORGE_RGB,   // e₂: Creation, craft
    colony::FLOW_RGB,    // e₃: Adaptation, sensing
    colony::NEXUS_RGB,   // e₄: Connection, coordination
    colony::BEACON_RGB,  // e₅: Guidance, signaling
    colony::GROVE_RGB,   // e₆: Growth, nurturing
    colony::CRYSTAL_RGB, // e₇: Clarity, verification
];

// ============================================================================
// Prismorphism Colors — Spectral Wavelength Mapping (from PRISMORPHISM.md)
// ============================================================================

/// Prismorphism spectral colors mapped to wavelengths (physics-accurate order)
/// These follow the actual light spectrum: Red (620nm) -> Violet (400nm)
///
/// NOTE: These are DIFFERENT from COLONY_COLORS! Colony colors are semantic
/// (Spark=initiative, etc.), while spectral colors follow physics wavelength order.
/// For animations that need the actual colony colors, use COLONY_COLORS.
/// For physics-accurate spectral effects (prism, rainbow), use these.
pub mod prism {
    /// Spark e₁ - 620nm Red (spectral red, not colony Spark orange)
    pub const SPARK: (u8, u8, u8) = (0xFF, 0x41, 0x36);
    /// Forge e₂ - 590nm Orange (spectral orange, close to colony Forge gold)
    pub const FORGE: (u8, u8, u8) = (0xFF, 0x85, 0x1B);
    /// Flow e₃ - 570nm Yellow (spectral yellow, NOT colony Flow cyan)
    pub const FLOW: (u8, u8, u8) = (0xFF, 0xDC, 0x00);
    /// Nexus e₄ - 510nm Green (spectral green, NOT colony Nexus purple)
    pub const NEXUS: (u8, u8, u8) = (0x2E, 0xCC, 0x40);
    /// Beacon e₅ - 475nm Cyan (spectral cyan, NOT colony Beacon amber)
    pub const BEACON: (u8, u8, u8) = (0x00, 0xD4, 0xFF);
    /// Grove e₆ - 445nm Blue (spectral blue, NOT colony Grove green)
    pub const GROVE: (u8, u8, u8) = (0x00, 0x74, 0xD9);
    /// Crystal e₇ - 400nm Violet (spectral violet, NOT colony Crystal cyan)
    pub const CRYSTAL: (u8, u8, u8) = (0xB1, 0x0D, 0xC9);
}

/// Spectral colors in physics wavelength order (red to violet)
/// Used for SpectralSweep animation - light separating through a prism
/// NOTE: These follow physics (ROYGBIV), NOT colony semantic order!
pub const SPECTRAL_ORDER: [(u8, u8, u8); 7] = [
    prism::SPARK,   // Red (620nm) - bends least
    prism::FORGE,   // Orange (590nm)
    prism::FLOW,    // Yellow (570nm)
    prism::NEXUS,   // Green (510nm)
    prism::BEACON,  // Cyan (475nm)
    prism::GROVE,   // Blue (445nm)
    prism::CRYSTAL, // Violet (400nm) - bends most
];

/// The 7 Fano lines - each encodes an octonion multiplication relationship
/// Format: [colony_a, colony_b, colony_c] where e_a * e_b = e_c (cyclically)
pub const FANO_LINES: [[usize; 3]; 7] = [
    [SPARK, FORGE, FLOW],     // (1,2,3): Warm spectrum concentration
    [SPARK, NEXUS, BEACON],   // (1,4,5): Red-green-cyan diagonal
    [SPARK, CRYSTAL, GROVE],  // (1,7,6): Red-violet-blue harmonic
    [FORGE, NEXUS, GROVE],    // (2,4,6): Orange-green-blue triadic
    [FORGE, BEACON, CRYSTAL], // (2,5,7): Warm-to-cool transition
    [FLOW, NEXUS, CRYSTAL],   // (3,4,7): Yellow-green-violet path
    [FLOW, GROVE, BEACON],    // (3,6,5): Yellow-blue-cyan arc
];

/// Prismorphism timing constants (Fibonacci-based, from spec)
pub mod timing {
    /// Micro-feedback
    pub const INSTANT_MS: f32 = 89.0;
    /// Clicks, toggles
    pub const FAST_MS: f32 = 144.0;
    /// Hover states
    pub const NORMAL_MS: f32 = 233.0;
    /// Dispersion, transforms
    pub const SLOW_MS: f32 = 377.0;
    /// Page transitions
    pub const DRAMATIC_MS: f32 = 610.0;
    /// Full reveals
    pub const EPIC_MS: f32 = 987.0;
    /// Physics-accurate delay between adjacent spectral colors (8ms)
    pub const SPECTRAL_DELAY_MS: f32 = 8.0;
}

/// Colony indices for reference
pub const SPARK: usize = 0;
pub const FORGE: usize = 1;
pub const FLOW: usize = 2;
pub const NEXUS: usize = 3;
pub const BEACON: usize = 4;
pub const GROVE: usize = 5;
pub const CRYSTAL: usize = 6;

/// Safety status colors
const SAFE_COLOR: (u8, u8, u8) = (0, 255, 136); // Green - h(x) >= 0.5
const CAUTION_COLOR: (u8, u8, u8) = (255, 215, 0); // Yellow - 0 <= h(x) < 0.5
const VIOLATION_COLOR: (u8, u8, u8) = (255, 68, 68); // Red - h(x) < 0

/// Voice pipeline state colors
const LISTENING_COLOR: (u8, u8, u8) = (78, 205, 196); // Flow cyan
const PROCESSING_COLOR: (u8, u8, u8) = (155, 126, 189); // Nexus purple
const ERROR_COLOR: (u8, u8, u8) = (255, 68, 68); // Red
const SUCCESS_COLOR: (u8, u8, u8) = (0, 255, 136); // Green

// ============================================================================
// Animation Patterns
// ============================================================================

/// Animation patterns for different states
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum AnimationPattern {
    /// All colonies showing their colors at steady brightness
    Idle,
    /// Soft breathing animation - all colonies rise and fall
    Breathing,
    /// Single LED rotating around ring - processing indicator
    Spin,
    /// Pulsing for listening state - Flow (cyan) pulsing
    Pulse,
    /// Cascade from center outward - executing commands
    Cascade,
    /// Flash for success/error feedback
    Flash,
    /// Flash red for error state
    ErrorFlash,
    /// Highlight single colony with subtle pulse
    Highlight(usize),
    /// Safety gradient based on h(x) value
    Safety(f64),
    /// Rainbow chase - celebration/success
    Rainbow,
    /// Sparkle effect - ambient delight
    Sparkle,
    /// Spectral shimmer - smooth color sweep through Fano basis (prismorphism)
    Spectral,
    /// Fano pulse - each LED pulses at different phase (7 phases for 7 colonies)
    FanoPulse,

    // ========================================================================
    // Prismorphism Patterns (from PRISMORPHISM.md)
    // ========================================================================
    /// FanoLine: Cycles through the 3 colors of a specific Fano multiplication line
    /// The line_index (0-6) selects which of the 7 Fano lines to trace
    /// Each line encodes an octonion multiplication: e_a * e_b = e_c
    FanoLine(usize),

    /// SpectralSweep: Physics-accurate ROYGBIV sweep (red to violet)
    /// Simulates light passing through a prism - red bends least, violet most
    /// Uses 8ms delay between adjacent colors for physics-accurate timing
    SpectralSweep,

    /// ChromaticPulse: Success/error feedback using colony colors
    /// For success: warm colors (Spark->Forge->Flow) pulse outward
    /// For error: cool colors pulse with sharper timing
    ChromaticPulse { success: bool },

    /// DiscoveryGlow: Gradual brightness increase on sustained presence
    /// Brightness increases over time as attention is detected
    /// Follows the discovery states: Rest(0%) -> Glance(10%) -> Interest(25%) -> Focus(40%)
    DiscoveryGlow {
        /// Current attention level (0.0 = no attention, 1.0 = full focus)
        attention: f32,
    },
}

// ============================================================================
// LED Ring State
// ============================================================================

/// LED ring hardware controller
pub struct LEDRing {
    /// Number of LEDs in the ring
    count: u8,
    /// GPIO pin for data (stored for hardware reference)
    #[allow(dead_code)]
    pin: u8,
    /// Global brightness (0.0 - 1.0)
    brightness: f32,
    /// Current animation pattern
    current_pattern: AnimationPattern,
    /// Animation start time
    animation_start: Instant,
    /// Frame counter for sparkle effect
    frame_counter: u64,
    /// SPI device handle for WS2812/SK6812 LEDs
    #[cfg(feature = "rpi")]
    spi: Option<rppal::spi::Spi>,
}

impl LEDRing {
    /// Create a new LED ring controller
    ///
    /// Initializes SPI communication with WS2812/SK6812 LEDs on Raspberry Pi.
    /// Uses SPI0 at 3.2 MHz (timing for 800 kHz data rate with 4-bit encoding).
    pub fn new(config: &LEDRingConfig) -> Result<Self> {
        info!("Initializing LED ring on GPIO {}", config.pin);
        info!("  LED count: {}", config.count);
        info!("  Brightness: {:.0}%", config.brightness * 100.0);

        // Initialize SPI for WS2812/SK6812 LEDs on Raspberry Pi
        #[cfg(feature = "rpi")]
        let spi = {
            use rppal::spi::{Bus, Mode, SlaveSelect, Spi};

            // WS2812/SK6812 timing:
            // - Data rate: 800 kHz
            // - SPI encoding: 4 bits per data bit
            // - SPI clock: 3.2 MHz (800 kHz * 4)
            // - Each LED byte becomes 4 SPI bytes
            match Spi::new(Bus::Spi0, SlaveSelect::Ss0, 3_200_000, Mode::Mode0) {
                Ok(spi) => {
                    info!("✓ SPI initialized for LED ring");
                    Some(spi)
                }
                Err(e) => {
                    tracing::warn!("⚠ SPI init failed: {}, LED ring will run in simulation mode", e);
                    None
                }
            }
        };

        Ok(Self {
            count: config.count,
            pin: config.pin,
            brightness: config.brightness,
            current_pattern: AnimationPattern::Idle,
            animation_start: Instant::now(),
            frame_counter: 0,
            #[cfg(feature = "rpi")]
            spi,
        })
    }

    /// Set the current animation pattern
    pub fn set_pattern(&mut self, pattern: AnimationPattern) {
        if self.current_pattern != pattern {
            self.current_pattern = pattern;
            self.animation_start = Instant::now();
            self.frame_counter = 0;
            debug!("LED pattern changed to {:?}", pattern);
        }
    }

    /// Get the current animation pattern
    pub fn pattern(&self) -> AnimationPattern {
        self.current_pattern
    }

    /// Calculate animation frame based on elapsed time
    /// Returns array of 7 RGB colors for each LED
    pub fn calculate_frame(&mut self) -> [(u8, u8, u8); 7] {
        let elapsed = self.animation_start.elapsed().as_millis() as f32;
        self.frame_counter += 1;

        match self.current_pattern {
            AnimationPattern::Idle => self.frame_idle(),
            AnimationPattern::Breathing => self.frame_breathing(elapsed),
            AnimationPattern::Spin => self.frame_spin(elapsed),
            AnimationPattern::Pulse => self.frame_pulse(elapsed),
            AnimationPattern::Cascade => self.frame_cascade(elapsed),
            AnimationPattern::Flash => self.frame_flash(elapsed),
            AnimationPattern::ErrorFlash => self.frame_error_flash(elapsed),
            AnimationPattern::Highlight(idx) => self.frame_highlight(idx, elapsed),
            AnimationPattern::Safety(h_x) => self.frame_safety(h_x),
            AnimationPattern::Rainbow => self.frame_rainbow(elapsed),
            AnimationPattern::Sparkle => self.frame_sparkle(),
            AnimationPattern::Spectral => self.frame_spectral(elapsed),
            AnimationPattern::FanoPulse => self.frame_fano_pulse(elapsed),
            // Prismorphism patterns
            AnimationPattern::FanoLine(line_idx) => self.frame_fano_line(line_idx, elapsed),
            AnimationPattern::SpectralSweep => self.frame_spectral_sweep(elapsed),
            AnimationPattern::ChromaticPulse { success } => {
                self.frame_chromatic_pulse(success, elapsed)
            }
            AnimationPattern::DiscoveryGlow { attention } => {
                self.frame_discovery_glow(attention, elapsed)
            }
        }
    }

    /// Calculate animation frame as RGBW with gamma correction
    /// This is the preferred method for SK6812 hardware
    /// Returns array of 7 RGBW colors for each LED
    pub fn calculate_frame_rgbw(&mut self) -> [RGBW; 7] {
        let rgb_colors = self.calculate_frame();

        let mut rgbw_colors = [RGBW::new(0, 0, 0, 0); 7];
        for (i, rgb) in rgb_colors.iter().enumerate() {
            // Convert RGB to RGBW (extracts white channel)
            let rgbw = RGBW::from_tuple(*rgb);
            // Apply gamma correction for perceptually linear brightness
            rgbw_colors[i] = gamma_correct_rgbw(rgbw);
        }
        rgbw_colors
    }

    /// Render the current frame to the LED hardware
    /// Uses SK6812 RGBW format with gamma correction
    ///
    /// # SPI Encoding for WS2812/SK6812
    ///
    /// Each data bit is encoded as 4 SPI bits:
    /// - Logical 1: 0b1110 (high for 3 periods, low for 1)
    /// - Logical 0: 0b1000 (high for 1 period, low for 3)
    ///
    /// At 3.2 MHz SPI clock, each 4-bit pattern takes 1.25 µs, matching
    /// the WS2812 timing requirement of ~1.25 µs per bit.
    pub fn render(&mut self) {
        let rgbw_colors = self.calculate_frame_rgbw();

        #[cfg(feature = "rpi")]
        if let Some(ref mut spi) = self.spi {
            // Build SPI data buffer with 4-bit encoding
            // Each LED has 4 color bytes (GRBW), each byte becomes 4 SPI bytes
            // 7 LEDs * 4 colors * 4 SPI bytes = 112 bytes
            let mut spi_data: Vec<u8> = Vec::with_capacity(self.count as usize * 4 * 4);

            for rgbw in rgbw_colors.iter() {
                // SK6812 uses GRBW byte order
                let grbw = rgbw.to_grbw_bytes();
                for &byte in &grbw {
                    // Encode each bit of the byte as 4 SPI bits
                    spi_data.extend_from_slice(&Self::encode_byte_to_spi(byte));
                }
            }

            // Add reset pulse (low for at least 50 µs = 160 SPI bytes at 3.2 MHz)
            // Use 200 bytes (62.5 µs) to be safe
            spi_data.extend(std::iter::repeat(0u8).take(200));

            // Write to SPI
            if let Err(e) = spi.write(&spi_data) {
                tracing::warn!("SPI write failed: {}", e);
            }
        }

        #[cfg(not(feature = "rpi"))]
        {
            // Simulation mode: just log the frame
            debug!(
                "LED frame (RGBW): {:?}",
                rgbw_colors
                    .iter()
                    .map(|c| (c.r, c.g, c.b, c.w))
                    .collect::<Vec<_>>()
            );
        }
    }

    /// Encode a single byte into 4 SPI bytes using WS2812 timing
    ///
    /// Each data bit becomes 4 SPI bits:
    /// - Bit 1: 0b1110 (0xE)
    /// - Bit 0: 0b1000 (0x8)
    ///
    /// Input byte is encoded MSB first.
    #[cfg(feature = "rpi")]
    fn encode_byte_to_spi(byte: u8) -> [u8; 4] {
        let mut spi_bytes = [0u8; 4];

        for i in 0..4 {
            // Each SPI byte encodes 2 data bits
            let bit_high = (byte >> (7 - i * 2)) & 1;
            let bit_low = (byte >> (6 - i * 2)) & 1;

            // Combine the 4-bit patterns for both data bits
            let pattern_high: u8 = if bit_high == 1 { 0xE } else { 0x8 };
            let pattern_low: u8 = if bit_low == 1 { 0xE } else { 0x8 };

            spi_bytes[i] = (pattern_high << 4) | pattern_low;
        }

        spi_bytes
    }

    // ========================================================================
    // Animation Frame Generators
    // ========================================================================

    /// Idle: all colonies at steady brightness
    fn frame_idle(&self) -> [(u8, u8, u8); 7] {
        let mut colors = [(0u8, 0u8, 0u8); 7];
        for (i, color) in COLONY_COLORS.iter().enumerate() {
            colors[i] = self.apply_brightness(*color);
        }
        colors
    }

    /// Breathing: slow sinusoidal brightness variation
    /// 4-second cycle, all LEDs breathe together
    fn frame_breathing(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // 4-second breathing cycle using sine wave
        let phase = (elapsed / 4000.0 * std::f32::consts::TAU).sin();
        let breath_factor = 0.4 + 0.6 * (phase * 0.5 + 0.5); // Range 0.4 to 1.0

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for (i, color) in COLONY_COLORS.iter().enumerate() {
            colors[i] = (
                (color.0 as f32 * self.brightness * breath_factor) as u8,
                (color.1 as f32 * self.brightness * breath_factor) as u8,
                (color.2 as f32 * self.brightness * breath_factor) as u8,
            );
        }
        colors
    }

    /// Spin: single bright LED rotating - indicates processing
    /// 1-second rotation with smooth trailing
    fn frame_spin(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        let rotation_period = 800.0; // 800ms per rotation
        let position = (elapsed / rotation_period * 7.0) % 7.0;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            // Calculate distance from current position (with wrapping)
            let dist = (i as f32 - position)
                .abs()
                .min((i as f32 + 7.0 - position).abs())
                .min((position + 7.0 - i as f32).abs());

            // Smooth falloff for trailing effect
            let factor = if dist < 1.0 {
                1.0 - dist * 0.3
            } else if dist < 2.0 {
                0.7 - (dist - 1.0) * 0.5
            } else {
                0.1
            };

            let color = PROCESSING_COLOR;
            colors[i] = (
                (color.0 as f32 * self.brightness * factor) as u8,
                (color.1 as f32 * self.brightness * factor) as u8,
                (color.2 as f32 * self.brightness * factor) as u8,
            );
        }
        colors
    }

    /// Pulse: Flow color (cyan) pulsing for listening state
    /// Fast 500ms pulse to indicate active listening
    fn frame_pulse(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // Fast 500ms pulse using absolute sine
        let phase = (elapsed / 500.0 * std::f32::consts::TAU).sin();
        let pulse_factor = 0.3 + 0.7 * phase.abs(); // Range 0.3 to 1.0

        let pulsed = (
            (LISTENING_COLOR.0 as f32 * self.brightness * pulse_factor) as u8,
            (LISTENING_COLOR.1 as f32 * self.brightness * pulse_factor) as u8,
            (LISTENING_COLOR.2 as f32 * self.brightness * pulse_factor) as u8,
        );

        [pulsed; 7]
    }

    /// Cascade: outward wave from center (LED 3) - executing commands
    /// 600ms cascade cycle
    fn frame_cascade(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        let wave_position = (elapsed / 600.0 * 4.0) % 4.0;
        let center = 3;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            let distance = (i as i32 - center as i32).abs() as f32;

            // Wave intensity based on distance from wave front
            let intensity = if (wave_position - distance).abs() < 1.0 {
                1.0 - (wave_position - distance).abs()
            } else {
                0.15
            };

            let color = COLONY_COLORS[i];
            colors[i] = (
                (color.0 as f32 * self.brightness * intensity) as u8,
                (color.1 as f32 * self.brightness * intensity) as u8,
                (color.2 as f32 * self.brightness * intensity) as u8,
            );
        }
        colors
    }

    /// Flash: quick success flash (green)
    /// 3 flashes over 600ms
    fn frame_flash(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        let flash_phase = (elapsed / 100.0) as u32 % 4;
        let on = flash_phase < 2;

        if on && elapsed < 600.0 {
            [self.apply_brightness(SUCCESS_COLOR); 7]
        } else {
            [(0, 0, 0); 7]
        }
    }

    /// Error flash: red pulsing for error state
    /// Slower, more noticeable pattern
    fn frame_error_flash(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // 200ms on/off cycle, 3 cycles total
        let cycle = (elapsed / 200.0) as u32;
        let on = cycle % 2 == 0 && cycle < 6;

        if on {
            [self.apply_brightness(ERROR_COLOR); 7]
        } else {
            // Dim red background
            let dim_red = (
                (ERROR_COLOR.0 as f32 * 0.1) as u8,
                (ERROR_COLOR.1 as f32 * 0.1) as u8,
                (ERROR_COLOR.2 as f32 * 0.1) as u8,
            );
            [self.apply_brightness(dim_red); 7]
        }
    }

    /// Highlight: single colony bright with subtle pulse, others dim
    fn frame_highlight(&self, colony_idx: usize, elapsed: f32) -> [(u8, u8, u8); 7] {
        // Subtle pulse on highlighted colony
        let phase = (elapsed / 800.0 * std::f32::consts::TAU).sin();
        let pulse_factor = 0.85 + 0.15 * phase;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for (i, color) in COLONY_COLORS.iter().enumerate() {
            let factor = if i == colony_idx { pulse_factor } else { 0.15 };
            colors[i] = (
                (color.0 as f32 * self.brightness * factor) as u8,
                (color.1 as f32 * self.brightness * factor) as u8,
                (color.2 as f32 * self.brightness * factor) as u8,
            );
        }
        colors
    }

    /// Safety: color based on h(x) value
    /// Green (>= 0.5), Yellow (0.0 - 0.5), Red (< 0)
    fn frame_safety(&self, h_x: f64) -> [(u8, u8, u8); 7] {
        let color = if h_x >= 0.5 {
            SAFE_COLOR
        } else if h_x >= 0.0 {
            // Interpolate between caution and safe
            let t = (h_x * 2.0) as f32; // 0.0 -> 0.0, 0.5 -> 1.0
            (
                (CAUTION_COLOR.0 as f32 * (1.0 - t) + SAFE_COLOR.0 as f32 * t) as u8,
                (CAUTION_COLOR.1 as f32 * (1.0 - t) + SAFE_COLOR.1 as f32 * t) as u8,
                (CAUTION_COLOR.2 as f32 * (1.0 - t) + SAFE_COLOR.2 as f32 * t) as u8,
            )
        } else {
            VIOLATION_COLOR
        };

        [self.apply_brightness(color); 7]
    }

    /// Rainbow: HSV rainbow chase for celebration
    fn frame_rainbow(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        let speed = 1500.0; // 1.5 second full cycle
        let base_hue = (elapsed / speed) % 1.0;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            let hue = (base_hue + (i as f32 / 7.0)) % 1.0;
            let rgb = hsv_to_rgb(hue, 1.0, 1.0);
            colors[i] = self.apply_brightness(rgb);
        }
        colors
    }

    /// Sparkle: random twinkling for ambient delight
    fn frame_sparkle(&self) -> [(u8, u8, u8); 7] {
        // Simple pseudo-random based on frame counter
        let seed = self.frame_counter;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            // Pseudo-random intensity
            let rand_val =
                ((seed.wrapping_mul(31337).wrapping_add(i as u64 * 7919)) % 100) as f32 / 100.0;
            let factor = if rand_val > 0.85 {
                1.0 // Sparkle
            } else {
                0.2 + rand_val * 0.3 // Subtle variation
            };

            let color = COLONY_COLORS[i];
            colors[i] = (
                (color.0 as f32 * self.brightness * factor) as u8,
                (color.1 as f32 * self.brightness * factor) as u8,
                (color.2 as f32 * self.brightness * factor) as u8,
            );
        }
        colors
    }

    /// Spectral: smooth color sweep through Fano basis (prismorphism effect)
    /// Each LED shows the color of the next colony in sequence, creating
    /// a smooth spectral shimmer that sweeps around the ring.
    fn frame_spectral(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // 8-second full spectral cycle (matches prismorphism shimmer duration)
        let cycle_progress = (elapsed / 8000.0) % 1.0;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            // Each LED is offset by 1/7 of the cycle
            let led_phase = (cycle_progress + (i as f32 / 7.0)) % 1.0;

            // Interpolate between adjacent colony colors
            let color_idx = (led_phase * 7.0) as usize;
            let color_frac = (led_phase * 7.0) - color_idx as f32;

            let c1 = COLONY_COLORS[color_idx % 7];
            let c2 = COLONY_COLORS[(color_idx + 1) % 7];

            // Smooth interpolation
            let r = c1.0 as f32 * (1.0 - color_frac) + c2.0 as f32 * color_frac;
            let g = c1.1 as f32 * (1.0 - color_frac) + c2.1 as f32 * color_frac;
            let b = c1.2 as f32 * (1.0 - color_frac) + c2.2 as f32 * color_frac;

            colors[i] = (
                (r * self.brightness) as u8,
                (g * self.brightness) as u8,
                (b * self.brightness) as u8,
            );
        }
        colors
    }

    /// Fano Pulse: each LED pulses at a different phase (7 phases for Fano plane)
    /// Creates a rhythmic "breathing" effect where each colony breathes
    /// at offset phases, creating a wave-like pattern.
    fn frame_fano_pulse(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // 6-second cycle (matches prismorphism spectral border duration)
        let base_phase = elapsed / 6000.0 * std::f32::consts::TAU;

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            // Each LED gets a phase offset of (i/7) * 2π
            let phase_offset = (i as f32 / 7.0) * std::f32::consts::TAU;
            let led_phase = base_phase + phase_offset;

            // Sinusoidal intensity (0.3 to 1.0)
            let intensity = 0.3 + 0.7 * ((led_phase.sin() + 1.0) * 0.5);

            let color = COLONY_COLORS[i];
            colors[i] = (
                (color.0 as f32 * self.brightness * intensity) as u8,
                (color.1 as f32 * self.brightness * intensity) as u8,
                (color.2 as f32 * self.brightness * intensity) as u8,
            );
        }
        colors
    }

    // ========================================================================
    // Prismorphism Frame Generators (from PRISMORPHISM.md)
    // ========================================================================

    /// FanoLine: Cycles through the 3 colors of a specific Fano multiplication line
    ///
    /// Each Fano line encodes an octonion multiplication: e_a * e_b = e_c
    /// The animation smoothly cycles through all 3 colors, creating a
    /// "multiplicative gradient" effect described in the Prismorphism spec.
    ///
    /// # Arguments
    /// * `line_idx` - Index into FANO_LINES (0-6), wraps if out of range
    /// * `elapsed` - Milliseconds since animation started
    fn frame_fano_line(&self, line_idx: usize, elapsed: f32) -> [(u8, u8, u8); 7] {
        // Wrap line index to valid range
        let line = FANO_LINES[line_idx % 7];

        // Get the 3 Prismorphism colors for this Fano line
        let line_colors = [
            SPECTRAL_ORDER[line[0]],
            SPECTRAL_ORDER[line[1]],
            SPECTRAL_ORDER[line[2]],
        ];

        // 3-second cycle to show each color prominently
        // Uses slow timing (377ms per transition) for smooth dispersion effect
        let cycle_duration = timing::SLOW_MS * 3.0 * 3.0; // ~3.4 seconds full cycle
        let progress = (elapsed % cycle_duration) / cycle_duration;

        // Which of the 3 colors is currently dominant
        let color_phase = progress * 3.0;
        let current_idx = color_phase.floor() as usize;
        let blend_factor = color_phase - current_idx as f32;

        // Smooth interpolation between adjacent line colors
        let c1 = line_colors[current_idx % 3];
        let c2 = line_colors[(current_idx + 1) % 3];

        // Use smooth easing for glass-like light behavior
        let t = smooth_step(blend_factor);

        let blended = (
            lerp_u8(c1.0, c2.0, t),
            lerp_u8(c1.1, c2.1, t),
            lerp_u8(c1.2, c2.2, t),
        );

        // All LEDs show the same blended color, but with position-based intensity
        // to create a subtle "light concentration" effect along the line
        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            // LEDs that are part of this Fano line glow brighter
            let is_on_line = line.contains(&i);
            let intensity = if is_on_line { 1.0 } else { 0.3 };

            colors[i] = (
                (blended.0 as f32 * self.brightness * intensity) as u8,
                (blended.1 as f32 * self.brightness * intensity) as u8,
                (blended.2 as f32 * self.brightness * intensity) as u8,
            );
        }
        colors
    }

    /// SpectralSweep: Physics-accurate ROYGBIV sweep from red to violet
    ///
    /// Simulates light passing through a prism - red light (620nm) arrives first
    /// because it bends least, violet light (400nm) arrives last.
    ///
    /// Uses 8ms delay between adjacent colors for physics-accurate dispersion timing
    /// as specified in PRISMORPHISM.md.
    fn frame_spectral_sweep(&self, elapsed: f32) -> [(u8, u8, u8); 7] {
        // Full sweep takes 987ms (epic duration) - dramatic reveal timing
        let sweep_duration = timing::EPIC_MS;
        let progress = (elapsed % (sweep_duration * 2.0)) / sweep_duration;

        // Bidirectional sweep: forward (red->violet) then reverse (violet->red)
        let _forward = progress <= 1.0;

        let mut colors = [(0u8, 0u8, 0u8); 7];

        for i in 0..7 {
            // Each LED has a physics-accurate delay based on wavelength
            // Red (i=0) has 0ms delay, Violet (i=6) has 48ms delay
            let spectral_delay = i as f32 * timing::SPECTRAL_DELAY_MS;
            let delayed_elapsed = (elapsed - spectral_delay).max(0.0);
            let led_progress = (delayed_elapsed % (sweep_duration * 2.0)) / sweep_duration;

            // Calculate which spectral color this LED should show
            let led_sweep = if led_progress <= 1.0 {
                led_progress
            } else {
                2.0 - led_progress
            };

            // Map progress to color index with smooth interpolation
            let color_position = led_sweep * 6.0; // 0 to 6 across 7 colors
            let color_idx = color_position.floor() as usize;
            let blend = color_position - color_idx as f32;

            let c1 = SPECTRAL_ORDER[color_idx.min(6)];
            let c2 = SPECTRAL_ORDER[(color_idx + 1).min(6)];

            // Smooth easing for natural light dispersion
            let t = smooth_step(blend);

            colors[i] = (
                (lerp_u8(c1.0, c2.0, t) as f32 * self.brightness) as u8,
                (lerp_u8(c1.1, c2.1, t) as f32 * self.brightness) as u8,
                (lerp_u8(c1.2, c2.2, t) as f32 * self.brightness) as u8,
            );
        }
        colors
    }

    /// ChromaticPulse: Success/error feedback using colony colors
    ///
    /// For success: warm colors (Spark->Forge->Flow) pulse outward from center
    /// For error: cool colors (Crystal->Grove->Beacon) pulse with sharper timing
    ///
    /// Uses chromatic-pulse animation timing from PRISMORPHISM.md (610ms)
    fn frame_chromatic_pulse(&self, success: bool, elapsed: f32) -> [(u8, u8, u8); 7] {
        // 610ms pulse duration (dramatic timing from spec)
        let pulse_duration = timing::DRAMATIC_MS;
        let progress = (elapsed % pulse_duration) / pulse_duration;

        // Colors based on success/error state
        let pulse_colors: [(u8, u8, u8); 3] = if success {
            // Warm spectrum: Spark -> Forge -> Flow (success = energy/creation/adaptation)
            [prism::SPARK, prism::FORGE, prism::FLOW]
        } else {
            // Cool spectrum: Crystal -> Grove -> Beacon (error = needs clarity/growth/guidance)
            [prism::CRYSTAL, prism::GROVE, prism::BEACON]
        };

        // Pulse wave emanates from center (LED 3) outward
        let center = 3;
        let wave_radius = progress * 4.0; // Expands to cover all 7 LEDs

        let mut colors = [(0u8, 0u8, 0u8); 7];
        for i in 0..7 {
            let distance = (i as i32 - center).abs() as f32;

            // Wave intensity: bright at wave front, fading behind
            let wave_intensity = if distance <= wave_radius {
                let relative_pos = 1.0 - (wave_radius - distance) / wave_radius.max(0.1);
                // Sharper falloff for error, smoother for success
                if success {
                    smooth_step(1.0 - relative_pos * 0.5)
                } else {
                    (1.0 - relative_pos).powi(2)
                }
            } else {
                0.1 // Dim background
            };

            // Hue shift across the pulse wave (0-2 maps to 3 colors)
            let hue_progress = (progress * 2.0).min(2.0);
            let color_idx = hue_progress.floor() as usize;
            let color_blend = hue_progress - color_idx as f32;

            let c1 = pulse_colors[color_idx.min(2)];
            let c2 = pulse_colors[(color_idx + 1).min(2)];

            let blended = (
                lerp_u8(c1.0, c2.0, color_blend),
                lerp_u8(c1.1, c2.1, color_blend),
                lerp_u8(c1.2, c2.2, color_blend),
            );

            colors[i] = (
                (blended.0 as f32 * self.brightness * wave_intensity) as u8,
                (blended.1 as f32 * self.brightness * wave_intensity) as u8,
                (blended.2 as f32 * self.brightness * wave_intensity) as u8,
            );
        }
        colors
    }

    /// DiscoveryGlow: Gradual brightness increase on sustained presence
    ///
    /// Follows the discovery states from PRISMORPHISM.md:
    /// - Rest (attention=0): 0% effect opacity
    /// - Glance (attention=0.1): 10% - subtle shimmer begins
    /// - Interest (attention=0.25): 25% - color cycle begins
    /// - Focus (attention=0.4+): 40%+ - full spectral effect
    ///
    /// The attention level is provided externally (e.g., from presence sensors)
    fn frame_discovery_glow(&self, attention: f32, elapsed: f32) -> [(u8, u8, u8); 7] {
        // Clamp attention to valid range
        let attention = attention.clamp(0.0, 1.0);

        // Base intensity follows discovery state thresholds
        let base_intensity = if attention < 0.1 {
            // Rest state: very dim
            0.05
        } else if attention < 0.25 {
            // Glance state: subtle shimmer
            0.1 + (attention - 0.1) * 0.5 // 0.1 -> 0.175
        } else if attention < 0.4 {
            // Interest state: color cycle begins
            0.25 + (attention - 0.25) * 1.0 // 0.25 -> 0.4
        } else {
            // Focus state: full effect
            0.4 + (attention - 0.4) * 0.5 // 0.4 -> 0.7 (capped)
        };

        // Animation complexity increases with attention
        let mut colors = [(0u8, 0u8, 0u8); 7];

        if attention < 0.1 {
            // Rest: static dim colony colors
            for i in 0..7 {
                let color = COLONY_COLORS[i];
                colors[i] = (
                    (color.0 as f32 * self.brightness * base_intensity) as u8,
                    (color.1 as f32 * self.brightness * base_intensity) as u8,
                    (color.2 as f32 * self.brightness * base_intensity) as u8,
                );
            }
        } else if attention < 0.25 {
            // Glance: subtle shimmer (slow breathing)
            let shimmer_phase = (elapsed / 4000.0 * std::f32::consts::TAU).sin();
            let shimmer = base_intensity * (0.8 + 0.2 * shimmer_phase);

            for i in 0..7 {
                let color = COLONY_COLORS[i];
                colors[i] = (
                    (color.0 as f32 * self.brightness * shimmer) as u8,
                    (color.1 as f32 * self.brightness * shimmer) as u8,
                    (color.2 as f32 * self.brightness * shimmer) as u8,
                );
            }
        } else if attention < 0.4 {
            // Interest: color cycle begins (spectral colors start appearing)
            let cycle_progress = (elapsed / 8000.0) % 1.0;

            for i in 0..7 {
                // Blend between colony color and spectral color based on attention
                let spectral_blend = (attention - 0.25) / 0.15; // 0 at 0.25, 1 at 0.4
                let colony_color = COLONY_COLORS[i];
                let spectral_color = SPECTRAL_ORDER[i];

                // Phase offset per LED for subtle wave
                let led_phase = (cycle_progress + i as f32 / 7.0) % 1.0;
                let phase_intensity = 0.8 + 0.2 * (led_phase * std::f32::consts::TAU).sin();

                let blended = (
                    lerp_u8(colony_color.0, spectral_color.0, spectral_blend),
                    lerp_u8(colony_color.1, spectral_color.1, spectral_blend),
                    lerp_u8(colony_color.2, spectral_color.2, spectral_blend),
                );

                colors[i] = (
                    (blended.0 as f32 * self.brightness * base_intensity * phase_intensity) as u8,
                    (blended.1 as f32 * self.brightness * base_intensity * phase_intensity) as u8,
                    (blended.2 as f32 * self.brightness * base_intensity * phase_intensity) as u8,
                );
            }
        } else {
            // Focus: full spectral effect with Fano line shimmer
            let cycle_progress = (elapsed / 6000.0) % 1.0;

            // Determine which Fano line to highlight based on cycle
            let active_line_idx = (cycle_progress * 7.0).floor() as usize;
            let active_line = FANO_LINES[active_line_idx % 7];

            for i in 0..7 {
                let is_on_active_line = active_line.contains(&i);
                let spectral_color = SPECTRAL_ORDER[i];

                // LEDs on active Fano line glow brighter with pulsing
                let line_pulse = if is_on_active_line {
                    let pulse_phase = ((elapsed / timing::SLOW_MS) * std::f32::consts::TAU).sin();
                    1.0 + 0.3 * pulse_phase
                } else {
                    0.7
                };

                let intensity = base_intensity * line_pulse;

                colors[i] = (
                    (spectral_color.0 as f32 * self.brightness * intensity) as u8,
                    (spectral_color.1 as f32 * self.brightness * intensity) as u8,
                    (spectral_color.2 as f32 * self.brightness * intensity) as u8,
                );
            }
        }

        colors
    }

    // ========================================================================
    // Convenience Methods
    // ========================================================================

    /// Set all LEDs to a single color
    pub fn set_all(&mut self, color: (u8, u8, u8)) {
        let adjusted = self.apply_brightness(color);
        info!("Setting all {} LEDs to {:?}", self.count, adjusted);

        // In full implementation:
        // let colors: Vec<RGB8> = (0..self.count)
        //     .map(|_| RGB8::new(adjusted.0, adjusted.1, adjusted.2))
        //     .collect();
        // self.ws.write(colors.iter().cloned())?;
    }

    /// Set LEDs to colony colors (idle state)
    pub fn set_colony_ring(&mut self) {
        self.set_pattern(AnimationPattern::Idle);
        info!("Setting colony ring pattern");
    }

    /// Highlight a specific colony
    pub fn highlight_colony(&mut self, colony_index: usize) {
        if colony_index >= 7 {
            return;
        }
        self.set_pattern(AnimationPattern::Highlight(colony_index));
        info!("Highlighting colony {}", colony_index + 1);
    }

    /// Pulse animation for listening state
    pub fn pulse_listening(&mut self) {
        self.set_pattern(AnimationPattern::Pulse);
        info!("Pulsing for listening state");
    }

    /// Safety status indicator
    pub fn set_safety_status(&mut self, h_x: f64) {
        self.set_pattern(AnimationPattern::Safety(h_x));

        let status = if h_x >= 0.5 {
            "SAFE"
        } else if h_x >= 0.0 {
            "CAUTION"
        } else {
            "VIOLATION"
        };
        info!("Setting safety status: h(x) = {:.2} [{}]", h_x, status);
    }

    /// Show error state
    pub fn show_error(&mut self) {
        self.set_pattern(AnimationPattern::ErrorFlash);
        info!("Showing error state");
    }

    /// Show success feedback
    pub fn show_success(&mut self) {
        self.set_pattern(AnimationPattern::Flash);
        info!("Showing success state");
    }

    /// Apply brightness scaling
    fn apply_brightness(&self, color: (u8, u8, u8)) -> (u8, u8, u8) {
        (
            (color.0 as f32 * self.brightness) as u8,
            (color.1 as f32 * self.brightness) as u8,
            (color.2 as f32 * self.brightness) as u8,
        )
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Convert HSV to RGB
/// h, s, v in range 0.0 - 1.0
fn hsv_to_rgb(h: f32, s: f32, v: f32) -> (u8, u8, u8) {
    let h = h * 6.0;
    let i = h.floor() as i32;
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

    ((r * 255.0) as u8, (g * 255.0) as u8, (b * 255.0) as u8)
}

/// Smooth step interpolation (Hermite curve)
/// Creates natural, glass-like light transitions
/// Maps x from 0-1 to a smooth S-curve
#[inline]
fn smooth_step(x: f32) -> f32 {
    let x = x.clamp(0.0, 1.0);
    x * x * (3.0 - 2.0 * x)
}

/// Linear interpolation for u8 color components
/// Prevents overflow and ensures smooth color blending
#[inline]
fn lerp_u8(a: u8, b: u8, t: f32) -> u8 {
    let t = t.clamp(0.0, 1.0);
    (a as f32 * (1.0 - t) + b as f32 * t) as u8
}

// ============================================================================
// Module-Level API (for simpler usage)
// Thread-safe singleton using OnceLock<Mutex<Option<LEDRing>>>
// ============================================================================

/// Initialize the LED ring from config (thread-safe)
pub fn init(config: &LEDRingConfig) -> Result<()> {
    let ring = LEDRing::new(config)?;
    let mut guard = get_led_ring()
        .lock()
        .map_err(|e| anyhow::anyhow!("LED ring mutex poisoned: {}", e))?;
    *guard = Some(ring);
    Ok(())
}

/// Helper macro to reduce boilerplate in module-level functions
macro_rules! with_led_ring {
    ($body:expr) => {
        if let Ok(mut guard) = get_led_ring().lock() {
            if let Some(ref mut ring) = *guard {
                $body(ring);
            }
        }
    };
}

/// Set to idle pattern (colony colors)
pub fn show_idle() {
    with_led_ring!(|ring: &mut LEDRing| ring.set_colony_ring());
}

/// Set to listening pattern (pulsing cyan)
pub fn show_listening() {
    with_led_ring!(|ring: &mut LEDRing| ring.pulse_listening());
}

/// Set to processing pattern (spinning)
pub fn show_processing() {
    with_led_ring!(|ring: &mut LEDRing| ring.set_pattern(AnimationPattern::Spin));
}

/// Set to executing pattern (cascade)
pub fn show_executing() {
    with_led_ring!(|ring: &mut LEDRing| ring.set_pattern(AnimationPattern::Cascade));
}

/// Set to speaking pattern (highlight Crystal)
pub fn show_speaking() {
    with_led_ring!(|ring: &mut LEDRing| ring.highlight_colony(CRYSTAL));
}

/// Set to error pattern (red flash)
pub fn show_error() {
    with_led_ring!(|ring: &mut LEDRing| ring.show_error());
}

/// Set to success pattern (green flash)
pub fn show_success() {
    with_led_ring!(|ring: &mut LEDRing| ring.show_success());
}

/// Highlight a specific colony
pub fn highlight_colony(idx: usize) {
    with_led_ring!(|ring: &mut LEDRing| ring.highlight_colony(idx));
}

/// Update safety status
pub fn update_status(h_x: Option<f64>) {
    if let Some(score) = h_x {
        with_led_ring!(|ring: &mut LEDRing| ring.set_safety_status(score));
    }
}

/// Set safety status directly
pub fn set_safety_status(h_x: f64) {
    with_led_ring!(|ring: &mut LEDRing| ring.set_safety_status(h_x));
}

/// Render current frame (call in animation loop)
pub fn render() {
    with_led_ring!(|ring: &mut LEDRing| ring.render());
}

/// Show spectral shimmer (prismorphism effect)
pub fn show_spectral() {
    with_led_ring!(|ring: &mut LEDRing| ring.set_pattern(AnimationPattern::Spectral));
}

/// Show Fano pulse (phase-offset breathing)
pub fn show_fano_pulse() {
    with_led_ring!(|ring: &mut LEDRing| ring.set_pattern(AnimationPattern::FanoPulse));
}

// ============================================================================
// Prismorphism Module-Level API (from PRISMORPHISM.md)
// ============================================================================

/// Show Fano line pattern - cycles through 3 colors of a multiplication line
///
/// # Arguments
/// * `line_idx` - Which Fano line (0-6):
///   - 0: (1,2,3) Spark-Forge-Flow - warm spectrum
///   - 1: (1,4,5) Spark-Nexus-Beacon - red-green-cyan
///   - 2: (1,7,6) Spark-Crystal-Grove - red-violet-blue
///   - 3: (2,4,6) Forge-Nexus-Grove - orange-green-blue
///   - 4: (2,5,7) Forge-Beacon-Crystal - warm-to-cool
///   - 5: (3,4,7) Flow-Nexus-Crystal - yellow-green-violet
///   - 6: (3,6,5) Flow-Grove-Beacon - yellow-blue-cyan
pub fn show_fano_line(line_idx: usize) {
    with_led_ring!(|ring: &mut LEDRing| {
        ring.set_pattern(AnimationPattern::FanoLine(line_idx));
        info!("Showing Fano line {} pattern", line_idx);
    });
}

/// Show spectral sweep - physics-accurate ROYGBIV (red to violet)
/// Simulates light passing through a prism
pub fn show_spectral_sweep() {
    with_led_ring!(|ring: &mut LEDRing| {
        ring.set_pattern(AnimationPattern::SpectralSweep);
        info!("Showing spectral sweep pattern");
    });
}

/// Show chromatic pulse - success/error feedback with colony colors
///
/// # Arguments
/// * `success` - true for warm colors (success), false for cool colors (error)
pub fn show_chromatic_pulse(success: bool) {
    with_led_ring!(|ring: &mut LEDRing| {
        ring.set_pattern(AnimationPattern::ChromaticPulse { success });
        info!(
            "Showing chromatic pulse ({} feedback)",
            if success { "success" } else { "error" }
        );
    });
}

/// Show discovery glow - brightness increases with sustained attention
///
/// # Arguments
/// * `attention` - Attention level (0.0-1.0):
///   - 0.0-0.1: Rest state (very dim)
///   - 0.1-0.25: Glance state (subtle shimmer)
///   - 0.25-0.4: Interest state (color cycle begins)
///   - 0.4-1.0: Focus state (full spectral effect)
pub fn show_discovery_glow(attention: f32) {
    with_led_ring!(|ring: &mut LEDRing| {
        ring.set_pattern(AnimationPattern::DiscoveryGlow { attention });
        debug!("Discovery glow at {:.0}% attention", attention * 100.0);
    });
}

/// Update discovery glow attention level without resetting animation
/// Useful for smoothly transitioning between attention states
pub fn update_discovery_attention(attention: f32) {
    if let Ok(mut guard) = get_led_ring().lock() {
        if let Some(ref mut ring) = *guard {
            // Only update if we're already in discovery mode
            if let AnimationPattern::DiscoveryGlow { .. } = ring.pattern() {
                // Create new pattern with updated attention, preserving animation timing
                ring.current_pattern = AnimationPattern::DiscoveryGlow { attention };
                debug!("Updated discovery attention to {:.0}%", attention * 100.0);
            }
        }
    }
}

/// Cycle through all 7 Fano lines sequentially
/// Good for demonstration/ambient mode
pub fn cycle_fano_lines() {
    if let Ok(mut guard) = get_led_ring().lock() {
        if let Some(ref mut ring) = *guard {
            // Get current line index or start at 0
            let next_idx = if let AnimationPattern::FanoLine(idx) = ring.pattern() {
                (idx + 1) % 7
            } else {
                0
            };
            ring.set_pattern(AnimationPattern::FanoLine(next_idx));
            info!("Cycling to Fano line {}", next_idx);
        }
    }
}

// =============================================================================
// Orb Cross-Client Sync (January 5, 2026)
// =============================================================================

/// Flash the LED ring in response to an orb interaction from another client
///
/// When the orb is tapped on VisionOS, the Hub LED ring flashes to
/// acknowledge the cross-client sync. This creates a unified presence
/// across all devices.
///
/// # Arguments
/// * `action` - The interaction type (tap, long_press, gaze_dwell, etc.)
/// * `colony` - Optional colony to highlight during flash
pub fn orb_flash(action: &str, colony: Option<&str>) {
    with_led_ring!(|ring: &mut LEDRing| {
        // Choose animation based on action type
        let pattern = match action {
            "tap" => AnimationPattern::Flash,
            "long_press" => AnimationPattern::Cascade,
            "double_tap" => AnimationPattern::SpectralSweep,
            "gaze_dwell" => AnimationPattern::DiscoveryGlow { attention: 1.0 },
            "voice_wake" => AnimationPattern::Pulse,
            _ => AnimationPattern::Flash,
        };

        ring.set_pattern(pattern);
        info!("🔮 Orb flash: {} (colony: {:?})", action, colony);

        // If a specific colony is provided, highlight it after brief flash
        if let Some(colony_name) = colony {
            let idx = match colony_name {
                "spark" => Some(SPARK),
                "forge" => Some(FORGE),
                "flow" => Some(FLOW),
                "nexus" => Some(NEXUS),
                "beacon" => Some(BEACON),
                "grove" => Some(GROVE),
                "crystal" => Some(CRYSTAL),
                _ => None,
            };

            if let Some(colony_idx) = idx {
                // Schedule highlight after flash completes
                // (In production, use actual async scheduling)
                ring.highlight_colony(colony_idx);
            }
        }
    });
}

/// Update LED ring color based on orb state from API
///
/// Sets the LED ring to match the canonical orb color from the server.
/// This ensures visual consistency across all Kagami devices.
///
/// # Arguments
/// * `color_hex` - Hex color string (e.g., "#FFB347")
pub fn set_orb_color(color_hex: &str) {
    // Parse hex color
    let hex = color_hex.trim_start_matches('#');
    if hex.len() != 6 {
        return;
    }

    let r = u8::from_str_radix(&hex[0..2], 16).unwrap_or(224);
    let g = u8::from_str_radix(&hex[2..4], 16).unwrap_or(224);
    let b = u8::from_str_radix(&hex[4..6], 16).unwrap_or(224);

    with_led_ring!(|ring: &mut LEDRing| {
        ring.set_all((r, g, b));
        debug!("🔮 Orb color set to {} ({}, {}, {})", color_hex, r, g, b);
    });
}

/*
 * 鏡
 * Seven lights. Seven colonies. One mirror.
 * The ring breathes with the home.
 *
 * Light bends. Color separates. Mathematics becomes visible.
 * But the user just sees: beautiful.
 */
