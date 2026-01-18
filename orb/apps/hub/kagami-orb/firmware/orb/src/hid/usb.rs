//! USB HID Implementation (Docked Mode)
//!
//! Provides wired USB HID when the Orb is docked on the base station.
//! Uses the ESP32-S3's USB-OTG peripheral.
//!
//! h(x) >= 0. Always.

use super::{HidReport, KeyboardReport, MouseReport, ConsumerReport, GamepadReport};
use super::rate_limiter::RateLimiter;
use log::*;

/// USB HID Device
pub struct UsbHid {
    connected: bool,
    rate_limiter: RateLimiter,
}

impl UsbHid {
    /// Initialize USB HID
    pub fn new(_usb: esp_idf_hal::peripheral::Peripheral<impl esp_idf_hal::peripheral::Peripheral>) -> anyhow::Result<Self> {
        info!("Initializing USB HID...");

        // TODO: Initialize ESP-IDF TinyUSB stack
        // 1. tinyusb_driver_install()
        // 2. Configure HID device descriptors
        // 3. Register callbacks

        info!("USB HID initialized");

        Ok(Self {
            connected: false,
            rate_limiter: RateLimiter::new(50, 125, 10),
        })
    }

    /// Check if USB is connected
    pub fn is_connected(&self) -> bool {
        self.connected
    }

    /// Process pending USB events
    pub fn process(&mut self) {
        // TODO: Process TinyUSB events
        // - Connection events
        // - Suspend/Resume events
        // - SET_REPORT requests
    }

    /// Send an HID report over USB
    pub fn send_report(&mut self, report: &HidReport) {
        if !self.connected {
            return;
        }

        let report_type = match report {
            HidReport::Keyboard(_) => "keyboard",
            HidReport::Mouse(_) => "mouse",
            HidReport::Consumer(_) => "consumer",
            HidReport::Gamepad(_) => "gamepad",
        };

        if !self.rate_limiter.allow(report_type) {
            warn!("USB HID report rate limited: {}", report_type);
            return;
        }

        match report {
            HidReport::Keyboard(kb) => self.send_keyboard_report(kb),
            HidReport::Mouse(mouse) => self.send_mouse_report(mouse),
            HidReport::Consumer(consumer) => self.send_consumer_report(consumer),
            HidReport::Gamepad(gamepad) => self.send_gamepad_report(gamepad),
        }
    }

    fn send_keyboard_report(&self, report: &KeyboardReport) {
        let bytes = report.to_bytes();
        trace!("USB keyboard report: {:02X?}", bytes);
        // TODO: tud_hid_keyboard_report()
    }

    fn send_mouse_report(&self, report: &MouseReport) {
        let bytes = report.to_bytes();
        trace!("USB mouse report: {:02X?}", bytes);
        // TODO: tud_hid_mouse_report()
    }

    fn send_consumer_report(&self, report: &ConsumerReport) {
        let bytes = report.to_bytes();
        trace!("USB consumer report: {:02X?}", bytes);
        // TODO: tud_hid_report() with consumer report ID
    }

    fn send_gamepad_report(&self, report: &GamepadReport) {
        let bytes = report.to_bytes();
        trace!("USB gamepad report: {:02X?}", bytes);
        // TODO: tud_hid_report() with gamepad report ID
    }

    /// Handle USB mount event
    fn on_mount(&mut self) {
        info!("USB HID mounted");
        self.connected = true;
        // TODO: Set LED ring to green solid
    }

    /// Handle USB unmount event
    fn on_unmount(&mut self) {
        info!("USB HID unmounted");
        self.connected = false;
    }
}

/// USB Device Descriptor
#[allow(dead_code)]
const USB_DEVICE_DESCRIPTOR: &[u8] = &[
    18,         // bLength
    1,          // bDescriptorType (Device)
    0x00, 0x02, // bcdUSB 2.0
    0,          // bDeviceClass (Use class from Interface)
    0,          // bDeviceSubClass
    0,          // bDeviceProtocol
    64,         // bMaxPacketSize0
    0x6D, 0x04, // idVendor (Kagami)
    0x01, 0x00, // idProduct (Orb HID)
    0x00, 0x01, // bcdDevice 1.0
    1,          // iManufacturer
    2,          // iProduct
    3,          // iSerialNumber
    1,          // bNumConfigurations
];

/// USB String Descriptors
#[allow(dead_code)]
mod strings {
    pub const MANUFACTURER: &str = "Kagami";
    pub const PRODUCT: &str = "Kagami Orb HID";
    pub const SERIAL: &str = "ORB-001";
}
