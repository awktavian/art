//! Kagami Orb ESP32-S3 Co-processor Firmware
//!
//! Provides real-time control of:
//! - LED Ring (16× HD108 RGBW via SPI)
//! - Bluetooth HID (keyboard, mouse, gamepad)
//! - USB HID (docked mode)
//! - Sensor polling (IMU, Hall sensor)
//!
//! Communicates with QCS6490 main processor via UART.
//!
//! h(x) >= 0. Always.

use esp_idf_hal::prelude::*;
use esp_idf_svc::log::EspLogger;
use log::*;

mod connectivity;
mod hid;
mod led;
mod plugin;
mod protocol;
mod safety;

use hid::{BleHid, UsbHid, HidReport};
use led::LedRing;
use plugin::PluginManager;
use protocol::{Command, Response};
use safety::SafetyMonitor;

/// Global firmware state
struct OrbFirmware {
    led_ring: LedRing,
    ble_hid: Option<BleHid>,
    usb_hid: Option<UsbHid>,
    plugin_manager: PluginManager,
    safety: SafetyMonitor,
}

fn main() -> anyhow::Result<()> {
    // Initialize ESP-IDF
    esp_idf_sys::link_patches();
    EspLogger::initialize_default();

    info!("Kagami Orb ESP32-S3 Firmware v1.0.0");
    info!("h(x) >= 0. Always.");

    // Initialize peripherals
    let peripherals = Peripherals::take()?;

    // Initialize LED ring (SPI to HD108)
    let led_ring = LedRing::new(
        peripherals.spi2,
        peripherals.pins.gpio18, // SCLK
        peripherals.pins.gpio23, // MOSI
    )?;

    // Initialize Bluetooth HID
    #[cfg(feature = "ble_hid")]
    let ble_hid = Some(BleHid::new()?);
    #[cfg(not(feature = "ble_hid"))]
    let ble_hid = None;

    // Initialize USB HID (docked mode only)
    #[cfg(feature = "usb_hid")]
    let usb_hid = Some(UsbHid::new(peripherals.usb)?);
    #[cfg(not(feature = "usb_hid"))]
    let usb_hid = None;

    // Initialize plugin manager
    #[cfg(feature = "plugin_system")]
    let plugin_manager = PluginManager::new()?;
    #[cfg(not(feature = "plugin_system"))]
    let plugin_manager = PluginManager::stub();

    // Initialize safety monitor
    let safety = SafetyMonitor::new();

    let mut firmware = OrbFirmware {
        led_ring,
        ble_hid,
        usb_hid,
        plugin_manager,
        safety,
    };

    info!("All subsystems initialized");

    // Main loop
    loop {
        // Check for UART commands from QCS6490
        if let Some(cmd) = protocol::receive_command() {
            let response = firmware.handle_command(cmd);
            protocol::send_response(response);
        }

        // Update LED ring animation (60fps)
        firmware.led_ring.update();

        // Process HID reports
        if let Some(ref mut ble) = firmware.ble_hid {
            ble.process();
        }
        if let Some(ref mut usb) = firmware.usb_hid {
            usb.process();
        }

        // Check safety constraints
        firmware.safety.check();

        // Yield to other tasks
        esp_idf_hal::delay::FreeRtos::delay_ms(1);
    }
}

impl OrbFirmware {
    fn handle_command(&mut self, cmd: Command) -> Response {
        match cmd {
            // LED Commands
            Command::SetLedPattern { pattern } => {
                self.led_ring.set_pattern(pattern);
                Response::Ok
            }
            Command::SetLedBrightness { level } => {
                self.led_ring.set_brightness(level);
                Response::Ok
            }
            Command::SetLedColor { r, g, b, w } => {
                self.led_ring.set_color(r, g, b, w);
                Response::Ok
            }

            // HID Commands
            Command::HidKeyboard { report } => {
                if !self.safety.allow_hid() {
                    return Response::Error("HID disabled by safety".into());
                }
                self.send_hid_report(HidReport::Keyboard(report));
                Response::Ok
            }
            Command::HidMouse { report } => {
                if !self.safety.allow_hid() {
                    return Response::Error("HID disabled by safety".into());
                }
                self.send_hid_report(HidReport::Mouse(report));
                Response::Ok
            }
            Command::HidConsumer { report } => {
                if !self.safety.allow_hid() {
                    return Response::Error("HID disabled by safety".into());
                }
                self.send_hid_report(HidReport::Consumer(report));
                Response::Ok
            }

            // DuckyScript Commands
            #[cfg(feature = "duckyscript")]
            Command::ExecutePayload { payload_id } => {
                if !self.safety.allow_payload_execution() {
                    return Response::Error("Payload execution disabled".into());
                }
                match self.execute_payload(&payload_id) {
                    Ok(()) => Response::Ok,
                    Err(e) => Response::Error(e.to_string()),
                }
            }

            // Plugin Commands
            #[cfg(feature = "plugin_system")]
            Command::LoadPlugin { manifest } => {
                match self.plugin_manager.load(manifest) {
                    Ok(id) => Response::PluginLoaded { id },
                    Err(e) => Response::Error(e.to_string()),
                }
            }
            #[cfg(feature = "plugin_system")]
            Command::UnloadPlugin { id } => {
                self.plugin_manager.unload(id);
                Response::Ok
            }

            // Status Commands
            Command::GetStatus => Response::Status {
                led_pattern: self.led_ring.current_pattern(),
                led_brightness: self.led_ring.brightness(),
                hid_connected: self.is_hid_connected(),
                safety_ok: self.safety.is_ok(),
            },
            Command::Ping => Response::Pong,

            _ => Response::Error("Unknown command".into()),
        }
    }

    fn send_hid_report(&mut self, report: HidReport) {
        // Try BLE first, then USB
        if let Some(ref mut ble) = self.ble_hid {
            if ble.is_connected() {
                ble.send_report(&report);
                return;
            }
        }
        if let Some(ref mut usb) = self.usb_hid {
            if usb.is_connected() {
                usb.send_report(&report);
            }
        }
    }

    fn is_hid_connected(&self) -> bool {
        let ble_connected = self.ble_hid.as_ref().map(|b| b.is_connected()).unwrap_or(false);
        let usb_connected = self.usb_hid.as_ref().map(|u| u.is_connected()).unwrap_or(false);
        ble_connected || usb_connected
    }

    #[cfg(feature = "duckyscript")]
    fn execute_payload(&mut self, payload_id: &str) -> anyhow::Result<()> {
        use crate::hid::ducky::DuckyInterpreter;

        let payload = self.load_payload(payload_id)?;

        // Verify signature
        if !self.safety.verify_payload_signature(&payload) {
            anyhow::bail!("Payload signature verification failed");
        }

        // Set HID mode indicator (red LED pulse)
        self.led_ring.set_pattern(led::Pattern::HidActive);

        // Execute
        let interpreter = DuckyInterpreter::new(&mut *self);
        interpreter.execute(&payload.script)?;

        // Clear HID mode indicator
        self.led_ring.set_pattern(led::Pattern::Idle);

        Ok(())
    }

    #[cfg(feature = "duckyscript")]
    fn load_payload(&self, payload_id: &str) -> anyhow::Result<hid::ducky::SignedPayload> {
        // Load from filesystem
        // Payloads stored in /kagami/payloads/{builtin,user,community}/
        todo!("Load payload from filesystem")
    }
}

/*
 * Kagami Orb Co-processor
 *
 * The ESP32-S3 handles real-time tasks that the QCS6490 cannot:
 * - LED animation at 60fps
 * - Bluetooth HID with low latency
 * - USB HID when docked
 * - Sensor polling
 *
 * h(x) >= 0. Always.
 */
