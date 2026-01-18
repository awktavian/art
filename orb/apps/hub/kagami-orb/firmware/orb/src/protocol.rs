//! UART Protocol for QCS6490 Communication
//!
//! Defines the command/response protocol between the ESP32-S3 co-processor
//! and the QCS6490 main processor.

use super::hid::{KeyboardReport, MouseReport, ConsumerReport, GamepadReport};
use super::led::Pattern;
use super::plugin::manifest::PluginManifest;
use heapless::String;
use serde::{Deserialize, Serialize};

/// Commands from QCS6490 to ESP32-S3
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Command {
    // LED Commands
    SetLedPattern { pattern: Pattern },
    SetLedBrightness { level: u8 },
    SetLedColor { r: u8, g: u8, b: u8, w: u8 },

    // HID Commands
    HidKeyboard { report: KeyboardReport },
    HidMouse { report: MouseReport },
    HidConsumer { report: ConsumerReport },
    HidGamepad { report: GamepadReport },

    // DuckyScript Commands
    #[cfg(feature = "duckyscript")]
    ExecutePayload { payload_id: String<64> },

    // Plugin Commands
    #[cfg(feature = "plugin_system")]
    LoadPlugin { manifest: PluginManifest },
    #[cfg(feature = "plugin_system")]
    UnloadPlugin { id: u32 },
    #[cfg(feature = "plugin_system")]
    ExecutePlugin { id: u32, command: String<64>, args: heapless::Vec<u8, 256> },

    // Status Commands
    GetStatus,
    Ping,
}

/// Responses from ESP32-S3 to QCS6490
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Response {
    Ok,
    Error(String<128>),

    Status {
        led_pattern: Pattern,
        led_brightness: u8,
        hid_connected: bool,
        safety_ok: bool,
    },

    Pong,

    #[cfg(feature = "plugin_system")]
    PluginLoaded { id: u32 },

    #[cfg(feature = "plugin_system")]
    PluginResult { data: heapless::Vec<u8, 1024> },
}

/// Receive a command from UART (non-blocking)
pub fn receive_command() -> Option<Command> {
    // TODO: Read from UART buffer
    // Protocol: JSON-encoded Command terminated by newline
    None
}

/// Send a response over UART
pub fn send_response(_response: Response) {
    // TODO: Write to UART
    // Protocol: JSON-encoded Response terminated by newline
}

/// Parse a command from bytes
pub fn parse_command(data: &[u8]) -> Option<Command> {
    let json = core::str::from_utf8(data).ok()?;
    serde_json::from_str(json).ok()
}

/// Serialize a response to bytes
pub fn serialize_response(response: &Response) -> heapless::Vec<u8, 512> {
    let mut buf = heapless::Vec::new();
    if let Ok(json) = serde_json::to_string(response) {
        buf.extend_from_slice(json.as_bytes()).ok();
    }
    buf
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_serialization() {
        let cmd = Command::SetLedBrightness { level: 128 };
        let json = serde_json::to_string(&cmd).unwrap();
        assert!(json.contains("128"));
    }

    #[test]
    fn test_response_serialization() {
        let response = Response::Status {
            led_pattern: Pattern::Idle,
            led_brightness: 128,
            hid_connected: true,
            safety_ok: true,
        };
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("hid_connected"));
    }
}
