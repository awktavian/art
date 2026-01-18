# Kagami Orb — Cellular Modem Integration

**Version:** 1.0
**Date:** January 2026
**Status:** SPECIFICATION
**CANONICAL REFERENCE:** See `hardware/SPECS.md` for hardware specifications

---

## Overview

This document specifies the integration of an LTE cellular modem inside the Kagami Orb, enabling fully untethered operation without WiFi dependency.

---

## Component Selection

### Recommended: Quectel EG25-G (LTE Cat 4)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Dimensions** | 29.0 × 32.0 × 2.4mm | Smallest footprint |
| **Volume** | 2,227 mm³ | Fits in available margin |
| **Weight** | 5.5g | +1.4% of orb mass |
| **Interface** | USB 2.0 | QCS6490 has USB host |
| **Power (Idle)** | 0.1W | Negligible |
| **Power (TX)** | 2.0W peak | Brief bursts during transmission |
| **Bands** | LTE B1-5, B7-8, B12-13, B18-21, B25-26, B28, B66 | Global coverage |
| **3G Fallback** | WCDMA B1-2, B4-6, B8, B19 | Rural areas |
| **GNSS** | GPS, GLONASS, BeiDou, Galileo | Replaces need for separate GNSS |
| **SIM** | Nano-SIM or eSIM | eSIM preferred for sealed orb |
| **Certification** | FCC, CE, GCF, PTCRB | Pre-certified |

### Alternative: Quectel BG96 (LTE Cat M1/NB-IoT)

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Dimensions** | 26.5 × 22.5 × 2.3mm | Even smaller |
| **Volume** | 1,371 mm³ | Lowest volume |
| **Weight** | 3.7g | Lightest option |
| **Power (Idle)** | 0.01W | Ultra-low power |
| **Power (TX)** | 0.5W peak | Very efficient |
| **Bands** | LTE-M B1-5, B8, B12-13, B18-20, B25-28 | IoT optimized |
| **Speed** | 375kbps down, 375kbps up | Sufficient for voice/commands |

**Recommendation:** EG25-G for full LTE speed, BG96 for maximum battery life.

---

## Physical Integration

### Assembly Location

```
    Y = +10mm   ┌─────────────────────────┐  ← Main PCB (Ø60mm)
                │                         │
    Y = +8mm    │  ┌───────────────────┐  │  ← Hailo-10H (existing)
                │  │     M.2 2242      │  │
                │  └───────────────────┘  │
                │                         │
    Y = +6mm    │  ┌─────────────────┐    │  ← CELLULAR MODEM (NEW)
                │  │  Quectel EG25-G │    │    29 × 32 × 2.4mm
                │  │   USB + Antenna │    │
                │  └─────────────────┘    │
                │                         │
    Y = +5mm    │  🎤  🎤  🎤  🎤         │  ← Microphones
                └─────────────────────────┘
```

**Vertical clearance:** 3mm gap between Hailo-10H bottom (Y=+5.4mm) and mic tops (Y=+7.5mm)
**Modem height:** 2.4mm → **FITS** with 0.6mm margin

### PCB Footprint

The modem mounts on the **bottom side of the main PCB**, facing downward:

```
        Main PCB Bottom View
        ════════════════════

              ┌─────────────────────────────────┐
             ╱                                   ╲
            │     ┌───────────────────────┐      │
            │     │                       │      │
            │     │   QUECTEL EG25-G      │      │
            │     │     29 × 32mm         │      │
            │     │                       │      │
            │     │  [USB]  [ANT]  [SIM]  │      │
            │     └───────────────────────┘      │
            │                                    │
            │  ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○ ○   │  ← Other components
             ╲                                  ╱
              └─────────────────────────────────┘
                         Ø60mm PCB
```

---

## Antenna Design

### Challenge

LTE antennas typically require 50-100mm of length for efficient radiation. Inside an 85mm sphere, this is tight.

### Solution: Flexible PCB Antenna on Inner Shell

```
        Cross-Section View
        ═══════════════════

                    ╭────────────────────╮
                   ╱                      ╲
                  │   ┌─┐                  │
                  │   │ │ ← LTE Antenna    │  ← Flex PCB adhered to
                  │   │ │   (meander)      │    inner shell surface
                  │   │ │                  │
                  │   └─┘                  │
                  │                        │
                  │    ┌──────────────┐    │
                  │    │   MODEM      │    │
                  │    │              │────┼── Coax to antenna
                  │    └──────────────┘    │
                  │                        │
                   ╲                      ╱
                    ╰────────────────────╯
```

### Antenna Specifications

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Type** | PIFA (Planar Inverted-F) | Good efficiency in small space |
| **Length** | 70mm (meander pattern) | Fits on hemisphere interior |
| **Bandwidth** | 700-2700 MHz | Covers all LTE bands |
| **Gain** | 0-2 dBi | Acceptable for mobile |
| **Impedance** | 50Ω | Standard |
| **Cable** | U.FL to U.FL, 30mm | Low loss micro-coax |

### Alternative: Chip Antenna

| Component | Dimensions | Bands |
|-----------|------------|-------|
| **Taoglas PC104** | 36 × 9 × 1mm | 698-960, 1710-2700 MHz |
| **Molex 206640** | 40 × 10 × 1mm | 698-960, 1710-2690 MHz |

Chip antennas are smaller but have lower gain (~-3 to 0 dBi).

---

## SIM Card Options

### Option 1: Nano-SIM Slot

- Requires external SIM slot access
- User-replaceable SIM
- Complicates sealed enclosure

### Option 2: eSIM (Recommended)

- Soldered eSIM chip (e.g., Infineon SLM97)
- Remote provisioning via QR code
- No physical slot needed
- Perfect for sealed orb

**eSIM Providers:**
- Truphone (global IoT eSIM)
- Twilio Super SIM
- 1NCE (€10/10 years, 500MB)

---

## Power Budget Impact

### Current System (No Cellular)

| Mode | Power (W) |
|------|-----------|
| Idle | 6.7 |
| Active | 13.8 |
| Peak | 22.7 |

### With Cellular

| Mode | Cellular (W) | New Total (W) |
|------|--------------|---------------|
| Idle | +0.1 | 6.8 |
| Active (connected) | +0.3 | 14.1 |
| TX burst | +2.0 | 15.8 (brief) |

**Battery impact:**
- Idle: -1.5% runtime (negligible)
- Active with LTE: -2% runtime
- Acceptable tradeoff for cellular independence

---

## Mass Budget Impact

| Component | Mass (g) |
|-----------|----------|
| Quectel EG25-G | 5.5 |
| Flex antenna | 1.5 |
| Coax cable | 0.5 |
| eSIM chip | 0.1 |
| **TOTAL** | **7.6g** |

**Updated Mass Budget:**

| Item | Without Cellular | With Cellular |
|------|------------------|---------------|
| Orb Total | 391g | 398.6g |
| Target | 350g | 350g |
| Over Target | +41g | +48.6g |

We're still within the 500g maglev capacity with 100g margin.

---

## Software Integration

### QCS6490 Driver

The Quectel EG25-G appears as a USB device:
- `/dev/ttyUSB0` - AT command interface
- `/dev/ttyUSB1` - PPP data interface
- `/dev/ttyUSB2` - GNSS NMEA output

### ModemManager Integration

```bash
# Check modem status
mmcli -m 0

# Connect to network
mmcli -m 0 --simple-connect="apn=hologram"

# Get signal strength
mmcli -m 0 --signal-get
```

### Rust Driver

```rust
//! Cellular modem interface for Kagami Orb

use tokio_serial::SerialPortBuilderExt;

pub struct CellularModem {
    at_port: tokio_serial::SerialStream,
    connected: bool,
    signal_strength: i32, // dBm
}

impl CellularModem {
    pub async fn new() -> Result<Self, CellularError> {
        let at_port = tokio_serial::new("/dev/ttyUSB0", 115200)
            .open_native_async()?;

        let mut modem = Self {
            at_port,
            connected: false,
            signal_strength: -999,
        };

        // Initialize modem
        modem.send_at("ATE0").await?;  // Disable echo
        modem.send_at("AT+CFUN=1").await?;  // Full functionality

        Ok(modem)
    }

    pub async fn connect(&mut self, apn: &str) -> Result<(), CellularError> {
        // Configure APN
        self.send_at(&format!("AT+CGDCONT=1,\"IP\",\"{}\"", apn)).await?;

        // Attach to network
        self.send_at("AT+CGATT=1").await?;

        // Activate PDP context
        self.send_at("AT+CGACT=1,1").await?;

        self.connected = true;
        Ok(())
    }

    pub async fn get_signal_strength(&mut self) -> Result<i32, CellularError> {
        let response = self.send_at("AT+CSQ").await?;
        // Parse CSQ response: +CSQ: 20,0
        // 20 * 2 - 113 = -73 dBm
        let rssi = parse_csq(&response)?;
        self.signal_strength = rssi * 2 - 113;
        Ok(self.signal_strength)
    }

    pub async fn get_location(&mut self) -> Result<(f64, f64), CellularError> {
        // Use built-in GNSS
        self.send_at("AT+QGPS=1").await?;
        tokio::time::sleep(Duration::from_secs(2)).await;
        let nmea = self.send_at("AT+QGPSLOC=2").await?;
        parse_gps_location(&nmea)
    }

    async fn send_at(&mut self, cmd: &str) -> Result<String, CellularError> {
        use tokio::io::{AsyncWriteExt, AsyncBufReadExt, BufReader};

        self.at_port.write_all(format!("{}\r\n", cmd).as_bytes()).await?;

        let mut reader = BufReader::new(&mut self.at_port);
        let mut response = String::new();

        loop {
            let mut line = String::new();
            reader.read_line(&mut line).await?;

            if line.contains("OK") {
                break;
            } else if line.contains("ERROR") {
                return Err(CellularError::AtError(line));
            }

            response.push_str(&line);
        }

        Ok(response)
    }
}
```

---

## Fallback Strategy

The orb should gracefully handle connectivity options:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONNECTIVITY PRIORITY                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. WiFi (fastest, no data cost)                                │
│     │                                                            │
│     └─ If unavailable or signal weak ──┐                        │
│                                         │                        │
│  2. LTE (cellular data)    ◄────────────┘                       │
│     │                                                            │
│     └─ If unavailable or roaming ──────┐                        │
│                                         │                        │
│  3. Offline Mode           ◄────────────┘                       │
│     - Local whisper STT                                         │
│     - Cached responses                                          │
│     - Queue commands for sync                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Bill of Materials Addition

| Component | Part Number | Price | Source |
|-----------|-------------|-------|--------|
| Quectel EG25-G | EG25-G | $25 | Quectel/DigiKey |
| eSIM (Infineon) | SLM97 | $3 | Infineon |
| Flex Antenna | Custom | $5 | PCBWay |
| U.FL Cable 30mm | Various | $1 | DigiKey |
| **TOTAL** | | **$34** | |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 2026 | Initial specification |

---

**Document Status:** SPECIFICATION
**Next Action:** PCB layout integration
**Author:** Kagami (鏡)
