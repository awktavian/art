# 📚 Hardware Driver Implementation Learnings

**Date:** January 11, 2026
**Author:** Kagami
**Version:** 0.4.0

This document captures learnings from implementing production-grade hardware drivers for the Kagami Orb. These insights are critical for anyone working with these components.

---

## 🏗️ HAL Architecture (v0.4.0)

### Design Principles

1. **Clean Boundaries**
   ```
   Application → HAL Interface → Hardware Drivers → Physical Hardware
   ```
   - Application NEVER touches hardware directly
   - All access goes through OrbSystem unified interface
   - Drivers are interchangeable (real ↔ simulated)

2. **Protocol Conformance**
   Every driver MUST implement:
   - `simulate: bool` - Simulation mode flag
   - `is_initialized() -> bool` - Ready state check
   - `close()` - Resource cleanup

3. **Simulation-First**
   - ALL drivers support `simulate=True`
   - Tests run 100% in simulation (222 tests)
   - No hardware required for development

4. **Error Hierarchy**
   ```python
   HALError
   ├── HardwareNotInitializedError  # Driver not ready
   ├── HardwareNotAvailableError    # Hardware missing
   ├── HardwareCommunicationError   # I2C/SPI failure
   └── HardwareTimeoutError         # Operation timeout
   ```

### Key Files

| File | Purpose |
|------|---------|
| `kagami_orb/__init__.py` | OrbSystem unified interface |
| `kagami_orb/hal.py` | Protocol definitions & validation |
| `kagami_orb/drivers/*.py` | Individual hardware drivers |

### Capability Detection

```python
from kagami_orb import HardwareCapability, HardwareCapabilities

# Get platform capabilities
caps = HardwareCapabilities.qcs6490()

if caps.has(HardwareCapability.NPU):
    # Use NPU acceleration
    pass
```

### Validation

```python
from kagami_orb import validate_hal_interface, OrbSystem

orb = OrbSystem(simulate=True)
errors = validate_hal_interface(orb)
assert errors == []  # No HAL violations
```

---

## 🔌 BQ25895 Charger IC

### Key Learnings

1. **Register Architecture**
   - 21 registers (0x00-0x14)
   - Status registers (0x08-0x0D) are READ-ONLY
   - ADC registers (0x0E-0x13) require ADC_START bit
   - Part info (0x14) useful for device validation

2. **ADC Conversion Formulas** (Critical!)
   ```
   VBAT = 2304mV + 20mV × BATV[6:0]
   VSYS = 2304mV + 20mV × SYSV[6:0]
   VBUS = 2600mV + 100mV × BUSV[6:0]
   ICHG = 0mA + 50mA × ICHGR[6:0]
   ```

3. **I2C Address Selection**
   - 0x6A when ADDR pin LOW
   - 0x6B when ADDR pin HIGH
   - Verify with WHO_AM_I equivalent (PART_INFO register)

4. **Charge State Machine**
   ```
   NOT_CHARGING → PRE_CHARGE → FAST_CHARGING → CHARGE_DONE
        ↑              ↓              ↓              ↓
        └──────────────┴──────────────┴──────────────┘
                     (Any fault resets)
   ```

5. **Gotchas**
   - Must enable ADC explicitly before reading voltage/current
   - Watchdog timer needs reset every 40s (default)
   - Thermal regulation can reduce charge current silently

---

## 🔋 BQ40Z50 Fuel Gauge

### Key Learnings

1. **SMBus Protocol**
   - Uses SMBus v1.1 (not plain I2C!)
   - Default address: 0x0B (standard SBS)
   - Word reads are little-endian
   - Block reads have length prefix

2. **Critical SBS Commands**
   | Command | Addr | Returns |
   |---------|------|---------|
   | Voltage | 0x09 | Pack voltage in mV |
   | Current | 0x0A | Signed mA (+ = charging) |
   | Temperature | 0x08 | 0.1K units |
   | RelativeSOC | 0x0D | 0-100% |
   | RemainingCap | 0x0F | mAh remaining |
   | CycleCount | 0x17 | Full charge cycles |

3. **Temperature Conversion**
   ```python
   temp_c = (raw_value / 10.0) - 273.15
   ```
   Returns 0.1 Kelvin units, must convert!

4. **Current Sign Convention**
   - Positive = charging (current flowing IN)
   - Negative = discharging (current flowing OUT)
   - Raw value is unsigned, interpret as signed 16-bit

5. **Cell Voltage Commands** (for 3S pack)
   - 0x3C: Cell 4 (if 4S)
   - 0x3D: Cell 3
   - 0x3E: Cell 2
   - 0x3F: Cell 1

6. **Gotchas**
   - Device enters SLEEP mode to save power
   - First read after wake may be stale
   - Impedance Track™ needs learning time for accuracy

---

## 🎯 ICM-45686 IMU

### Key Learnings

1. **WHO_AM_I = 0xE5** (Important for validation!)

2. **Register Bank Architecture**
   - Bank 0: Main config + sensor data
   - Banks 1-4: APEX features + calibration
   - Must select bank before accessing registers
   ```python
   write(REG_BANK_SEL, 0x00)  # Select bank 0
   ```

3. **Power Management**
   ```
   PWR_MGMT0 (0x4E):
   [7:4] = Reserved
   [3:2] = GYRO_MODE (00=OFF, 11=Low Noise)
   [1:0] = ACCEL_MODE (00=OFF, 11=Low Noise)
   ```

4. **Sensitivity Tables**
   | Accel FS | Sensitivity |
   |----------|-------------|
   | ±2g | 16384 LSB/g |
   | ±4g | 8192 LSB/g |
   | ±8g | 4096 LSB/g |
   | ±16g | 2048 LSB/g |

   | Gyro FS | Sensitivity |
   |---------|-------------|
   | ±250°/s | 131 LSB/(°/s) |
   | ±500°/s | 65.5 LSB/(°/s) |
   | ±1000°/s | 32.8 LSB/(°/s) |
   | ±2000°/s | 16.4 LSB/(°/s) |

5. **Data Format**
   - 16-bit signed integers
   - Big-endian (high byte first)
   - Burst read recommended for consistency

6. **Unit Conversions**
   ```python
   # Accelerometer: LSB → m/s²
   accel_ms2 = (raw / sensitivity) * 9.80665

   # Gyroscope: LSB → rad/s
   gyro_rads = (raw / sensitivity) * (π / 180)
   ```

7. **Temperature**
   ```python
   temp_c = (raw / 132.48) + 25.0
   ```

---

## 📡 VL53L8CX ToF Sensor

### Key Learnings

1. **No Direct Register Access!**
   - ST doesn't publish register map
   - MUST use their ULD (Ultra Lite Driver) library
   - Python bindings require wrapping C library

2. **Architecture**
   ```
   Application → Python wrapper → ULD API (C) → I2C → VL53L8CX
   ```

3. **Resolution Options**
   - 4×4 = 16 zones (faster)
   - 8×8 = 64 zones (more detail)

4. **Frame Rate vs Resolution**
   | Resolution | Max FPS |
   |------------|---------|
   | 4×4 | 60 Hz |
   | 8×8 | 15 Hz |

5. **Zone Status Codes**
   | Status | Meaning |
   |--------|---------|
   | 0 | Valid |
   | 5 | Valid (low signal) |
   | 6 | Sigma failure |
   | 9 | Range valid, quality low |
   | Other | Invalid |

6. **Integration Note**
   For production, use ST's official C library via ctypes/cffi.
   Don't try to implement from scratch.

---

## 🌡️ SHT45 Temperature/Humidity

### Key Learnings

1. **Simple I2C Protocol** (refreshingly straightforward!)
   - Send command byte
   - Wait for measurement
   - Read 6 bytes (T_high, T_low, T_crc, H_high, H_low, H_crc)

2. **Commands**
   | Precision | Command | Wait Time |
   |-----------|---------|-----------|
   | High | 0xFD | 8.2ms |
   | Medium | 0xF6 | 4.5ms |
   | Low | 0xE0 | 1.7ms |

3. **CRC-8 Algorithm**
   - Polynomial: 0x31
   - Init: 0xFF
   - Check each word independently

4. **Conversion Formulas**
   ```python
   temperature_c = -45.0 + 175.0 * (raw_temp / 65535.0)
   humidity_pct = -6.0 + 125.0 * (raw_hum / 65535.0)

   # Clamp humidity
   humidity_pct = max(0.0, min(100.0, humidity_pct))
   ```

5. **Derived Calculations**
   - Dew point: Magnus formula
   - Heat index: Rothfusz regression
   - Both useful for comfort applications

---

## 🧠 Hailo-10H NPU

### Key Learnings

1. **HailoRT SDK Structure**
   ```
   HEF File (compiled model)
       ↓
   hailort.Hef()
       ↓
   device.configure(hef)
       ↓
   network_group.get_input/output_vstreams()
       ↓
   vstream.write() / vstream.read()
   ```

2. **Model Compilation**
   - Use Hailo Dataflow Compiler
   - Input: ONNX/TensorFlow model
   - Output: .hef (Hailo Executable File)
   - Quantization happens during compilation

3. **Input Preprocessing**
   - Resize to model input shape
   - Normalize (mean/std from training)
   - Convert to quantized format (uint8/int8)
   - Add batch dimension

4. **Common Model Configs**
   | Model | Input | Output |
   |-------|-------|--------|
   | YOLOv8n | 640×640×3 | 8400×6 |
   | RetinaFace | 640×640×3 | 16800×16 |
   | ArcFace | 112×112×3 | 512 |

5. **Performance Expectations**
   - Hailo-10H: 40 TOPS
   - YOLOv8n: ~10ms inference
   - Can run multiple models simultaneously

6. **Gotchas**
   - Models must be compiled for specific Hailo version
   - Batch size often fixed at compile time
   - Memory is limited—can't load unlimited models

---

## 💡 HD108 LED Protocol

**Reference:** Rose Lighting HD108 Datasheet v1.2

### CRITICAL: Correct Protocol

**⚠️ Many implementations get this wrong! Here is the CORRECT format:**

1. **Frame Structure (per datasheet)**
   ```
   [START: 32 bits (4 bytes) of 0x00]
   [LED 0: 64 bits (8 bytes)]
   [LED 1: 64 bits (8 bytes)]
   ...
   [LED N: 64 bits (8 bytes)]
   [END: 32 bits (4 bytes) of 0xFF]
   ```

2. **Per-LED Format (64 bits)**
   ```
   Byte 0: [1:1][G_GAIN:5][R_GAIN[4:3]:2]
   Byte 1: [R_GAIN[2:0]:3][B_GAIN:5]
   Bytes 2-3: GREEN (16-bit, MSB first)
   Bytes 4-5: RED (16-bit, MSB first)
   Bytes 6-7: BLUE (16-bit, MSB first)
   ```
   - Start bit (bit 63) MUST be 1
   - Per-channel 5-bit gain (0-31) for G, R, B independently
   - **COLOR ORDER IS G, R, B (NOT RGB!)**

3. **Common Mistakes to Avoid**
   - ❌ Using 64-bit (8-byte) start/end frames (correct: 32-bit/4-byte)
   - ❌ Single global brightness (correct: per-channel gains)
   - ❌ RGB color order (correct: GRB order)
   - ❌ Missing start bit (correct: bit 63 must be 1)

4. **Key Differences from APA102**
   - HD108 has 16-bit color depth (vs 8-bit)
   - HD108 has PER-CHANNEL gain (vs global brightness only)
   - HD108 uses GRB order (vs RGB)
   - HD108 has 32-bit frames (vs 32-bit frames - same)

5. **SPI Configuration**
   - Mode 0 (CPOL=0, CPHA=0)
   - Max 40 MHz clock (faster than APA102!)
   - PWM refresh rate: 27kHz
   - Data order: MSB first

---

## 🏗️ Architecture Patterns

### Simulation Mode

Every driver should support simulation mode:

```python
class Driver:
    def __init__(self, simulate: bool = False):
        self.simulate = simulate or not HAS_HARDWARE_LIB

    def read(self):
        if self.simulate:
            return self._simulate_read()
        return self._hardware_read()
```

**Benefits:**
- Test on development machine
- CI/CD without hardware
- Graceful degradation
- Faster iteration

### Factory Pattern for Initialization

```python
def create_driver(config: DriverConfig) -> Driver:
    """Factory that handles platform detection."""
    if platform.machine() == "aarch64":
        return RealDriver(config)
    return SimulatedDriver(config)
```

### Resource Cleanup

Always implement cleanup:

```python
class Driver:
    def close(self) -> None:
        """Release hardware resources."""
        if self._bus:
            self._bus.close()
            self._bus = None
        self._initialized = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
```

---

## 📊 Testing Patterns

### Hardware Abstraction Testing

```python
def test_initialization():
    """Test with simulation doesn't need hardware."""
    driver = Driver(simulate=True)
    assert driver.is_initialized()

def test_real_hardware():
    """Only run on target platform."""
    if not platform_is_orb():
        pytest.skip("Requires orb hardware")
    driver = Driver(simulate=False)
    assert driver.is_initialized()
```

### Protocol Validation

```python
def test_spi_frame_structure():
    """Validate wire protocol without hardware."""
    driver = Driver(simulate=True)
    frame = driver._build_frame()

    assert frame[:8] == START_FRAME
    assert frame[-8:] == END_FRAME
    assert len(frame) == expected_length
```

---

## 🚨 Common Mistakes

1. **Not checking initialization**
   ```python
   # BAD
   value = driver.read()

   # GOOD
   if driver.is_initialized():
       value = driver.read()
   ```

2. **Forgetting endianness**
   ```python
   # BAD (assumes little-endian)
   value = (data[0] << 8) | data[1]

   # GOOD (explicit)
   value = struct.unpack(">H", data)[0]  # Big-endian
   ```

3. **Ignoring timing requirements**
   ```python
   # BAD (race condition)
   driver.start_conversion()
   result = driver.read_result()

   # GOOD
   driver.start_conversion()
   time.sleep(CONVERSION_TIME_MS / 1000.0)
   result = driver.read_result()
   ```

4. **Not handling signed values**
   ```python
   # BAD (always positive)
   current = word_value

   # GOOD (properly signed)
   if current >= 0x8000:
       current -= 0x10000
   ```

---

## 📁 File Structure

```
kagami_orb/
├── drivers/
│   ├── __init__.py
│   ├── led.py          # HD108 LED driver
│   ├── power.py        # BQ25895 + BQ40Z50
│   ├── sensors.py      # ICM-45686 + VL53L8CX + SHT45
│   └── npu.py          # Hailo-10H NPU
├── tests/
│   ├── __init__.py
│   ├── test_led_driver.py
│   ├── test_power_driver.py
│   ├── test_sensors.py
│   ├── test_npu.py
│   └── test_integration.py
└── LEARNINGS.md        # This file
```

---

## 📈 Quality Metrics

### Code Coverage Targets

| Module | Target | Current |
|--------|--------|---------|
| led.py | 90% | Simulated |
| power.py | 85% | Simulated |
| sensors.py | 85% | Simulated |
| npu.py | 80% | Simulated |

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| LED frame rate | 60 fps | Animation smooth |
| Sensor loop | 100 Hz | IMU primary |
| NPU inference | 30 fps | Person detection |
| Power monitoring | 1 Hz | Low priority |

---

## 🔮 Future Improvements

1. **Real Hardware Testing**
   - Need QCS6490 dev board
   - Need actual component breakouts
   - Create hardware-in-the-loop tests

2. **Async I/O**
   - Use `anyio` or `trio` for true async
   - Currently uses thread pool

3. **Power Optimization**
   - Implement sensor sleep modes
   - Dynamic ODR based on activity

4. **Error Recovery**
   - Implement automatic retry with backoff
   - Health monitoring daemon

---

## 📡 Cellular Modem (Quectel EG25-G)

### Key Learnings

1. **AT Command Interface**
   - Serial port at 115200 baud
   - Commands end with `\r\n`
   - Response ends with `OK` or `ERROR`
   - Use `ATE0` to disable echo

2. **Critical AT Commands**
   | Command | Purpose |
   |---------|---------|
   | AT | Test communication |
   | AT+CPIN? | SIM status |
   | AT+CSQ | Signal quality (0-31 CSQ) |
   | AT+CREG? | Network registration |
   | AT+COPS? | Operator info |
   | AT+CGDCONT | Set APN |
   | AT+CGACT | Activate PDP context |
   | AT+CMGS | Send SMS |

3. **Signal Quality Conversion**
   ```python
   # CSQ (0-31) to RSSI (dBm)
   rssi_dbm = -113 + (csq * 2)

   # Quality percentage
   quality_pct = (rssi_dbm + 113) / 62 * 100
   ```

4. **Network Registration Status**
   | Value | Meaning |
   |-------|---------|
   | 0 | Not registered |
   | 1 | Registered, home |
   | 2 | Searching |
   | 3 | Denied |
   | 5 | Registered, roaming |

5. **Access Technology (AcT) Values**
   | Value | Technology |
   |-------|------------|
   | 0 | GSM |
   | 2 | UMTS |
   | 7 | LTE |
   | 11 | NR5G NSA |
   | 12 | NR5G SA |

6. **Integrated GNSS Control**
   ```
   AT+QGPS=1        # Enable GNSS
   AT+QGPSLOC?      # Get location
   AT+QGPSEND       # Disable GNSS
   ```

7. **Gotchas**
   - Always check SIM status before network operations
   - SMS in PDU mode is complex, prefer text mode (AT+CMGF=1)
   - PDP context activation can take 30+ seconds
   - Signal quality varies wildly indoors

---

## 🛰️ GNSS (GPS/GLONASS/Galileo/BeiDou)

### Key Learnings

1. **NMEA-0183 Protocol**
   - ASCII text protocol
   - Sentences start with `$`
   - End with `*XX` checksum
   - Fields separated by commas

2. **Essential NMEA Sentences**
   | Sentence | Data |
   |----------|------|
   | GGA | Position fix data |
   | RMC | Recommended minimum |
   | GSA | DOP and satellites |
   | GSV | Satellites in view |
   | VTG | Course and speed |

3. **NMEA Checksum Calculation**
   ```python
   def calc_checksum(sentence: str) -> str:
       """XOR all chars between $ and *."""
       checksum = 0
       for char in sentence:
           checksum ^= ord(char)
       return f"{checksum:02X}"
   ```

4. **Coordinate Format** (CRITICAL!)
   - NMEA uses DDDMM.MMMM format
   - Must convert to decimal degrees
   ```python
   # NMEA: 4807.038,N = 48°07.038' N
   degrees = 48
   minutes = 7.038
   decimal = 48 + (7.038 / 60) = 48.1173°
   ```

5. **Talker IDs**
   | ID | System |
   |----|--------|
   | GP | GPS |
   | GL | GLONASS |
   | GA | Galileo |
   | BD/GB | BeiDou |
   | GN | Combined |

6. **DOP (Dilution of Precision)**
   | Value | Quality |
   |-------|---------|
   | < 1 | Ideal |
   | 1-2 | Excellent |
   | 2-5 | Good |
   | 5-10 | Moderate |
   | 10-20 | Fair |
   | > 20 | Poor |

   Horizontal accuracy ≈ HDOP × 5m (rough estimate)

7. **Fix Types**
   | Value | Type |
   |-------|------|
   | 0 | No fix |
   | 1 | GPS fix |
   | 2 | DGPS fix |
   | 4 | RTK fix |
   | 5 | RTK float |

8. **Haversine Distance Formula**
   ```python
   def distance(lat1, lon1, lat2, lon2):
       R = 6371000  # Earth radius in meters
       dlat = radians(lat2 - lat1)
       dlon = radians(lon2 - lon1)
       a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
       return R * 2 * atan2(sqrt(a), sqrt(1-a))
   ```

9. **Geofencing**
   - Store center point and radius
   - Calculate distance on each position update
   - Hysteresis prevents rapid toggling at boundary

10. **Gotchas**
    - NMEA checksums are MANDATORY for reliable parsing
    - Cold start can take 30+ seconds (need almanac download)
    - Indoor reception is poor to nonexistent
    - Multi-constellation improves accuracy and availability

---

## 🔗 QCS6490 Connectivity

### Built-in Features

The Qualcomm QCS6490 SoM includes:

| Feature | Specification |
|---------|---------------|
| 5G NR | mmWave + Sub-6 GHz |
| 4G LTE | Cat 18 |
| Wi-Fi | 6/6E (802.11ax) |
| Bluetooth | 5.2 |
| GNSS | GPS, GLONASS, Galileo, BeiDou, QZSS, NavIC, SBAS |

### Integration Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    KAGAMI ORB                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │ WiFi 6/6E   │    │ Cellular    │    │   GNSS      │ │
│  │ Primary     │    │ Fallback    │    │ Location    │ │
│  │ 160MHz      │    │ LTE/5G      │    │ Multi-GNSS  │ │
│  └─────────────┘    └─────────────┘    └─────────────┘ │
│         │                 │                  │          │
│         └─────────────────┼──────────────────┘          │
│                           │                             │
│  ┌────────────────────────┴────────────────────────────┐│
│  │              Location Service                        ││
│  │  • Fused positioning (GNSS + Cell + WiFi)           ││
│  │  • Automatic source selection                       ││
│  │  • Geofencing                                       ││
│  │  • Power-aware operation                            ││
│  └──────────────────────────────────────────────────────┘│
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Connectivity Strategy

1. **Primary**: WiFi 6E when available (home/office)
2. **Secondary**: Cellular LTE/5G when mobile
3. **Location**: GNSS for outdoor, Cell/WiFi for indoor

---

*This document should be updated as new learnings emerge.*

鏡
