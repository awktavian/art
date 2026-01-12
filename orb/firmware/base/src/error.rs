//! Error types for the base station firmware.

use core::fmt;

/// Base station error types
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BaseError {
    // Levitation errors
    /// Height out of valid range (5-25mm)
    HeightOutOfRange,
    /// Invalid bobble amplitude
    InvalidAmplitude,
    /// Invalid bobble frequency
    InvalidFrequency,
    /// Levitation unstable
    LevitationUnstable,
    /// Emergency landing triggered
    EmergencyLanding,

    // Hardware errors
    /// DAC communication failed
    DacError,
    /// ADC read failed
    AdcError,
    /// I2C bus error
    I2cError,
    /// Hall sensor fault
    HallSensorFault,

    // WPT errors
    /// Wireless power transfer fault
    WptFault,
    /// Foreign object detected
    ForeignObjectDetected,
    /// Coil overtemperature
    CoilOvertemperature,

    // Safety errors
    /// Control barrier function violation
    SafetyViolation,
    /// Power supply fault
    PowerSupplyFault,

    // Communication errors
    /// Orb communication timeout
    OrbTimeout,
    /// Protocol error
    ProtocolError,
}

impl fmt::Display for BaseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::HeightOutOfRange => write!(f, "Height out of range (5-25mm)"),
            Self::InvalidAmplitude => write!(f, "Invalid bobble amplitude"),
            Self::InvalidFrequency => write!(f, "Invalid bobble frequency"),
            Self::LevitationUnstable => write!(f, "Levitation unstable"),
            Self::EmergencyLanding => write!(f, "Emergency landing triggered"),
            Self::DacError => write!(f, "DAC communication failed"),
            Self::AdcError => write!(f, "ADC read failed"),
            Self::I2cError => write!(f, "I2C bus error"),
            Self::HallSensorFault => write!(f, "Hall sensor fault"),
            Self::WptFault => write!(f, "Wireless power transfer fault"),
            Self::ForeignObjectDetected => write!(f, "Foreign object detected"),
            Self::CoilOvertemperature => write!(f, "Coil overtemperature"),
            Self::SafetyViolation => write!(f, "Safety violation: h(x) < 0"),
            Self::PowerSupplyFault => write!(f, "Power supply fault"),
            Self::OrbTimeout => write!(f, "Orb communication timeout"),
            Self::ProtocolError => write!(f, "Protocol error"),
        }
    }
}

/// Result type for base station operations
pub type BaseResult<T> = Result<T, BaseError>;
