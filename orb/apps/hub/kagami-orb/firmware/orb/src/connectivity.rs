//! BLE and USB HID Connectivity Layer
//!
//! Dual connectivity for Kagami Orb: wireless BLE GATT and wired USB HID.
//! Provides orb control, state reporting, and OTA firmware updates.
//!
//! h(x) >= 0. Always.

use heapless::Vec;
use log::*;
use serde::{Deserialize, Serialize};

// ============================================================================
// BLE Service UUIDs (128-bit, Kagami namespace: 0x4B4147414D49xxxx)
// ============================================================================

/// Orb State Service - exposes state, battery, activity
pub const ORB_STATE_SERVICE_UUID: [u8; 16] = [
    0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x00, 0x01, 0, 0, 0, 0, 0, 0, 0, 0x01,
];

/// Orb Control Service - accepts commands (color, animation)
pub const ORB_CONTROL_SERVICE_UUID: [u8; 16] = [
    0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x00, 0x02, 0, 0, 0, 0, 0, 0, 0, 0x01,
];

/// OTA Update Service - firmware updates over BLE
pub const ORB_OTA_SERVICE_UUID: [u8; 16] = [
    0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x00, 0x03, 0, 0, 0, 0, 0, 0, 0, 0x01,
];

/// Characteristic UUIDs for BLE GATT services
pub mod characteristics {
    /// Orb state (notify): state_flags, pattern, orientation
    pub const ORB_STATE: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x01, 0x01, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
    /// Battery level (notify): 0-100%
    pub const BATTERY_LEVEL: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x01, 0x02, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
    /// LED color command (write): RGBW values
    pub const LED_COLOR: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x02, 0x01, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
    /// Animation trigger (write): pattern ID
    pub const ANIMATION: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x02, 0x02, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
    /// OTA control (write): start/abort/verify commands
    pub const OTA_CONTROL: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x03, 0x01, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
    /// OTA data (write-no-response): firmware chunks
    pub const OTA_DATA: [u8; 16] = [
        0x4B, 0x41, 0x47, 0x41, 0x4D, 0x49, 0x03, 0x02, 0, 0, 0, 0, 0, 0, 0, 0x01,
    ];
}

// ============================================================================
// Connection State Machine
// ============================================================================

/// BLE connection state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ConnectionState {
    #[default]
    Disconnected,
    Advertising,
    Connected,
    Bonded,
}

/// Security level for connections
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Default)]
pub enum SecurityLevel {
    #[default]
    None = 0,
    Encrypted = 1,
    AuthenticatedEncrypted = 2,
    SecureConnections = 3,
}

/// Connection type identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionType {
    Ble,
    UsbHid,
}

// ============================================================================
// Traits
// ============================================================================

/// BLE GATT server trait for orb communication
pub trait BluetoothLe {
    fn initialize(&mut self) -> Result<(), ConnectivityError>;
    fn start_advertising(&mut self) -> Result<(), ConnectivityError>;
    fn stop_advertising(&mut self) -> Result<(), ConnectivityError>;
    fn disconnect(&mut self) -> Result<(), ConnectivityError>;
    fn connection_state(&self) -> ConnectionState;
    fn security_level(&self) -> SecurityLevel;
    fn notify(&mut self, characteristic: &[u8; 16], data: &[u8]) -> Result<(), ConnectivityError>;
    fn request_pairing(&mut self) -> Result<(), ConnectivityError>;
    fn accept_pairing(&mut self, passkey: u32) -> Result<(), ConnectivityError>;
    fn process(&mut self);
}

/// USB HID device trait for direct connection
pub trait UsbHidDevice {
    fn initialize(&mut self) -> Result<(), ConnectivityError>;
    fn is_connected(&self) -> bool;
    fn is_authorized(&self) -> bool;
    fn request_authorization(&mut self) -> Result<(), ConnectivityError>;
    fn send_input_report(&mut self, report: &OrbInputReport) -> Result<(), ConnectivityError>;
    fn read_output_report(&mut self) -> Option<OrbOutputReport>;
    fn read_feature_report(&mut self) -> Option<OrbFeatureReport>;
    fn write_feature_report(&mut self, report: &OrbFeatureReport) -> Result<(), ConnectivityError>;
    fn process(&mut self);
}

/// Connection manager for handling multiple connection types
pub trait ConnectionManager {
    fn active_connection(&self) -> Option<ConnectionType>;
    fn is_connected(&self) -> bool;
    fn connection_count(&self) -> usize;
    fn set_priority(&mut self, conn_type: ConnectionType, priority: u8);
    fn handle_reconnection(&mut self);
}

// ============================================================================
// USB HID Reports
// ============================================================================

/// Input report: orb state, touch events, orientation (16 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[repr(C)]
pub struct OrbInputReport {
    pub report_id: u8,     // Always 1
    pub state_flags: u8,   // Bit0:levitating, Bit1:charging, Bit2:ble, Bit3:usb, Bit4:touch
    pub battery_level: u8, // 0-100
    pub led_pattern: u8,
    pub touch_event: u8, // TouchEvent enum
    pub touch_x: u8,     // 0-255 normalized
    pub touch_y: u8,
    pub pitch: i8, // -128 to 127 degrees
    pub roll: i8,
    pub yaw: u8, // 0-255 (0-360 mapped)
    pub reserved: [u8; 6],
}

impl OrbInputReport {
    pub const REPORT_ID: u8 = 1;

    pub fn new() -> Self {
        Self {
            report_id: Self::REPORT_ID,
            ..Default::default()
        }
    }

    pub fn to_bytes(&self) -> [u8; 16] {
        let mut b = [0u8; 16];
        b[0] = self.report_id;
        b[1] = self.state_flags;
        b[2] = self.battery_level;
        b[3] = self.led_pattern;
        b[4] = self.touch_event;
        b[5] = self.touch_x;
        b[6] = self.touch_y;
        b[7] = self.pitch as u8;
        b[8] = self.roll as u8;
        b[9] = self.yaw;
        b
    }

    pub fn set_levitating(&mut self, v: bool) {
        if v {
            self.state_flags |= 0x01;
        } else {
            self.state_flags &= !0x01;
        }
    }
}

/// Output report: LED commands, haptic feedback (8 bytes)
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[repr(C)]
pub struct OrbOutputReport {
    pub report_id: u8, // Always 2
    pub command: u8,   // OutputCommand enum
    pub led_r: u8,
    pub led_g: u8,
    pub led_b: u8,
    pub led_w: u8,
    pub haptic_intensity: u8, // 0-255
    pub haptic_duration: u8,  // 10ms units
}

impl OrbOutputReport {
    pub const REPORT_ID: u8 = 2;

    pub fn from_bytes(b: &[u8]) -> Option<Self> {
        if b.len() < 8 {
            return None;
        }
        Some(Self {
            report_id: b[0],
            command: b[1],
            led_r: b[2],
            led_g: b[3],
            led_b: b[4],
            led_w: b[5],
            haptic_intensity: b[6],
            haptic_duration: b[7],
        })
    }
}

/// Feature report: configuration (32 bytes)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[repr(C)]
pub struct OrbFeatureReport {
    pub report_id: u8,       // Always 3
    pub fw_version: [u8; 3], // major, minor, patch
    pub hw_revision: u8,
    pub serial: [u8; 8],
    pub config_flags: u8, // Bit0-5: auto_lev, led, touch, haptic, ble_adv, usb
    pub default_brightness: u8,
    pub default_pattern: u8,
    pub idle_timeout: u8,
    pub touch_sensitivity: u8,
    pub reserved: [u8; 13],
}

impl Default for OrbFeatureReport {
    fn default() -> Self {
        Self {
            report_id: 3,
            fw_version: [1, 0, 0],
            hw_revision: 1,
            serial: [0; 8],
            config_flags: 0b0011_1111,
            default_brightness: 128,
            default_pattern: 1,
            idle_timeout: 0,
            touch_sensitivity: 128,
            reserved: [0; 13],
        }
    }
}

impl OrbFeatureReport {
    pub const REPORT_ID: u8 = 3;

    pub fn to_bytes(&self) -> [u8; 32] {
        let mut b = [0u8; 32];
        b[0] = self.report_id;
        b[1..4].copy_from_slice(&self.fw_version);
        b[4] = self.hw_revision;
        b[5..13].copy_from_slice(&self.serial);
        b[13] = self.config_flags;
        b[14] = self.default_brightness;
        b[15] = self.default_pattern;
        b[16] = self.idle_timeout;
        b[17] = self.touch_sensitivity;
        b
    }
}

// ============================================================================
// Error Types
// ============================================================================

#[derive(Debug, Clone)]
pub enum ConnectivityError {
    BleNotInitialized,
    UsbNotInitialized,
    NotConnected,
    AlreadyConnected,
    PairingFailed(heapless::String<64>),
    AuthorizationRequired,
    InsufficientSecurity,
    WriteFailed,
    Timeout,
}

impl core::fmt::Display for ConnectivityError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Self::BleNotInitialized => write!(f, "BLE not initialized"),
            Self::UsbNotInitialized => write!(f, "USB not initialized"),
            Self::NotConnected => write!(f, "Not connected"),
            Self::AlreadyConnected => write!(f, "Already connected"),
            Self::PairingFailed(r) => write!(f, "Pairing failed: {}", r),
            Self::AuthorizationRequired => write!(f, "Authorization required"),
            Self::InsufficientSecurity => write!(f, "Insufficient security"),
            Self::WriteFailed => write!(f, "Write failed"),
            Self::Timeout => write!(f, "Timeout"),
        }
    }
}

// ============================================================================
// BLE GATT Server Implementation
// ============================================================================

/// BLE GATT server for orb services
pub struct BleGattServer {
    state: ConnectionState,
    security: SecurityLevel,
    pairing_pending: bool,
    pending_passkey: Option<u32>,
    bonded_devices: Vec<[u8; 6], 8>,
}

impl BleGattServer {
    pub fn new() -> Self {
        info!("Creating BLE GATT server");
        Self {
            state: ConnectionState::Disconnected,
            security: SecurityLevel::None,
            pairing_pending: false,
            pending_passkey: None,
            bonded_devices: Vec::new(),
        }
    }

    pub fn handle_connect(&mut self, addr: [u8; 6]) {
        info!("BLE connected: {:02X?}", addr);
        self.state = if self.bonded_devices.contains(&addr) {
            self.security = SecurityLevel::SecureConnections;
            ConnectionState::Bonded
        } else {
            self.security = SecurityLevel::None;
            ConnectionState::Connected
        };
    }

    pub fn handle_disconnect(&mut self) {
        info!("BLE disconnected");
        self.state = ConnectionState::Disconnected;
        self.security = SecurityLevel::None;
        self.pairing_pending = false;
    }

    pub fn handle_bond_complete(&mut self, addr: [u8; 6]) {
        info!("Bonding complete: {:02X?}", addr);
        if !self.bonded_devices.contains(&addr) {
            if self.bonded_devices.is_full() {
                self.bonded_devices.remove(0);
            }
            let _ = self.bonded_devices.push(addr);
        }
        self.state = ConnectionState::Bonded;
        self.security = SecurityLevel::SecureConnections;
    }
}

impl BluetoothLe for BleGattServer {
    fn initialize(&mut self) -> Result<(), ConnectivityError> {
        info!(
            "Initializing BLE GATT: State={:02X?}, Control={:02X?}, OTA={:02X?}",
            &ORB_STATE_SERVICE_UUID[..4],
            &ORB_CONTROL_SERVICE_UUID[..4],
            &ORB_OTA_SERVICE_UUID[..4]
        );
        // TODO: ESP-IDF BLE init, register services/characteristics
        Ok(())
    }

    fn start_advertising(&mut self) -> Result<(), ConnectivityError> {
        if matches!(
            self.state,
            ConnectionState::Connected | ConnectionState::Bonded
        ) {
            return Err(ConnectivityError::AlreadyConnected);
        }
        info!("Starting BLE advertising");
        self.state = ConnectionState::Advertising;
        // TODO: esp_ble_gap_start_advertising()
        Ok(())
    }

    fn stop_advertising(&mut self) -> Result<(), ConnectivityError> {
        if self.state == ConnectionState::Advertising {
            self.state = ConnectionState::Disconnected;
        }
        Ok(())
    }

    fn disconnect(&mut self) -> Result<(), ConnectivityError> {
        self.state = ConnectionState::Disconnected;
        self.security = SecurityLevel::None;
        Ok(())
    }

    fn connection_state(&self) -> ConnectionState {
        self.state
    }
    fn security_level(&self) -> SecurityLevel {
        self.security
    }

    fn notify(&mut self, char_uuid: &[u8; 16], data: &[u8]) -> Result<(), ConnectivityError> {
        if !matches!(
            self.state,
            ConnectionState::Connected | ConnectionState::Bonded
        ) {
            return Err(ConnectivityError::NotConnected);
        }
        trace!("Notify {:02X?}: {} bytes", &char_uuid[..4], data.len());
        // TODO: esp_ble_gatts_send_indicate()
        Ok(())
    }

    fn request_pairing(&mut self) -> Result<(), ConnectivityError> {
        if self.state != ConnectionState::Connected {
            return Err(ConnectivityError::NotConnected);
        }
        info!("Requesting BLE pairing with MITM protection");
        // TODO: esp_ble_set_encryption() with SC_MITM_BOND
        Ok(())
    }

    fn accept_pairing(&mut self, passkey: u32) -> Result<(), ConnectivityError> {
        if !self.pairing_pending {
            return Err(ConnectivityError::PairingFailed(
                "No pending request".into(),
            ));
        }
        if self.pending_passkey.map_or(false, |p| p != passkey) {
            self.pairing_pending = false;
            return Err(ConnectivityError::PairingFailed("Invalid passkey".into()));
        }
        info!("Accepting BLE pairing");
        self.pairing_pending = false;
        self.pending_passkey = None;
        Ok(())
    }

    fn process(&mut self) {
        // TODO: Process BLE stack events
    }
}

// ============================================================================
// USB HID Implementation
// ============================================================================

/// USB HID device for orb communication
pub struct OrbUsbHid {
    connected: bool,
    authorized: bool,
    authorization_pending: bool,
    feature_report: OrbFeatureReport,
}

impl OrbUsbHid {
    pub fn new() -> Self {
        info!("Creating Orb USB HID device");
        Self {
            connected: false,
            authorized: false,
            authorization_pending: false,
            feature_report: OrbFeatureReport::default(),
        }
    }

    /// Call when physical button pressed (grants USB authorization)
    pub fn on_button_press(&mut self) {
        if self.authorization_pending {
            info!("USB HID authorized via button press");
            self.authorized = true;
            self.authorization_pending = false;
        }
    }

    pub fn on_mount(&mut self) {
        info!("USB HID mounted");
        self.connected = true;
    }

    pub fn on_unmount(&mut self) {
        info!("USB HID unmounted");
        self.connected = false;
        self.authorized = false;
        self.authorization_pending = false;
    }
}

impl UsbHidDevice for OrbUsbHid {
    fn initialize(&mut self) -> Result<(), ConnectivityError> {
        info!("Initializing Orb USB HID");
        // TODO: TinyUSB init with vendor HID report descriptor
        Ok(())
    }

    fn is_connected(&self) -> bool {
        self.connected
    }
    fn is_authorized(&self) -> bool {
        self.authorized
    }

    fn request_authorization(&mut self) -> Result<(), ConnectivityError> {
        if !self.connected {
            return Err(ConnectivityError::NotConnected);
        }
        if self.authorized {
            return Ok(());
        }
        info!("USB authorization pending - press button to confirm");
        self.authorization_pending = true;
        Ok(())
    }

    fn send_input_report(&mut self, report: &OrbInputReport) -> Result<(), ConnectivityError> {
        if !self.connected {
            return Err(ConnectivityError::NotConnected);
        }
        if !self.authorized {
            return Err(ConnectivityError::AuthorizationRequired);
        }
        trace!("USB input report: {:02X?}", report.to_bytes());
        // TODO: tud_hid_report()
        Ok(())
    }

    fn read_output_report(&mut self) -> Option<OrbOutputReport> {
        if !self.connected || !self.authorized {
            return None;
        }
        None // TODO: Read from TinyUSB
    }

    fn read_feature_report(&mut self) -> Option<OrbFeatureReport> {
        if !self.connected {
            return None;
        }
        Some(self.feature_report.clone())
    }

    fn write_feature_report(&mut self, report: &OrbFeatureReport) -> Result<(), ConnectivityError> {
        if !self.connected {
            return Err(ConnectivityError::NotConnected);
        }
        if !self.authorized {
            return Err(ConnectivityError::AuthorizationRequired);
        }
        self.feature_report = report.clone();
        Ok(())
    }

    fn process(&mut self) {
        // TODO: Process TinyUSB events
    }
}

// ============================================================================
// Connection Manager
// ============================================================================

/// Dual connectivity manager (BLE + USB)
pub struct DualConnectionManager {
    ble: BleGattServer,
    usb: OrbUsbHid,
    ble_priority: u8,
    usb_priority: u8,
    reconnect_attempts: u8,
}

impl DualConnectionManager {
    pub fn new() -> Self {
        Self {
            ble: BleGattServer::new(),
            usb: OrbUsbHid::new(),
            ble_priority: 1,
            usb_priority: 2,
            reconnect_attempts: 0,
        }
    }

    pub fn initialize(&mut self) -> Result<(), ConnectivityError> {
        self.ble.initialize()?;
        self.usb.initialize()?;
        Ok(())
    }

    pub fn ble(&self) -> &BleGattServer {
        &self.ble
    }
    pub fn ble_mut(&mut self) -> &mut BleGattServer {
        &mut self.ble
    }
    pub fn usb(&self) -> &OrbUsbHid {
        &self.usb
    }
    pub fn usb_mut(&mut self) -> &mut OrbUsbHid {
        &mut self.usb
    }

    pub fn process(&mut self) {
        self.ble.process();
        self.usb.process();
    }

    pub fn on_button_press(&mut self) {
        self.usb.on_button_press();
    }
}

impl ConnectionManager for DualConnectionManager {
    fn active_connection(&self) -> Option<ConnectionType> {
        let ble_active = matches!(
            self.ble.state,
            ConnectionState::Connected | ConnectionState::Bonded
        );
        let usb_active = self.usb.connected && self.usb.authorized;
        match (ble_active, usb_active) {
            (true, true) => Some(if self.ble_priority < self.usb_priority {
                ConnectionType::Ble
            } else {
                ConnectionType::UsbHid
            }),
            (true, false) => Some(ConnectionType::Ble),
            (false, true) => Some(ConnectionType::UsbHid),
            (false, false) => None,
        }
    }

    fn is_connected(&self) -> bool {
        self.active_connection().is_some()
    }

    fn connection_count(&self) -> usize {
        let mut n = 0;
        if matches!(
            self.ble.state,
            ConnectionState::Connected | ConnectionState::Bonded
        ) {
            n += 1;
        }
        if self.usb.connected && self.usb.authorized {
            n += 1;
        }
        n
    }

    fn set_priority(&mut self, t: ConnectionType, p: u8) {
        match t {
            ConnectionType::Ble => self.ble_priority = p,
            ConnectionType::UsbHid => self.usb_priority = p,
        }
    }

    fn handle_reconnection(&mut self) {
        if self.ble.state == ConnectionState::Disconnected && self.reconnect_attempts < 3 {
            if self.ble.start_advertising().is_ok() {
                self.reconnect_attempts += 1;
            }
        } else if self.ble.state != ConnectionState::Disconnected {
            self.reconnect_attempts = 0;
        }
    }
}

// ============================================================================
// USB HID Report Descriptor
// ============================================================================

/// HID report descriptor for Orb device (vendor-defined)
#[allow(dead_code)]
pub const ORB_HID_REPORT_DESCRIPTOR: &[u8] = &[
    0x06, 0x00, 0xFF, // Usage Page (Vendor Defined)
    0x09, 0x01, // Usage (Vendor Usage 1)
    0xA1, 0x01, // Collection (Application)
    // Input Report (16 bytes)
    0x85, 0x01, 0x09, 0x02, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x10, 0x81, 0x02,
    // Output Report (8 bytes)
    0x85, 0x02, 0x09, 0x03, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x08, 0x91, 0x02,
    // Feature Report (32 bytes)
    0x85, 0x03, 0x09, 0x04, 0x15, 0x00, 0x26, 0xFF, 0x00, 0x75, 0x08, 0x95, 0x20, 0xB1, 0x02, 0xC0,
];

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_input_report() {
        let mut r = OrbInputReport::new();
        r.battery_level = 85;
        r.set_levitating(true);
        let b = r.to_bytes();
        assert_eq!(b[0], 1);
        assert_eq!(b[1] & 0x01, 1);
        assert_eq!(b[2], 85);
    }

    #[test]
    fn test_output_report() {
        let b = [2, 1, 255, 128, 64, 32, 200, 10];
        let r = OrbOutputReport::from_bytes(&b).unwrap();
        assert_eq!(r.led_r, 255);
        assert_eq!(r.haptic_intensity, 200);
    }

    #[test]
    fn test_connection_manager() {
        let m = DualConnectionManager::new();
        assert!(!m.is_connected());
        assert_eq!(m.connection_count(), 0);
    }
}
