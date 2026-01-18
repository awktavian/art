//! Base Station Hardware Abstraction Layer
//!
//! Provides trait-based abstractions for the Colony Orb magnetic levitation
//! base station hardware subsystems, enabling hardware-agnostic control and
//! comprehensive testing via mock implementations.
//!
//! # Architecture
//!
//! ```text
//!             ┌─────────────────────────────────────────────┐
//!             │            BaseStation                       │
//!             │  ┌───────────┬───────────┬───────────────┐  │
//!             │  │  Maglev   │  Charging │   Position    │  │
//!             │  │Controller │ Controller│    Sensor     │  │
//!             │  └─────┬─────┴─────┬─────┴───────┬───────┘  │
//!             │        └───────────┼─────────────┘          │
//!             │              ┌─────┴─────┐                  │
//!             │              │   Power   │                  │
//!             │              │  Manager  │                  │
//!             │              └───────────┘                  │
//!             └─────────────────────────────────────────────┘
//! ```

use crate::error::{BaseError, BaseResult};

/// Safety limits for base station operation
pub mod limits {
    /// Maximum coil current in milliamps
    pub const MAX_COIL_CURRENT_MA: u32 = 2500;
    /// Maximum safe temperature in Celsius
    pub const MAX_TEMPERATURE_C: f32 = 80.0;
    /// Thermal warning threshold in Celsius
    pub const THERMAL_WARNING_C: f32 = 65.0;
    /// Levitation height range (mm)
    pub const HEIGHT_MIN_MM: f32 = 5.0;
    pub const HEIGHT_MAX_MM: f32 = 25.0;
}

/// Charging state of the wireless power transfer system
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChargingState {
    /// Not charging (orb not present or disabled)
    Idle,
    /// Actively transferring power
    Charging { power_mw: u32 },
    /// Battery full, trickle charge
    Full,
    /// Error condition (foreign object, thermal, etc.)
    Error(ChargingError),
}

/// Charging subsystem error conditions
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChargingError {
    /// Foreign object detected on charging surface
    ForeignObject,
    /// Coil overtemperature
    Overtemperature,
    /// No receiver detected
    NoReceiver,
    /// Communication failure with receiver
    CommFailure,
}

/// Position reading from Hall effect sensors
#[derive(Debug, Clone, Copy, Default)]
pub struct Position {
    /// Height above base in millimeters
    pub height_mm: f32,
    /// X-axis tilt in degrees (-5 to +5 typical)
    pub tilt_x_deg: f32,
    /// Y-axis tilt in degrees (-5 to +5 typical)
    pub tilt_y_deg: f32,
    /// Sensor confidence (0.0 - 1.0)
    pub confidence: f32,
}

/// Electromagnetic coil control for magnetic levitation
pub trait MaglevController {
    /// Set the target levitation height in millimeters
    ///
    /// # Arguments
    /// * `height_mm` - Target height (5.0 - 25.0 mm)
    ///
    /// # Errors
    /// Returns `HeightOutOfRange` if height is outside valid bounds
    fn set_height(&mut self, height_mm: f32) -> BaseResult<()>;

    /// Get the current coil current in milliamps
    fn coil_current_ma(&self) -> u32;

    /// Get the coil temperature in Celsius
    fn coil_temperature_c(&self) -> f32;

    /// Emergency shutdown - disable all coils immediately
    fn emergency_stop(&mut self);

    /// Check if levitation is stable
    fn is_stable(&self) -> bool;
}

/// Qi wireless charging controller
pub trait ChargingController {
    /// Enable or disable wireless power transfer
    fn set_enabled(&mut self, enabled: bool);

    /// Get current charging state
    fn state(&self) -> ChargingState;

    /// Get transmitted power in milliwatts
    fn power_mw(&self) -> u32;

    /// Get charging coil temperature in Celsius
    fn coil_temperature_c(&self) -> f32;

    /// Set power level (0-100%)
    fn set_power_level(&mut self, percent: u8) -> BaseResult<()>;
}

/// Hall effect position sensing
pub trait PositionSensor {
    /// Read current orb position
    fn read(&mut self) -> BaseResult<Position>;

    /// Check if orb is present on base
    fn orb_present(&self) -> bool;

    /// Calibrate sensors (orb must be removed)
    fn calibrate(&mut self) -> BaseResult<()>;
}

/// Base station power management
pub trait BaseStationPower {
    /// Get input voltage in millivolts
    fn input_voltage_mv(&self) -> u32;

    /// Get total power consumption in milliwatts
    fn power_consumption_mw(&self) -> u32;

    /// Check if power supply is healthy
    fn is_healthy(&self) -> bool;

    /// Enter low-power standby mode
    fn enter_standby(&mut self);

    /// Wake from standby
    fn wake(&mut self);
}

/// Coordinated base station controller
pub struct BaseStation<M, C, P, W>
where
    M: MaglevController,
    C: ChargingController,
    P: PositionSensor,
    W: BaseStationPower,
{
    maglev: M,
    charging: C,
    position: P,
    power: W,
    target_height_mm: f32,
}

impl<M, C, P, W> BaseStation<M, C, P, W>
where
    M: MaglevController,
    C: ChargingController,
    P: PositionSensor,
    W: BaseStationPower,
{
    /// Create a new base station controller
    pub fn new(maglev: M, charging: C, position: P, power: W) -> Self {
        Self {
            maglev,
            charging,
            position,
            power,
            target_height_mm: limits::HEIGHT_MAX_MM,
        }
    }

    /// Set target levitation height with safety checks
    pub fn set_height(&mut self, height_mm: f32) -> BaseResult<()> {
        if height_mm < limits::HEIGHT_MIN_MM || height_mm > limits::HEIGHT_MAX_MM {
            return Err(BaseError::HeightOutOfRange);
        }
        if !self.power.is_healthy() {
            return Err(BaseError::PowerSupplyFault);
        }
        self.target_height_mm = height_mm;
        self.maglev.set_height(height_mm)
    }

    /// Start charging (sinks orb for optimal coupling)
    pub fn start_charging(&mut self) -> BaseResult<()> {
        self.set_height(limits::HEIGHT_MIN_MM)?;
        self.charging.set_enabled(true);
        Ok(())
    }

    /// Stop charging and return to float height
    pub fn stop_charging(&mut self) -> BaseResult<()> {
        self.charging.set_enabled(false);
        self.set_height(limits::HEIGHT_MAX_MM)
    }

    /// Run control loop iteration - call at 100Hz
    pub fn update(&mut self) -> BaseResult<Position> {
        // Safety checks
        if !self.power.is_healthy() {
            self.maglev.emergency_stop();
            return Err(BaseError::PowerSupplyFault);
        }

        let max_temp = self
            .maglev
            .coil_temperature_c()
            .max(self.charging.coil_temperature_c());
        if max_temp > limits::MAX_TEMPERATURE_C {
            self.maglev.emergency_stop();
            self.charging.set_enabled(false);
            return Err(BaseError::CoilOvertemperature);
        }

        if self.maglev.coil_current_ma() > limits::MAX_COIL_CURRENT_MA {
            self.maglev.emergency_stop();
            return Err(BaseError::SafetyViolation);
        }

        self.position.read()
    }

    /// Emergency shutdown all systems
    pub fn emergency_stop(&mut self) {
        self.maglev.emergency_stop();
        self.charging.set_enabled(false);
    }

    /// Get current charging state
    pub fn charging_state(&self) -> ChargingState {
        self.charging.state()
    }

    /// Check if orb is present
    pub fn orb_present(&self) -> bool {
        self.position.orb_present()
    }
}

// ============================================================================
// Mock implementations for testing
// ============================================================================

#[cfg(any(test, feature = "mock"))]
pub mod mock {
    use super::*;

    /// Mock maglev controller for testing
    #[derive(Default)]
    pub struct MockMaglev {
        pub height_mm: f32,
        pub current_ma: u32,
        pub temp_c: f32,
        pub stopped: bool,
    }

    impl MaglevController for MockMaglev {
        fn set_height(&mut self, height_mm: f32) -> BaseResult<()> {
            if height_mm < limits::HEIGHT_MIN_MM || height_mm > limits::HEIGHT_MAX_MM {
                return Err(BaseError::HeightOutOfRange);
            }
            self.height_mm = height_mm;
            self.current_ma = ((limits::HEIGHT_MAX_MM - height_mm) * 100.0) as u32;
            Ok(())
        }
        fn coil_current_ma(&self) -> u32 {
            self.current_ma
        }
        fn coil_temperature_c(&self) -> f32 {
            self.temp_c
        }
        fn emergency_stop(&mut self) {
            self.stopped = true;
            self.current_ma = 0;
        }
        fn is_stable(&self) -> bool {
            !self.stopped
        }
    }

    /// Mock charging controller for testing
    #[derive(Default)]
    pub struct MockCharging {
        pub enabled: bool,
        pub power_mw: u32,
        pub temp_c: f32,
    }

    impl ChargingController for MockCharging {
        fn set_enabled(&mut self, enabled: bool) {
            self.enabled = enabled;
        }
        fn state(&self) -> ChargingState {
            if self.enabled {
                ChargingState::Charging {
                    power_mw: self.power_mw,
                }
            } else {
                ChargingState::Idle
            }
        }
        fn power_mw(&self) -> u32 {
            self.power_mw
        }
        fn coil_temperature_c(&self) -> f32 {
            self.temp_c
        }
        fn set_power_level(&mut self, percent: u8) -> BaseResult<()> {
            self.power_mw = (percent as u32) * 150;
            Ok(())
        }
    }

    /// Mock position sensor for testing
    #[derive(Default)]
    pub struct MockPosition {
        pub position: Position,
        pub present: bool,
    }

    impl PositionSensor for MockPosition {
        fn read(&mut self) -> BaseResult<Position> {
            Ok(self.position)
        }
        fn orb_present(&self) -> bool {
            self.present
        }
        fn calibrate(&mut self) -> BaseResult<()> {
            Ok(())
        }
    }

    /// Mock power manager for testing
    #[derive(Default)]
    pub struct MockPower {
        pub voltage_mv: u32,
        pub power_mw: u32,
        pub healthy: bool,
    }

    impl BaseStationPower for MockPower {
        fn input_voltage_mv(&self) -> u32 {
            self.voltage_mv
        }
        fn power_consumption_mw(&self) -> u32 {
            self.power_mw
        }
        fn is_healthy(&self) -> bool {
            self.healthy
        }
        fn enter_standby(&mut self) {}
        fn wake(&mut self) {}
    }

    /// Create a fully-mocked base station for testing
    pub fn mock_base_station() -> BaseStation<MockMaglev, MockCharging, MockPosition, MockPower> {
        BaseStation::new(
            MockMaglev {
                temp_c: 40.0,
                ..Default::default()
            },
            MockCharging {
                power_mw: 15000,
                temp_c: 35.0,
                ..Default::default()
            },
            MockPosition {
                present: true,
                position: Position {
                    height_mm: 20.0,
                    confidence: 1.0,
                    ..Default::default()
                },
            },
            MockPower {
                voltage_mv: 24000,
                healthy: true,
                ..Default::default()
            },
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use mock::*;

    #[test]
    fn test_height_bounds() {
        let mut base = mock_base_station();
        assert!(base.set_height(15.0).is_ok());
        assert!(base.set_height(3.0).is_err());
        assert!(base.set_height(30.0).is_err());
    }

    #[test]
    fn test_charging_cycle() {
        let mut base = mock_base_station();
        assert!(base.start_charging().is_ok());
        assert_eq!(
            base.charging_state(),
            ChargingState::Charging { power_mw: 15000 }
        );
        assert!(base.stop_charging().is_ok());
        assert_eq!(base.charging_state(), ChargingState::Idle);
    }

    #[test]
    fn test_thermal_protection() {
        let mut base = mock_base_station();
        base.maglev.temp_c = 85.0;
        assert!(base.update().is_err());
        assert!(base.maglev.stopped);
    }

    #[test]
    fn test_power_fault() {
        let mut base = mock_base_station();
        base.power.healthy = false;
        assert!(base.set_height(15.0).is_err());
    }
}
