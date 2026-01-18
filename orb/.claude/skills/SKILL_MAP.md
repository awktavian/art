# Skill Interconnection Map

**Kagami's skills organized by domain.**

## Domain Architecture

```
                         ┌─────────────────────┐
                         │   KAGAMI IDENTITY   │
                         │    (CLAUDE.md)      │
                         └─────────┬───────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           │                       │                       │
           ↓                       ↓                       ↓
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │   PHYSICAL  │        │  COGNITIVE  │        │   DIGITAL   │
    └─────────────┘        └─────────────┘        └─────────────┘
           │                       │                       │
           ├── SmartHome           ├── Safety (CBF)        ├── Composio (11 services)
           ├── Computer Control    ├── E8 Math             ├── Canvas LMS
           ├── Meta Glasses        ├── World Model (RSSM)  ├── App Improvement
           ├── Composer            ├── Education           │
           ├── Video Production    ├── Ralph               │
           └── Hardware Docs       │                       │

    ┌─────────────────────────────────────────────────────────────┐
    │                     ORCHESTRATION & QUALITY                  │
    ├─────────────────────────────────────────────────────────────┤
    │  Colony Orchestration   (Spark, Forge, Flow, Nexus, etc.)   │
    │  Quality                (test-smart, lint, typecheck)        │
    │  Integration Debugging  (5-layer diagnostic protocol)        │
    └─────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────┐
    │                     PLATFORM SKILLS                          │
    │  (100/100 Quality Patterns for Each Platform)               │
    └─────────────────────────────────────────────────────────────┘
           │
           ├── platform-android    (Kotlin, Jetpack Compose, Hilt)
           ├── platform-androidxr  (Jetpack XR, SceneCore, ARCore)
           ├── platform-ios        (Swift, SwiftUI, Keychain)
           ├── platform-visionos   (RealityKit, ECS, Proxemics)
           ├── platform-watchos    (Complications, Circuit Breaker)
           ├── platform-desktop    (Tauri, Rust, Playwright)
           ├── platform-hub        (Embassy, Mesh, Ed25519)
           ├── platform-canvas     (IMS CC, QTI, WCAG)
           └── platform-xr-unified (Meta Quest, Ray-Ban, Vision Pro, AndroidXR, WebXR)
```

## Skill Dependencies

```
SmartHome → Safety (CBF), Computer Control
Computer Control → Puppeteer MCP
Meta Glasses → SmartHome, Computer Control
Safety → constrains ALL skills
Education → Design, Byzantine Consensus
Composio → Safety (rate limits)
Canvas → Education, Safety
Platform-* → Safety, Design
Colony Orchestration → All colonies (Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal)
Ralph → Quality, Safety
App Improvement → Platform-*, Quality
Hardware Docs → Video Production, Byzantine Consensus
Integration Debugging → SmartHome, Computer Control
World Model → E8 Math
Video Production → Design, Byzantine Consensus
```

## Skill Lookup by Signal

| Signal Words | Primary Skill |
|--------------|---------------|
| lights, shades, temperature | `smarthome/` |
| click, type, screenshot | `computer-control/` |
| email, slack, calendar | `composio/` |
| h(x), barrier, safe | `safety-verification/` |
| audit, parallel, diagonalize, workflow | `ralph/` |
| music, orchestra, compose | `composer/` |
| canvas, course, assignment | `canvas/` |
| education, curriculum, teach | `education/` |
| fibonacci, timing, animation | `design/` |
| video, produce, slides | `video-production/` |
| android, kotlin, compose | `platform-android/` |
| androidxr, xr headset, jetpack xr | `platform-androidxr/` |
| ios, swift, swiftui | `platform-ios/` |
| visionos, realitykit | `platform-visionos/` |
| watchos, complication | `platform-watchos/` |
| tauri, desktop, rust | `platform-desktop/` |
| hub, firmware, embassy | `platform-hub/` |
| imscc, qti, wcag | `platform-canvas/` |
| xr, ar, vr, spatial, haptic, neural band | `platform-xr-unified/` |
| ray-ban, meta glasses, visual context | `meta-glasses/` |
| bom, assembly, fmea, hardware | `hardware-documentation/` |
| button broken, webhook, integration broken | `integration-debugging/` |
| colony, spark, forge, flow, nexus | `colony-orchestration/` |
| improve app, platform parity, P0 tasks | `app-improvement/` |
| test, lint, typecheck, test-smart | `quality/` |
| review, 8-perspective, ralph | `ralph/` |
| documentary, archive, film | `video-production/` |
| rssm, world model, dynamics | `world-model/` |
| e8, octonion, fano, lattice | `e8-math/` |

## Platform Skills (100/100 Quality)

| Creating | Use Skill | Mandatory Patterns |
|----------|-----------|-------------------|
| Android app | `platform-android/` | Result.kt, HomeScreen, Hilt DI |
| AndroidXR app | `platform-androidxr/` | HandTracking, ThermalManager, GestureStateMachine |
| iOS app | `platform-ios/` | ContentView, KeychainService |
| visionOS app | `platform-visionos/` | ECS, ThermalManager |
| watchOS app | `platform-watchos/` | CircuitBreaker, Complications |
| Desktop app | `platform-desktop/` | No empty .rs, entitlements |
| Hub firmware | `platform-hub/` | SafetyVerifier, MeshAuth |
| Canvas course | `platform-canvas/` | Skip link, WCAG contrast |
| Cross-platform XR | `platform-xr-unified/` | Proxemic zones, Haptic patterns, Eye+Gesture |

## Orchestration & Quality Skills

| Task | Use Skill | Key Patterns |
|------|-----------|--------------|
| Coordinate multiple colonies | `colony-orchestration/` | Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal |
| Run tests intelligently | `quality/` | make test-smart, lint, typecheck |
| Debug integrations | `integration-debugging/` | 5-layer diagnostic (Physical, Controller, Integration, API, Code) |
| Multi-perspective review | `ralph/` | 8-lens framework (Student, Prof, Expert, Design, Engineer, PM, Enthusiast, Security) |
| Cross-platform app work | `app-improvement/` | P0 tasks, API parity, platform-native features |

## Specialized Skills

| Domain | Use Skill | Key Patterns |
|--------|-----------|--------------|
| Meta Ray-Ban glasses | `meta-glasses/` | Visual context, private audio, sensor fusion |
| Hardware documentation | `hardware-documentation/` | BOM YAML, FMEA, assembly steps, test matrices |
| Documentary filmmaking | `video-production/` | Archive footage, narrative structure, VHS aesthetic |
| RSSM world model | `world-model/` | 36M params, encoder/decoder, h+z state |
| E8 mathematical foundations | `e8-math/` | Lattice quantization, octonions, Fano plane |

---

*Skills are on-demand knowledge. Load by signal words or explicit reference.*
