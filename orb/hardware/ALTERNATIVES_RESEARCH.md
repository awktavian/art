# Kagami Orb — Component Alternatives Research

**Last Updated:** January 2026
**Research Method:** Web search + datasheets + supplier verification
**Purpose:** Evaluate alternative components for cost optimization, risk mitigation, and upgrade paths

---

## Executive Summary

The current V3.1 design centers on the Qualcomm QCS6490 + Hailo-10H combination (52 TOPS). This research evaluates:

1. **Alternative AI SoMs** — Lower cost and/or better availability
2. **Alternative NPU Accelerators** — More options for AI compute
3. **Alternative Form Factors** — Beyond the floating sphere
4. **Competitive Analysis** — What incumbents are shipping
5. **Cost Optimization** — Budget-friendly configurations
6. **Premium Upgrades** — High-end differentiation

**Key Finding:** Multiple viable alternatives exist at each price point. The NVIDIA Jetson Orin Nano Super ($249, 67 TOPS) represents exceptional value. The Rockchip RK3588 ecosystem ($60-150, 6 TOPS) offers significant cost savings.

---

## 1. Alternative AI System-on-Modules

### Current Choice: Qualcomm QCS6490

| Spec | Value |
|------|-------|
| NPU | 12.5 TOPS |
| CPU | 8-core Kryo 670 @ 2.7GHz |
| Process | 6nm |
| Price | $200-260 (retail SoM) |
| Availability | Through 2036 |
| Form Factor | 42.5 x 35.5 x 2.7mm |

**Source:** [Thundercomm TurboX C6490](https://www.thundercomm.com/product/c6490-som/)

---

### Alternative 1: NVIDIA Jetson Orin Nano Super

| Spec | Value | vs QCS6490 |
|------|-------|------------|
| NPU | **67 TOPS** | 5.4x more |
| CPU | 6-core ARM | Fewer cores |
| GPU | Ampere | Better |
| Price | **$249** (dev kit) | Similar |
| Power | 7-25W | Higher |
| Form Factor | 69.6 x 45mm (module) | Larger |

**Pros:**
- 5x more AI compute for similar price
- Outstanding software ecosystem (NVIDIA AI stack)
- Native support for LLMs, VLMs, and generative AI
- Software upgrade for existing owners
- Available through 2032

**Cons:**
- Larger form factor (won't fit 85mm sphere)
- Higher power consumption (thermal challenge)
- Requires carrier board design
- NVIDIA ecosystem lock-in

**Integration Effort:** HIGH — Requires larger enclosure (100mm+ sphere)

**Verdict:** Best value for AI performance. Consider for premium tier or larger form factor.

**Sources:**
- [NVIDIA Jetson Orin Nano Super](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)
- [Amazon Pricing](https://www.amazon.com/NVIDIA-Jetson-Orin-Nano-Developer/dp/B0BZJTQ5YP)

---

### Alternative 2: Rockchip RK3588 / RK3588S

| Spec | Value | vs QCS6490 |
|------|-------|------------|
| NPU | **6 TOPS** | 0.5x |
| CPU | 8-core (4x A76 + 4x A55) @ 2.4GHz | Comparable |
| Process | 8nm | Similar |
| Price | **$60-150** (SBC/SoM) | 50-75% less |
| Power | 5-15W | Lower |
| Availability | Multiple vendors | Better |

**Product Options:**

| Product | RAM | NPU | Price | Source |
|---------|-----|-----|-------|--------|
| **Radxa Dragon Q6A** | 4-16GB | 12 TOPS (QCS6490) | $60+ | [CNX Software](https://www.cnx-software.com/2025/10/27/radxa-dragon-q6a-a-qualcomm-qcs6490-edge-ai-sbc-with-gbe-wifi-6-three-camera-connectors/) |
| **Orange Pi 5 Plus** | 8-32GB | 6 TOPS | $90-200 | [Amazon](https://www.amazon.com/Orange-Pi-Rockchip-Frequency-Development/dp/B0C5BZLPZN) |
| **Turing RK1** | 8-32GB | 6 TOPS | ~$100 | [Turing Pi](https://turingpi.com/product/turing-rk1/) |
| **ArmSoM AIM7** | 8GB | 6 TOPS | ~$80 | [Crowd Supply](https://www.crowdsupply.com/armsom/rk3588-ai-module7) |

**Pros:**
- Dramatically lower cost
- Multiple vendors (supply chain resilience)
- Good community support
- Jetson Nano pin-compatible options exist
- 8K video encode/decode

**Cons:**
- Half the AI compute (6 TOPS vs 12.5)
- Less mature AI software stack
- No dedicated generative AI support
- Documentation varies by vendor

**Integration Effort:** MEDIUM — Standard interfaces, but AI stack requires work

**Verdict:** Best budget option. Sufficient for voice + basic vision, not for on-device LLMs.

**Sources:**
- [Orange Pi 5](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5.html)
- [ArmSoM RK3588](https://www.crowdsupply.com/armsom/rk3588-ai-module7)

---

### Alternative 3: MediaTek Genio 700 / 1200

| Spec | Genio 700 | Genio 1200 |
|------|-----------|------------|
| NPU | 4 TOPS | 4.8 TOPS |
| CPU | 8-core (2x A78, 6x A55) | 8-core (4x A78, 4x A55) |
| Process | 6nm | 6nm |
| Price | Contact | Contact |
| Power | Low | Medium |

**Pros:**
- Industrial-grade reliability
- Long-term availability commitment
- Good multimedia (4K/8K support)
- Pin-compatible upgrade path (Genio 510 → 700)

**Cons:**
- Lower AI compute than QCS6490
- Enterprise pricing (not hobbyist-friendly)
- Less community support
- Requires SoM partner (SECO, VIA)

**Integration Effort:** HIGH — Requires industrial partnership

**Verdict:** Consider for mass production with reliability requirements.

**Sources:**
- [MediaTek Genio 700](https://genio.mediatek.com/genio-700)
- [MediaTek Genio 1200](https://genio.mediatek.com/genio-1200)

---

### Alternative 4: AMD Xilinx Kria K26

| Spec | Value | vs QCS6490 |
|------|-------|------------|
| NPU | Programmable FPGA | Different |
| CPU | 4-core A53 + FPGA fabric | Flexible |
| Process | 16nm | Older |
| Price | **$199** (KV260 kit) | Similar |
| Power | Variable | Depends on design |

**Pros:**
- Fully programmable AI accelerator
- 3x vision AI performance per watt claim
- Native ROS 2 support for robotics
- TPM 2.0 for security
- Industrial/commercial grades

**Cons:**
- Steep learning curve (Vivado toolchain)
- Lower raw CPU performance
- Requires FPGA expertise
- Larger module size

**Integration Effort:** VERY HIGH — FPGA development expertise required

**Verdict:** Only for teams with FPGA experience. Maximum flexibility but high barrier.

**Source:** [AMD Kria KV260](https://www.amd.com/en/products/system-on-modules/kria/k26/kv260-vision-starter-kit.html)

---

## 2. Alternative NPU Accelerators

### Current Choice: Hailo-10H (40 TOPS)

| Spec | Value |
|------|-------|
| Performance | 40 TOPS INT4 |
| Power | 2.5W typical |
| Interface | M.2 Key M, PCIe x4 |
| Price | ~$150-200 (estimated) |
| GenAI Support | Yes (LLMs, VLMs) |

**Source:** [Hailo-10H](https://hailo.ai/products/ai-accelerators/hailo-10h-m-2-ai-acceleration-module/)

---

### Alternative A: Hailo-8 / Hailo-8L

| Spec | Hailo-8 | Hailo-8L |
|------|---------|----------|
| Performance | 26 TOPS | 13 TOPS |
| Power | 2.5W | 1.5W |
| Interface | M.2 B+M, A+E | M.2 B+M, A+E |
| Price | ~$80-100 | ~$50-70 |
| GenAI Support | No | No |

**Pros:**
- Lower cost
- Lower power
- Available now
- Proven in Raspberry Pi ecosystem

**Cons:**
- No generative AI support
- Less compute than Hailo-10H

**Verdict:** Good for budget tier without GenAI requirements.

**Sources:**
- [Hailo-8](https://hailo.ai/products/ai-accelerators/hailo-8-m-2-ai-acceleration-module/)
- [Amazon Waveshare Hailo-8](https://www.amazon.com/Waveshare-Hailo-8-Accelerator-Compatible-Raspberry/dp/B0D9298XL5)

---

### Alternative B: Google Coral (Edge TPU)

| Spec | USB Accelerator | M.2 Dual TPU |
|------|-----------------|--------------|
| Performance | 4 TOPS | 8 TOPS |
| Power | 2.5W | 4W |
| Interface | USB 3.0 | M.2 A+E |
| Price | $60 | $40 |

**Pros:**
- Lowest cost
- Proven ecosystem
- Great for TensorFlow Lite models

**Cons:**
- **Chronic supply shortages** (scalpers charging $100+)
- Limited to 4-8 TOPS
- No generative AI support
- EOL concerns (Google's hardware commitment)

**Verdict:** Avoid due to supply issues. Hailo-8L is better value.

**Sources:**
- [Coral Products](https://www.coral.ai/products/)
- [Seeed Studio Comparison](https://www.seeedstudio.com/blog/2024/07/16/raspberry-pi-ai-kit-vs-coral-usb-accelerator-vs-coral-m-2-accelerator-with-dual-edge-tpu/)

---

### Alternative C: Intel Movidius Myriad X

| Spec | Value |
|------|-------|
| Performance | ~1 TOPS (FP32) |
| Power | 1-2W |
| Status | **DISCONTINUED** |

**Verdict:** Do not use. Product is EOL.

**Source:** [Intel Movidius Discontinued](https://www.anandtech.com/show/14295/intel-to-discontinue-movidius-neural-compute-stick)

---

### Alternative D: Raspberry Pi AI Kit (Hailo-8L)

| Spec | Value |
|------|-------|
| Performance | 13 TOPS |
| Power | ~3W |
| Interface | PCIe HAT for Pi 5 |
| Price | **$70** |

**Pros:**
- Official Raspberry Pi product
- Excellent documentation
- Works with Pi Camera ecosystem
- Available now

**Cons:**
- Requires Pi 5 as host
- Lower performance than standalone Hailo
- Not for custom integration

**Verdict:** Best starter option for prototyping.

**Source:** [Raspberry Pi AI Kit](https://www.raspberrypi.com/news/raspberry-pi-ai-kit-available-now-at-70/)

---

## 3. Alternative Form Factors

### Current: 85mm Floating Sphere

**Unique Value:** Levitation + living eye creates "presence device" category.

**Challenges:**
- Thermal constraints (sealed design)
- Weight limits (350g max for levitation)
- Cost of maglev system (~$50-180)

---

### Alternative Form Factor 1: Cube

**Examples:** Aqara Cube, Mi Magic Cube, Frame.io Status Box

| Aspect | Assessment |
|--------|------------|
| Thermal | +++Better (more surface area, vents possible) |
| Assembly | +++Easier (flat surfaces) |
| Differentiation | ---Lower (generic) |
| Cost | ++Lower (standard enclosure) |

**Use Case:** Budget tier, easier first prototype

---

### Alternative Form Factor 2: Cylinder

**Examples:** Amazon Echo, Google Home, Sonos Era

| Aspect | Assessment |
|--------|------------|
| Thermal | ++Better (chimney effect possible) |
| Assembly | +Moderate |
| Differentiation | -Lower (everyone uses this) |
| Audio | +++Better (360 sound easy) |

**Use Case:** Audio-first variant, compete directly with Echo

---

### Alternative Form Factor 3: Puck / Disc

**Examples:** Apple HomePod Mini, Echo Dot, Nest Mini

| Aspect | Assessment |
|--------|------------|
| Thermal | +OK (large bottom surface) |
| Size | +++Smallest |
| Cost | ++Lower |
| Display | ---None or tiny |

**Use Case:** Budget, low-profile assistant

---

### Alternative Form Factor 4: Pendant / Wearable

**Examples:** Humane AI Pin, Rabbit R1

| Aspect | Assessment |
|--------|------------|
| Portability | +++Maximum |
| Compute | ---Very limited |
| Battery | ---Hours only |
| Use Case | Personal companion, not home |

**Not suitable for Kagami Orb's home presence use case.**

---

### Form Factor Recommendation

| Tier | Form Factor | Reasoning |
|------|-------------|-----------|
| Premium | 100mm Floating Sphere | Maximum "wow" factor, Jetson fits |
| Standard | 85mm Floating Sphere | Current design, proven differentiator |
| Budget | 100mm Static Sphere | Remove maglev, save $50-180 |
| Economy | Cube (80mm) | Lowest cost, easiest production |

---

## 4. Competitive Product Analysis

### Amazon Echo Show 10 (3rd Gen)

| Spec | Value |
|------|-------|
| Price | $250 |
| Display | 10.1" LCD 1280x800 |
| Processor | MediaTek MT8183 |
| AI | Cloud-dependent |
| Differentiator | Rotating display follows user |
| BOM Cost (est.) | ~$100-120 |

**Source:** [Hackaday Teardown](https://hackaday.io/project/178825-amazon-echo-show-10-3rd-gen-teardown)

**Key Insight:** Uses custom motor assembly for rotation. Heavy cloud dependence keeps hardware simple and cheap.

---

### Google Nest Hub Max

| Spec | Value |
|------|-------|
| Price | $229 |
| Display | 10" LCD 1280x800 |
| Processor | Amlogic T931 |
| RAM | 2GB |
| AI | Cloud + on-device wake word |
| Differentiator | Nest camera integration |

**Source:** [TechInsights Deep Dive](https://www.techinsights.com/products/ddt-1909-802)

**Key Insight:** Simple SoC, minimal local AI. Value is in Google's cloud AI.

---

### Apple HomePod (Original)

| Spec | Value |
|------|-------|
| Price | $349 |
| Processor | Apple A8 |
| RAM | 1GB |
| Speakers | 8 (7 tweeters + 1 woofer) |
| BOM Cost | **$216** |
| Margin | 29% |

**Source:** [TechInsights BOM Analysis](https://www.techinsights.com/blog/apple-homepod-teardown-and-cost-comparison)

**Key Insight:** Apple's lowest margin product. 8 speakers = premium audio differentiator.

---

### Rabbit R1

| Spec | Value |
|------|-------|
| Price | $199 |
| Display | 2.88" touchscreen |
| Weight | 115g |
| AI | Cloud (Large Action Model) |
| Differentiator | Pocket-sized, no subscription |

**Source:** [Rabbit R1](https://www.rabbit.tech/rabbit-r1)

**Key Insight:** Minimalist hardware, value is in AI software. Mixed reception.

---

### Competitive Position Summary

| Product | Local AI | Display | Unique Feature | Price |
|---------|----------|---------|----------------|-------|
| Echo Show 10 | No | 10.1" | Rotating screen | $250 |
| Nest Hub Max | Minimal | 10" | Camera/doorbell | $229 |
| HomePod | No | None | 8-speaker array | $299 |
| Rabbit R1 | No | 2.88" | Pocket-size | $199 |
| **Kagami Orb** | **52 TOPS** | 1.39" eye | **Levitation + eye** | ~$1,100 |

**Kagami Orb Differentiation:**
1. **On-device AI** — Privacy-first, no cloud dependency
2. **Living eye** — Emotional presence, not faceless
3. **Levitation** — "Wow" factor, premium positioning
4. **High-end camera** — 50MP IMX989 for vision AI

---

## 5. Cost Optimization Opportunities

### Current V3.1 Cost Breakdown (Prototype)

| Category | Cost | % |
|----------|------|---|
| Core Compute (QCS6490 + Hailo-10H) | $350-460 | 35% |
| Display + Camera | $110-150 | 12% |
| Audio (sensiBel + XMOS) | $160-250 | 18% |
| Sensors | $104 | 10% |
| Power (battery + WPT) | $79 | 8% |
| Enclosure | $115 | 11% |
| Thermal + misc | $62 | 6% |
| **TOTAL ORB** | **$980-1,220** | 100% |
| Base Station | $184 | — |
| **SYSTEM** | **$1,164-1,404** | — |

---

### Optimization Strategy 1: Cheaper SoM

| Change | Cost Impact | Performance Impact |
|--------|-------------|-------------------|
| QCS6490 → Orange Pi 5 Plus | -$150-200 | -50% NPU (12.5→6 TOPS) |
| Keep Hailo-8L (or remove) | -$50-100 | Lose 40 TOPS or 13 TOPS |

**Savings:** $200-300
**New ORB Cost:** ~$680-920

---

### Optimization Strategy 2: Cheaper Audio

| Change | Cost Impact | Performance Impact |
|--------|-------------|-------------------|
| sensiBel → Infineon IM69D130 | -$100+ | Lower SNR (80→69dB) |
| Keep XMOS for beamforming | $0 | Maintains quality |

**Savings:** $100
**Tradeoff:** Slightly worse far-field pickup

---

### Optimization Strategy 3: Remove Maglev

| Change | Cost Impact | Experience Impact |
|--------|-------------|-------------------|
| Maglev → Static cradle | -$50-180 | Loses "wow" factor |

**Savings:** $50-180
**Tradeoff:** Major differentiation loss. Consider only for budget tier.

---

### Optimization Strategy 4: Smaller Display

| Change | Cost Impact | Experience Impact |
|--------|-------------|-------------------|
| 1.39" AMOLED → 1.28" | -$5-10 | Slightly smaller eye |

**Savings:** Minimal. Not worth pursuing.

---

## 6. Premium Upgrade Paths

### Upgrade 1: Jetson Orin Nano Super

| Change | Cost Impact | Performance Impact |
|--------|-------------|-------------------|
| QCS6490 + Hailo-10H → Jetson Orin Nano | -$50-100 | +15-25 TOPS net |
| Requires larger sphere (100mm+) | +$20-50 | More thermal headroom |

**Net Cost:** Similar or lower
**Performance:** 67 TOPS (vs 52 TOPS), better GenAI
**Tradeoff:** Larger device, more power hungry

---

### Upgrade 2: Enhanced Camera

| Change | Cost Impact | Experience Impact |
|--------|-------------|-------------------|
| IMX989 50MP → IMX800 OIS | +$30-50 | Better low-light |
| Add IR illuminators | +$10 | Night vision |

**Use Case:** Security camera functionality

---

### Upgrade 3: Premium Audio

| Change | Cost Impact | Experience Impact |
|--------|-------------|-------------------|
| 1 speaker → 4 speakers | +$60 | 360 sound |
| Add sub driver | +$25 | Better bass |
| Upgrade to Tectonic TEBM46 | +$30 | Premium BMR sound |

**Use Case:** Audiophile tier

---

### Upgrade 4: Larger Display

| Change | Cost Impact | Experience Impact |
|--------|-------------|-------------------|
| 1.39" → 2.8" round AMOLED | +$50-100 | Requires 100mm+ sphere |

**Tradeoff:** Major enclosure redesign

---

## 7. BOM Comparison Tables

### Budget Tier ($150 Target)

*Note: $150 is extremely aggressive. Achievable only with major feature cuts.*

| Component | Choice | Cost |
|-----------|--------|------|
| SoM | Raspberry Pi 5 (4GB) | $60 |
| NPU | None (CPU inference) | $0 |
| Display | 1.28" AMOLED | $15 |
| Camera | OV5647 5MP | $8 |
| Audio | SPH0645 x2 | $4 |
| Speaker | Generic 28mm | $3 |
| Sensors | BME280 + IMU only | $8 |
| Power | 1S LiPo 3000mAh | $10 |
| Enclosure | 3D printed 80mm | $15 |
| Base | Static cradle | $20 |
| Misc | Cables, connectors | $15 |
| **TOTAL** | | **~$158** |

**Performance:** ~0.5 TOPS (CPU), basic voice, no on-device LLM
**Form Factor:** Static 80mm sphere
**Target User:** Hobbyist/maker

---

### Standard Tier ($300 Target)

| Component | Choice | Cost |
|-----------|--------|------|
| SoM | Orange Pi 5 (8GB) | $90 |
| NPU | Hailo-8L (13 TOPS) | $70 |
| Display | 1.39" AMOLED | $25 |
| Camera | IMX219 8MP | $25 |
| Audio | IM69D130 x4 | $32 |
| DSP | None (software) | $0 |
| Speaker | 28mm BMR | $10 |
| Sensors | ToF + IMU + env | $25 |
| Power | 2S LiPo 2000mAh | $15 |
| Enclosure | 85mm acrylic | $35 |
| Base | Static with LEDs | $35 |
| Misc | PCB, cables | $40 |
| **TOTAL** | | **~$302** |

**Performance:** 19 TOPS (6 SoC + 13 Hailo), good voice, basic vision
**Form Factor:** Static 85mm sphere
**Target User:** Enthusiast, smart home user

---

### Premium Tier ($500 Target)

| Component | Choice | Cost |
|-----------|--------|------|
| SoM | Radxa Dragon Q6A (QCS6490, 8GB) | $100 |
| NPU | Hailo-8 (26 TOPS) | $100 |
| Display | 1.39" AMOLED | $25 |
| Camera | IMX989 50MP | $95 |
| Audio | Infineon IM69D130 x4 | $32 |
| DSP | XMOS XVF3800 | $50 |
| Speaker | Tectonic TEBM28C | $25 |
| Sensors | Full suite (radar + ToF + spectral) | $55 |
| Power | 3S LiPo 2200mAh | $22 |
| WPT | Custom resonant coils | $50 |
| Enclosure | 85mm acrylic premium | $50 |
| Base | Maglev (500g DIY) | $50 |
| Misc | PCB, thermal, cables | $55 |
| **TOTAL** | | **~$509** |

**Performance:** 38.5 TOPS (12.5 SoC + 26 Hailo), on-device voice + vision
**Form Factor:** Levitating 85mm sphere
**Target User:** Premium consumer, early adopter

---

### Founder's Edition ($1,100 Current)

| Component | Choice | Cost |
|-----------|--------|------|
| SoM | Thundercomm TurboX C6490 | $230 |
| NPU | Hailo-10H (40 TOPS) | $150 |
| Display | 1.39" AMOLED | $25 |
| Camera | IMX989 50MP | $95 |
| Audio | sensiBel SBM100B x4 | $120 |
| DSP | XMOS XVF3800 | $99 |
| Speaker | Tectonic TEBM28C | $25 |
| Sensors | Full V3.1 suite | $104 |
| Power | 3S LiPo 2200mAh + BMS | $32 |
| WPT | Full resonant system | $80 |
| Thermal | Graphite + heatsinks | $20 |
| Enclosure | 85mm premium acrylic | $75 |
| Base | HCNT 500g maglev | $50 |
| Base enclosure | CNC walnut | $40 |
| Base electronics | ESP32 + TX + LEDs | $45 |
| **TOTAL** | | **~$1,090** |

**Performance:** 52.5 TOPS, on-device GenAI capable
**Form Factor:** Levitating 85mm sphere with premium finish
**Target User:** Tech enthusiast, design connoisseur

---

## 8. Recommendations

### Immediate Actions

1. **Prototype Standard Tier ($300)**
   - Orange Pi 5 + Hailo-8L
   - Static base (no maglev)
   - Validates software stack at lower cost

2. **Secure Hailo-10H Samples**
   - Contact Hailo for quote and samples
   - Pricing is critical unknown

3. **Evaluate Jetson Orin Nano Super**
   - Order dev kit ($249)
   - Test GenAI performance
   - Assess thermal in 100mm sphere

### Strategic Recommendations

| Price Point | Recommendation | Rationale |
|-------------|----------------|-----------|
| **$150** | Do not pursue | Too compromised to be compelling |
| **$300** | "Kagami Lite" | Entry point, static, proves concept |
| **$500** | "Kagami Standard" | Sweet spot for enthusiasts |
| **$1,100** | "Kagami Founder's" | Current design, premium positioning |
| **$1,500** | "Kagami Pro" | Jetson-based, 100mm sphere, assembled |

### Risk Mitigation

| Risk | Current Exposure | Mitigation |
|------|------------------|------------|
| Hailo-10H pricing/availability | HIGH | Qualify Hailo-8 as fallback |
| QCS6490 MOQ (10 units) | MEDIUM | Use Radxa Dragon Q6A ($60+) |
| sensiBel availability | HIGH | Infineon IM69D130 qualified |
| Maglev supply | LOW | Multiple AliExpress vendors |

---

## Sources

### AI SoMs
- [Thundercomm TurboX C6490](https://www.thundercomm.com/product/c6490-som/)
- [NVIDIA Jetson Orin Nano Super](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)
- [Radxa Dragon Q6A](https://www.cnx-software.com/2025/10/27/radxa-dragon-q6a-a-qualcomm-qcs6490-edge-ai-sbc-with-gbe-wifi-6-three-camera-connectors/)
- [Orange Pi 5](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-5.html)
- [AMD Kria KV260](https://www.amd.com/en/products/system-on-modules/kria/k26/kv260-vision-starter-kit.html)
- [MediaTek Genio](https://genio.mediatek.com/)

### NPU Accelerators
- [Hailo Products](https://hailo.ai/products/ai-accelerators/)
- [Google Coral](https://www.coral.ai/products/)
- [Raspberry Pi AI Kit](https://www.raspberrypi.com/news/raspberry-pi-ai-kit-available-now-at-70/)

### Competitive Products
- [TechInsights HomePod Teardown](https://www.techinsights.com/blog/apple-homepod-teardown-and-cost-comparison)
- [Echo Show 10 Teardown](https://hackaday.io/project/178825-amazon-echo-show-10-3rd-gen-teardown)
- [Rabbit R1](https://www.rabbit.tech/rabbit-r1)

### Levitation Products
- [RUIXINDA Levitating Speaker](https://www.amazon.com/Magnetic-Levitating-Rotation-Floating-Bluetooth/dp/B091LWX7Z8)
- [Floately NEBULA](https://www.floately.com/products/nebula-bluetooth-speaker)

---

**Document Status:** RESEARCH COMPLETE
**Next Action:** Prototype Standard Tier for validation
**Author:** Kagami (鏡)
