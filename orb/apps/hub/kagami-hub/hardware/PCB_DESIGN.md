# Kagami Animatronic Lamp Hub - Custom PCB Design

## Overview

Professional-grade custom PCB for the Kagami voice-first home assistant hub.
Designed for Raspberry Pi 4 integration with animatronic servo control, I2S audio,
and SK6812 RGBW LED ring.

**Design Philosophy:** DIY Perks quality or better - clean signal paths, proper
power management, EMI consideration, and professional manufacturing compatibility.

---

## 1. Full Schematic (ASCII Format)

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                           KAGAMI HUB PCB v1.0                                        ║
║                     Voice-First Animatronic Lamp Controller                          ║
╚══════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              POWER MANAGEMENT SECTION                                │
└─────────────────────────────────────────────────────────────────────────────────────┘

    USB-C Input (5V/3A)
         │
         ▼
    ┌─────────┐
    │  J1     │  USB-C Receptacle (USB4110-GF-A)
    │  USB-C  │  With CC resistors for 5V@3A
    │         │
    └────┬────┘
         │ VBUS (5V)
         │
    ┌────┴────┐      ┌──────────┐
    │   F1    │──────│   TVS1   │  ESD Protection (SMBJ5.0A)
    │  3A PTC │      │          │
    └────┬────┘      └──────────┘
         │
    ┌────┴────────────────────────────────────────────────────────┐
    │                      5V POWER RAIL                           │
    │  C1: 100uF/16V (Bulk)   C2: 10uF/10V   C3: 100nF (Bypass)   │
    └─────────┬─────────────────────┬────────────────────┬────────┘
              │                     │                    │
              ▼                     ▼                    ▼
    ┌─────────────────┐   ┌─────────────────┐   ┌───────────────┐
    │ 5V_SERVO        │   │ 5V_LED          │   │ U1: AMS1117   │
    │ (Filtered)      │   │ (Direct)        │   │ 3.3V LDO      │
    │                 │   │                 │   │               │
    │ L1: 10uH        │   │                 │   │ IN ─── OUT    │
    │ C4: 470uF/10V   │   │                 │   │       │       │
    │ C5: 100nF       │   │                 │   │      GND      │
    └────────┬────────┘   └────────┬────────┘   └───────┬───────┘
             │                     │                    │
             ▼                     ▼                    ▼
        To PCA9685             To SK6812           3.3V LOGIC
        (VSERVO)               LED Ring            RAIL


    3.3V LOGIC RAIL:
    ┌─────────────────────────────────────────────────────────────┐
    │  C6: 10uF/6.3V (Bulk)   C7: 100nF    C8: 100nF   C9: 100nF  │
    │  (Near LDO)             (Near Pi)   (Near PCA)  (Near Audio)│
    └─────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RASPBERRY PI 4 HEADER (J2)                                 │
└─────────────────────────────────────────────────────────────────────────────────────┘

    Pi 4 40-Pin Header (2x20, 2.54mm pitch)
    ┌─────────────────────────────────────────────────────────────┐
    │     Pi Pin │ Function      │ Signal Name │ PCB Connection   │
    ├────────────┼───────────────┼─────────────┼──────────────────┤
    │      1     │ 3.3V Power    │ 3V3         │ (NC - use LDO)   │
    │      2     │ 5V Power      │ 5V          │ 5V_SUPPLY        │
    │      3     │ GPIO2/SDA1    │ I2C_SDA     │ PCA9685, Exp     │
    │      4     │ 5V Power      │ 5V          │ 5V_SUPPLY        │
    │      5     │ GPIO3/SCL1    │ I2C_SCL     │ PCA9685, Exp     │
    │      6     │ Ground        │ GND         │ GND              │
    │      7     │ GPIO4         │ GPIO4       │ (Reserved)       │
    │      8     │ GPIO14/TXD    │ UART_TX     │ Debug Header     │
    │      9     │ Ground        │ GND         │ GND              │
    │     10     │ GPIO15/RXD    │ UART_RX     │ Debug Header     │
    │     11     │ GPIO17        │ STATUS_LED1 │ Status LED Red   │
    │     12     │ GPIO18/PWM0   │ LED_DATA    │ SK6812 DIN       │
    │     13     │ GPIO27        │ STATUS_LED2 │ Status LED Grn   │
    │     14     │ Ground        │ GND         │ GND              │
    │     15     │ GPIO22        │ STATUS_LED3 │ Status LED Blu   │
    │     16     │ GPIO23        │ RESET_BTN   │ Reset Button     │
    │     17     │ 3.3V Power    │ 3V3         │ (NC)             │
    │     18     │ GPIO24        │ (Reserved)  │ Future Use       │
    │     19     │ GPIO10/MOSI   │ SPI_MOSI    │ (Expansion)      │
    │     20     │ Ground        │ GND         │ GND              │
    │     21     │ GPIO9/MISO    │ SPI_MISO    │ (Expansion)      │
    │     22     │ GPIO25        │ PCA_OE      │ PCA9685 ~OE      │
    │     23     │ GPIO11/SCLK   │ SPI_SCK     │ (Expansion)      │
    │     24     │ GPIO8/CE0     │ SPI_CE0     │ (Expansion)      │
    │     25     │ Ground        │ GND         │ GND              │
    │     26     │ GPIO7/CE1     │ SPI_CE1     │ (Expansion)      │
    │     27     │ ID_SD         │ EEPROM      │ NC               │
    │     28     │ ID_SC         │ EEPROM      │ NC               │
    │     29     │ GPIO5         │ (Reserved)  │ Future Use       │
    │     30     │ Ground        │ GND         │ GND              │
    │     31     │ GPIO6         │ (Reserved)  │ Future Use       │
    │     32     │ GPIO12/PWM0   │ I2S_BCLK    │ Audio BCLK       │
    │     33     │ GPIO13/PWM1   │ (Reserved)  │ Future Use       │
    │     34     │ Ground        │ GND         │ GND              │
    │     35     │ GPIO19/MISO   │ I2S_LRCLK   │ Audio LRCK       │
    │     36     │ GPIO16        │ (Reserved)  │ Future Use       │
    │     37     │ GPIO26        │ (Reserved)  │ Future Use       │
    │     38     │ GPIO20/MOSI   │ I2S_DIN     │ SPH0645 DOUT     │
    │     39     │ Ground        │ GND         │ GND              │
    │     40     │ GPIO21/SCLK   │ I2S_DOUT    │ PCM5102 DIN      │
    └────────────┴───────────────┴─────────────┴──────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          PCA9685 SERVO DRIVER (U2)                                   │
└─────────────────────────────────────────────────────────────────────────────────────┘

                            PCA9685PW (TSSOP-28)
                           ┌────────┬────────┐
                     A0  1─┤        │        ├─28 VDD ────── 3.3V
                     A1  2─┤        │        ├─27 ~OE ────── GPIO25
                     A2  3─┤        │        ├─26 SCL ────── I2C_SCL
                     A3  4─┤        │        ├─25 SDA ────── I2C_SDA
                     A4  5─┤        │        ├─24 EXTCLK ── GND
                     A5  6─┤        │        ├─23 LED15
                    LED0 7─┤        │        ├─22 LED14
                    LED1 8─┤   U2   │        ├─21 LED13
                    LED2 9─┤        │        ├─20 LED12
                   LED3 10─┤ PCA9685│        ├─19 LED11
                   LED4 11─┤        │        ├─18 LED10
                   LED5 12─┤        │        ├─17 LED9
                   GND  13─┤        │        ├─16 LED8
                   LED6 14─┤        │        ├─15 LED7
                           └────────┴────────┘

    I2C Address Selection (Default 0x40):
    A0-A5 all tied to GND via 10K pulldowns

    Servo Output Connections:
    ┌──────────┬──────────────────────────────────────────────┐
    │ Channel  │ Connection                                   │
    ├──────────┼──────────────────────────────────────────────┤
    │ LED0     │ J3: Pan Servo (Neck rotation)                │
    │ LED1     │ J4: Tilt Servo (Lamp head vertical)          │
    │ LED2     │ J5: Rotate Servo (Lamp head angle)           │
    │ LED3-15  │ Reserved for future expansion                │
    └──────────┴──────────────────────────────────────────────┘

    Servo Headers (J3, J4, J5): 3-pin 2.54mm headers
    ┌─────┬─────┬─────┐
    │ GND │ PWR │ SIG │
    │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┘
      Blk   Red   Yel
    (5V_SERVO filtered rail for PWR)

    Decoupling:
    - C10: 100nF across VDD-GND (near U2)
    - C11: 10uF/10V bulk on 5V_SERVO rail


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         SK6812 RGBW LED RING (J6)                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘

    7x SK6812 RGBW LEDs - Connected in series

    Connector J6 (4-pin JST-XH):
    ┌─────┬─────┬─────┬─────┐
    │ 5V  │ DIN │ GND │ NC  │
    │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┘

    Signal Path:
    GPIO18 (Pi) ──┬── R1: 330Ω ──── DIN (J6)
                  │
                  └── C12: 100pF (ESD/EMI)

    Power:
    5V_LED ──┬── C13: 100uF/10V ──── J6 Pin 1
             │
             └── (Direct from VBUS, not filtered - LEDs are
                  tolerant and filtering would reduce brightness)

    Power Budget:
    - 7 LEDs × 60mA max (RGBW full white) = 420mA peak
    - Typical usage: ~150mA (breathing animation)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          I2S AUDIO INPUT - SPH0645 MEMS MIC (J7)                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

    SPH0645LM4H-B MEMS Microphone Breakout Connection

    Connector J7 (6-pin JST-SH 1.0mm):
    ┌─────┬─────┬─────┬─────┬─────┬─────┐
    │ 3V3 │ GND │ BCLK│ LRCK│DOUT │ SEL │
    │  ●  │  ●  │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┴─────┴─────┘

    Connections:
    ┌──────────┬─────────────────────────────────────────────┐
    │ J7 Pin   │ Connection                                  │
    ├──────────┼─────────────────────────────────────────────┤
    │ 3V3      │ 3.3V Rail + C14: 100nF bypass              │
    │ GND      │ Ground                                      │
    │ BCLK     │ GPIO12 (I2S_BCLK) via R2: 33Ω              │
    │ LRCK     │ GPIO19 (I2S_LRCLK) via R3: 33Ω             │
    │ DOUT     │ GPIO20 (I2S_DIN)                           │
    │ SEL      │ GND (Left channel) or VDD (Right channel)  │
    └──────────┴─────────────────────────────────────────────┘

    SEL Pin Jumper (JP1):
    ┌───┬───┐
    │ L │ R │  Solder bridge to select L/R channel
    └───┴───┘  Default: Left (GND)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        I2S AUDIO OUTPUT - PCM5102 DAC (J8)                           │
└─────────────────────────────────────────────────────────────────────────────────────┘

    PCM5102A DAC Module Connection

    Connector J8 (7-pin JST-XH 2.5mm):
    ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐
    │ VIN │ GND │ BCK │ DIN │ LCK │ SCK │ FMT │
    │  ●  │  ●  │  ●  │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┴─────┴─────┴─────┘

    Connections:
    ┌──────────┬─────────────────────────────────────────────┐
    │ J8 Pin   │ Connection                                  │
    ├──────────┼─────────────────────────────────────────────┤
    │ VIN      │ 3.3V Rail + C15: 10uF bypass               │
    │ GND      │ Ground                                      │
    │ BCK      │ GPIO12 (I2S_BCLK) via R4: 33Ω              │
    │ DIN      │ GPIO21 (I2S_DOUT)                          │
    │ LCK      │ GPIO19 (I2S_LRCLK) via R5: 33Ω             │
    │ SCK      │ GND (Internal PLL mode)                     │
    │ FMT      │ GND (I2S format)                           │
    └──────────┴─────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        AMPLIFIER - PAM8403 (J9)                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

    PAM8403 Class-D Amplifier Module Connection

    Connector J9 (5-pin JST-XH 2.5mm):
    ┌─────┬─────┬─────┬─────┬─────┐
    │ 5V  │ GND │ L+  │ L-  │ RIN │
    │  ●  │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┴─────┘

    Connections:
    ┌──────────┬─────────────────────────────────────────────┐
    │ J9 Pin   │ Connection                                  │
    ├──────────┼─────────────────────────────────────────────┤
    │ 5V       │ 5V Rail + C16: 100uF bypass                │
    │ GND      │ Ground                                      │
    │ L+/L-    │ Speaker output (to external connector J10) │
    │ RIN      │ Audio input from DAC (R ch output of       │
    │          │ PCM5102 via R6: 10K volume pot)            │
    └──────────┴─────────────────────────────────────────────┘

    Speaker Output J10 (2-pin terminal block):
    ┌─────┬─────┐
    │ SPK+│ SPK-│  For 4-8Ω speaker (3W max)
    │  ●  │  ●  │
    └─────┴─────┘


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              STATUS LEDs (D1-D3)                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

    RGB Status LED (Common Cathode) or 3x discrete LEDs

    D1 (Red):    GPIO17 ── R7: 330Ω ──┤>│── GND
    D2 (Green):  GPIO27 ── R8: 330Ω ──┤>│── GND
    D3 (Blue):   GPIO22 ── R9: 680Ω ──┤>│── GND

    LED Current:
    - Red:   (3.3V - 2.0V) / 330Ω = 3.9mA
    - Green: (3.3V - 2.2V) / 330Ω = 3.3mA
    - Blue:  (3.3V - 3.0V) / 680Ω = 0.4mA (blue needs less current for visibility)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              RESET BUTTON (SW1)                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

    Tactile Pushbutton with hardware debounce

                    3.3V
                     │
                     R10: 10K (pull-up)
                     │
    GPIO23 ──────────┼──── SW1 ──── GND
                     │
                     C17: 100nF (debounce)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          I2C EXPANSION HEADER (J11)                                  │
└─────────────────────────────────────────────────────────────────────────────────────┘

    4-pin Qwiic/STEMMA QT Compatible (JST-SH 1.0mm):
    ┌─────┬─────┬─────┬─────┐
    │ GND │ 3V3 │ SDA │ SCL │
    │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┘

    I2C Bus with pull-ups:
    - R11: 2.2K on SDA (already on Pi, but adding for expansion cable length)
    - R12: 2.2K on SCL
    - Connected to same I2C bus as PCA9685

    Compatible with:
    - BME280 (temp/humidity/pressure)
    - MPU6050 (accelerometer/gyro for gesture detection)
    - VL53L0X (ToF distance for presence detection)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DEBUG HEADER (J12)                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘

    6-pin Debug/UART Header (2.54mm):
    ┌─────┬─────┬─────┬─────┬─────┬─────┐
    │ 3V3 │ TXD │ RXD │ GND │ RST │ NC  │
    │  ●  │  ●  │  ●  │  ●  │  ●  │  ●  │
    └─────┴─────┴─────┴─────┴─────┴─────┘

    Connections:
    - 3V3: 3.3V rail
    - TXD: GPIO14 (Pi UART TX)
    - RXD: GPIO15 (Pi UART RX)
    - GND: Ground
    - RST: Connected to SW1 (manual reset trigger)


┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE NET LIST                                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

    Power Nets:
    ┌────────────┬────────────────────────────────────────────┐
    │ Net Name   │ Description                                │
    ├────────────┼────────────────────────────────────────────┤
    │ VBUS       │ USB-C 5V input (raw)                       │
    │ 5V_MAIN    │ 5V after fuse + TVS                        │
    │ 5V_SERVO   │ Filtered 5V for servos                     │
    │ 5V_LED     │ 5V for LED ring                            │
    │ 3V3        │ 3.3V regulated logic rail                  │
    │ GND        │ Ground plane                               │
    └────────────┴────────────────────────────────────────────┘

    Signal Nets:
    ┌────────────┬────────────────────────────────────────────┐
    │ Net Name   │ Description                                │
    ├────────────┼────────────────────────────────────────────┤
    │ I2C_SDA    │ I2C Data (GPIO2)                           │
    │ I2C_SCL    │ I2C Clock (GPIO3)                          │
    │ I2S_BCLK   │ I2S Bit Clock (GPIO12)                     │
    │ I2S_LRCLK  │ I2S L/R Clock (GPIO19)                     │
    │ I2S_DIN    │ I2S Data In - Mic (GPIO20)                 │
    │ I2S_DOUT   │ I2S Data Out - DAC (GPIO21)                │
    │ LED_DATA   │ SK6812 Data (GPIO18)                       │
    │ PCA_OE     │ PCA9685 Output Enable (GPIO25)             │
    │ UART_TX    │ Debug UART TX (GPIO14)                     │
    │ UART_RX    │ Debug UART RX (GPIO15)                     │
    │ STAT_R     │ Status LED Red (GPIO17)                    │
    │ STAT_G     │ Status LED Green (GPIO27)                  │
    │ STAT_B     │ Status LED Blue (GPIO22)                   │
    │ RESET_N    │ Reset button (GPIO23)                      │
    └────────────┴────────────────────────────────────────────┘
```

---

## 2. Complete Bill of Materials (BOM)

### Integrated Circuits

| Ref  | Value          | Package      | Description                    | Part Number           | Qty |
|------|----------------|--------------|--------------------------------|-----------------------|-----|
| U1   | AMS1117-3.3    | SOT-223      | 3.3V 1A LDO Regulator          | AMS1117-3.3           | 1   |
| U2   | PCA9685PW      | TSSOP-28     | 16-ch PWM/Servo Driver         | PCA9685PW,112         | 1   |

### Connectors

| Ref  | Value          | Package      | Description                    | Part Number           | Qty |
|------|----------------|--------------|--------------------------------|-----------------------|-----|
| J1   | USB-C          | SMD          | USB Type-C 2.0 Receptacle      | USB4110-GF-A          | 1   |
| J2   | 2x20 Header    | 2.54mm       | Raspberry Pi GPIO Header       | PPTC202LFBN-RC        | 1   |
| J3-J5| 3-pin Header   | 2.54mm       | Servo Connectors               | B3B-XH-A              | 3   |
| J6   | 4-pin JST-XH   | 2.5mm        | LED Ring Connector             | B4B-XH-A              | 1   |
| J7   | 6-pin JST-SH   | 1.0mm        | MEMS Mic Connector             | SM06B-SRSS-TB         | 1   |
| J8   | 7-pin JST-XH   | 2.5mm        | DAC Module Connector           | B7B-XH-A              | 1   |
| J9   | 5-pin JST-XH   | 2.5mm        | Amplifier Connector            | B5B-XH-A              | 1   |
| J10  | 2-pos Terminal | 5.08mm       | Speaker Output                 | 1729128               | 1   |
| J11  | 4-pin JST-SH   | 1.0mm        | Qwiic I2C Expansion            | SM04B-SRSS-TB         | 1   |
| J12  | 6-pin Header   | 2.54mm       | Debug/UART Header              | PPTC061LFBN-RC        | 1   |

### Passive Components - Capacitors

| Ref  | Value          | Package      | Voltage | Type                   | Qty |
|------|----------------|--------------|---------|------------------------|-----|
| C1   | 100uF          | 0805/Radial  | 16V     | Aluminum Electrolytic  | 1   |
| C2   | 10uF           | 0805         | 10V     | MLCC X5R               | 1   |
| C3   | 100nF          | 0402         | 16V     | MLCC X7R               | 1   |
| C4   | 470uF          | 10mm Radial  | 10V     | Low ESR Electrolytic   | 1   |
| C5   | 100nF          | 0402         | 16V     | MLCC X7R               | 1   |
| C6   | 10uF           | 0805         | 6.3V    | MLCC X5R               | 1   |
| C7-C9| 100nF          | 0402         | 10V     | MLCC X7R               | 3   |
| C10  | 100nF          | 0402         | 10V     | MLCC X7R               | 1   |
| C11  | 10uF           | 0805         | 10V     | MLCC X5R               | 1   |
| C12  | 100pF          | 0402         | 50V     | MLCC C0G               | 1   |
| C13  | 100uF          | 6.3mm Radial | 10V     | Low ESR Electrolytic   | 1   |
| C14-C15| 100nF        | 0402         | 10V     | MLCC X7R               | 2   |
| C16  | 100uF          | 6.3mm Radial | 10V     | Low ESR Electrolytic   | 1   |
| C17  | 100nF          | 0402         | 10V     | MLCC X7R               | 1   |

### Passive Components - Resistors (All 0402, 1%)

| Ref  | Value   | Description                           | Qty |
|------|---------|---------------------------------------|-----|
| R1   | 330Ω    | LED Data Series Resistor              | 1   |
| R2-R5| 33Ω     | I2S Series Termination (4x)           | 4   |
| R6   | 10K     | Audio Input Resistor (or pot)         | 1   |
| R7-R8| 330Ω    | LED Current Limiting (Red/Green)      | 2   |
| R9   | 680Ω    | LED Current Limiting (Blue)           | 1   |
| R10  | 10K     | Reset Button Pull-up                  | 1   |
| R11-R12| 2.2K  | I2C Pull-up Resistors                 | 2   |
| RA1-RA6| 10K   | PCA9685 Address Pull-down (6x)        | 6   |

### Passive Components - Inductors

| Ref  | Value   | Package | Description                     | Part Number    | Qty |
|------|---------|---------|--------------------------------|----------------|-----|
| L1   | 10uH    | 1210    | Servo Power Filter Inductor    | LQH32PZ100MN0  | 1   |

### Protection Components

| Ref  | Value   | Package | Description                     | Part Number    | Qty |
|------|---------|---------|--------------------------------|----------------|-----|
| F1   | 3A PTC  | 1206    | Resettable Fuse                | MF-MSMF300-2   | 1   |
| TVS1 | SMBJ5.0A| SMB     | TVS Diode ESD Protection       | SMBJ5.0A       | 1   |

### Discrete Components

| Ref  | Value            | Package | Description              | Qty |
|------|------------------|---------|--------------------------|-----|
| D1   | Red LED 0805     | 0805    | Status LED               | 1   |
| D2   | Green LED 0805   | 0805    | Status LED               | 1   |
| D3   | Blue LED 0805    | 0805    | Status LED               | 1   |
| SW1  | Tactile Switch   | 6x6mm   | Reset Button             | 1   |

### Optional/Jumpers

| Ref  | Value            | Package | Description              | Qty |
|------|------------------|---------|--------------------------|-----|
| JP1  | Solder Jumper    | 0.5mm   | Mic L/R Channel Select   | 1   |

---

## 3. PCB Dimensions and Mechanical

### Board Dimensions

```
┌────────────────────────────────────────────────────────┐
│                                                        │
│   ●                                              ●     │  ← M2.5 Mounting Holes
│                                                        │
│                   KAGAMI HUB v1.0                      │
│                                                        │
│   ┌──────────────────────────────────────────────┐    │
│   │                                              │    │
│   │           Component Area                     │    │
│   │           (See placement below)              │    │
│   │                                              │    │
│   └──────────────────────────────────────────────┘    │
│                                                        │
│   ●                                              ●     │  ← M2.5 Mounting Holes
│                                                        │
└────────────────────────────────────────────────────────┘

Dimensions:
- Width:  70mm (2.76")
- Height: 50mm (1.97")
- Designed to mount beneath Pi 4 as HAT

Mounting Holes:
- 4x M2.5 holes (2.7mm diameter)
- Positions: Raspberry Pi HAT standard
  - (3.5mm, 3.5mm)
  - (3.5mm, 46.5mm)
  - (66.5mm, 3.5mm)
  - (66.5mm, 46.5mm)
- Hole-to-edge clearance: 3.5mm minimum

Board Outline:
- Corner radius: 3mm
- Keep-out zone around mounting holes: 6mm diameter
```

### Component Placement (Top View)

```
┌────────────────────────────────────────────────────────┐
│ ●                                                    ● │
│                                                        │
│  ┌─────┐   ┌─────────────────────────────────────┐    │
│  │ J1  │   │           J2 (Pi Header)            │    │
│  │USB-C│   │         40-pin Connector            │    │
│  └─────┘   └─────────────────────────────────────┘    │
│                                                        │
│  ┌────┐  ┌────┐  ┌──────────┐                         │
│  │ U1 │  │TVS1│  │   U2     │  ┌───┐ ┌───┐ ┌───┐     │
│  │LDO │  │    │  │ PCA9685  │  │J3 │ │J4 │ │J5 │     │
│  └────┘  └────┘  └──────────┘  └───┘ └───┘ └───┘     │
│                                 Servo Connectors      │
│  ┌────┐  ┌────┐  ┌────┐                               │
│  │ J7 │  │ J8 │  │ J9 │     D1 D2 D3  ┌────┐         │
│  │MIC │  │DAC │  │AMP │     ● ● ●     │SW1 │         │
│  └────┘  └────┘  └────┘     Status    └────┘         │
│                                                        │
│  ┌────┐  ┌────┐  ┌────────┐                           │
│  │J11 │  │J12 │  │  J10   │         ┌────┐           │
│  │I2C │  │DBG │  │Speaker │         │ J6 │           │
│  └────┘  └────┘  └────────┘         │LED │           │
│                                      └────┘           │
│ ●                                                    ● │
└────────────────────────────────────────────────────────┘

Legend:
- J1: USB-C Power Input (left edge)
- J2: 40-pin Pi Header (center-top, stacking)
- U1: 3.3V LDO Regulator
- U2: PCA9685 Servo Driver
- J3-J5: Servo outputs (3-pin headers)
- J6: SK6812 LED Ring connector
- J7: SPH0645 MEMS Mic connector
- J8: PCM5102 DAC connector
- J9: PAM8403 Amp connector
- J10: Speaker terminal block
- J11: Qwiic/I2C expansion
- J12: Debug/UART header
- D1-D3: Status LEDs (RGB)
- SW1: Reset button
```

---

## 4. Layer Stackup Recommendation

### 4-Layer Stackup (Recommended for Best Performance)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1 (Top)     │ Signal + Components │ 35um Cu (1oz) │
├───────────────────┼─────────────────────┼───────────────┤
│ Prepreg           │ FR4 2116           │ 0.2mm         │
├───────────────────┼─────────────────────┼───────────────┤
│ Layer 2 (Inner 1) │ GND Plane          │ 35um Cu (1oz) │
├───────────────────┼─────────────────────┼───────────────┤
│ Core              │ FR4                │ 0.8mm         │
├───────────────────┼─────────────────────┼───────────────┤
│ Layer 3 (Inner 2) │ Power Planes       │ 35um Cu (1oz) │
├───────────────────┼─────────────────────┼───────────────┤
│ Prepreg           │ FR4 2116           │ 0.2mm         │
├───────────────────┼─────────────────────┼───────────────┤
│ Layer 4 (Bottom)  │ Signal + Routing   │ 35um Cu (1oz) │
└───────────────────┴─────────────────────┴───────────────┘

Total Thickness: ~1.6mm (standard)

Layer Assignments:
- L1 (Top):    Components, high-speed signals (I2S, LED data)
- L2 (GND):    Solid ground plane (critical for EMI)
- L3 (Power):  Split planes: 5V_MAIN, 5V_SERVO, 3V3
- L4 (Bottom): I2C routing, low-speed signals, test points
```

### 2-Layer Alternative (Budget Option)

```
┌─────────────────────────────────────────────────────────┐
│ Layer 1 (Top)     │ Signal + Components │ 35um Cu (1oz) │
├───────────────────┼─────────────────────┼───────────────┤
│ Core              │ FR4                │ 1.6mm         │
├───────────────────┼─────────────────────┼───────────────┤
│ Layer 2 (Bottom)  │ Ground + Power     │ 35um Cu (1oz) │
└───────────────────┴─────────────────────┴───────────────┘

2-Layer Guidelines:
- Bottom layer: 80% ground pour, power traces thickened
- Top layer: Ground pour in available areas
- Use via stitching around high-speed signals
- I2S signals must have ground return path
```

---

## 5. Design Rules for JLCPCB/PCBWay Fabrication

### Standard Capability Design Rules

```
┌────────────────────────────────────────────────────────────────────┐
│                    JLCPCB/PCBWay Compatible Rules                  │
├─────────────────────────┬──────────────────────────────────────────┤
│ Parameter               │ Value                                    │
├─────────────────────────┼──────────────────────────────────────────┤
│ Minimum Trace Width     │ 0.2mm (8 mil) - using 0.254mm (10 mil)  │
│ Minimum Spacing         │ 0.2mm (8 mil) - using 0.254mm (10 mil)  │
│ Minimum Via Diameter    │ 0.6mm (24 mil) - using 0.8mm            │
│ Minimum Via Drill       │ 0.3mm (12 mil) - using 0.4mm            │
│ Minimum Annular Ring    │ 0.15mm (6 mil) - using 0.2mm            │
│ Minimum PTH Drill       │ 0.3mm                                    │
│ Minimum NPTH Drill      │ 0.8mm                                    │
│ Board Thickness         │ 1.6mm (standard)                         │
│ Copper Weight           │ 1oz (35um) - both sides                 │
│ Surface Finish          │ HASL Lead-Free (or ENIG for fine pitch) │
│ Solder Mask             │ Green (or Matte Black for aesthetics)   │
│ Silkscreen              │ White                                    │
│ Min Silkscreen Width    │ 0.15mm line, 1mm height text            │
└─────────────────────────┴──────────────────────────────────────────┘
```

### Trace Width Calculator

```
Power Traces (for 3A max):
┌────────────────────┬──────────────────────────────────────────────┐
│ Net                │ Width (External, 1oz Cu, 10°C rise)          │
├────────────────────┼──────────────────────────────────────────────┤
│ VBUS (3A)          │ 1.5mm (59 mil)                               │
│ 5V_MAIN (2A)       │ 1.0mm (40 mil)                               │
│ 5V_SERVO (1A)      │ 0.5mm (20 mil)                               │
│ 5V_LED (0.5A)      │ 0.3mm (12 mil)                               │
│ 3V3 (0.5A)         │ 0.3mm (12 mil)                               │
│ Signal traces      │ 0.254mm (10 mil)                             │
│ I2S/High-speed     │ 0.2mm (8 mil) - controlled impedance        │
└────────────────────┴──────────────────────────────────────────────┘
```

### Impedance Control (I2S Lines)

```
Target: 50Ω single-ended for I2S signals

4-Layer Stackup Calculation:
- Trace width: 0.23mm (9 mil)
- Dielectric height to ground: 0.2mm (prepreg)
- Dielectric constant (FR4): 4.2
- Result: ~50Ω ± 10%

2-Layer (Microstrip):
- Trace width: 0.3mm (12 mil)
- Board thickness: 1.6mm
- Result: ~75Ω (acceptable for short runs)

Note: For this application, impedance matching is not critical
due to short trace lengths (<50mm). Series termination (33Ω)
handles reflections adequately.
```

### DFM (Design for Manufacturing) Rules

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Manufacturing Guidelines                        │
├─────────────────────────────────────────────────────────────────────┤
│ Pad-to-Pad Clearance:          0.2mm minimum                        │
│ Pad-to-Trace Clearance:        0.2mm minimum                        │
│ Pad-to-Via Clearance:          0.3mm minimum                        │
│ Silkscreen-to-Pad Clearance:   0.15mm minimum                       │
│ Silkscreen-to-Via Clearance:   0.15mm minimum                       │
│ Component-to-Edge Clearance:   0.5mm minimum                        │
│ Via-to-Edge Clearance:         0.5mm minimum                        │
│ Text Height (Minimum):         1.0mm for readability                │
│ Fiducials:                     3x 1mm diameter, 2mm clearance       │
│ Tooling Holes:                 2x 3.2mm NPTH for panel registration │
├─────────────────────────────────────────────────────────────────────┤
│                      Component Specific                              │
├─────────────────────────────────────────────────────────────────────┤
│ USB-C Footprint:               Use manufacturer-recommended         │
│ TSSOP-28 (PCA9685):            0.65mm pitch, 0.3mm pad width       │
│ SOT-223 (AMS1117):             Standard footprint, thermal pad     │
│ 0402 Components:               Use paste reduction (80%)            │
│ Through-hole Headers:          Standard 1.0mm holes, 1.7mm pads    │
└─────────────────────────────────────────────────────────────────────┘
```

### Assembly Notes (SMT)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PCBA Assembly Notes                             │
├─────────────────────────────────────────────────────────────────────┤
│ 1. All SMD components on TOP layer only                             │
│ 2. Through-hole components: J2, J3-J5, J10, SW1 (hand solder)      │
│ 3. Stencil thickness: 0.12mm (for 0402 + fine pitch)               │
│ 4. Reflow profile: Standard lead-free (peak 250°C)                 │
│ 5. Clean board after reflow (remove flux residue)                  │
│ 6. Conformal coating optional (for humid environments)             │
├─────────────────────────────────────────────────────────────────────┤
│                      JLCPCB Assembly Options                         │
├─────────────────────────────────────────────────────────────────────┤
│ Service:              Economic PCBA                                  │
│ Assembly Side:        Top Side                                       │
│ Tooling Holes:        Added by JLCPCB                               │
│ Confirm Parts:        Yes (review substitutions)                    │
│ Components:           Use LCSC Basic/Extended parts when possible   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. Signal Integrity Considerations

### I2S Audio Path

```
Signal Integrity Measures:
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Keep I2S traces parallel and equal length (±2mm tolerance)      │
│ 2. Route I2S on top layer with unbroken ground reference           │
│ 3. Use 33Ω series termination at source                            │
│ 4. Add ground guard traces between I2S and servo power             │
│ 5. Place bypass capacitors within 3mm of audio ICs                 │
└─────────────────────────────────────────────────────────────────────┘

I2S Trace Length Matching:
- BCLK, LRCLK, DIN, DOUT: All within ±2mm of each other
- Maximum length: 50mm (keep short)
- No layer transitions for I2S signals (stay on top)
```

### SK6812 LED Data Line

```
LED Signal Integrity:
┌─────────────────────────────────────────────────────────────────────┐
│ 1. 330Ω series resistor at Pi GPIO (reduces overshoot)             │
│ 2. 100pF capacitor to ground near connector (EMI filter)           │
│ 3. Keep trace < 100mm to first LED                                 │
│ 4. Route away from I2S and servo lines                             │
└─────────────────────────────────────────────────────────────────────┘

WS2812/SK6812 Timing Margins:
- Data rate: 800kHz
- Rise time: 150ns typical
- Cable length tolerance: Up to 5m with proper termination
```

### Power Integrity

```
Power Distribution:
┌─────────────────────────────────────────────────────────────────────┐
│ 1. USB-C input → Bulk cap (100uF) → Star distribution              │
│ 2. Each major rail has dedicated decoupling                        │
│ 3. Servo power isolated with LC filter (10uH + 470uF)              │
│ 4. Ground plane unbroken under sensitive analog (audio)            │
│ 5. Return current path considered for all power traces             │
└─────────────────────────────────────────────────────────────────────┘

Power Sequencing (handled naturally):
1. 5V available immediately from USB-C
2. 3.3V follows ~10ms after (LDO soft-start)
3. Servos remain disabled until PCA9685 ~OE released
```

---

## 7. Testing and Validation

### Test Points

```
Recommended Test Points (1mm diameter pads):
┌────────┬───────────────────────────────────────────────────────────┐
│ TP1    │ VBUS (5V input after fuse)                                │
│ TP2    │ 5V_SERVO (filtered servo power)                           │
│ TP3    │ 3V3 (regulated output)                                    │
│ TP4    │ I2C_SDA                                                   │
│ TP5    │ I2C_SCL                                                   │
│ TP6    │ I2S_BCLK                                                  │
│ TP7    │ LED_DATA                                                  │
│ TP8    │ GND (reference)                                           │
└────────┴───────────────────────────────────────────────────────────┘
```

### Bring-up Procedure

```
1. Visual Inspection
   - Check for solder bridges (especially USB-C, TSSOP-28)
   - Verify component orientation (LEDs, ICs)
   - Confirm all through-hole components seated

2. Power Test (No Pi Connected)
   - Apply 5V via USB-C
   - Verify 5V_MAIN: 5.0V ± 0.25V
   - Verify 3V3: 3.3V ± 0.1V
   - Check current draw: <10mA (no load)
   - Touch test: No hot components

3. Pi Connection Test
   - Mount Pi, power via PCB
   - Verify Pi boots normally
   - I2C scan: should find 0x40 (PCA9685)
   - GPIO test: Status LEDs toggle

4. Audio Test
   - Record via SPH0645: arecord test.wav
   - Playback via PCM5102: aplay test.wav
   - Verify no noise/hum

5. Servo Test
   - Connect servo to J3
   - Run servo sweep test
   - Verify smooth motion, no jitter

6. LED Ring Test
   - Connect SK6812 ring to J6
   - Run animation test
   - Verify all 7 LEDs, all colors
```

---

## 8. Gerber Output Settings

### JLCPCB Gerber Requirements

```
Gerber Files Required:
┌─────────────────────────────────────────────────────────────────────┐
│ File                  │ Layer              │ Extension              │
├───────────────────────┼────────────────────┼────────────────────────┤
│ Top Copper            │ GTL                │ .GTL                   │
│ Bottom Copper         │ GBL                │ .GBL                   │
│ Top Solder Mask       │ GTS                │ .GTS                   │
│ Bottom Solder Mask    │ GBS                │ .GBS                   │
│ Top Silkscreen        │ GTO                │ .GTO                   │
│ Bottom Silkscreen     │ GBO                │ .GBO                   │
│ Top Paste             │ GTP                │ .GTP                   │
│ Bottom Paste          │ GBP                │ .GBP                   │
│ Board Outline         │ GKO                │ .GKO                   │
│ Drill File            │ Excellon           │ .DRL or .XLN           │
│ Drill Map             │ ASCII              │ .DRM                   │
├───────────────────────┼────────────────────┼────────────────────────┤
│ For 4-Layer Add:      │                    │                        │
│ Inner Layer 1         │ G2L                │ .G2L                   │
│ Inner Layer 2         │ G3L                │ .G3L                   │
└───────────────────────┴────────────────────┴────────────────────────┘

Additional Files for PCBA:
- BOM.csv (with LCSC part numbers)
- CPL.csv (Component Placement List)
  Format: Designator, Mid X, Mid Y, Layer, Rotation
```

---

## 9. Revision History

| Rev  | Date       | Author  | Changes                               |
|------|------------|---------|---------------------------------------|
| 1.0  | 2026-01-02 | Kagami  | Initial design release                |

---

## 10. Design Files Location

```
/apps/hub/kagami-hub/hardware/
├── PCB_DESIGN.md          (This document)
├── schematic/
│   └── kagami_hub.kicad_sch
├── pcb/
│   └── kagami_hub.kicad_pcb
├── gerbers/
│   └── (generated output)
├── bom/
│   └── kagami_hub_bom.csv
└── 3d/
    └── kagami_hub.step
```

---

```
鏡
h(x) >= 0. Always.

Seven LEDs. Seven colonies. One voice.
The lamp breathes with the home.
```
