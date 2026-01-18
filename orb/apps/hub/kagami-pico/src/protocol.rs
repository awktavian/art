//! 鏡 Kagami Pico Protocol — Pi <-> Pico Communication
//!
//! Simple line-based ASCII protocol over UART for communication
//! between the Raspberry Pi (Kagami Hub) and the Pico coprocessor.
//!
//! Protocol Format:
//! - Commands: `CMD:arg1,arg2,...\n`
//! - Responses: `RSP:data\n`
//!
//! ## Commands (Pi -> Pico)
//!
//! | Command | Args | Description |
//! |---------|------|-------------|
//! | `PAT` | pattern_id | Set LED animation pattern (0-15) |
//! | `BRT` | level | Set brightness (0-255) |
//! | `COL` | r,g,b | Set override color |
//! | `PNG` | - | Ping (heartbeat) |
//! | `STS` | - | Request status |
//!
//! ## Responses (Pico -> Pi)
//!
//! | Response | Data | Description |
//! |----------|------|-------------|
//! | `PON` | - | Pong (heartbeat response) |
//! | `STS` | pattern,brightness,frames | Status response |
//! | `BTN` | - | Button pressed event |
//! | `ERR` | code | Error occurred |
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use defmt::*;
use heapless::String;

// ============================================================================
// Commands (Pi -> Pico)
// ============================================================================

/// Commands the Pi can send to the Pico
#[derive(Debug, Clone)]
pub enum Command {
    /// Set LED animation pattern
    SetPattern { pattern: u8 },

    /// Set LED brightness (0-255)
    SetBrightness { level: u8 },

    /// Set override color (RGB)
    SetColor { r: u8, g: u8, b: u8 },

    /// Ping for heartbeat
    Ping,

    /// Request status
    GetStatus,
}

/// Parse a command from a byte slice
pub fn parse_command(data: &[u8]) -> Option<Command> {
    // Convert to string, trim whitespace
    let s = core::str::from_utf8(data).ok()?;
    let s = s.trim();

    // Split on ':'
    let mut parts = s.splitn(2, ':');
    let cmd = parts.next()?;
    let args = parts.next().unwrap_or("");

    match cmd {
        "PAT" => {
            let pattern: u8 = args.trim().parse().ok()?;
            Some(Command::SetPattern { pattern })
        }
        "BRT" => {
            let level: u8 = args.trim().parse().ok()?;
            Some(Command::SetBrightness { level })
        }
        "COL" => {
            let mut rgb = args.split(',');
            let r: u8 = rgb.next()?.trim().parse().ok()?;
            let g: u8 = rgb.next()?.trim().parse().ok()?;
            let b: u8 = rgb.next()?.trim().parse().ok()?;
            Some(Command::SetColor { r, g, b })
        }
        "PNG" => Some(Command::Ping),
        "STS" => Some(Command::GetStatus),
        _ => {
            warn!("Unknown command: {}", cmd);
            None
        }
    }
}

// ============================================================================
// Responses (Pico -> Pi)
// ============================================================================

/// Responses the Pico can send to the Pi
#[derive(Debug, Clone)]
pub enum Response {
    /// Pong (heartbeat response)
    Pong,

    /// Status response
    Status {
        pattern: u8,
        brightness: u8,
        frame_count: u32,
    },

    /// Button pressed event
    ButtonPressed,

    /// Error occurred
    Error { code: u8 },
}

/// Encode a response to a string
pub fn encode_response(response: &Response) -> String<64> {
    let mut s: String<64> = String::new();

    match response {
        Response::Pong => {
            let _ = s.push_str("PON");
        }
        Response::Status { pattern, brightness, frame_count } => {
            // Format: STS:pattern,brightness,frames
            let _ = s.push_str("STS:");
            let _ = write_u8(&mut s, *pattern);
            let _ = s.push(',');
            let _ = write_u8(&mut s, *brightness);
            let _ = s.push(',');
            let _ = write_u32(&mut s, *frame_count);
        }
        Response::ButtonPressed => {
            let _ = s.push_str("BTN");
        }
        Response::Error { code } => {
            let _ = s.push_str("ERR:");
            let _ = write_u8(&mut s, *code);
        }
    }

    s
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Write a u8 to a heapless String
fn write_u8(s: &mut String<64>, n: u8) {
    let mut buf = [0u8; 3];
    let len = format_u8(n, &mut buf);
    for i in 0..len {
        let _ = s.push(buf[i] as char);
    }
}

/// Write a u32 to a heapless String
fn write_u32(s: &mut String<64>, n: u32) {
    let mut buf = [0u8; 10];
    let len = format_u32(n, &mut buf);
    for i in 0..len {
        let _ = s.push(buf[i] as char);
    }
}

/// Format u8 to decimal ASCII
fn format_u8(mut n: u8, buf: &mut [u8; 3]) -> usize {
    if n == 0 {
        buf[0] = b'0';
        return 1;
    }

    let mut pos = 0;
    let mut temp = [0u8; 3];
    while n > 0 {
        temp[pos] = b'0' + (n % 10) as u8;
        n /= 10;
        pos += 1;
    }

    // Reverse
    for i in 0..pos {
        buf[i] = temp[pos - 1 - i];
    }
    pos
}

/// Format u32 to decimal ASCII
fn format_u32(mut n: u32, buf: &mut [u8; 10]) -> usize {
    if n == 0 {
        buf[0] = b'0';
        return 1;
    }

    let mut pos = 0;
    let mut temp = [0u8; 10];
    while n > 0 {
        temp[pos] = b'0' + (n % 10) as u8;
        n /= 10;
        pos += 1;
    }

    // Reverse
    for i in 0..pos {
        buf[i] = temp[pos - 1 - i];
    }
    pos
}

// ============================================================================
// Pattern IDs
// ============================================================================

/// Animation pattern IDs (must match led_ring.rs)
pub mod patterns {
    pub const IDLE: u8 = 0;
    pub const BREATHING: u8 = 1;
    pub const SPIN: u8 = 2;
    pub const PULSE: u8 = 3;
    pub const CASCADE: u8 = 4;
    pub const FLASH: u8 = 5;
    pub const ERROR_FLASH: u8 = 6;
    pub const RAINBOW: u8 = 7;
    pub const SPECTRAL: u8 = 8;
    pub const FANO_PULSE: u8 = 9;
    pub const SPECTRAL_SWEEP: u8 = 10;
    pub const CHROMATIC_SUCCESS: u8 = 11;
    pub const CHROMATIC_ERROR: u8 = 12;
    pub const SAFETY_SAFE: u8 = 13;
    pub const SAFETY_CAUTION: u8 = 14;
    pub const SAFETY_VIOLATION: u8 = 15;
}

/*
 * 鏡
 * Simple protocol. Fast parsing. No allocations.
 */
