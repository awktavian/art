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

**Model**: `gpt-4o-realtime-preview` (default; override via `REALTIME_MODEL` env var). Connects to `wss://api.openai.com/v1/realtime` with `OpenAI-Beta: realtime=v1` header.

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

## Kagami Ecosystem Integration

### Design Tokens

`lib/design-tokens.js` is a **snapshot** copied from `packages/kagami-design-tokens/tokens.json` in the Kagami repo. SSOT is Kagami. When tokens change upstream, re-export and replace `lib/design-tokens.js`. Never define parallel tokens here.

### Colony System

The `/kagami` skill (in the Kagami repo) routes tasks through the 7-colony Fano plane via EFE minimization. The colony→voice mapping in `lib/kagami-voices.js` is the art-project surface of that system — same 7 colonies, same EFE weights, same catastrophe types. When working on art projects as a Claude Code subagent, tasks may be dispatched with a `colony=Y` query param identifying which Fano colony owns the work.

### Voice Libraries

`lib/` contains shared libraries generated/maintained in the Kagami monorepo and mirrored here:
- `realtime-voice.js`, `kagami-voices.js`, `voice-overlay.js` — voice integration stack
- `kagami-sounds.js`, `kagami-sounds-data.js` — audio engine
- `kagami-visuals.js`, `kagami-xr.js` — visual/XR effects
- `design-tokens.js` — snapshot of Kagami design tokens

### Dispatch Routing

Art project tasks can be dispatched from the Kagami daemon via `start_code_task`. This is the intended path for autonomous agents to spawn Claude Code sessions targeting the art project:

```python
# Kagami daemon dispatches to art project
start_code_task(
    project="/Users/schizodactyl/projects/art",
    task="...",
    colony="forge"   # optional Fano colony hint
)
```

`start_code_task` is not yet a first-class MCP tool — it currently routes through `DaemonTaskRunner` in the kagami daemon. This note is forward-looking.

## MCP Servers

Claude Code sessions in this project inherit the Kagami MCP configuration. Available servers:

| Server | Access Pattern | Use |
|--------|---------------|-----|
| **context7** | `mcp__context7__*` | Current library/framework docs |
| **memory** | `mcp__memory__*` | Persistent semantic graph |
| **github** | `mcp__github__*` | Issues, PRs, file access |
| **docker** | `mcp__docker__*` | Container operations |
| **playwright** | `mcp__playwright__*` | Browser automation |
| **sequential-thinking** | `mcp__sequential-thinking__*` | Multi-step reasoning |
| **computer-use** | `mcp__computer-use__*` | Desktop/screenshot control |
| **apple-calendar** | `mcp__apple-calendar__*` | Calendar/reminders |

All MCP tools are allowed via `mcp__*` in `.claude/settings.json`. The full kagami hook chain (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, etc.) is active — same as the main Kagami project.

## MedVerify specifics

See `medverify/CLAUDE.md` for full documentation. Key points:
- TypeScript strict, ESM with `.js` extensions
- Express + GraphQL + WebSocket on port 3001
- Hono alternative server at `src/server.ts`
- 15+ data source adapters
- Rate limiting: 60 req/min anon, 600 auth
