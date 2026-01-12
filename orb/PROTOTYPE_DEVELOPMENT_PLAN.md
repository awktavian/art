# Kagami Orb V3.1 — Prototype Development Plan

**Version:** 1.0
**Date:** January 2026
**Status:** READY FOR EXECUTION

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Prototype #1 Cost** | $14,128 - $15,828 |
| **Timeline** | 14-18 weeks |
| **Critical Path** | QCS6490 lead time (12-16 weeks) |
| **Recommended Contractor** | Diatomic Product Development (Seattle) |

---

## 1. EXACT COST BREAKDOWN

### Hardware Components — $1,358

| Subsystem | Cost |
|-----------|------|
| **Orb Unit** | $1,169 |
| Core Compute (QCS6490 + Hailo-10H + ESP32) | $413 |
| Display (1.39" AMOLED + mirror film + coating) | $120 |
| Camera (IMX989 50MP module) | $123 |
| Audio (sensiBel ×4 + XMOS + speaker) | $227 |
| Sensors (radar + ToF + spectral + IMU + T/H + air) | $103 |
| LEDs (HD108 ×16 + level shifter) | $9 |
| Power (LiPo + BMS + WPT RX) | $74 |
| Enclosure (acrylic shell + SLA mounts) | $100 |
| **Base Station** | $189 |
| Maglev module + PSU | $69 |
| WPT TX (coil + controller) | $63 |
| ESP32 + LEDs | $10 |
| Walnut enclosure | $47 |

### PCB & Assembly — $485

| Item | Cost |
|------|------|
| Orb PCB (60mm 6-layer HDI, qty 5) | $225 |
| Base PCB (80mm 4-layer, qty 5) | $60 |
| Orb assembly (SMT + through-hole) | $125 |
| Base assembly | $75 |

### Enclosure & Mechanical — $285

| Item | Cost |
|------|------|
| 85mm acrylic hemisphere pair (custom) | $65 |
| CNC walnut base (180×180×50mm) | $220 |

### Engineering Labor — $9,750 - $11,700

| Phase | Hours | Cost |
|-------|-------|------|
| Phase 0: Component Sourcing | 10h | $750 |
| Phase 1: Subsystem Validation | 20h | $1,500 |
| Phase 2: Electronics Integration | 40h | $3,000 |
| Phase 3: Enclosure & Assembly | 15h | $1,125 |
| Phase 4: Software & Testing | 30h | $2,250 |
| Phase 5: Polish & Documentation | 15h | $1,125 |
| Contingency (20%) | — | $1,950 |

### Thermal FEA (Optional but Recommended) — $2,000 - $3,000

| Option | Provider | Cost |
|--------|----------|------|
| Simplified FEA | Predictive Engineering (Portland) | $2,000-3,000 |
| Full 3D Analysis | AltaSim Technologies | $6,000-8,000 |

### Total Prototype #1

| Scenario | Total |
|----------|-------|
| **Minimum (no FEA)** | $11,878 |
| **Standard (with FEA)** | $14,128 |
| **Maximum (full labor + FEA)** | $15,828 |

---

## 2. TIMELINE

```
Week 1-2   ████████████████████████████████  Phase 0: Order Components
           └─ QCS6490, Hailo-10H, sensiBel (long lead)
           └─ All other components (short lead)

Week 3-5   ████████████████████████████████  Phase 1: Subsystem Validation
           └─ WPT bench test
           └─ Maglev stability test
           └─ Display/camera bring-up

Week 5-7   ████████████████████████████████  Phase 2: Electronics Integration
           └─ PCB assembly
           └─ Power system integration
           └─ Audio subsystem test

Week 7-10  ████████████████████████████████  Phase 3: Enclosure & Mechanical
           └─ 3D print internal mounts
           └─ CNC walnut base
           └─ Acrylic shell fitting

Week 10-12 ████████████████████████████████  Phase 4: Software & Testing
           └─ Firmware integration
           └─ Voice pipeline
           └─ LED animations
           └─ Thermal validation

Week 12-14 ████████████████████████████████  Phase 5: Polish & Ship
           └─ Final assembly
           └─ Documentation
           └─ Packaging

TOTAL: 14 weeks (parallel tracks reduce critical path)
```

### Critical Path Dependencies

1. **QCS6490 SoM** — 12-16 week lead time from Thundercomm
2. **Hailo-10H** — 8-12 week lead time (available July 2025+)
3. **sensiBel SBM100B** — 8-12 week lead time (B2B samples)

**Recommendation:** Order long-lead components IMMEDIATELY (Week 0)

---

## 3. CONTRACTOR CONTACTS

### Primary Recommendation: Diatomic Product Development

| Field | Information |
|-------|-------------|
| **Website** | www.diatomicpd.com |
| **Email** | info@diatomicpd.com |
| **Phone** | (206) 915-1058 |
| **Address** | 2341 Eastlake Avenue East, Seattle, WA 98102 |
| **Rate** | $150-250/hr |
| **Why** | Strong embedded systems, consumer electronics, Seattle local |

### Alternative: Facture Product Development

| Field | Information |
|-------|-------------|
| **Website** | www.facture.design |
| **Email** | info@facture.design |
| **Phone** | (206) 420-8086 |
| **Address** | 1762 Airport Way S, Unit B, Seattle, WA 98134 |
| **Rate** | $125-200/hr |
| **Why** | AI voice interface experience (Open Interpreter project) |

### Budget Option: Pillar Product Design

| Field | Information |
|-------|-------------|
| **Website** | pillardesign.net |
| **Email** | info@pillardesign.net |
| **Phone** | (206) 294-3691 |
| **Address** | 6049 California Ave SW, Seattle, WA 98136 |
| **Rate** | $100-175/hr |
| **Why** | Audio electronics specialty, smaller firm, flexible |

### Thermal FEA: Predictive Engineering (Recommended)

| Field | Information |
|-------|-------------|
| **Website** | www.predictiveengineering.com |
| **Phone** | (503) 206-5571 |
| **Address** | 555 SE MLK Jr Blvd, Suite 105, Portland, OR 97214 |
| **Contact** | George Laird, Ph.D., P.E. |
| **Cost** | $2,000-3,000 (simplified), $10,000-20,000 (full) |
| **Why** | 30+ years experience, local (Portland), reasonable rates |

---

## 4. EMAIL OUTREACH TEMPLATES

### Initial Contact — Diatomic

```
Subject: Seattle AI Hardware Prototype - Embedded QCS6490 Project

Hi Diatomic team,

I'm developing a compact AI assistant device (85mm levitating sphere) and am
looking for a Seattle-based partner for prototype development.

Key specs:
• Qualcomm QCS6490 + Hailo-10H (52 TOPS total)
• 140kHz resonant wireless charging (non-Qi)
• 4x optical MEMS microphones + far-field voice
• Custom 6-layer HDI PCB (60mm circular)

Budget: $8,000-15,000 for first functional prototype
Timeline: 10-14 weeks

Hardware designs, schematics, and full BOM are ready. Looking for integration,
assembly, and validation expertise.

Would you have availability for a project of this scope? Happy to share full
technical documentation for review.

Best,
Tim Jacoby
timothyjacoby@gmail.com
```

### Initial Contact — Thermal FEA

```
Subject: Thermal FEA for Sealed Consumer Electronics (85mm sphere)

Hi,

I'm developing a sealed consumer electronics product and need thermal analysis
to validate the design before prototyping.

Device: 85mm sealed sphere (no vents)
Heat load: 6.7W idle, 13.8W active, 22.7W peak
Constraint: Surface temp ≤45°C (UL 62368-1)
Shell: Acrylic, 7.5mm wall thickness

Looking for:
• Transient thermal analysis (2-hour soak)
• Multiple scenarios (docked vs portable)
• Recommendations for heat spreading optimization

Could you provide a rough quote and timeline?

Best,
Tim Jacoby
```

---

## 5. EMAIL STRATEGY RECOMMENDATION

### Use: timothyjacoby@gmail.com

**Reasons:**

1. **Professional credibility** — Gmail is universally accepted for professional correspondence
2. **Established identity** — Your name builds personal trust with contractors
3. **Continuity** — Future correspondence, contracts, invoices all linked to one identity
4. **Domain irrelevance** — For early prototyping, custom domain adds no value

### When to use awkronos:

- **If launching as a company** — Use `tim@awkronos.com` or `hello@awkronos.com`
- **For investor communications** — Custom domain signals commitment
- **For press/marketing** — Brand consistency matters

### Setup awkronos.com (if needed):

```bash
# Google Workspace or Cloudflare Email Routing
# Cost: $6/month (Workspace) or free (Cloudflare routing to Gmail)
```

**For prototype development:** Stick with Gmail. Save the domain for product launch.

---

## 6. RECOMMENDED EXECUTION PLAN

### Week 0 (Now)

1. ☐ Email Diatomic for initial consultation
2. ☐ Email Predictive Engineering for thermal FEA quote
3. ☐ Order long-lead components:
   - QCS6490 SoM (Thundercomm contact)
   - Hailo-10H (J-Squared Technologies)
   - sensiBel SBM100B (samples request)

### Week 1-2

1. ☐ Contractor selection and contract signing
2. ☐ Deposit payment (25% = $2,000-3,750)
3. ☐ Order remaining components from DigiKey/Mouser

### Week 3+

1. ☐ Begin Phase 1 with contractor
2. ☐ Weekly check-ins and milestone reviews
3. ☐ Thermal FEA in parallel (if proceeding)

---

## 7. RISK MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| QCS6490 unavailable | Medium | Critical | Order immediately, Radxa Q6A fallback |
| sensiBel samples denied | Medium | High | Infineon IM69D130 fallback ($32 for 4) |
| Contractor overrun | Medium | Medium | Fixed-price milestones, clear scope |
| Thermal failure | Low | High | FEA before prototype, throttling in firmware |
| PCB respin needed | Medium | Medium | Budget 2 PCB runs, design review first |

---

## 8. GO/NO-GO DECISION POINTS

| Milestone | Week | Decision |
|-----------|------|----------|
| Component availability confirmed | 2 | GO: Proceed / NO-GO: Source alternatives |
| Contractor selected | 3 | GO: Sign contract / NO-GO: Try next option |
| Subsystems validated | 5 | GO: Full integration / NO-GO: Debug or redesign |
| First power-on | 8 | GO: Software development / NO-GO: Hardware fix |
| Thermal validation | 11 | GO: Final assembly / NO-GO: Redesign cooling |

---

## Summary

**Total Investment Required:** $14,128 - $15,828

**Next Actions:**
1. Send email to Diatomic (info@diatomicpd.com)
2. Send email to Predictive Engineering for thermal quote
3. Order QCS6490, Hailo-10H, sensiBel immediately
4. Use timothyjacoby@gmail.com for all correspondence

**Expected Outcome:** Working prototype in 14-18 weeks
