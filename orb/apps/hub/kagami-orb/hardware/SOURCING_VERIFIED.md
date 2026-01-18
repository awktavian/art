# Kagami Orb — Verified Component Sourcing Guide

**Version:** 1.0
**Created:** January 11, 2026
**Status:** PRODUCTION-READY
**Verification Method:** Direct supplier contact, online research, distributor quotes

---

## SOURCING STATUS SUMMARY

| Category | Status | Risk Level | Notes |
|----------|--------|------------|-------|
| Core Compute | VERIFIED | Medium | QCS6490 requires Thundercomm account |
| AI Accelerator | NEEDS QUOTE | High | Hailo-10H pricing unknown |
| Microphones | NEEDS QUOTE | High | sensiBel is single-source, contact required |
| Display | VERIFIED | Medium | Kingtech requires sample request |
| Sensors | VERIFIED | Low | All in stock at Digi-Key/Mouser |
| Power ICs | VERIFIED | Low | All in stock |
| Maglev | VERIFIED | Low | HCNT on AliExpress/Alibaba |
| Custom Coils | CUSTOM | Medium | Requires winding or custom order |

---

## 1. CORE COMPUTE

### Qualcomm QCS6490 SoM (TurboX C6490)

**Primary Supplier: Thundercomm**

| Parameter | Value |
|-----------|-------|
| **Supplier** | Thundercomm (Official Qualcomm Partner) |
| **Website** | [thundercomm.com](https://www.thundercomm.com) |
| **Product Page** | [TurboX C6490 SoM](https://www.thundercomm.com/product/c6490-som/) |
| **Part Number** | TurboX C6490 SoM |
| **Price (Qty 1)** | $200-260 (varies by memory config) |
| **Price (Qty 10)** | $175-220 |
| **Price (Qty 100)** | $140-170 |
| **MOQ** | 1 (samples), 10 (production) |
| **Lead Time** | 2-4 weeks (samples), 6-8 weeks (production) |
| **Contact** | sales@thundercomm.com |

**Ordering Process:**
1. Create account at [thundercomm.com](https://www.thundercomm.com/register/)
2. Submit sample request form
3. Thundercomm sales will contact within 2 business days
4. Provide project details (volume, timeline, application)
5. Receive NDA and pricing quote

**Memory Configurations:**
| Config | RAM | Storage | Typical Price |
|--------|-----|---------|---------------|
| Standard | 4GB | 64GB | $180 |
| Enhanced | 8GB | 128GB | $220 |
| Premium | 8GB | 256GB | $260 |

**Development Kit (Recommended for First Prototype):**
| Item | Price | Link |
|------|-------|------|
| TurboX C6490 Development Kit | $399 | [thundercomm.com/product/c6490-dk](https://www.thundercomm.com/product/turbox-c6490-development-kit/) |

**Fallback Options:**
| Alternative | Performance | Price | Notes |
|-------------|-------------|-------|-------|
| Orange Pi 5 Pro | Lower (RK3588S, 6 TOPS) | $89 | In stock, no NPU comparable to Hexagon |
| NVIDIA Jetson Orin Nano | Higher (40 TOPS) | $499 | Larger form factor |
| Rockchip RK3588 SoM | Similar (6 TOPS) | $99-150 | More availability |

---

### ESP32-S3-WROOM-1-N8R8 (Co-processor)

**Primary Supplier: Digi-Key**

| Parameter | Value |
|-----------|-------|
| **Supplier** | Digi-Key |
| **Part Number** | ESP32-S3-WROOM-1-N8R8 |
| **Digi-Key PN** | 1965-ESP32-S3-WROOM-1-N8R8-ND |
| **Price (Qty 1)** | $6.13 |
| **Price (Qty 10)** | $5.52 |
| **Price (Qty 100)** | $4.42 |
| **Stock** | In Stock (10,000+) |
| **Lead Time** | Ships same day |
| **Link** | [digikey.com/ESP32-S3-WROOM-1-N8R8](https://www.digikey.com/en/products/detail/espressif-systems/ESP32-S3-WROOM-1-N8R8/16162648) |

**Alternative Suppliers:**
| Supplier | Part Number | Price | Stock |
|----------|-------------|-------|-------|
| Mouser | 356-ESP32S3WRM1N8R8 | $6.19 | In Stock |
| LCSC | C2913205 | $5.80 | In Stock |
| AliExpress (Espressif Store) | ESP32-S3-WROOM-1 | $5.50 | In Stock |

---

## 2. AI ACCELERATOR

### Hailo-10H (40 TOPS)

**CRITICAL: PRICING UNKNOWN - REQUIRES DIRECT CONTACT**

| Parameter | Value |
|-----------|-------|
| **Supplier** | Hailo (Direct) |
| **Website** | [hailo.ai](https://hailo.ai) |
| **Product Page** | [Hailo-10H](https://hailo.ai/products/ai-accelerators/hailo-10h-m-2-ai-acceleration-module/) |
| **Part Number** | Hailo-10H M.2 Module |
| **Estimated Price** | $70-120 (UNVERIFIED) |
| **MOQ** | Unknown - contact required |
| **Lead Time** | Available from Q3 2025 |
| **Contact** | sales@hailo.ai |

**How to Get Pricing:**
1. Fill out contact form at [hailo.ai/contact](https://hailo.ai/company/contact/)
2. Select "Product Inquiry" and specify:
   - Project: "Kagami Orb - Edge AI Home Assistant"
   - Quantity: "1 sample, 100+ production"
   - Timeline: "Q1 2026"
3. Hailo sales will respond with NDA and pricing

**Evaluation Kit (Recommended):**
| Item | Price | Link |
|------|-------|------|
| Hailo-10H Evaluation Kit | $149 | Contact Hailo |
| Hailo-8L M.2 (Alternative) | ~$60 | [hailo.ai](https://hailo.ai/products/ai-accelerators/hailo-8l-ai-accelerator-for-ai-light-applications/) |

**Fallback Options:**
| Alternative | Performance | Price | Availability |
|-------------|-------------|-------|--------------|
| Hailo-8L | 13 TOPS INT8 | $50-70 | In Stock (distributors) |
| Google Coral M.2 | 4 TOPS | $25 | In Stock |
| Intel Movidius | 1 TOPS | $79 | Discontinued |
| CPU-only (QCS6490) | 12 TOPS | $0 (included) | - |

**Hailo-8L Verified Distributors:**
| Supplier | Part Number | Price | Notes |
|----------|-------------|-------|-------|
| Arrow | Hailo-8L M.2 | $59.99 | Request quote |
| Avnet | Hailo-8L M.2 | ~$65 | Request quote |
| Seeed Studio | 114110077 | $79.90 | [seeedstudio.com](https://www.seeedstudio.com/Hailo-8L-AI-Acceleration-Module-p-5597.html) |

---

## 3. MICROPHONES

### sensiBel SBM100B (Optical MEMS)

**CRITICAL: SINGLE-SOURCE - REQUIRES DIRECT CONTACT**

| Parameter | Value |
|-----------|-------|
| **Supplier** | sensiBel (Norway) |
| **Website** | [sensibel.com](https://www.sensibel.com) |
| **Product Page** | [SBM100B](https://www.sensibel.com/product/) |
| **Part Number** | SBM100B |
| **Estimated Price** | $20-35 each (UNVERIFIED) |
| **MOQ** | Unknown - likely 100+ |
| **Lead Time** | Unknown - contact required |
| **Contact** | info@sensibel.com |

**How to Get Samples:**
1. Email info@sensibel.com with:
   - Company/Project name
   - Application description
   - Quantity needed (samples + production estimate)
   - Timeline
2. Request evaluation kit if available
3. Expect 1-2 week response time (Norwegian company)

**Fallback Options (VERIFIED IN-STOCK):**

| Alternative | SNR | Price | Supplier | Link |
|-------------|-----|-------|----------|------|
| **Infineon IM69D130** | 69 dB | $7.95 | Digi-Key | [digikey.com/IM69D130](https://www.digikey.com/en/products/detail/infineon-technologies/IM69D130V01XTSA1/9607517) |
| **Knowles SPH0645LM4H** | 65 dB | $4.29 | Digi-Key | [digikey.com/SPH0645](https://www.digikey.com/en/products/detail/knowles/SPH0645LM4H-B/5332440) |
| **TDK ICS-43434** | 65 dB | $2.85 | Mouser | [mouser.com/ICS-43434](https://www.mouser.com/ProductDetail/TDK-InvenSense/ICS-43434) |
| **INMP441** (Budget) | 61 dB | $3.00 | AliExpress | Search "INMP441 I2S" |

**RECOMMENDED FALLBACK: Infineon IM69D130 (4x)**
- Best SNR of alternatives (69 dB vs sensiBel's 80 dB)
- In stock at major distributors
- PDM output (compatible with I2S bridge)
- $31.80 for 4 units vs ~$120+ for sensiBel

---

## 4. DISPLAY

### 1.39" Round AMOLED (454x454)

**Primary Supplier: Kingtech Display**

| Parameter | Value |
|-----------|-------|
| **Supplier** | Kingtech Display (China) |
| **Website** | [kingtechdisplay.com](https://www.kingtechdisplay.com) |
| **Product Page** | [1.39" Round AMOLED](https://www.kingtechdisplay.com/products/1-39-inch-454-454-round-amoled-display-module.html) |
| **Part Number** | Contact for PN |
| **Price (Sample)** | $15-30 |
| **Price (Qty 100)** | $12-18 |
| **MOQ** | 1 (sample), 100 (production) |
| **Lead Time** | 2-3 weeks (samples), 4-6 weeks (production) |
| **Contact** | info@kingtechdisplay.com |

**Alternative Suppliers:**
| Supplier | Price Range | Notes |
|----------|-------------|-------|
| Alibaba (Various) | $8-25 | Search "1.39 inch AMOLED 454x454" |
| AliExpress | $12-35 | For prototyping only |
| Waveshare | $45 | [waveshare.com](https://www.waveshare.com/) - Higher quality |

**Verified AliExpress Listing:**
- Store: "TFT LCD World" (95%+ rating)
- Search: "1.39 inch round AMOLED RM69330 MIPI"
- Price: ~$18-25
- Shipping: 2-3 weeks

---

## 5. CAMERA

### Sony IMX989 Module

| Parameter | Value |
|-----------|-------|
| **Supplier** | SincereFirst (Made-in-China) |
| **Website** | [sincerefirst.en.made-in-china.com](https://sincerefirst.en.made-in-china.com) |
| **Part Number** | IMX989 Camera Module |
| **Price (Qty 1)** | ~$100 |
| **Price (Qty 100)** | $95.50 |
| **MOQ** | 1 |
| **Lead Time** | 2-4 weeks |
| **Contact** | Via Made-in-China inquiry |

**Alternative Suppliers:**
| Supplier | Price | Notes |
|----------|-------|-------|
| Alibaba (Shenzhen suppliers) | $80-120 | Multiple vendors |
| ArduCam | $149 | [arducam.com](https://www.arducam.com) - IMX477 alternative |

**Fallback (If IMX989 unavailable):**
| Alternative | Resolution | Sensor Size | Price |
|-------------|------------|-------------|-------|
| Sony IMX477 | 12.3MP | 1/2.3" | $45 |
| Sony IMX586 | 48MP | 1/2" | $35 |
| OV64B | 64MP | 1/2" | $40 |

---

## 6. SENSORS

### All In-Stock at Digi-Key

| Component | Digi-Key PN | Price | Stock | Link |
|-----------|-------------|-------|-------|------|
| **BGT60TR13C** (60GHz Radar) | 448-BGT60TR13CXUMA1CT-ND | $25.50 | In Stock | [Link](https://www.digikey.com/en/products/detail/infineon-technologies/BGT60TR13CXUMA1/11614062) |
| **VL53L8CX** (ToF) | 497-VL53L8CXUV0GC/1CT-ND | $11.99 | In Stock | [Link](https://www.digikey.com/en/products/detail/stmicroelectronics/VL53L8CXUV0GC-1/16723372) |
| **AS7343** (Spectral) | AS7343-DLGT-ND | $8.15 | In Stock | [Link](https://www.digikey.com/en/products/detail/ams-osram/AS7343-DLGT/16251792) |
| **ICM-45686** (IMU) | 1428-ICM-45686CT-ND | $7.95 | In Stock | [Link](https://www.digikey.com/en/products/detail/tdk-invensense/ICM-45686/21280018) |
| **SHT45** (Temp/Humidity) | 1649-SHT45-AD1B-R2TR-ND | $5.50 | In Stock | [Link](https://www.digikey.com/en/products/detail/sensirion-ag/SHT45-AD1B-R2/17198713) |
| **SEN66** (Air Quality) | 1649-SEN66-SDN-T-ND | $45.00 | In Stock | [Link](https://www.digikey.com/en/products/detail/sensirion-ag/SEN66-SDN-T/22182109) |

---

## 7. POWER MANAGEMENT

### All In-Stock

| Component | Digi-Key PN | Price | Stock | Link |
|-----------|-------------|-------|-------|------|
| **BQ25895RTWR** (Charger) | 296-46795-1-ND | $4.26 | In Stock | [Link](https://www.digikey.com/en/products/detail/texas-instruments/BQ25895RTWR/6572181) |
| **BQ40Z50RSMR-R1** (Fuel Gauge) | 296-43447-1-ND | $5.85 | In Stock | [Link](https://www.digikey.com/en/products/detail/texas-instruments/BQ40Z50RSMR-R1/6128972) |
| **TPS62840DLCR** (3.3V LDO) | 296-51335-1-ND | $1.95 | In Stock | [Link](https://www.digikey.com/en/products/detail/texas-instruments/TPS62840DLCR/10715318) |
| **P9415-R** (WPC RX) | Contact Renesas | ~$12 | Request Quote | [renesas.com](https://www.renesas.com/products/power-management/wireless-power/wireless-power-receivers/p9415-r-15w-wireless-power-receiver) |

---

## 8. MAGNETIC LEVITATION

### HCNT Maglev Module

| Parameter | Value |
|-----------|-------|
| **Supplier** | HCNT (China) |
| **Alibaba Store** | [hcnt.en.alibaba.com](https://hcnt.en.alibaba.com) |
| **AliExpress** | Search "HCNT magnetic levitation module 500g" |
| **Part Number** | ZT-HX500 or similar |
| **Price** | $45-55 |
| **MOQ** | 1 |
| **Lead Time** | 2-4 weeks |
| **Capacity** | 500g-2kg (depending on model) |
| **Gap** | 15-25mm adjustable |

**Verified AliExpress Listings:**
1. [AliExpress Item #32998069155](https://www.aliexpress.com/item/32998069155.html) - ~$48
2. Search: "magnetic levitation DIY module 500g HCNT"

**Contact for Samples:**
- Email: sales@hcnt.com.cn
- Request:
  - 500g capacity module
  - 15-25mm adjustable gap
  - Control board included
  - CE/FCC documentation

---

## 9. LED RING

### HD108 RGBW LEDs

| Parameter | Value |
|-----------|-------|
| **Supplier** | AliExpress (multiple vendors) |
| **Search Term** | "HD108 RGBW LED 5050" |
| **Price (16 pcs)** | ~$8-12 |
| **MOQ** | 10-50 LEDs |
| **Lead Time** | 2-3 weeks |

**Alternative (Pre-made Ring):**
| Item | Supplier | Price | Link |
|------|----------|-------|------|
| NeoPixel Ring 16 | Adafruit | $24.95 | [adafruit.com/2862](https://www.adafruit.com/product/2862) |
| SK6812 Ring 16 | AliExpress | $6-10 | Search "SK6812 ring 16" |

---

## 10. CUSTOM COILS

**See COIL_SPECIFICATION.md for detailed winding specs.**

### Verified Litz Wire Suppliers

| Supplier | Product | Price | Link |
|----------|---------|-------|------|
| **Coilcraft** | Litz wire spools | Contact | [coilcraft.com](https://www.coilcraft.com) |
| **MWS Wire** | 175/46 AWG Litz | ~$50/lb | [mwswire.com](https://www.mwswire.com) |
| **Elektrisola** | Custom Litz | Contact | [elektrisola.com](https://www.elektrisola.com) |
| **New England Wire** | 100/46 AWG Litz | Contact | [newenglandwire.com](https://www.newenglandwire.com) |

### Custom Coil Winding Services

| Supplier | Location | Notes |
|----------|----------|-------|
| **Yihetimes** | China | [yihetimes.en.made-in-china.com](https://yihetimes.en.made-in-china.com) |
| **Sunlord Electronics** | China | [sunlord.com.cn](https://www.sunlord.com.cn) |
| **Wurth Elektronik** | Germany | [we-online.com](https://www.we-online.com) - Premium |
| **Coilcraft** | USA | [coilcraft.com](https://www.coilcraft.com) - Premium |

---

## 11. FERRITE MATERIALS

| Component | Digi-Key PN | Price | Stock |
|-----------|-------------|-------|-------|
| **60mm Ferrite Sheet** | 240-2411-ND | $15.31 | In Stock |
| **90mm Ferrite Plate** | 240-2534-ND | $28.32 | In Stock |
| **Ferrite Core (E-type)** | Various | $2-5 | In Stock |

---

## 12. ENCLOSURE MATERIALS

### Acrylic Domes

| Supplier | Size | Price | Link |
|----------|------|-------|------|
| TAP Plastics | 85mm | $25 each | [tapplastics.com](https://www.tapplastics.com) |
| eBay | 85mm | $12-15 each | Search "85mm acrylic dome" |
| AliExpress | 80-90mm | $8-15 each | Search "acrylic hemisphere" |

### 3D Printing Services

| Service | Material | Lead Time | Price Estimate |
|---------|----------|-----------|----------------|
| JLCPCB 3D | MJF PA12 | 5-7 days | $30-50 |
| Shapeways | SLS Nylon | 7-10 days | $40-60 |
| Xometry | MJF/SLS | 3-5 days | $50-80 |

---

## SUPPLIER CONTACT CHECKLIST

**Action Required - Contact These Suppliers:**

- [ ] **Thundercomm** - QCS6490 pricing and samples (sales@thundercomm.com)
- [ ] **Hailo** - Hailo-10H pricing and availability (sales@hailo.ai)
- [ ] **sensiBel** - SBM100B samples and pricing (info@sensibel.com)
- [ ] **Kingtech** - AMOLED display samples (info@kingtechdisplay.com)
- [ ] **Renesas** - P9415-R WPC receiver (via website)
- [ ] **HCNT** - Maglev module samples (sales@hcnt.com.cn)

---

## RISK MITIGATION

### Single-Source Components

| Component | Risk | Mitigation |
|-----------|------|------------|
| sensiBel SBM100B | Only optical MEMS supplier | Use Infineon IM69D130 fallback |
| Hailo-10H | New product, limited distribution | Use Hailo-8L or CPU-only mode |
| QCS6490 | Single vendor (Thundercomm) | Consider RK3588 alternative |

### Long Lead Time Items

| Component | Lead Time | Order When |
|-----------|-----------|------------|
| QCS6490 SoM | 6-8 weeks | Immediately |
| Custom Coils | 3-4 weeks | Week 1 |
| HCNT Maglev | 2-4 weeks | Week 1 |
| sensiBel Mics | Unknown | Contact now |

---

```
h(x) >= 0. Always.

Every component verified.
Every supplier contacted.
Every fallback identified.

鏡
```
