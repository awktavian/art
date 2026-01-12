# Kagami Orb — One-Click Buy Guide

**Version:** 2.0
**Last Updated:** January 11, 2026
**Total Prototype Cost:** ~$683 (Orb + Base)

### 📥 Download Files for Direct Upload

| File | Supplier | Action |
|------|----------|--------|
| [kagami_orb_digikey.csv](hardware/kagami_orb_digikey.csv) | Digi-Key | Upload to [BOM Manager](https://www.digikey.com/BOM/) |
| [kagami_orb_bom.csv](hardware/kagami_orb_bom.csv) | Mouser | Upload to [BOM Tool](https://www.mouser.com/bom/) |
| [kagami_orb_adafruit.txt](hardware/kagami_orb_adafruit.txt) | Adafruit | Copy product IDs |

### 🔗 Related Documents

| Document | Description |
|----------|-------------|
| [Full BOM](bom.html) | Complete component list with specs |
| [Assembly Guide](assembly.html) | Build instructions |
| [Alternatives](alternatives.html) | Component substitution options |
| [Custom PCB](custom-pcb.html) | PCB design specifications |
| [Landing Page](index.html) | Project overview |

---

## Quick Start — Order Everything in 10 Minutes

### Step 1: Digi-Key Cart (Electronics Core) — ~$180

Click to add all Digi-Key items to cart:

**[🛒 Open Digi-Key BOM Manager](https://www.digikey.com/BOM/)**

Upload this CSV or manually add:

| Qty | Part Number | Description | Unit Price |
|-----|-------------|-------------|------------|
| 1 | QCS6490-0-572CTXNSP-TR-01-0-AC | Qualcomm QCS6490 8GB WiFi | $85.00 |
| 1 | QCS6490-IO-BOARD | QCS6490 IO Board | $45.00 |
| 1 | BQ24072TRGTR | Battery Charger IC | $2.35 |
| 1 | ICM-42688-P | IMU 6-axis | $4.67 |
| 1 | TMP117MAIYBGR | Temperature Sensor | $2.23 |
| 2 | AH49E | Hall Effect Sensor | $0.80 |
| 1 | GST60A24-P1J | 24V 60W Power Supply | $18.60 |
| 1 | ESP32-S3-WROOM-1-N8R8 | Base Station MCU | $6.13 |
| 1 | IRS2011SPBF | Full-Bridge Driver | $5.00 |

**Digi-Key Subtotal: ~$132**

---

### Step 2: Adafruit Cart — ~$55

**[🛒 Add All to Adafruit Cart](https://www.adafruit.com/shopping_cart)**

| Qty | Product | Link | Price |
|-----|---------|------|-------|
| 1 | HD108 Ring 16 RGBW | [adafruit.com/product/2862](https://www.adafruit.com/product/2862) | $24.95 |
| 1 | MAX98357A I2S Amp | [adafruit.com/product/3006](https://www.adafruit.com/product/3006) | $5.95 |
| 1 | 74AHCT125 Level Shifter | [adafruit.com/product/1787](https://www.adafruit.com/product/1787) | $1.50 |
| 4 | SPH0645 I2S Mic (alt to INMP441) | [adafruit.com/product/3421](https://www.adafruit.com/product/3421) | $6.95 ea |

**Adafruit Subtotal: ~$55**

---

### Step 3: Amazon Cart — ~$80

| Qty | Item | Link | Price |
|-----|------|------|-------|
| 1 | Intel AX210 WiFi 6E M.2 | [amazon.com/dp/B08NSSJNV1](https://www.amazon.com/dp/B08NSSJNV1) | $19.99 |
| 1 | M.2 to USB Adapter | Search "M.2 WiFi USB adapter" | $8.00 |
| 2 | MHF4 WiFi Antenna | Search "MHF4 6GHz antenna" | $5.00 ea |
| 1 | Gila Two-Way Mirror Film | Search "Gila PR285" | $15.00 |
| 1 | Oracal 351 Chrome Vinyl | Search "Oracal 351 chrome" | $10.00 |
| 1 | Thermal Grizzly Pad 3mm | Search "Thermal Grizzly pad" | $8.00 |
| 1 | Arctic Silver AS-5 | [amazon.com/dp/B0087X728K](https://www.amazon.com/dp/B0087X728K) | $6.00 |
| 1 | M2 Brass Standoff Kit | Search "M2 brass standoff" | $5.00 |
| 1 | Heat Shrink Kit | Search "heat shrink tubing kit" | $5.00 |
| 1 | 20AWG Silicone Wire | Search "20AWG silicone wire" | $3.00 |
| 1 | 24AWG Silicone Wire | Search "24AWG silicone wire" | $2.00 |

**Amazon Subtotal: ~$80**

---

### Step 4: AliExpress/Alibaba — ~$95

#### AliExpress (Small Qty)

| Qty | Item | Search Term | Price |
|-----|------|-------------|-------|
| 4 | INMP441 I2S Microphone | "INMP441 I2S MEMS" | ~$12 total |
| 1 | TP4056 Module | "TP4056 USB C" | $1.00 |
| 1 | MP1584EN Buck Module | "MP1584EN 5V" | $3.00 |
| 1 | IP2721 USB-C PD Trigger | "IP2721 PD trigger" | $3.00 |

#### Alibaba (Maglev Module — CRITICAL)

| Qty | Item | Supplier | Price |
|-----|------|----------|-------|
| 1 | Magnetic Levitation DIY Module | **[HCNT on Alibaba](https://hcnt.en.alibaba.com)** | $45-55 |

**Contact HCNT directly for samples.** Ask for:
- 500g-2kg capacity DIY module
- 15mm levitation gap
- Include control board
- CE/FCC certification docs

**AliExpress/Alibaba Subtotal: ~$95**

---

### Step 5: Specialty Suppliers — ~$115

#### Battery (RC Hobby Store)

| Qty | Item | Supplier | Link | Price |
|-----|------|----------|------|-------|
| 1 | 3S 2200mAh 30C LiPo | RC Juice | [rcjuice.com](https://rcjuice.com/products/hobbystar-2200mah-11-1v-3s-30c-lipo-battery) | $15.00 |

#### Ferrite Shields (Fair-Rite via Digi-Key)

Already included in Digi-Key order above, or order separately:

| Qty | Part Number | Description | Price |
|-----|-------------|-------------|-------|
| 1 | 38M5010AA0808 | 85×85mm ferrite sheet | $14.34 |
| 1 | 3595000541 | 150×100mm ferrite plate | $28.32 |

#### Magnets (K&J Magnetics)

| Qty | Item | Link | Price |
|-----|------|------|-------|
| 1 | N52 Neodymium Ring | [kjmagnetics.com](https://www.kjmagnetics.com) | $15.00 |

#### Acrylic Domes (eBay)

| Qty | Item | Link | Price |
|-----|------|------|-------|
| 2 | 85mm Clear Acrylic Dome | [eBay](https://www.ebay.com/itm/163442152684) | $12.36 ea |

**Specialty Subtotal: ~$115**

---

### Step 6: AI Accelerator (Choose One) — ~$60

| Option | Supplier | Link | Price | Notes |
|--------|----------|------|-------|-------|
| **Hailo-10H (Recommended)** | Hailo | [hailo.ai](https://hailo.ai/products/ai-accelerators/hailo-10h/) | $70-90 | 40 TOPS, best value |
| Hailo-8L | Hailo | [hailo.ai](https://hailo.ai/products/ai-accelerators/hailo-8l-ai-accelerator-for-ai-light-applications/) | $50-70 | 13 TOPS, budget option |
| None (CPU Only) | - | - | $0 | Slower wake word |

---

### Step 7: 3D Printed Parts — ~$50

#### Option A: Form 4 (If you have one)

Print these files from `apps/hub/kagami-orb/cad/`:
- Internal Frame (Tough 2000, 50μm)
- LED Mounting Ring (Grey Pro, 25μm)
- Diffuser Ring (White, 50μm)
- Battery Cradle (Tough 2000, 50μm)
- Resonant Coil Mount (Tough 2000, 50μm)

#### Option B: Print Service

| Service | Material | Est. Cost | Lead Time |
|---------|----------|-----------|-----------|
| **JLC3DP** | MJF PA12 | $30-50 | 5-7 days |
| **Craftcloud** | MJF PA12 | $40-60 | 5-10 days |
| **Shapeways** | SLS Nylon | $40-60 | 5-10 days |

---

### Step 8: Custom Coils — ~$50

Custom Litz wire coils (RX: 70mm, TX: 80mm, ~140kHz resonant):

| Qty | Item | Supplier | Price |
|-----|------|----------|-------|
| 1 | RX Coil (20 turns, 45μH) | Request quote from [yihetimes.en.made-in-china.com](https://yihetimes.en.made-in-china.com/) | ~$25 |
| 1 | TX Coil (15 turns, 47μH) | Same supplier | ~$25 |

**Alternative:** Wind your own with Litz wire from [wurth.com](https://www.wurth.com) or [digikey.com](https://www.digikey.com)

---

### Step 9: Base Enclosure — ~$40-200

| Option | Material | Cost | Lead Time |
|--------|----------|------|-----------|
| **DIY CNC** | Walnut block from [rockler.com](https://www.rockler.com) | $40 | + your time |
| **Commission** | Xometry/Fictiv CNC walnut | $150-200 | 1-2 weeks |
| **3D Print** | MJF PA12 (temporary) | $30 | 5-7 days |

---

## Total Cost Summary

| Supplier | Subtotal |
|----------|----------|
| Digi-Key | $132 |
| Adafruit | $55 |
| Amazon | $80 |
| AliExpress/Alibaba | $95 |
| Specialty | $115 |
| AI Accelerator | $60 |
| 3D Printing | $50 |
| Custom Coils | $50 |
| Base Enclosure | $40 |
| **TOTAL (Orb + Base)** | **~$677** |

*Prices validated January 11, 2026. Actual costs may vary ±10%.*

---

## Digi-Key BOM Upload Format

Save this as `kagami_orb_digikey.csv` and upload to [Digi-Key BOM Manager](https://www.digikey.com/BOM/):

```csv
Quantity,Manufacturer Part Number,Description
1,QCS6490-0-572CTXNSP-TR-01-0-AC,Qualcomm QCS6490 8GB WiFi
1,QCS6490-IO-BOARD,QCS6490 IO Board
1,BQ24072TRGTR,Battery Charger IC
1,ICM-42688-P,IMU 6-axis
1,TMP117MAIYBGR,Temperature Sensor
2,AH49E,Hall Effect Sensor
1,GST60A24-P1J,24V 60W Power Supply
1,ESP32-S3-WROOM-1-N8R8,ESP32-S3 Module
1,IRS2011SPBF,Full-Bridge Driver
1,38M5010AA0808,Ferrite Sheet 85mm
1,3595000541,Ferrite Plate 150mm
```

---

## Mouser BOM Upload Format

Save this as `kagami_orb_mouser.csv` and upload to [Mouser BOM Tool](https://www.mouser.com/bom/):

```csv
Mouser Part Number,Quantity,Description
QCS6490-0-572CTXNSP-TR-01-0-AC,1,Qualcomm QCS6490 8GB WiFi
QCS6490-IO-BOARD,1,QCS6490 IO Board
595-BQ24072TRGTR,1,Battery Charger IC
410-ICM-42688-P,1,IMU 6-axis
595-TMP117MAIYBGR,1,Temperature Sensor
```

---

## Order Timeline

| Day | Action |
|-----|--------|
| 1 | Place Digi-Key, Adafruit, Amazon orders |
| 1 | Contact HCNT for maglev sample quote |
| 2 | Place AliExpress orders |
| 3-5 | Receive domestic orders |
| 5-7 | Request custom coil quotes |
| 7-10 | Receive 3D prints |
| 10-14 | Receive AliExpress orders |
| 14-21 | Receive maglev module |
| 21+ | Begin assembly |

---

## Supplier Contact Quick Reference

| Supplier | Contact | For |
|----------|---------|-----|
| **HCNT** | [hcnt.en.alibaba.com](https://hcnt.en.alibaba.com) | Maglev module |
| **Digi-Key** | digikey.com | Electronics |
| **Adafruit** | adafruit.com | LEDs, audio |
| **Hailo** | hailo.ai | AI accelerator |
| **JLC3DP** | jlc3dp.com | 3D printing |
| **K&J Magnetics** | kjmagnetics.com | Neodymium magnets |
| **RC Juice** | rcjuice.com | LiPo batteries |

---

## Verification Checklist

Before ordering, verify:

- [ ] QCS6490 variant matches your needs (WiFi vs Lite)
- [ ] Maglev module has 500g+ capacity and 15mm gap
- [ ] Battery connector matches BMS
- [ ] Ferrite shield diameter covers coil area
- [ ] Acrylic domes are 85mm (not larger)

---

```
h(x) ≥ 0. Always.

All prices validated January 11, 2026.
Ready to build the floating mirror.

鏡
```
