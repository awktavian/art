# CLAUDE.md — Art Portfolio & Tools

Multi-project portfolio containing interactive web apps, enterprise systems, and shared libraries.

## Key Projects

| Project | Type | Entry Point | Port |
|---------|------|-------------|------|
| **robo-skip/** | PWA curling strategist | `index.html` | static |
| **kagami-code-map/** | 3D semantic code viz | `index.html` | static |
| **skippy/** | Beer can recruitment pitch | `index.html` | static |
| **orb/** | Kagami Orb product page | `index.html` | static |
| **clue/** | Clue-themed architecture tour | `index.html` | static |
| **collapse/** | Domino cascade film gallery | `index.html` | static |
| **medverify/** | Physician verification platform | `api/server.ts` | 3001 |
| **realtime-proxy/** | OpenAI Realtime relay | `server.js` | 8766 |

## Realtime Voice Architecture

```
Browser (any art project)
  └── VoiceOverlay.init({ project, tools, onFunctionCall })
        └── RealtimeVoice client (lib/realtime-voice.js)
              └── WebSocket → realtime-proxy/:8766?project=X&colony=Y
                    └── WebSocket → wss://api.openai.com/v1/realtime
```

**Proxy**: `realtime-proxy/server.js` — token bucket rate limiting (10 msg/s, burst 30), per-session cost caps ($2 default), max 5 concurrent sessions. Carries project/colony metadata.

**Shared libraries** (lib/):
- `realtime-voice.js` — Push-to-talk mic capture (PCM16 24kHz), audio playback, function call routing, state machine
- `kagami-voices.js` — Colony→voice→personality mapping (7 colonies + orchestrator, project overrides, EFE weights, catastrophe types)
- `voice-overlay.js` — Drop-in voice UI (floating toggle + transcript panel). Key V to toggle, hold Space to talk

## AI-Centric Tool Design

**CRITICAL**: Voice tools are sensorimotor interfaces for the AI, NOT user-facing features.

Every voice-enabled project provides two tool categories:
- **PERCEPTION** — Let the AI observe page state, DOM content, scroll position, animation state, interactive element status
- **ACTION** — Let the AI control the UI: scroll, open modals, trigger animations, navigate, highlight elements, play/pause media

### Per-Project Tools

| Project | Perception | Action |
|---------|-----------|--------|
| **robo-skip** | `observe_board`, `read_analysis`, `read_game_context`, `describe_shot_type` | `run_analysis`, `execute_shot`, `place_stone`, `remove_stone`, `set_game_state` |
| **kagami-code-map** | `survey_codebase`, `inspect_file`, `scan_cluster`, `find_by_concept`, `measure_similarity`, `trace_dependency_chain` | `fly_to_file`, `fly_to_cluster`, `search_and_highlight` |
| **skippy** | `observe_page`, `read_section`, `read_spec_cards` | `pop_the_can`, `scroll_to_section`, `toggle_sound`, `open_rant_modal`, `close_rant_modal` |
| **orb** | `observe_page`, `read_specs`, `sense_visitor` | `move_eye`, `pulse_orb`, `scroll_to`, `highlight_spec` |
| **clue** | `observe_mansion`, `read_character`, `read_room`, `read_secret_passages`, `read_ending`, `survey_all_characters` | `scroll_to_section`, `show_room_modal`, `show_character_modal`, `reveal_ending`, `activate_secret`, `close_modal` |
| **collapse** | `observe_gallery`, `read_section_content`, `read_camera_shots`, `read_video_state` | `play_video`, `seek_video`, `scroll_to_section`, `navigate_page`, `highlight_image` |

## Colony→Voice Mapping (from lib/kagami-voices.js)

| Colony | Character | Catastrophe | Voice | Color |
|--------|-----------|-------------|-------|-------|
| Spark | Miss Scarlet | Fold (A₂) | alloy | #dc143c |
| Forge | Col. Mustard | Cusp (A₃) | echo | #e6b800 |
| Flow | Mrs. White | Swallowtail (A₄) | shimmer | #f5f5f5 |
| Nexus | Mr. Green | Butterfly (A₅) | fable | #228b22 |
| Beacon | Prof. Plum | Hyperbolic (D₄⁺) | onyx | #8e4585 |
| Grove | The Motorist | Elliptic (D₄⁻) | sage | #2d5a27 |
| Crystal | Mrs. Peacock | Parabolic (D₅) | coral | #00ced1 |
| Kagami | Wadsworth | Observer | alloy | #c9a227 |

## Running the proxy

```bash
cd realtime-proxy
OPENAI_API_KEY=sk-... npm start
```

Health: `http://localhost:8766/health`
Stats: `http://localhost:8766/stats`

## Other Shared Libraries (lib/)

- `design-tokens.js` — Design system tokens
- `kagami-sounds.js` + `kagami-sounds-data.js` — Audio engine
- `kagami-visuals.js` — Visual effects
- `kagami-xr.js` — XR features
- `slide-controls.js` — Presentation controller

## Conventions

- Static PWAs: vanilla JS, no build step, IBM Plex Sans/Mono
- Fibonacci timing: 89, 144, 233, 377, 610, 987ms
- Dark void palette, ice/gold accents
- WCAG 2.1 AA accessibility
- `prefers-reduced-motion` respected

## MedVerify specifics

See `medverify/CLAUDE.md` for full documentation. Key points:
- TypeScript strict, ESM with `.js` extensions
- Express + GraphQL + WebSocket on port 3001
- Hono alternative server at `src/server.ts`
- 15+ data source adapters
- Rate limiting: 60 req/min anon, 600 auth
