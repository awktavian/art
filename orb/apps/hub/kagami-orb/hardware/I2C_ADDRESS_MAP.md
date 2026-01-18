# Kagami Orb V3.1 — I2C Address Map

**CANONICAL REFERENCE**: See `hardware/SPECS.md` for authoritative specifications.
**Last Updated:** January 2026
**Status:** NO CONFLICTS (verified)

---

## I2C BUS TOPOLOGY

The Kagami Orb uses two I2C bus controllers on the QCS6490:

```
                           QCS6490 SoM
                      ┌─────────────────────┐
                      │                     │
              I2C0 ◄──┤  Main I2C Bus       │──► Power ICs, Sensors
       (GPIO2/GPIO3)  │  400kHz             │
                      │                     │
              I2C1 ◄──┤  SMBus (optional)   │──► Fuel Gauge (BQ40Z50)
       (GPIO4/GPIO5)  │  100kHz             │
                      │                     │
                      └─────────────────────┘
```

---

## COMPLETE ADDRESS MAP

### Orb Internals (I2C0 Bus)

| Addr (7-bit) | Addr (8-bit R/W) | Device | Function | Speed | Pull-ups |
|--------------|------------------|--------|----------|-------|----------|
| **0x0B** | 0x16/0x17 | BQ40Z50 | Fuel gauge (SMBus) | 100kHz | 4.7k to 3.3V |
| **0x35** | 0x6A/0x6B | sensiBel SBM100B | MEMS mic config | 400kHz | 2.2k to 1.8V |
| **0x3B** | 0x76/0x77 | P9415-R | WPC RX controller | 400kHz | 2.2k to 3.3V |
| **0x48** | 0x90/0x91 | TMP117 | Temperature sensor | 400kHz | 2.2k to 3.3V |
| **0x6A** | 0xD4/0xD5 | BQ25895 | Battery charger | 400kHz | 2.2k to 3.3V |

### Base Station (Separate ESP32-S3 I2C Bus)

| Addr (7-bit) | Addr (8-bit R/W) | Device | Function | Speed | Pull-ups |
|--------------|------------------|--------|----------|-------|----------|
| **0x48** | 0x90/0x91 | TMP117 | Coil temperature | 400kHz | 2.2k to 3.3V |
| **0x50** | 0xA0/0xA1 | AT24C32 | Calibration EEPROM | 400kHz | 4.7k to 3.3V |
| **0x60** | 0xC0/0xC1 | MCP4725 | Height control DAC | 400kHz | 4.7k to 3.3V |
| **0x68** | 0xD0/0xD1 | bq500215 | WPT TX controller | 400kHz | 2.2k to 3.3V |

---

## ADDRESS CONFLICT ANALYSIS

### Historical Errors (CORRECTED)

Previous documentation incorrectly stated:
- "BQ25895 and BQ40Z50 both at 0x55" - **INCORRECT**

**Actual addresses:**
- BQ25895: **0x6A** (factory default, non-configurable)
- BQ40Z50: **0x0B** (SMBus address, distinct from I2C)

### Verification Source

| Device | Address | Source |
|--------|---------|--------|
| BQ25895 | 0x6A | [TI Datasheet](https://www.ti.com/lit/ds/symlink/bq25895.pdf) Section 9.5 |
| BQ40Z50 | 0x0B | [TI Datasheet](https://www.ti.com/lit/ds/symlink/bq40z50-r1.pdf) Section 7.6.1 |
| P9415-R | 0x3B | Renesas P9415-R datasheet |
| TMP117 | 0x48 | TI TMP117 (ADDR pin grounded) |
| sensiBel | 0x35 | sensiBel application note |

**NO ADDRESS CONFLICTS EXIST** on either bus.

---

## I2C BUS CONFIGURATION

### Orb Main Bus (I2C0)

```
                    3.3V
                     │
                    ┌┴┐ 2.2k
                    │ │
                    └┬┘
     QCS6490         │
   ┌─────────┐       ├──────┬──────┬──────┬──────►  SDA
   │         │       │      │      │      │
   │  GPIO2 ─┼───────┤      │      │      │
   │  (SDA)  │      ┌┴┐    ┌┴┐    ┌┴┐    ┌┴┐
   │         │      │ │    │ │    │ │    │ │
   │  GPIO3 ─┼───┐  │BQ│   │P9│   │TMP│  │SB│
   │  (SCL)  │   │  │25│   │41│   │117│  │M1│
   └─────────┘   │  │895│  │5R│   │   │  │00│
                 │  └──┘   └──┘   └──┘   └──┘
                 │   │      │      │      │
                 │   │      │      │      │
                 └───┼──────┼──────┼──────┼──────►  SCL
                     │      │      │      │
                    ┌┴┐ 2.2k
                    │ │
                    └┬┘
                     │
                    3.3V
```

### Configuration Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Bus speed | 400kHz | Fast mode |
| Pull-up resistors | 2.2k Ohm | To 3.3V |
| Max capacitance | 200pF | Short traces, few devices |
| Rise time | < 300ns | Verified |
| Address mode | 7-bit | Standard |

### Special Cases

#### BQ40Z50 (Fuel Gauge) - SMBus Protocol

The BQ40Z50 uses SMBus protocol, which is compatible with I2C but has additional timing requirements:

```
SMBus timing constraints:
  - Clock stretch: max 25ms
  - Low time: min 4.7us
  - High time: min 4.0us
  - PEC (Packet Error Code): optional but recommended
```

**Firmware implementation:**

```rust
// Use 100kHz for SMBus compatibility
let smbus_config = I2cConfig {
    speed: 100_000,  // 100kHz for SMBus
    clock_stretch_timeout_ms: 30,
};

// BQ40Z50 read example
async fn read_battery_voltage(i2c: &mut I2c) -> Result<u16, Error> {
    const BQ40Z50_ADDR: u8 = 0x0B;
    const CMD_VOLTAGE: u8 = 0x09;

    let mut buf = [0u8; 2];
    i2c.write_read(BQ40Z50_ADDR, &[CMD_VOLTAGE], &mut buf).await?;
    Ok(u16::from_le_bytes(buf))
}
```

#### sensiBel SBM100B - 1.8V Domain

The sensiBel MEMS microphones operate at 1.8V I/O:

```
                    1.8V                      3.3V
                     │                         │
                    ┌┴┐ 2.2k                  ┌┴┐ 2.2k
                    │ │                       │ │
                    └┬┘                       └┬┘
                     │                         │
     sensiBel        │      ┌─────────────┐   │
   ┌─────────┐       │      │  Level      │   │
   │         │       │      │  Shifter    │   │
   │  SDA   ─┼───────┤      │  (TXS0108E) │   │
   │         │       └─────►│ A1      B1  │───┼───► To QCS6490
   │  SCL   ─┼─────────────►│ A2      B2  │───┼───►
   │         │              │             │   │
   │  VDD    │──── 1.8V ───►│ VA      VB  │◄──┘ 3.3V
   │         │              └─────────────┘
   └─────────┘
```

---

## DEVICE REGISTER MAPS (Summary)

### BQ25895 (0x6A) - Key Registers

| Addr | Register | Description |
|------|----------|-------------|
| 0x00 | REG00 | Input current limit |
| 0x02 | REG02 | ADC control |
| 0x04 | REG04 | Charge current |
| 0x06 | REG06 | Charge voltage |
| 0x0B | REG0B | VBUS status |
| 0x0C | REG0C | Fault status |

### BQ40Z50 (0x0B) - SMBus Commands

| Cmd | Name | Description |
|-----|------|-------------|
| 0x09 | Voltage | Battery voltage (mV) |
| 0x0A | Current | Battery current (mA) |
| 0x0D | RelStateOfCharge | SOC (%) |
| 0x10 | RunTimeToEmpty | Minutes remaining |
| 0x08 | Temperature | Cell temp (0.1K) |
| 0x18 | DesignCapacity | Design capacity (mAh) |

### P9415-R (0x3B) - Key Registers

| Addr | Register | Description |
|------|----------|-------------|
| 0x00 | ChipID | Chip identification |
| 0x04 | Status | Operating status |
| 0x06 | IntFlag | Interrupt flags |
| 0x20 | VRECT | Rectified voltage |
| 0x22 | VOUT | Output voltage |
| 0x24 | IOUT | Output current |

### TMP117 (0x48) - Registers

| Addr | Register | Description |
|------|----------|-------------|
| 0x00 | Temperature | 16-bit temp (0.0078125C/LSB) |
| 0x01 | Configuration | Operating mode |
| 0x02 | THigh | High limit |
| 0x03 | TLow | Low limit |

---

## FIRMWARE I2C BUS INITIALIZATION

```rust
use embedded_hal::i2c::I2c;

/// Initialize I2C buses
pub async fn init_i2c_buses() -> (I2c, I2c) {
    // Main I2C bus - 400kHz for most devices
    let i2c_main = I2c::new_async(
        peripherals.I2C0,
        peripherals.GPIO2,  // SDA
        peripherals.GPIO3,  // SCL
        400_000,            // 400kHz
    );

    // SMBus for BQ40Z50 - 100kHz for compatibility
    let i2c_smbus = I2c::new_async(
        peripherals.I2C1,
        peripherals.GPIO4,  // SDA
        peripherals.GPIO5,  // SCL
        100_000,            // 100kHz
    );

    (i2c_main, i2c_smbus)
}

/// Scan I2C bus for devices
pub async fn scan_i2c_bus(i2c: &mut I2c) -> Vec<u8> {
    let mut found = Vec::new();

    for addr in 0x08..=0x77 {
        let mut buf = [0u8; 1];
        if i2c.read(addr, &mut buf).await.is_ok() {
            found.push(addr);
        }
    }

    found
}

/// Expected devices on orb I2C0 bus
pub const EXPECTED_DEVICES: &[(u8, &str)] = &[
    (0x0B, "BQ40Z50 Fuel Gauge"),
    (0x35, "sensiBel SBM100B"),
    (0x3B, "P9415-R WPC RX"),
    (0x48, "TMP117 Temperature"),
    (0x6A, "BQ25895 Charger"),
];

/// Verify all expected devices are present
pub async fn verify_i2c_devices(i2c: &mut I2c) -> Result<(), I2cError> {
    for (addr, name) in EXPECTED_DEVICES {
        let mut buf = [0u8; 1];
        match i2c.read(*addr, &mut buf).await {
            Ok(_) => log::info!("Found {} at 0x{:02X}", name, addr),
            Err(_) => {
                log::error!("Missing {} at 0x{:02X}", name, addr);
                return Err(I2cError::DeviceNotFound(*addr));
            }
        }
    }
    Ok(())
}
```

---

## HARDWARE CHECKLIST

Before power-on:
- [ ] Verify 2.2k pull-ups installed on SDA/SCL
- [ ] Confirm 3.3V rail stable
- [ ] Level shifter for sensiBel powered (1.8V side)
- [ ] No shorts between adjacent traces
- [ ] All ICs properly soldered (no bridges)

After power-on:
- [ ] I2C scan detects all 5 expected devices
- [ ] No unexpected addresses respond
- [ ] BQ25895 STATUS register readable
- [ ] BQ40Z50 returns valid voltage (9.0-12.6V)
- [ ] TMP117 returns room temperature (15-35C)

---

## TROUBLESHOOTING

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| No devices found | Pull-ups missing | Add 2.2k to 3.3V |
| Device ACKs but no data | Wrong voltage domain | Check level shifter |
| Intermittent failures | Noise on bus | Add 100pF caps |
| Clock stretching timeout | SMBus device busy | Increase timeout |
| NACK on write | Wrong address | Verify 7-bit format |

---

**CANONICAL REFERENCE**: This document details the I2C bus topology.
For component specifications, see `hardware/SPECS.md`.
