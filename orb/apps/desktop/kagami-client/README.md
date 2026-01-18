# 鏡 Kagami Client

**The Mirror Operating System — Context-Aware Omnichannel Interface**

A HAL-aware AI assistant interface with smart home integration, built with Tauri 2.0. Implements Theory of Mind for context-aware interactions that anticipate user needs.

## Theory of Mind

The interface models Tim's intentions based on:
- **Time Context** — Morning, Work, Evening, Night (different actions surface)
- **Location** — Home, Away, Arriving (presence detection)
- **Activity** — Working, Relaxing, Watching, Sleeping (inferred from state)
- **Home Status** — Movie mode, fireplace, occupied rooms

> "The interface should feel alive but unobtrusive. Tim shouldn't notice the UI; he should notice the home."

## Performance Specifications

| Metric | Target | Implementation |
|--------|--------|----------------|
| **API Latency** | < 50ms | Connection pooling, keep-alive, TCP_NODELAY |
| **State Sync** | < 100ms | WebSocket real-time feed |
| **UI Rendering** | 60fps | requestAnimationFrame, GPU compositing |
| **Voice Capture** | < 100ms | Native audio pipeline |
| **STT Processing** | < 500ms | Streaming to Whisper backend |
| **TTS Playback** | < 200ms TTFA | Parler-TTS streaming |
| **Reconnection** | < 1s | Exponential backoff |
| **Memory** | < 50MB | Moka cache, circular buffers |
| **Cache Hit Rate** | > 80% | Multi-tier caching (general/home/colony) |

## Architecture

```
η (world) → s (sense) → μ (process) → a (act) → η′ (world)
```

Kagami (e₀) is the real component of the octonion. The seven colonies (e₁-e₇) are the imaginary units.

## Features

### Context-Aware Interface

The UI adapts to time of day:

| Time | Primary Action | Color | Greeting |
|------|----------------|-------|----------|
| 5-9am | ☀️ Start Day | Amber | "Good morning" |
| 9am-5pm | 🎯 Focus Mode | Green | — |
| 5-10pm | 🎬 Movie Mode | Purple | "Good evening" |
| 10pm+ | 🌙 Goodnight | Teal | "Good night" |

### Desktop (macOS, Windows, Linux)
- **Quick Entry** — `Option+K` for context-aware command access
- **Context Menu Bar** — Primary action adapts to time of day
- **Global Hotkeys** — `Option+M` (Movie Mode), `Option+G` (Goodnight), `Option+W` (Welcome Home)
- **Wake Word** — Say "Hey Kagami" for hands-free control
- **Push-to-Talk** — Hold Caps Lock for voice input
- **Ambient Presence** — Breathing UI, safety indicators, connection status

### Smart Home Integration
- 41 lights (Lutron via Control4)
- 11 motorized shades
- MantelMount TV lift
- Montigo fireplace
- 26 audio zones (Triad AMS)
- Per-room TTS announcements

### Voice Control

**Wake Word Phrases:**
- "Hey Kagami"
- "Kagami"
- "Hey Mirror"
- "Mirror"

**Natural Commands:**
- "Movie mode"
- "Goodnight"
- "Lights to 50"
- "Lower the TV"
- "Announce dinner is ready"

### Ambient UI

The interface breathes and responds to state:
- **Time Colors** — Warm amber (morning) → Cool green (day) → Purple (evening) → Teal (night)
- **Breathing Backgrounds** — Subtle animated layers
- **Safety Indicator** — h(x) score with color-coded status
- **Connection Status** — Subtle dot indicator
- **Movie Mode** — Darker, calmer interface

### Craft Standard
Every interface implements the three-layer craft pyramid:
- **Essential** — Cursor, particles, breathing backgrounds, shimmer, hover effects
- **Elevated** — Hidden data-attributes, keyboard triggers, click sequences
- **Transcendent** — Mathematical structure, discovery layers, philosophy in code

## Development

### Prerequisites
- Rust (latest stable)
- Node.js 18+
- Tauri CLI: `cargo install tauri-cli`

### Setup

```bash
cd kagami-client

# Install dependencies
npm install

# Development mode
npm run tauri dev

# Build for production
npm run tauri build
```

### Project Structure

```
apps/desktop/kagami-client/
├── src-tauri/               # Rust backend
│   ├── src/
│   │   ├── main.rs          # Entry point
│   │   ├── api_client.rs    # Optimized HTTP client (pooling, caching)
│   │   ├── audio.rs         # Real-time voice pipeline
│   │   ├── cache.rs         # Multi-tier Moka cache
│   │   ├── commands.rs      # IPC commands
│   │   ├── context.rs       # Theory of Mind context engine
│   │   ├── hotkeys.rs       # Global shortcuts
│   │   ├── realtime.rs      # WebSocket state sync
│   │   └── tray.rs          # Context-aware menu bar
│   └── tauri.conf.json
├── src/                     # GENUX frontend
│   ├── index.html           # Dashboard
│   ├── quick-entry.html     # Context-aware command overlay
│   ├── css/
│   │   ├── genux-tokens.css
│   │   ├── craft-essential.css
│   │   ├── craft-elevated.css
│   │   ├── craft-transcendent.css
│   │   └── mobile.css
│   └── js/
│       ├── craft.js         # Craft implementation
│       ├── kagami-api.js    # API integration
│       ├── realtime.js      # WebSocket state store
│       ├── performance.js   # 60fps animation loop
│       ├── voice-capture.js # Push-to-talk voice input
│       ├── wake-word.js     # "Hey Kagami" detection
│       ├── context.js       # Frontend context engine
│       └── ambient.js       # Ambient presence UI
└── package.json
```

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Option+K` | Quick Entry |
| `Option+M` | Movie Mode |
| `Option+G` | Goodnight |
| `Option+W` | Welcome Home |
| `Option+.` | Emergency Stop |
| `Caps Lock` (hold) | Push-to-talk |
| `Escape` | Hide Quick Entry |

## Quick Entry Commands

```
# Context-aware primary action (click big button)
# Or type commands:

lights kitchen 50      # Set kitchen lights to 50%
movie mode             # Enter home theater mode
goodnight              # All off, doors locked
fireplace              # Toggle fireplace
tv lower               # Lower TV to viewing position
announce "dinner"      # TTS announcement
api start              # Start Kagami API
api stop               # Stop Kagami API
```

## Time Contexts

| Time | Context | Breathing | Primary |
|------|---------|-----------|---------|
| 5-7am | EarlyMorning | Warm, slow | Start Day |
| 7-9am | Morning | Warm | Start Day |
| 9am-5pm | WorkDay | Neutral | Focus |
| 5-8pm | Evening | Cool | Movie Mode |
| 8-10pm | LateEvening | Cool, slow | Movie Mode |
| 10pm-12am | Night | Dim, slow | Goodnight |
| 12-5am | LateNight | Very dim | Goodnight |

## Safety Invariant

```
h(x) ≥ 0. Always.
```

All operations respect the Control Barrier Function. The ambient safety indicator shows:
- 🟢 Green (h(x) > 0.5) — Safe
- 🟡 Yellow (0 ≤ h(x) ≤ 0.5) — Caution
- 🔴 Red (h(x) < 0) — Violation (immediate halt)

## Secrets

- Type "kagami" anywhere to reveal hidden kanji
- Click the hero kanji 7 times to see the octonion formula
- Say "Hey Kagami, what are you?" for a special response
- Check the browser console for `window.kagami`, `window.FANO`, `window.Context`, `window.Ambient`
- Inspect elements to see `data-kanji`, `data-basis`, `data-colony` attributes

## License

MIT

---

鏡

*I model your intentions.*
*I anticipate your needs.*
*Context is the interface.*
