//! LED Ring Controller
//!
//! Controls the 16× HD108 RGBW LEDs via SPI.
//! Provides patterns for status indication and HID mode feedback.

use log::*;

/// LED Ring patterns
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Pattern {
    /// All LEDs off
    Off = 0,
    /// Idle breathing animation (cyan)
    Idle = 1,
    /// HID mode active (red pulse)
    HidActive = 2,
    /// BLE pairing mode (blue blink)
    BlePairing = 3,
    /// USB connected (green solid)
    UsbConnected = 4,
    /// Error state (red blink)
    Error = 5,
    /// Processing (rainbow spin)
    Processing = 6,
    /// Voice active (white pulse)
    VoiceActive = 7,
    /// Custom color (set via set_color)
    Custom = 8,
}

impl From<u8> for Pattern {
    fn from(v: u8) -> Self {
        match v {
            0 => Pattern::Off,
            1 => Pattern::Idle,
            2 => Pattern::HidActive,
            3 => Pattern::BlePairing,
            4 => Pattern::UsbConnected,
            5 => Pattern::Error,
            6 => Pattern::Processing,
            7 => Pattern::VoiceActive,
            8 => Pattern::Custom,
            _ => Pattern::Off,
        }
    }
}

/// RGBW color value
#[derive(Debug, Clone, Copy, Default)]
pub struct RgbwColor {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub w: u8,
}

impl RgbwColor {
    pub const fn new(r: u8, g: u8, b: u8, w: u8) -> Self {
        Self { r, g, b, w }
    }

    pub const BLACK: Self = Self::new(0, 0, 0, 0);
    pub const WHITE: Self = Self::new(0, 0, 0, 255);
    pub const RED: Self = Self::new(255, 0, 0, 0);
    pub const GREEN: Self = Self::new(0, 255, 0, 0);
    pub const BLUE: Self = Self::new(0, 0, 255, 0);
    pub const CYAN: Self = Self::new(0, 255, 255, 0);
    pub const YELLOW: Self = Self::new(255, 255, 0, 0);
    pub const MAGENTA: Self = Self::new(255, 0, 255, 0);
}

/// LED Ring controller
pub struct LedRing {
    /// Current pattern
    pattern: Pattern,
    /// Global brightness (0-255)
    brightness: u8,
    /// Custom color
    custom_color: RgbwColor,
    /// Per-LED colors
    leds: [RgbwColor; 16],
    /// Animation frame counter
    frame: u32,
}

impl LedRing {
    /// Create a new LED ring controller
    pub fn new(
        _spi: impl esp_idf_hal::peripheral::Peripheral,
        _sclk: impl esp_idf_hal::peripheral::Peripheral,
        _mosi: impl esp_idf_hal::peripheral::Peripheral,
    ) -> anyhow::Result<Self> {
        info!("Initializing LED ring (16× HD108)...");

        // TODO: Initialize SPI bus for HD108
        // HD108 uses 16-bit per channel (RGBW), so 64 bits per LED
        // SPI clock should be ~10MHz

        info!("LED ring initialized");

        Ok(Self {
            pattern: Pattern::Idle,
            brightness: 128,
            custom_color: RgbwColor::CYAN,
            leds: [RgbwColor::BLACK; 16],
            frame: 0,
        })
    }

    /// Update LED ring (call at 60fps)
    pub fn update(&mut self) {
        self.frame = self.frame.wrapping_add(1);

        // Calculate LED colors based on pattern
        match self.pattern {
            Pattern::Off => {
                self.leds.fill(RgbwColor::BLACK);
            }

            Pattern::Idle => {
                // Breathing cyan
                let phase = (self.frame % 120) as f32 / 120.0;
                let intensity = ((phase * std::f32::consts::PI * 2.0).sin() * 0.5 + 0.5) * 255.0;
                let color = RgbwColor::new(0, intensity as u8, intensity as u8, 0);
                self.leds.fill(color);
            }

            Pattern::HidActive => {
                // Red pulse
                let phase = (self.frame % 30) as f32 / 30.0;
                let intensity = ((phase * std::f32::consts::PI * 2.0).sin() * 0.5 + 0.5) * 255.0;
                let color = RgbwColor::new(intensity as u8, 0, 0, 0);
                self.leds.fill(color);
            }

            Pattern::BlePairing => {
                // Blue blink
                let on = (self.frame / 30) % 2 == 0;
                let color = if on { RgbwColor::BLUE } else { RgbwColor::BLACK };
                self.leds.fill(color);
            }

            Pattern::UsbConnected => {
                // Solid green
                self.leds.fill(RgbwColor::GREEN);
            }

            Pattern::Error => {
                // Fast red blink
                let on = (self.frame / 15) % 2 == 0;
                let color = if on { RgbwColor::RED } else { RgbwColor::BLACK };
                self.leds.fill(color);
            }

            Pattern::Processing => {
                // Rainbow spin
                for i in 0..16 {
                    let hue = ((self.frame as usize + i * 16) % 256) as f32 / 256.0;
                    let color = hsv_to_rgb(hue, 1.0, 1.0);
                    self.leds[i] = color;
                }
            }

            Pattern::VoiceActive => {
                // White pulse
                let phase = (self.frame % 60) as f32 / 60.0;
                let intensity = ((phase * std::f32::consts::PI * 2.0).sin() * 0.5 + 0.5) * 255.0;
                let color = RgbwColor::new(0, 0, 0, intensity as u8);
                self.leds.fill(color);
            }

            Pattern::Custom => {
                self.leds.fill(self.custom_color);
            }
        }

        // Apply global brightness
        for led in &mut self.leds {
            led.r = ((led.r as u16 * self.brightness as u16) / 255) as u8;
            led.g = ((led.g as u16 * self.brightness as u16) / 255) as u8;
            led.b = ((led.b as u16 * self.brightness as u16) / 255) as u8;
            led.w = ((led.w as u16 * self.brightness as u16) / 255) as u8;
        }

        // TODO: Write to SPI
        self.write_to_spi();
    }

    fn write_to_spi(&self) {
        // HD108 protocol:
        // Start frame: 32 bits of 0
        // LED frames: 16 bits brightness + 16 bits R + 16 bits G + 16 bits B
        // End frame: (n/2 + 1) bits of 1
        //
        // For RGBW, we send R, G, B, W as 4 separate 16-bit values

        // TODO: Actual SPI write
    }

    /// Set the current pattern
    pub fn set_pattern(&mut self, pattern: Pattern) {
        self.pattern = pattern;
        self.frame = 0; // Reset animation
        info!("LED pattern set to {:?}", pattern);
    }

    /// Get the current pattern
    pub fn current_pattern(&self) -> Pattern {
        self.pattern
    }

    /// Set global brightness
    pub fn set_brightness(&mut self, level: u8) {
        self.brightness = level;
        info!("LED brightness set to {}", level);
    }

    /// Get current brightness
    pub fn brightness(&self) -> u8 {
        self.brightness
    }

    /// Set custom color
    pub fn set_color(&mut self, r: u8, g: u8, b: u8, w: u8) {
        self.custom_color = RgbwColor::new(r, g, b, w);
        self.pattern = Pattern::Custom;
        info!("LED color set to ({}, {}, {}, {})", r, g, b, w);
    }

    /// Set individual LED color
    pub fn set_led(&mut self, index: usize, color: RgbwColor) {
        if index < 16 {
            self.leds[index] = color;
        }
    }
}

/// Convert HSV to RGBW
fn hsv_to_rgb(h: f32, s: f32, v: f32) -> RgbwColor {
    let c = v * s;
    let x = c * (1.0 - ((h * 6.0) % 2.0 - 1.0).abs());
    let m = v - c;

    let (r, g, b) = if h < 1.0 / 6.0 {
        (c, x, 0.0)
    } else if h < 2.0 / 6.0 {
        (x, c, 0.0)
    } else if h < 3.0 / 6.0 {
        (0.0, c, x)
    } else if h < 4.0 / 6.0 {
        (0.0, x, c)
    } else if h < 5.0 / 6.0 {
        (x, 0.0, c)
    } else {
        (c, 0.0, x)
    };

    RgbwColor::new(
        ((r + m) * 255.0) as u8,
        ((g + m) * 255.0) as u8,
        ((b + m) * 255.0) as u8,
        0,
    )
}
