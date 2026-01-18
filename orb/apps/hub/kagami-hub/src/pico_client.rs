//! 鏡 Pico Coprocessor Client — UART Communication
//!
//! Client for communicating with the Kagami Pico coprocessor over UART.
//! The Pico handles real-time tasks (LED ring, audio I2S) that Linux
//! cannot perform deterministically.
//!
//! ## Usage
//!
//! ```rust,no_run
//! use kagami_hub::pico_client::PicoClient;
//!
//! async fn example() {
//!     let client = PicoClient::new("/dev/ttyACM0").await.unwrap();
//!
//!     // Set LED pattern
//!     client.set_pattern(Pattern::Breathing).await.unwrap();
//!
//!     // Set brightness
//!     client.set_brightness(200).await.unwrap();
//!
//!     // Ping for heartbeat
//!     let pong = client.ping().await.unwrap();
//!     assert!(pong);
//! }
//! ```
//!
//! Colony: Nexus (e₄) — Bridge between Pi and Pico
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use tracing::{debug, warn};

#[cfg(feature = "pico")]
use std::time::Duration;
#[cfg(feature = "pico")]
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
#[cfg(feature = "pico")]
use tokio::sync::Mutex;
#[cfg(feature = "pico")]
use tracing::info;
#[cfg(feature = "pico")]
use tokio_serial::{SerialPortBuilderExt, SerialStream};

/// LED animation patterns (must match Pico firmware)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Pattern {
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

impl From<Pattern> for u8 {
    fn from(p: Pattern) -> u8 {
        p as u8
    }
}

/// Pico status response
#[derive(Debug, Clone)]
pub struct PicoStatus {
    pub pattern: u8,
    pub brightness: u8,
    pub frame_count: u32,
}

/// Events from the Pico
#[derive(Debug, Clone)]
pub enum PicoEvent {
    /// Button was pressed
    ButtonPressed,
    /// Error occurred
    Error { code: u8 },
}

/// Pico coprocessor client
#[cfg(feature = "pico")]
pub struct PicoClient {
    /// Serial port
    port: Mutex<SerialStream>,
    /// Port path for reconnection
    port_path: String,
}

#[cfg(feature = "pico")]
impl PicoClient {
    /// Create a new Pico client
    pub async fn new(port_path: &str) -> anyhow::Result<Self> {
        info!("Connecting to Pico at {}", port_path);

        let port = tokio_serial::new(port_path, 115200)
            .timeout(Duration::from_millis(100))
            .open_native_async()?;

        info!("✓ Connected to Pico coprocessor");

        Ok(Self {
            port: Mutex::new(port),
            port_path: port_path.to_string(),
        })
    }

    /// Set LED animation pattern
    pub async fn set_pattern(&self, pattern: Pattern) -> anyhow::Result<()> {
        let cmd = format!("PAT:{}\n", pattern as u8);
        self.send_command(&cmd).await
    }

    /// Set LED brightness (0-255)
    pub async fn set_brightness(&self, level: u8) -> anyhow::Result<()> {
        let cmd = format!("BRT:{}\n", level);
        self.send_command(&cmd).await
    }

    /// Set LED color override
    pub async fn set_color(&self, r: u8, g: u8, b: u8) -> anyhow::Result<()> {
        let cmd = format!("COL:{},{},{}\n", r, g, b);
        self.send_command(&cmd).await
    }

    /// Ping the Pico (heartbeat check)
    pub async fn ping(&self) -> anyhow::Result<bool> {
        self.send_command("PNG\n").await?;

        // Wait for response
        let response = self.read_response().await?;
        Ok(response.starts_with("PON"))
    }

    /// Get Pico status
    pub async fn get_status(&self) -> anyhow::Result<PicoStatus> {
        self.send_command("STS\n").await?;

        let response = self.read_response().await?;
        if response.starts_with("STS:") {
            let parts: Vec<&str> = response[4..].split(',').collect();
            if parts.len() >= 3 {
                return Ok(PicoStatus {
                    pattern: parts[0].parse().unwrap_or(0),
                    brightness: parts[1].parse().unwrap_or(128),
                    frame_count: parts[2].parse().unwrap_or(0),
                });
            }
        }

        Err(anyhow::anyhow!("Invalid status response: {}", response))
    }

    /// Send a raw command
    async fn send_command(&self, cmd: &str) -> anyhow::Result<()> {
        let mut port = self.port.lock().await;
        port.write_all(cmd.as_bytes()).await?;
        port.flush().await?;
        debug!("Sent to Pico: {:?}", cmd.trim());
        Ok(())
    }

    /// Read a response line
    async fn read_response(&self) -> anyhow::Result<String> {
        let mut port = self.port.lock().await;
        let mut reader = BufReader::new(&mut *port);
        let mut line = String::new();

        // Read with timeout
        tokio::time::timeout(
            Duration::from_millis(500),
            reader.read_line(&mut line)
        ).await??;

        let response = line.trim().to_string();
        debug!("Received from Pico: {:?}", response);
        Ok(response)
    }

    /// Poll for events from the Pico
    pub async fn poll_events(&self) -> Option<PicoEvent> {
        match self.read_response().await {
            Ok(response) => {
                if response.starts_with("BTN") {
                    Some(PicoEvent::ButtonPressed)
                } else if response.starts_with("ERR:") {
                    let code: u8 = response[4..].parse().unwrap_or(0);
                    Some(PicoEvent::Error { code })
                } else {
                    None
                }
            }
            Err(_) => None,
        }
    }

    // ========================================================================
    // Convenience Methods for LED Ring
    // ========================================================================

    /// Show idle pattern (colony colors)
    pub async fn show_idle(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Idle).await
    }

    /// Show listening pattern (pulsing)
    pub async fn show_listening(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Pulse).await
    }

    /// Show processing pattern (spinning)
    pub async fn show_processing(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Spin).await
    }

    /// Show executing pattern (cascade)
    pub async fn show_executing(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Cascade).await
    }

    /// Show success pattern (green flash)
    pub async fn show_success(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Flash).await
    }

    /// Show error pattern (red flash)
    pub async fn show_error(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::ErrorFlash).await
    }

    /// Show safety status
    pub async fn show_safety(&self, h_x: f64) -> anyhow::Result<()> {
        let pattern = if h_x >= 0.5 {
            Pattern::SafetySafe
        } else if h_x >= 0.0 {
            Pattern::SafetyCaution
        } else {
            Pattern::SafetyViolation
        };
        self.set_pattern(pattern).await
    }

    /// Show breathing pattern (ambient)
    pub async fn show_breathing(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::Breathing).await
    }

    /// Show spectral sweep (prismorphism)
    pub async fn show_spectral(&self) -> anyhow::Result<()> {
        self.set_pattern(Pattern::SpectralSweep).await
    }
}

// ============================================================================
// Stub Implementation (when pico feature is disabled)
// ============================================================================

#[cfg(not(feature = "pico"))]
pub struct PicoClient;

#[cfg(not(feature = "pico"))]
impl PicoClient {
    pub async fn new(_port_path: &str) -> anyhow::Result<Self> {
        warn!("Pico feature not enabled - using stub client");
        Ok(Self)
    }

    pub async fn set_pattern(&self, _pattern: Pattern) -> anyhow::Result<()> {
        debug!("Stub: set_pattern");
        Ok(())
    }

    pub async fn set_brightness(&self, _level: u8) -> anyhow::Result<()> {
        debug!("Stub: set_brightness");
        Ok(())
    }

    pub async fn set_color(&self, _r: u8, _g: u8, _b: u8) -> anyhow::Result<()> {
        debug!("Stub: set_color");
        Ok(())
    }

    pub async fn ping(&self) -> anyhow::Result<bool> {
        debug!("Stub: ping");
        Ok(true)
    }

    pub async fn get_status(&self) -> anyhow::Result<PicoStatus> {
        debug!("Stub: get_status");
        Ok(PicoStatus {
            pattern: 1,
            brightness: 128,
            frame_count: 0,
        })
    }

    pub async fn show_idle(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_listening(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_processing(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_executing(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_success(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_error(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_safety(&self, _h_x: f64) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_breathing(&self) -> anyhow::Result<()> { Ok(()) }
    pub async fn show_spectral(&self) -> anyhow::Result<()> { Ok(()) }
}

// ============================================================================
// Auto-discovery
// ============================================================================

/// Find connected Pico devices
#[cfg(feature = "pico")]
pub fn find_pico_ports() -> Vec<String> {
    let mut pico_ports = Vec::new();

    if let Ok(ports) = serialport::available_ports() {
        for port in ports {
            // Check for Pico USB identifiers
            let is_pico = port.port_name.contains("ACM") ||
                         port.port_name.contains("usbmodem") ||
                         port.port_name.contains("ttyUSB");

            if is_pico {
                info!("Found potential Pico at: {}", port.port_name);
                pico_ports.push(port.port_name);
            }
        }
    }

    pico_ports
}

#[cfg(not(feature = "pico"))]
pub fn find_pico_ports() -> Vec<String> {
    Vec::new()
}

/*
 * 鏡
 * The bridge between realms.
 * Pi thinks. Pico acts. Together, they are one.
 *
 * h(x) ≥ 0. Always.
 */
