# CLAUDE.md — Art Portfolio & Tools

@./.claude/rules/art-creation.md
@./.claude/rules/vercel-deployment.md

Multi-project portfolio of interactive web apps and shared libraries. Canonical deployment is GitHub Pages (`https://awktavian.github.io/art/`); a realtime voice proxy runs on Fly.io. Full deployment record: `docs/DEPLOY-STATUS.md`.

## Key Projects

| Project | Type | Entry Point | Port |
|---------|------|-------------|---------|
| **robo-skip/** | PWA curling strategist | `index.html` | static |
| **kagami-code-map/** | 3D semantic code viz | `index.html` | static |
| **skippy/** | Beer can recruitment pitch | `index.html` | static |
| **orb/** | Kagami Orb product page | `index.html` | static |
| **clue/** | Clue-themed architecture tour | `index.html` | static |
| **collapse/** | Domino cascade film gallery | `index.html` | static |
| **gen/** | Generative art gallery | `index.html` | static |
| **patent-portfolio/** | 3D patent museum (Three.js) | `index.html` | static |
| **realtime-proxy/** | OpenAI Realtime relay | `server.js` | 8766 |

(`medverify/` is a separate repository living inside this tree; it is ignored
here and not published with the portfolio — see `docs/DEPLOY-STATUS.md`.)

## Deployment

### Architecture

```
Static Portfolio (GitHub Pages)      Satellite Services (Fly.io)
├── 108-work inventory         ───→  realtime-proxy.fly.dev (OpenAI voice relay)
├── Generative art (gen/)
├── 3D experiences (Three.js)
├── Games & puzzles
├── Voice-enabled interfaces
└── Curated galleries
```

**Canonical site**: `https://awktavian.github.io/art/` (GitHub Pages, branch
`main`, folder `/`, `.nojekyll`; verified 2026-07-11 — see
`docs/DEPLOY-STATUS.md`). The branch tree IS the site; no build step.
`medverify/` is a separate ignored repository and is not published here.

**Quality gate**: `npm test` runs `test:unit` (node --test over `tests/unit/`, offline,
no credentials) then the same static + Chromium checks as CI
(link/asset targets, metadata, directory totals, PWA manifests, service
workers). See `docs/QUALITY.md`.

**Vercel**: `vercel.json` remains for incidental preview usage only; it is not
the canonical deployment. Do not configure a custom domain for this repo.
The cache and routing tables below describe that legacy Vercel config.

### Vercel MCP Tools — Capability Map (preview deploys only)

Claude has direct access to the Vercel platform via MCP. Use these tools for all deployment operations.

#### Deployment Lifecycle
| Tool | Use |
|------|-----|
| `deploy_to_vercel` | Trigger deployment from current project state |
| `get_deployment(idOrUrl, teamId)` | Check specific deployment status/details |
| `list_deployments(projectId, teamId, since?, until?)` | View deployment history with date filtering |
| `get_deployment_build_logs(idOrUrl, teamId, limit?)` | Debug build failures (default 100 lines) |

#### Monitoring & Testing
| Tool | Use |
|------|-----|
| `get_runtime_logs(projectId, teamId, ...)` | Filter by env, level, source, status code, query, time range |
| `web_fetch_vercel_url(url)` | Fetch deployed pages (handles Vercel auth automatically) |
| `get_access_to_vercel_url(url)` | Generate 23-hour shareable link for protected deployments |

#### Project & Team Management
| Tool | Use |
|------|-----|
| `list_teams` | Discover teams (returns IDs, slugs, roles) |
| `list_projects(teamId)` | List all projects for a team (max 50) |
| `get_project(projectId, teamId)` | Full project config: env vars, build settings, domains, framework |

#### Collaboration (Toolbar Threads)
| Tool | Use |
|------|-----|
| `list_toolbar_threads(teamId, ...)` | List feedback threads (filter by project, branch, page, status) |
| `get_toolbar_thread(threadId, teamId)` | Read full thread with all messages |
| `reply_to_toolbar_thread(threadId, teamId, markdown)` | Post reply in markdown |
| `edit_toolbar_message(threadId, messageId, teamId, markdown)` | Edit existing message |
| `add_toolbar_reaction(threadId, messageId, teamId, emoji)` | React with emoji |
| `change_toolbar_thread_resolve_status(threadId, teamId, resolved)` | Resolve/unresolve thread |

#### Domain & Docs
| Tool | Use |
|------|-----|
| `check_domain_availability_and_price(names[])` | Check up to 10 domains with pricing |
| `search_vercel_documentation(topic, tokens?)` | Search Vercel docs (default 2500 tokens) |

### Deployment Workflow — Standard Loop

```
1. DEVELOP  → Edit files locally (vanilla JS, no build step)
2. VALIDATE → npm test (static gate + Chromium canary; same as CI)
3. DEPLOY   → push to main — GitHub Pages deploys the branch tree as-is
4. VERIFY   → check the pages-build-deployment Action, then canary the live
             pages under https://awktavian.github.io/art/
5. ITERATE  → fix forward on main
```

### Cache Strategy (vercel.json — previews only)

| Asset Type | Cache Rule | Rationale |
|-----------|-----------|-----------|
| HTML | `max-age=0, must-revalidate` | Always fresh — content changes frequently |
| design-system.css | `max-age=0, must-revalidate` | Design tokens evolve with Kagami upstream |
| `/lib/*.js` | `max-age=31536000, immutable` | Shared libraries — versioned, rarely change |
| Other JS | `max-age=86400` | Project JS — 1 day cache, reasonable staleness |
| Other CSS | `max-age=86400` | Project CSS — 1 day cache |
| Assets (svg/png/jpg/woff2/mid) | `max-age=31536000, immutable` | Binary assets — content-addressed, never change |

### Routing (vercel.json)

- `/apps` → `/apps/index.html`, `/showcase` → `/home/index.html` (rewrites)
- `/medverify` → `https://medverify.fly.dev` (redirect, non-permanent)
- `/realtime-proxy` → `https://realtime-proxy.fly.dev` (redirect, non-permanent)
- `ignoreCommand` skips preview deploys when only medverify/ or realtime-proxy/ changed

## Creative Technology Stack

### Generative Art (`gen/`)
- Hash-seeded deterministic generation via Xorshift128+ PRNG
- 7 colony algorithm variations (Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal)
- Infinite unique variations from URL hash seeds
- "Breathing" animated backgrounds with palette swaps

### 3D Experiences
- **Patent Museum** (`patent-portfolio/`): Three.js museum with Fano plane geometry, Hopf fibrations, octonion algebra visualizations
- **Code Galaxy** (`kagami-code-map/`): Semantic 3D codebase visualization with voice-guided exploration

### Games & Interactive
- **Robo-Skip**: Real-time curling simulator with Monte Carlo shot analysis
- **Rogue**: Roguelike deck builder with daily puzzles
- **GemCraft Daily**: Puzzle game with LLM integration
- **Clue Architecture Tour**: Clue-themed mansion exploration

### Voice-Enabled AI Interfaces
- OpenAI Realtime API via WebSocket relay (realtime-proxy)
- 7 AI voice personas mapped to Fano colonies with catastrophe theory personalities
- Per-project perception/action tool systems for AI sensorimotor interaction

## Realtime Voice Architecture

```
Browser (any art project)
  └── VoiceOverlay.init({ project, tools, onFunctionCall })
        └── RealtimeVoice client (lib/realtime-voice.js)
              └── resolveRealtimeEndpoint('voice')  (lib/realtime-endpoint.js)
                    └── WebSocket → realtime-proxy?project=X&colony=Y  (both required)
                    └── WebSocket → wss://api.openai.com/v1/realtime
```

**Model**: required via `REALTIME_MODEL` — there is no default. `realtime-proxy/fly.toml`
sets `gpt-realtime` together with its four `REALTIME_PRICE_*_PER_MTOK` values
(source: https://developers.openai.com/api/docs/pricing, read 2026-09-04). The former
built-in default `gpt-4o-realtime-preview` is no longer on that page, which is why the
default was removed rather than updated.

**Proxy**: `realtime-proxy/server.js` — token bucket rate limiting (10 msg/s, burst 30),
per-session cost caps ($2 default), max 5 concurrent sessions. Cost is metered from the
`usage` block on OpenAI's `response.done`, never estimated per message; `/stats` rows
carry `metered: false` until the first response is billed, so a zero there means
"nothing charged yet" and not "measured as free". The `project` and `colony` query
params are required — a connection missing either is closed with 4400.

**Shared libraries** (lib/):
- `realtime-endpoint.js` — the ONE place a proxy URL is decided; no silent localhost
  default, throws `RealtimeEndpointUnavailable` naming the service when none exists
- `realtime-voice.js` — Push-to-talk mic capture (PCM16 24kHz), audio playback, function
  call routing. `proxyUrl` and `voice` are required constructor options
- `kagami-voices.js` — Colony→voice→personality mapping (7 colonies + orchestrator, EFE weights, catastrophe types)
- `voice-overlay.js` — Drop-in voice UI (floating toggle + transcript panel). Key V to toggle, hold Space to talk

## AI-Centric Tool Design

**CRITICAL**: Voice tools are sensorimotor interfaces for the AI, NOT user-facing features.

Every voice-enabled project provides two tool categories:
- **PERCEPTION** — Let the AI observe page state, DOM content, scroll position, animation state
- **ACTION** — Let the AI control the UI: scroll, open modals, trigger animations, navigate, highlight

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
OPENAI_API_KEY=sk-... \
REALTIME_MODEL=gpt-realtime \
REALTIME_PRICE_TEXT_IN_PER_MTOK=4 REALTIME_PRICE_TEXT_OUT_PER_MTOK=24 \
REALTIME_PRICE_AUDIO_IN_PER_MTOK=32 REALTIME_PRICE_AUDIO_OUT_PER_MTOK=64 \
npm start
```

The proxy refuses to start without all six, naming each missing one. The claude
scene director additionally requires `CLAUDE_DIRECTOR_MODEL`.

Health: `http://localhost:8766/health`
Stats: `http://localhost:8766/stats`

## Other Shared Libraries (lib/)

- `design-tokens.js` — Design system tokens (snapshot from Kagami upstream)
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
- Seeded PRNG for deterministic generative art (Xorshift128+ with FNV-1a hash)

## Kagami Ecosystem Integration

### Design Tokens
`lib/design-tokens.js` is a **snapshot** copied from `packages/kagami-design-tokens/tokens.json` in the Kagami repo. SSOT is Kagami. When tokens change upstream, re-export and replace. Never define parallel tokens here.

### Colony System
The `/kagami` skill routes tasks through the 7-colony Fano plane via EFE minimization. Colony→voice mapping in `lib/kagami-voices.js` is the art-project surface of that system. Tasks may arrive with `colony=Y` query param identifying which Fano colony owns the work.

### Dispatch Routing
Art project tasks can be dispatched from the Kagami daemon via `start_code_task`:
```python
start_code_task(
    project="/Users/schizodactyl/projects/art",
    task="...",
    colony="forge"   # optional Fano colony hint
)
```

## MCP Servers

Claude sessions in this project may have access to the following servers
(the `mcp__<hash>__*` tool prefixes are per-install; check the live session):

| Server | Use |
|--------|-----|
| **vercel** | Deploy, monitor, manage Vercel previews |
| **context7** | Current library/framework docs |
| **memory** | Persistent semantic graph |
| **github** | Issues, PRs, file access |
| **docker** | Container operations |
| **playwright** | Browser automation & E2E testing |
| **figma** | Design system, screenshots, diagrams |
| **huggingface** | Model hub, papers, docs |

All MCP tools allowed via `mcp__*` in `.claude/settings.json`. Full Kagami hook chain active.

## MedVerify specifics

MedVerify is a separate repository (`medverify/`, ignored here). See
`medverify/CLAUDE.md` for full documentation. Key points:
- TypeScript strict, ESM with `.js` extensions
- Express + GraphQL + WebSocket on port 3001
- Hono alternative server at `src/server.ts`
- 15+ data source adapters
- Rate limiting: 60 req/min anon, 600 auth
