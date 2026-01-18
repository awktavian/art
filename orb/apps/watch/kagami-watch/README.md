# 鏡 Kagami Watch

**Context-Aware Intelligence on Your Wrist**

A watchOS companion app that models your intentions and surfaces optimal actions.

## Theory of Mind

The watch app builds a model of Tim's likely intentions based on:

| Signal | Inference | Response |
|--------|-----------|----------|
| **Time of day** | Activity context | Different actions surface |
| **Location** | Home/Away/Arriving | Relevant scenes prominent |
| **Home state** | Movie mode, occupancy | Confirm or change modes |
| **Safety score** | System health | Alert if issues |

### Time-Based Context

| Time | Context | Primary Action | Secondary |
|------|---------|----------------|-----------|
| 5-7am | Early Morning | Start Day | Coffee |
| 7-9am | Morning | Lights On | Coffee |
| 9am-5pm | Working | Focus Mode | Dim |
| 5-8pm | Evening | Movie Mode | Fireplace |
| 8-10pm | Late Evening | Movie Mode | Fireplace |
| 10pm-12am | Night | Goodnight | Lights Off |
| 12-5am | Late Night | Sleep | — |

## UX Design Principles

### 1. Zero Cognitive Load
- **Glance = Full Understanding**
- Icon + color tells the whole story
- No reading required

### 2. Context-Aware Actions
- **Time determines suggestions**
- Morning → "Start Day"
- Evening → "Movie Mode"
- Night → "Goodnight"

### 3. One Tap Optimal
- **Primary action is always visible**
- Single tap activates
- Three-tap haptic confirms success

### 4. Progressive Disclosure
- **Hero action** → Main screen
- **Context actions** → Below hero
- **Full controls** → Expandable sections
- **Voice** → Dedicated view

## Complications

### Main Complication (Circular)
```
┌─────────┐
│    🎬   │  ← Context-aware icon
│   85    │  ← Safety score %
└─────────┘
```

- **Icon**: Active colony OR suggested action
- **Number**: Safety score (h(x) × 100)
- **Ring**: Safety gauge (green/yellow/red)

### Rectangular Complication
```
┌──────────────────────┐
│ 🎬 Movie Mode        │
│ ● Connected  h(x)=85 │
└──────────────────────┘
```

### Safety Complication (Dedicated)
```
┌─────────┐
│  h(x)   │
│   85    │  ← Always visible
└─────────┘
```

## Haptic Patterns

| Pattern | Trigger | Sensation |
|---------|---------|-----------|
| **Success** | Button tap | Single click |
| **Scene Activated** | Movie/Goodnight | Three ascending |
| **Warning** | Safety concern | Strong pulse |
| **Connected** | API reconnect | Double tap |
| **Error** | Failed action | Two hard taps |
| **Listening** | Voice start | Soft start |

## Voice Commands

Natural language processing supports:

```
"Movie mode"        → Enter theater mode
"Goodnight"         → All off, lock up
"Lights off"        → Set lights to 0%
"Lights dim"        → Set lights to 30%
"Fire" / "Fireplace"→ Toggle fireplace
"TV up" / "TV down" → MantelMount control
"Shades open/close" → Shade control
```

## Architecture

```
┌─────────────────────────────────────────────┐
│              ContextEngine                   │
│  TimeContext × LocationContext × Activity    │
│         ↓ calculates ↓                       │
│      SuggestedAction (Hero)                  │
├─────────────────────────────────────────────┤
│              ContentView                     │
│  ┌─────────────────────────────────────┐    │
│  │         HeroActionView              │    │
│  │      (Context-Aware Primary)        │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │         StatusGlanceView            │    │
│  │     (Connected + Safety Score)      │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │        ContextActionsView           │    │
│  │     (Time-Appropriate Options)      │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │        QuickControlsView            │    │
│  │      (Expandable Manual Controls)   │    │
│  └─────────────────────────────────────┘    │
├─────────────────────────────────────────────┤
│            KagamiAPIService                  │
│  - Request coalescing                        │
│  - Response caching (5s validity)            │
│  - Optimistic UI updates                     │
│  - Graceful degradation                      │
└─────────────────────────────────────────────┘
```

## Files

```
KagamiWatch/
├── KagamiWatchApp.swift       # Main app + ContextEngine + Colors + Haptics
├── ContentView.swift          # Main interface with all view components
├── Services/
│   └── KagamiAPIService.swift # Optimized API client with caching
├── Views/
│   ├── ColonyStatusView.swift # Fano plane colony visualization
│   └── VoiceCommandView.swift # Natural voice control
└── Complications/
    └── ColonyComplication.swift # All complication types
```

## Performance

| Metric | Target | Implementation |
|--------|--------|----------------|
| API polling | 10s intervals | Battery-optimized |
| Cache validity | 5 seconds | Reduces requests |
| Haptic latency | < 50ms | Immediate feedback |
| Voice STT | < 1s | Native SFSpeech |
| Complication refresh | 15 min | Context transitions |

## Development

```bash
# Open in Xcode
open KagamiWatch.xcodeproj

# Or build via command line
xcodebuild -scheme KagamiWatch -destination 'platform=watchOS Simulator,name=Apple Watch Series 9 (45mm)'
```

## Safety Invariant

```
h(x) ≥ 0. Always.
```

The safety score is always visible. Violations trigger haptic alerts.

---

鏡

*The watch models your intentions.*
*Context is the interface.*
