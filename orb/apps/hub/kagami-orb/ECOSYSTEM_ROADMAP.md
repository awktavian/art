# Kagami Orb Ecosystem Roadmap

**Version:** 1.0
**Date:** January 2026
**Status:** Strategic Roadmap

---

## Executive Summary

The Kagami Orb launches as a **standalone presence device** but must integrate with the smart home ecosystem to achieve mainstream adoption. This roadmap details the path from launch to full ecosystem compatibility.

### Philosophy: Independence First, Integration Second

**Why not launch with Matter/HomeKit?**
1. Focus resources on core experience (levitation + eye + privacy)
2. Avoid certification delays pushing launch
3. Establish brand before becoming "another Matter device"
4. Learn from early adopters what integrations matter most

**Integration Priority (based on focus group feedback):**
1. Matter — Universal smart home protocol
2. HomeKit — Premium Apple ecosystem
3. Alexa/Google Assistant — Voice control interop
4. Developer SDK — Custom integrations

---

## Phase 1: Kagami-Native Launch (Month 0)

### Launch Capabilities

| Feature | Status | Description |
|---------|--------|-------------|
| **Voice Control** | Included | Natural language via Kagami AI |
| **Face Recognition** | Included | On-device face detection |
| **Presence Detection** | Included | Camera-based room awareness |
| **Local Automation** | Included | Time/presence triggers |
| **Hub Integration** | Included | Full kagami-hub ecosystem |

### Kagami Ecosystem at Launch

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        KAGAMI ECOSYSTEM (V1)                             │
│                                                                          │
│   ┌─────────────┐       ┌─────────────┐       ┌─────────────┐          │
│   │   Kagami    │       │   Kagami    │       │   Kagami    │          │
│   │    Orb      │◄─────►│     Hub     │◄─────►│    Apps     │          │
│   │  (Presence) │       │   (Brain)   │       │  (Control)  │          │
│   └─────────────┘       └─────────────┘       └─────────────┘          │
│         │                     │                     │                   │
│         │                     ▼                     │                   │
│         │            ┌─────────────────┐           │                   │
│         └───────────►│  Kagami Cloud   │◄──────────┘                   │
│                      │  (Opt-in sync)  │                               │
│                      └─────────────────┘                               │
│                                                                          │
│   Supported at Launch:                                                  │
│   • kagami-ios, kagami-android, kagami-watch, kagami-visionOS          │
│   • kagami-desktop (macOS, Windows, Linux)                             │
│   • kagami-hub (central controller)                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### API Preview (Developer Access)

Launch includes read-only API access for developers:

```typescript
// Orb State API (REST)
GET /api/v1/orb/state
{
  "state": "docked_idle",
  "eye_expression": "curious",
  "battery_soc": 78,
  "levitating": true,
  "face_detected": true,
  "face_position": { "x": 0.3, "y": 0.1 }
}

// Event Stream (WebSocket)
ws://kagami-orb.local/events
{
  "event": "face_detected",
  "timestamp": "2026-01-15T10:30:00Z",
  "data": { "face_count": 1, "familiar": true }
}
```

---

## Phase 2: Matter Integration (Months 1-3)

### Matter Protocol Overview

| Aspect | Detail |
|--------|--------|
| **Standard** | Matter 1.4 (October 2025) |
| **Transport** | Thread + WiFi |
| **Certification** | CSA (Connectivity Standards Alliance) |
| **Timeline** | 6-8 weeks for certification |
| **Cost** | ~$50K (certification + testing) |

### Matter Device Types

Orb will implement multiple Matter device types:

| Device Type | Cluster | Orb Feature |
|-------------|---------|-------------|
| **Occupancy Sensor** | 0x0406 | Face/presence detection |
| **On/Off Light** | 0x0006 | LED ring control |
| **Color Temperature** | 0x0300 | Eye color control |
| **Speaker** | 0x050A | TTS output |
| **Microphone** | 0x050B | Voice capture |

### Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MATTER INTEGRATION ARCHITECTURE                       │
│                                                                          │
│   ┌─────────────┐    Matter    ┌─────────────┐                         │
│   │   Kagami    │◄───over────►│   Matter    │                          │
│   │    Orb      │    Thread    │ Controller  │                          │
│   └─────────────┘              └─────────────┘                          │
│         │                            │                                   │
│         │ Internal                   │ Matter                           │
│         ▼                            ▼                                   │
│   ┌─────────────┐             ┌─────────────┐                          │
│   │ QCS6490     │             │ Apple Home  │                          │
│   │ + Thread    │             │ Google Home │                          │
│   │ (built-in)  │             │ SmartThings │                          │
│   └─────────────┘             │ Home Asst.  │                          │
│                               └─────────────┘                          │
│                                                                          │
│   Thread Border Router: Built into Orb base (ESP32-H2)                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Matter Milestone Schedule

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1-2 | SDK Integration | Matter SDK (ConnectedHomeIP) compiling |
| 3-4 | Device Types | Occupancy sensor working |
| 5-6 | Full Clusters | All clusters implemented |
| 7-8 | Testing | Internal QA complete |
| 9-12 | Certification | CSA certification process |

### Thread Border Router

The base station includes Thread support:

| Component | Role |
|-----------|------|
| **ESP32-H2** | Thread 1.3 + BLE 5.3 |
| **nRF52840** | Backup Thread radio |

**Benefit:** Orb base becomes a Thread border router, extending your mesh network.

---

## Phase 3: HomeKit Integration (Months 2-4)

### HomeKit Strategy

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| **Native HAP** | Full control | MFi certification | Selected |
| **via Matter** | Faster | Limited device types | Backup |
| **via HomeBridge** | Community | Unofficial | Not recommended |

### MFi Certification Path

| Step | Timeline | Cost |
|------|----------|------|
| Apply for MFi license | Week 1 | Free |
| Receive MFi portal access | Week 2-4 | — |
| Self-certification testing | Week 4-8 | Lab time |
| Submit to Apple | Week 8 | $99/year dev fee |
| Approval | Week 10-12 | — |

### HomeKit Accessory Categories

| Category | Orb Feature | Siri Command |
|----------|-------------|--------------|
| **Sensor** | Presence detection | "Is anyone in the living room?" |
| **Camera** | Hidden pupil camera | "Show me the office" |
| **Light** | LED ring | "Set Kagami to purple" |
| **Speaker** | TTS output | "Tell Kagami to say hello" |

### HomeKit Secure Video (HSV)

**Optional upgrade path:**

| Feature | Requirement | Orb Status |
|---------|-------------|------------|
| On-device analysis | A12+ chip equivalent | QCS6490 capable |
| iCloud+ storage | Subscription | User provides |
| End-to-end encryption | Apple framework | Planned M4 |

**Privacy note:** HSV footage goes directly to iCloud, never to Kagami servers. Maintains privacy promise.

---

## Phase 4: Voice Assistant Interoperability (Months 3-6)

### Multi-Assistant Strategy

Orb supports its own AI, but users may want familiar assistants:

| Assistant | Integration Method | Status |
|-----------|-------------------|--------|
| **Kagami AI** | Native | Default |
| **Amazon Alexa** | AVS SDK | Planned M4 |
| **Google Assistant** | Embedded SDK | Planned M5 |
| **Siri** | HomeKit integration | Via HomeKit |

### Alexa Voice Service (AVS) Integration

| Component | Implementation |
|-----------|----------------|
| **AVS SDK** | v3.0 embedded |
| **Wake Word** | "Alexa" (licensed) |
| **Auth** | OAuth via companion app |
| **Audio** | Opus to AVS cloud |

```
┌───────────────────────────────────────────────────────────────────┐
│                     DUAL ASSISTANT MODE                            │
│                                                                    │
│   "Hey Kagami" → Kagami AI (on-device, private)                   │
│   "Alexa"      → Amazon AVS (cloud, Alexa ecosystem)              │
│   "Hey Google" → Google Assistant (cloud, Google ecosystem)       │
│                                                                    │
│   User selects default or uses wake word to choose                │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Google Assistant Embedded

| Requirement | Status |
|-------------|--------|
| License agreement | Required (apply to Google) |
| Hardware requirements | QCS6490 exceeds minimum |
| Certification | ~8 weeks |

---

## Phase 5: Developer SDK (Months 4-8)

### SDK Vision

Developers can extend Orb's capabilities without hardware modification.

### SDK Components

| Component | Description | Release |
|-----------|-------------|---------|
| **REST API** | Full device control | M4 |
| **WebSocket API** | Real-time events | M4 |
| **Expression SDK** | Custom eye animations | M5 |
| **Voice SDK** | Custom wake words, intents | M6 |
| **Vision SDK** | Custom CV models | M7 |
| **Hardware SDK** | LED patterns, PTZ control | M8 |

### API Documentation Preview

```yaml
# OpenAPI 3.0 Specification
openapi: 3.0.3
info:
  title: Kagami Orb API
  version: 1.0.0
  description: Control your Kagami Orb programmatically

paths:
  /api/v1/eye/expression:
    post:
      summary: Set eye expression
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                expression:
                  type: string
                  enum: [neutral, curious, thinking, happy, concerned]
                duration_ms:
                  type: integer
                  default: 2000
      responses:
        200:
          description: Expression applied

  /api/v1/led/pattern:
    post:
      summary: Set LED ring pattern
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                pattern:
                  type: string
                  enum: [solid, breathing, rainbow, pulse, constellation]
                color:
                  type: string
                  format: hex
                  example: "#FF6B35"

  /api/v1/ptz/position:
    post:
      summary: Set PTZ position (docked only)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                pan:
                  type: number
                  minimum: -180
                  maximum: 180
                tilt:
                  type: number
                  minimum: -20
                  maximum: 20
```

### Expression SDK (Custom Eye Animations)

```typescript
// Expression definition format
interface OrbExpression {
  name: string;
  frames: EyeFrame[];
  duration_ms: number;
  loop: boolean;
}

interface EyeFrame {
  iris_position: { x: number; y: number };  // -1 to 1
  pupil_size: number;                        // 0.3 to 1.0
  eyelid_top: number;                        // 0 (open) to 1 (closed)
  eyelid_bottom: number;
  iris_color: string;                        // hex
  sclera_color: string;                      // hex
}

// Example: Suspicious squint
const suspicious: OrbExpression = {
  name: "suspicious",
  frames: [
    { iris_position: { x: -0.2, y: 0 }, pupil_size: 0.4, eyelid_top: 0.3, ... },
    { iris_position: { x: 0.2, y: 0 }, pupil_size: 0.4, eyelid_top: 0.3, ... },
  ],
  duration_ms: 1500,
  loop: true
};
```

### Developer Portal Timeline

| Month | Feature |
|-------|---------|
| M4 | Developer portal launch (portal.kagami.dev) |
| M5 | API key self-service |
| M6 | Expression SDK beta |
| M7 | Vision SDK beta |
| M8 | Full SDK GA |

---

## Phase 6: Enterprise Features (Months 8-12)

### Enterprise Edition

| Feature | Consumer | Enterprise |
|---------|----------|------------|
| Matter/HomeKit | Yes | Yes |
| Multi-Orb sync | 2 devices | Unlimited |
| Custom branding | No | Yes |
| Fleet management | No | Yes |
| SLA | No | Yes |
| SSO | No | Yes |
| Audit logs | No | Yes |

### Conference Room Presence

```
┌───────────────────────────────────────────────────────────────────┐
│                  ENTERPRISE CONFERENCE ROOM                        │
│                                                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                    DISPLAY SCREEN                        │    │
│   └─────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                         ╭────┴────╮                               │
│                        │  👁️ ORB  │  ← Tracks active speaker     │
│                         ╰─────────╯                               │
│                                                                    │
│   Features:                                                        │
│   • Auto-joins calendar meetings                                  │
│   • Tracks speaker with PTZ                                       │
│   • Displays meeting participants on LED ring                     │
│   • Announces when meeting starts/ends                            │
│   • Integrates with Teams/Zoom/Meet                               │
│                                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Microsoft Teams / Zoom Integration

| Platform | Integration | Status |
|----------|-------------|--------|
| Teams | Teams Devices certification | Planned M10 |
| Zoom | Zoom Rooms peripheral | Planned M11 |
| Google Meet | Meet hardware program | Planned M12 |

---

## Integration Architecture Summary

### Final State (Month 12+)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FULL ECOSYSTEM (MONTH 12+)                           │
│                                                                          │
│   ┌───────────────────────────────────────────────────────────────┐    │
│   │                        KAGAMI ORB                              │    │
│   │   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │    │
│   │   │  Voice  │ │  Vision │ │   PTZ   │ │   LED   │            │    │
│   │   │  Stack  │ │  Stack  │ │  Stack  │ │  Stack  │            │    │
│   │   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘            │    │
│   │        └───────────┴───────────┴───────────┘                   │    │
│   │                           │                                     │    │
│   │                     ┌─────┴─────┐                              │    │
│   │                     │  Orb API  │                              │    │
│   │                     └─────┬─────┘                              │    │
│   └───────────────────────────┼─────────────────────────────────────┘   │
│                               │                                          │
│   ┌───────────────────────────┼─────────────────────────────────────┐   │
│   │              INTEGRATION LAYER (on Orb)                          │   │
│   │   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐       │   │
│   │   │ Matter │ │HomeKit │ │  AVS   │ │ Google │ │  SDK   │       │   │
│   │   │ 1.4    │ │  HAP   │ │  v3    │ │  Asst  │ │   v1   │       │   │
│   │   └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘       │   │
│   └────────┼──────────┼─────────┼──────────┼──────────┼─────────────┘   │
│            │          │         │          │          │                  │
│            ▼          ▼         ▼          ▼          ▼                  │
│   ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐         │
│   │  Google  │ │  Apple   │ │ Amazon │ │ Google │ │ Third    │         │
│   │   Home   │ │   Home   │ │  Echo  │ │  Nest  │ │  Party   │         │
│   │ SmartThg │ │          │ │  Show  │ │  Hub   │ │  Apps    │         │
│   └──────────┘ └──────────┘ └────────┘ └────────┘ └──────────┘         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Resource Requirements

### Engineering

| Phase | Engineers | Duration | Total |
|-------|-----------|----------|-------|
| Matter | 2 | 3 months | 6 eng-months |
| HomeKit | 1 | 2 months | 2 eng-months |
| Voice Assistants | 2 | 3 months | 6 eng-months |
| SDK | 2 | 4 months | 8 eng-months |
| Enterprise | 2 | 4 months | 8 eng-months |
| **Total** | — | — | **30 eng-months** |

### Certification Costs

| Certification | Cost | Timeline |
|---------------|------|----------|
| Matter (CSA) | $50K | 8-12 weeks |
| HomeKit (MFi) | $10K | 10-12 weeks |
| Alexa (AVS) | $15K | 6-8 weeks |
| Google Assistant | $20K | 6-8 weeks |
| Teams Devices | $25K | 12 weeks |
| **Total** | **$120K** | — |

---

## Success Metrics

### Phase Completion Criteria

| Phase | Success Metric | Target |
|-------|---------------|--------|
| Matter | CSA certification | Month 3 |
| HomeKit | MFi certification + App Store | Month 4 |
| AVS | "Works with Alexa" badge | Month 5 |
| Google | "Works with Google" badge | Month 6 |
| SDK | 100 active developers | Month 8 |
| Enterprise | 10 paying customers | Month 12 |

### User Satisfaction

| Metric | Target |
|--------|--------|
| "Easy to set up" (NPS) | >80 |
| "Works with my smart home" | >90% |
| "Better than Echo" | >70% |

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Matter certification delayed | 30% | Medium | Start early, hire consultant |
| MFi rejected | 20% | High | Use Matter-to-HomeKit bridge |
| AVS license denied | 15% | Medium | Alexa Cast as fallback |
| SDK low adoption | 40% | Low | Bounty program, examples |
| Enterprise sales slow | 50% | Medium | Focus on consumer first |

---

## Conclusion

The ecosystem roadmap transforms Kagami Orb from a **standalone device** to a **platform**.

### Key Milestones

| Month | Milestone |
|-------|-----------|
| 0 | Launch (Kagami-native) |
| 3 | Matter certified |
| 4 | HomeKit certified |
| 6 | Alexa/Google available |
| 8 | Developer SDK GA |
| 12 | Enterprise ready |

### The Vision

By Month 12, Kagami Orb is:
- A **presence device** (core identity)
- A **Matter node** (smart home citizen)
- A **HomeKit accessory** (Apple ecosystem)
- A **voice endpoint** (Alexa/Google)
- A **developer platform** (custom apps)
- An **enterprise solution** (conference rooms)

**Without losing what makes it special: the eye that sees you.**

---

*"Integration without compromise."* — 鏡
