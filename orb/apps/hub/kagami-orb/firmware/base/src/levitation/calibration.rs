//! Calibration data and height-voltage mapping
//!
//! Stores the relationship between physical height and sensor/actuator values.
//! Calibration is performed during manufacturing and stored in EEPROM.

use super::constants;

/// Calibration point: height (mm) to ADC/DAC values
#[derive(Debug, Clone, Copy, Default)]
pub struct CalibrationPoint {
    pub height_mm: f32,
    pub adc_value: u16,
    pub dac_voltage: f32,
}

/// Complete calibration data for height control
#[derive(Debug, Clone)]
pub struct CalibrationData {
    /// Calibration points (sorted by height)
    points: [CalibrationPoint; 5],

    /// Number of valid points
    num_points: usize,

    /// Calibration version/date
    version: u32,

    /// Unit serial number
    serial: u32,
}

impl Default for CalibrationData {
    fn default() -> Self {
        // Default calibration based on typical HCNT + MCP4725 behavior
        Self {
            points: [
                CalibrationPoint { height_mm: 5.0, adc_value: 3800, dac_voltage: 2.5 },
                CalibrationPoint { height_mm: 10.0, adc_value: 3200, dac_voltage: 2.0 },
                CalibrationPoint { height_mm: 15.0, adc_value: 2600, dac_voltage: 1.5 },
                CalibrationPoint { height_mm: 20.0, adc_value: 2000, dac_voltage: 1.0 },
                CalibrationPoint { height_mm: 25.0, adc_value: 1400, dac_voltage: 0.5 },
            ],
            num_points: 5,
            version: 1,
            serial: 0,
        }
    }
}

impl CalibrationData {
    /// Create new calibration data with default values
    pub fn new() -> Self {
        Self::default()
    }

    /// Create from individual calibration points
    pub fn from_points(points: &[CalibrationPoint]) -> Self {
        let mut data = Self::default();
        for (i, p) in points.iter().take(5).enumerate() {
            data.points[i] = *p;
        }
        data.num_points = points.len().min(5);
        data
    }

    /// Set calibration version
    pub fn set_version(&mut self, version: u32) {
        self.version = version;
    }

    /// Set unit serial number
    pub fn set_serial(&mut self, serial: u32) {
        self.serial = serial;
    }

    /// Convert ADC reading to height (mm)
    ///
    /// Uses linear interpolation between calibration points.
    pub fn adc_to_height(&self, adc_value: u16) -> f32 {
        // Find surrounding calibration points
        // Note: ADC values are typically inversely proportional to height
        // (closer = stronger field = higher ADC)

        // Check bounds
        if adc_value >= self.points[0].adc_value {
            return self.points[0].height_mm;
        }
        if adc_value <= self.points[self.num_points - 1].adc_value {
            return self.points[self.num_points - 1].height_mm;
        }

        // Find interval
        for i in 0..self.num_points - 1 {
            let p1 = &self.points[i];
            let p2 = &self.points[i + 1];

            if adc_value <= p1.adc_value && adc_value >= p2.adc_value {
                // Linear interpolation
                let t = (p1.adc_value - adc_value) as f32
                    / (p1.adc_value - p2.adc_value) as f32;
                return p1.height_mm + t * (p2.height_mm - p1.height_mm);
            }
        }

        // Fallback
        15.0
    }

    /// Convert height (mm) to DAC voltage
    ///
    /// Uses linear interpolation between calibration points.
    pub fn height_to_dac(&self, height_mm: f32) -> f32 {
        // Clamp height to valid range
        let height = height_mm.clamp(
            constants::HEIGHT_MIN_MM,
            constants::HEIGHT_MAX_MM,
        );

        // Check bounds
        if height <= self.points[0].height_mm {
            return self.points[0].dac_voltage;
        }
        if height >= self.points[self.num_points - 1].height_mm {
            return self.points[self.num_points - 1].dac_voltage;
        }

        // Find interval
        for i in 0..self.num_points - 1 {
            let p1 = &self.points[i];
            let p2 = &self.points[i + 1];

            if height >= p1.height_mm && height <= p2.height_mm {
                // Linear interpolation
                let t = (height - p1.height_mm) / (p2.height_mm - p1.height_mm);
                return p1.dac_voltage + t * (p2.dac_voltage - p1.dac_voltage);
            }
        }

        // Fallback
        1.5
    }

    /// Convert DAC voltage to approximate height (for verification)
    pub fn dac_to_height(&self, voltage: f32) -> f32 {
        // Check bounds
        if voltage >= self.points[0].dac_voltage {
            return self.points[0].height_mm;
        }
        if voltage <= self.points[self.num_points - 1].dac_voltage {
            return self.points[self.num_points - 1].height_mm;
        }

        // Find interval
        for i in 0..self.num_points - 1 {
            let p1 = &self.points[i];
            let p2 = &self.points[i + 1];

            if voltage <= p1.dac_voltage && voltage >= p2.dac_voltage {
                // Linear interpolation
                let t = (p1.dac_voltage - voltage) / (p1.dac_voltage - p2.dac_voltage);
                return p1.height_mm + t * (p2.height_mm - p1.height_mm);
            }
        }

        // Fallback
        15.0
    }

    /// Validate calibration data
    ///
    /// Returns true if the data appears reasonable.
    pub fn is_valid(&self) -> bool {
        if self.num_points < 3 {
            return false;
        }

        // Check that heights are monotonically increasing
        for i in 1..self.num_points {
            if self.points[i].height_mm <= self.points[i - 1].height_mm {
                return false;
            }
        }

        // Check that DAC voltages are monotonically decreasing
        // (closer = higher voltage in our system)
        for i in 1..self.num_points {
            if self.points[i].dac_voltage >= self.points[i - 1].dac_voltage {
                return false;
            }
        }

        // Check reasonable ranges
        let first = &self.points[0];
        let last = &self.points[self.num_points - 1];

        first.height_mm >= 3.0
            && first.height_mm <= 10.0
            && last.height_mm >= 20.0
            && last.height_mm <= 30.0
            && first.dac_voltage > 2.0
            && last.dac_voltage < 1.0
    }

    /// Get calibration version
    pub fn version(&self) -> u32 {
        self.version
    }

    /// Get unit serial number
    pub fn serial(&self) -> u32 {
        self.serial
    }
}

/// WPT frequency calibration data
///
/// Maps height to optimal WPT operating frequency.
#[derive(Debug, Clone)]
pub struct WptCalibrationData {
    /// Height (mm) to frequency (Hz) mapping
    points: [(f32, f32); 4],
}

impl Default for WptCalibrationData {
    fn default() -> Self {
        Self {
            points: [
                (5.0, 132_000.0),   // 5mm -> 132kHz
                (10.0, 136_000.0),  // 10mm -> 136kHz
                (15.0, 138_000.0),  // 15mm -> 138kHz
                (20.0, 141_000.0),  // 20mm -> 141kHz
            ],
        }
    }
}

impl WptCalibrationData {
    /// Create new WPT calibration with default values
    pub fn new() -> Self {
        Self::default()
    }

    /// Get optimal frequency for given height
    pub fn optimal_frequency(&self, height_mm: f32) -> f32 {
        // Clamp height
        let height = height_mm.clamp(5.0, 25.0);

        // Find interval and interpolate
        for i in 0..self.points.len() - 1 {
            let (h1, f1) = self.points[i];
            let (h2, f2) = self.points[i + 1];

            if height >= h1 && height <= h2 {
                let t = (height - h1) / (h2 - h1);
                return f1 + t * (f2 - f1);
            }
        }

        // Extrapolate beyond calibration range
        if height < self.points[0].0 {
            self.points[0].1
        } else {
            self.points[self.points.len() - 1].1
        }
    }

    /// Get expected efficiency for given height
    pub fn expected_efficiency(&self, height_mm: f32) -> f32 {
        // Empirical efficiency curve
        // η ≈ 0.92 × exp(-height / 30)
        0.92 * libm::expf(-height_mm / 30.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_height_to_dac() {
        let cal = CalibrationData::default();

        // Exact calibration points
        assert!((cal.height_to_dac(5.0) - 2.5).abs() < 0.01);
        assert!((cal.height_to_dac(15.0) - 1.5).abs() < 0.01);
        assert!((cal.height_to_dac(25.0) - 0.5).abs() < 0.01);

        // Interpolated values
        let v_12 = cal.height_to_dac(12.5);
        assert!(v_12 > 1.5 && v_12 < 2.0);
    }

    #[test]
    fn test_adc_to_height() {
        let cal = CalibrationData::default();

        // Exact calibration points
        assert!((cal.adc_to_height(3800) - 5.0).abs() < 0.1);
        assert!((cal.adc_to_height(2600) - 15.0).abs() < 0.1);
        assert!((cal.adc_to_height(1400) - 25.0).abs() < 0.1);

        // Interpolated values
        let h = cal.adc_to_height(2900);
        assert!(h > 12.0 && h < 15.0);
    }

    #[test]
    fn test_calibration_validation() {
        let cal = CalibrationData::default();
        assert!(cal.is_valid());

        // Invalid: heights not monotonic
        let mut bad_cal = cal.clone();
        bad_cal.points[2].height_mm = 5.0;
        assert!(!bad_cal.is_valid());
    }

    #[test]
    fn test_wpt_calibration() {
        let wpt = WptCalibrationData::default();

        // Check interpolation
        let f_5 = wpt.optimal_frequency(5.0);
        assert!((f_5 - 132_000.0).abs() < 100.0);

        let f_12 = wpt.optimal_frequency(12.5);
        assert!(f_12 > 136_000.0 && f_12 < 138_000.0);

        // Efficiency decreases with height
        let eff_5 = wpt.expected_efficiency(5.0);
        let eff_20 = wpt.expected_efficiency(20.0);
        assert!(eff_5 > eff_20);
    }
}
