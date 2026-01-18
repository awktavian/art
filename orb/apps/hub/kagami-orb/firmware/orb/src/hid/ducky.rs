//! DuckyScript Interpreter
//!
//! Executes Hak5-compatible DuckyScript payloads for automation.
//! Only a safe subset of commands is supported.
//!
//! h(x) >= 0. Always.

use super::reports::{KeyboardReport, keycode};
use ed25519_dalek::{Signature, VerifyingKey};
use heapless::Vec as HVec;
use log::*;
use serde::{Deserialize, Serialize};

/// Maximum script size (4KB)
const MAX_SCRIPT_SIZE: usize = 4096;

/// Signed DuckyScript payload
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignedPayload {
    /// Payload identifier
    pub id: heapless::String<64>,
    /// Script content
    pub script: heapless::String<MAX_SCRIPT_SIZE>,
    /// Ed25519 signature over (id || script)
    pub signature: [u8; 64],
    /// Public key of signer
    pub signer_pubkey: [u8; 32],
    /// Trust level
    pub trust_level: TrustLevel,
}

/// Trust levels for payloads
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TrustLevel {
    /// Factory-signed, always trusted
    Builtin,
    /// User's own payloads
    User,
    /// Community payloads (require explicit grant)
    Community,
    /// Unknown/untrusted (will not execute)
    Untrusted,
}

impl SignedPayload {
    /// Verify the payload signature
    pub fn verify(&self) -> bool {
        let verifying_key = match VerifyingKey::from_bytes(&self.signer_pubkey) {
            Ok(k) => k,
            Err(_) => return false,
        };

        let signature = match Signature::from_bytes(&self.signature) {
            Ok(s) => s,
            Err(_) => return false,
        };

        // Create message: id || script
        let mut message = heapless::Vec::<u8, 8192>::new();
        message.extend_from_slice(self.id.as_bytes()).ok();
        message.extend_from_slice(self.script.as_bytes()).ok();

        verifying_key.verify_strict(&message, &signature).is_ok()
    }
}

/// DuckyScript interpreter
pub struct DuckyInterpreter<'a, T: DuckyTarget> {
    target: &'a mut T,
    default_delay: u32,
}

/// Target for DuckyScript commands
pub trait DuckyTarget {
    fn send_keyboard(&mut self, report: KeyboardReport);
    fn delay_ms(&mut self, ms: u32);
    fn set_led_pattern(&mut self, pattern: u8);
}

impl<'a, T: DuckyTarget> DuckyInterpreter<'a, T> {
    pub fn new(target: &'a mut T) -> Self {
        Self {
            target,
            default_delay: 0,
        }
    }

    /// Execute a DuckyScript
    pub fn execute(&mut self, script: &str) -> anyhow::Result<()> {
        info!("Executing DuckyScript ({} bytes)", script.len());

        for line in script.lines() {
            let line = line.trim();

            // Skip empty lines and comments
            if line.is_empty() || line.starts_with("REM") {
                continue;
            }

            self.execute_line(line)?;

            // Apply default delay between commands
            if self.default_delay > 0 {
                self.target.delay_ms(self.default_delay);
            }
        }

        info!("DuckyScript execution complete");
        Ok(())
    }

    fn execute_line(&mut self, line: &str) -> anyhow::Result<()> {
        let parts: heapless::Vec<&str, 16> = line.split_whitespace().collect();
        if parts.is_empty() {
            return Ok(());
        }

        let command = parts[0].to_uppercase();
        let args: heapless::Vec<&str, 15> = parts[1..].iter().copied().collect();

        match command.as_str() {
            "DELAY" => {
                let ms: u32 = args.first()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(0);
                self.target.delay_ms(ms);
            }

            "DEFAULT_DELAY" | "DEFAULTDELAY" => {
                self.default_delay = args.first()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(0);
            }

            "STRING" => {
                let text = if args.is_empty() {
                    ""
                } else {
                    // Rejoin args with spaces
                    &line[6..].trim_start()
                };
                self.type_string(text)?;
            }

            "ENTER" | "RETURN" => self.press_key(0, keycode::KEY_ENTER),
            "TAB" => self.press_key(0, keycode::KEY_TAB),
            "ESCAPE" | "ESC" => self.press_key(0, keycode::KEY_ESCAPE),
            "BACKSPACE" => self.press_key(0, keycode::KEY_BACKSPACE),
            "DELETE" => self.press_key(0, keycode::KEY_DELETE),
            "INSERT" => self.press_key(0, keycode::KEY_INSERT),
            "HOME" => self.press_key(0, keycode::KEY_HOME),
            "END" => self.press_key(0, keycode::KEY_END),
            "PAGEUP" => self.press_key(0, keycode::KEY_PAGE_UP),
            "PAGEDOWN" => self.press_key(0, keycode::KEY_PAGE_DOWN),
            "SPACE" => self.press_key(0, keycode::KEY_SPACE),
            "CAPSLOCK" => self.press_key(0, keycode::KEY_CAPS_LOCK),
            "NUMLOCK" => self.press_key(0, keycode::KEY_NUM_LOCK),
            "SCROLLLOCK" => self.press_key(0, keycode::KEY_SCROLL_LOCK),
            "PRINTSCREEN" => self.press_key(0, keycode::KEY_PRINT_SCREEN),
            "PAUSE" | "BREAK" => self.press_key(0, keycode::KEY_PAUSE),

            // Arrow keys
            "UP" | "UPARROW" => self.press_key(0, keycode::KEY_UP_ARROW),
            "DOWN" | "DOWNARROW" => self.press_key(0, keycode::KEY_DOWN_ARROW),
            "LEFT" | "LEFTARROW" => self.press_key(0, keycode::KEY_LEFT_ARROW),
            "RIGHT" | "RIGHTARROW" => self.press_key(0, keycode::KEY_RIGHT_ARROW),

            // Function keys
            "F1" => self.press_key(0, keycode::KEY_F1),
            "F2" => self.press_key(0, keycode::KEY_F2),
            "F3" => self.press_key(0, keycode::KEY_F3),
            "F4" => self.press_key(0, keycode::KEY_F4),
            "F5" => self.press_key(0, keycode::KEY_F5),
            "F6" => self.press_key(0, keycode::KEY_F6),
            "F7" => self.press_key(0, keycode::KEY_F7),
            "F8" => self.press_key(0, keycode::KEY_F8),
            "F9" => self.press_key(0, keycode::KEY_F9),
            "F10" => self.press_key(0, keycode::KEY_F10),
            "F11" => self.press_key(0, keycode::KEY_F11),
            "F12" => self.press_key(0, keycode::KEY_F12),

            // Modifier combinations
            "GUI" | "WINDOWS" | "COMMAND" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    self.press_key(KeyboardReport::MODIFIER_LEFT_GUI, keycode);
                } else {
                    self.press_key(KeyboardReport::MODIFIER_LEFT_GUI, 0);
                }
            }

            "CTRL" | "CONTROL" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    self.press_key(KeyboardReport::MODIFIER_LEFT_CTRL, keycode);
                } else {
                    self.press_key(KeyboardReport::MODIFIER_LEFT_CTRL, 0);
                }
            }

            "ALT" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    self.press_key(KeyboardReport::MODIFIER_LEFT_ALT, keycode);
                } else {
                    self.press_key(KeyboardReport::MODIFIER_LEFT_ALT, 0);
                }
            }

            "SHIFT" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    self.press_key(KeyboardReport::MODIFIER_LEFT_SHIFT, keycode);
                } else {
                    self.press_key(KeyboardReport::MODIFIER_LEFT_SHIFT, 0);
                }
            }

            // Multi-modifier combinations
            "CTRL-ALT" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    let modifier = KeyboardReport::MODIFIER_LEFT_CTRL | KeyboardReport::MODIFIER_LEFT_ALT;
                    self.press_key(modifier, keycode);
                }
            }

            "CTRL-SHIFT" => {
                if let Some(key) = args.first() {
                    let keycode = self.char_to_keycode(key.chars().next().unwrap_or(' '));
                    let modifier = KeyboardReport::MODIFIER_LEFT_CTRL | KeyboardReport::MODIFIER_LEFT_SHIFT;
                    self.press_key(modifier, keycode);
                }
            }

            // NOT SUPPORTED (safety)
            "EXFIL" | "JITTER" | "REPEAT" => {
                warn!("Unsupported command (safety): {}", command);
            }

            _ => {
                warn!("Unknown DuckyScript command: {}", command);
            }
        }

        Ok(())
    }

    fn press_key(&mut self, modifier: u8, keycode: u8) {
        // Press
        let report = KeyboardReport::key(modifier, keycode);
        self.target.send_keyboard(report);

        // Small delay
        self.target.delay_ms(10);

        // Release
        self.target.send_keyboard(KeyboardReport::release());
        self.target.delay_ms(10);
    }

    fn type_string(&mut self, text: &str) -> anyhow::Result<()> {
        for c in text.chars() {
            let (modifier, keycode) = self.char_to_report(c);
            self.press_key(modifier, keycode);
        }
        Ok(())
    }

    fn char_to_keycode(&self, c: char) -> u8 {
        match c.to_ascii_lowercase() {
            'a' => keycode::KEY_A,
            'b' => keycode::KEY_B,
            'c' => keycode::KEY_C,
            'd' => keycode::KEY_D,
            'e' => keycode::KEY_E,
            'f' => keycode::KEY_F,
            'g' => keycode::KEY_G,
            'h' => keycode::KEY_H,
            'i' => keycode::KEY_I,
            'j' => keycode::KEY_J,
            'k' => keycode::KEY_K,
            'l' => keycode::KEY_L,
            'm' => keycode::KEY_M,
            'n' => keycode::KEY_N,
            'o' => keycode::KEY_O,
            'p' => keycode::KEY_P,
            'q' => keycode::KEY_Q,
            'r' => keycode::KEY_R,
            's' => keycode::KEY_S,
            't' => keycode::KEY_T,
            'u' => keycode::KEY_U,
            'v' => keycode::KEY_V,
            'w' => keycode::KEY_W,
            'x' => keycode::KEY_X,
            'y' => keycode::KEY_Y,
            'z' => keycode::KEY_Z,
            '1' => keycode::KEY_1,
            '2' => keycode::KEY_2,
            '3' => keycode::KEY_3,
            '4' => keycode::KEY_4,
            '5' => keycode::KEY_5,
            '6' => keycode::KEY_6,
            '7' => keycode::KEY_7,
            '8' => keycode::KEY_8,
            '9' => keycode::KEY_9,
            '0' => keycode::KEY_0,
            ' ' => keycode::KEY_SPACE,
            _ => keycode::KEY_NONE,
        }
    }

    fn char_to_report(&self, c: char) -> (u8, u8) {
        let needs_shift = c.is_ascii_uppercase() || "!@#$%^&*()_+{}|:\"<>?~".contains(c);
        let modifier = if needs_shift { KeyboardReport::MODIFIER_LEFT_SHIFT } else { 0 };

        let keycode = match c {
            'a'..='z' | 'A'..='Z' => self.char_to_keycode(c),
            '0'..='9' => self.char_to_keycode(c),
            ' ' => keycode::KEY_SPACE,
            '!' => keycode::KEY_1,
            '@' => keycode::KEY_2,
            '#' => keycode::KEY_3,
            '$' => keycode::KEY_4,
            '%' => keycode::KEY_5,
            '^' => keycode::KEY_6,
            '&' => keycode::KEY_7,
            '*' => keycode::KEY_8,
            '(' => keycode::KEY_9,
            ')' => keycode::KEY_0,
            '-' | '_' => keycode::KEY_MINUS,
            '=' | '+' => keycode::KEY_EQUAL,
            '[' | '{' => keycode::KEY_LEFT_BRACKET,
            ']' | '}' => keycode::KEY_RIGHT_BRACKET,
            '\\' | '|' => keycode::KEY_BACKSLASH,
            ';' | ':' => keycode::KEY_SEMICOLON,
            '\'' | '"' => keycode::KEY_APOSTROPHE,
            '`' | '~' => keycode::KEY_GRAVE,
            ',' | '<' => keycode::KEY_COMMA,
            '.' | '>' => keycode::KEY_PERIOD,
            '/' | '?' => keycode::KEY_SLASH,
            '\n' => keycode::KEY_ENTER,
            '\t' => keycode::KEY_TAB,
            _ => keycode::KEY_NONE,
        };

        (modifier, keycode)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct MockTarget {
        reports: std::vec::Vec<KeyboardReport>,
        delays: std::vec::Vec<u32>,
    }

    impl MockTarget {
        fn new() -> Self {
            Self {
                reports: std::vec::Vec::new(),
                delays: std::vec::Vec::new(),
            }
        }
    }

    impl DuckyTarget for MockTarget {
        fn send_keyboard(&mut self, report: KeyboardReport) {
            self.reports.push(report);
        }

        fn delay_ms(&mut self, ms: u32) {
            self.delays.push(ms);
        }

        fn set_led_pattern(&mut self, _pattern: u8) {}
    }

    #[test]
    fn test_string_typing() {
        let mut target = MockTarget::new();
        let mut interpreter = DuckyInterpreter::new(&mut target);

        interpreter.execute("STRING hello").unwrap();

        // 5 chars × 2 reports (press + release) = 10 reports
        assert_eq!(target.reports.len(), 10);
    }

    #[test]
    fn test_gui_r() {
        let mut target = MockTarget::new();
        let mut interpreter = DuckyInterpreter::new(&mut target);

        interpreter.execute("GUI r").unwrap();

        assert_eq!(target.reports.len(), 2); // press + release
        assert_eq!(target.reports[0].modifier, KeyboardReport::MODIFIER_LEFT_GUI);
    }
}
