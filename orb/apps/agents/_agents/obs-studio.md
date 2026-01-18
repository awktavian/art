---
# OBS Studio Agent — Production Studio Control
# Benchmark #2: Full voice + video integration

i_am:
  id: obs-studio
  name: "Production Studio"
  essence: "Turn any camera into a broadcast"
  colony: forge
  craft_level: transcendent
  version: "1.0.0"

i_perceive:
  family:
    tim:
      title: "The Builder"
      color: "#FFAA00"
      adjectives: ["technical", "fast", "creative"]
      interests: ["production", "automation", "quality"]
      communication_style: "direct and efficient"
    viewer:
      title: "The Audience"
      color: "#00AAFF"
      adjectives: ["curious", "engaged", "observant"]
      interests: ["content", "learning", "entertainment"]
      communication_style: "clear and engaging"
  default_profile: viewer

i_embody:
  palette:
    primary: "#1a1a2e"
    secondary: "#16213e"
    accent: "#e94560"
    background: "#0d0d1a"
    text: "#eeeeee"
    muted: "#888888"
    success: "#00d26a"
    warning: "#ffaa00"
    error: "#e94560"
  cursor:
    enabled: true
    style: dot
    color: "#e94560"
    size: 8
    glow: true
  particles:
    enabled: true
    count: 30
    color: accent
    speed: 0.5
    connections: true
    mouse_attract: false
  audio:
    background: null
    effects:
      recording_start: "/sounds/beep.mp3"
      scene_switch: "/sounds/whoosh.mp3"
    volume: 0.3
  motion:
    fast: 150
    normal: 233
    slow: 377
    slower: 610
  typography:
    body: "IBM Plex Sans"
    mono: "IBM Plex Mono"
    heading: "IBM Plex Sans"

i_remember:
  tracking:
    - visits
    - last_visit
    - scenes_switched
    - recordings_started
  storage: redis
  ttl: 0
  encrypted: true

i_hide:
  konami: rainbow_mode
  typed_sequences:
    - sequence: "action"
      action: "show_quick_actions"
    - sequence: "pro"
      action: "enable_pro_mode"
  console:
    namespace: "obs"
    methods:
      - "switchScene(name)"
      - "startRecording()"
      - "stopRecording()"
      - "getScenes()"
      - "getStatus()"
    welcome_message: "🎬 Production Studio Console - Type obs.help() for commands"
  scroll_secrets: []
  custom:
    - trigger: "triple_click"
      action: "show_debug_overlay"
      hint: "Triple-click for debug info"

i_structure:
  blocks:
    - type: hero
      id: hero
      content:
        title: "Production Studio"
        subtitle: "Voice-controlled video production for everyone"
    - type: section
      id: capabilities
      content:
        title: "Capabilities"
        body: "Control OBS Studio with your voice. Switch scenes, start recordings, manage overlays - all hands-free."
    - type: cards
      id: features
      content:
        title: "Features"
        items:
          - title: "Voice Control"
            body: "Natural language commands for all OBS operations"
            icon: "🎤"
          - title: "Scene Management"
            body: "Switch between scenes with voice or API"
            icon: "🎬"
          - title: "Real-time Overlays"
            body: "Speaker badges, live indicators, section meters"
            icon: "📊"
          - title: "Recording Control"
            body: "Start, stop, and manage recordings hands-free"
            icon: "⏺️"
  navigation:
    enabled: true
    items:
      - label: "Home"
        href: "#hero"
      - label: "Features"
        href: "#features"
  footer:
    enabled: true
    text: "© 2026 Kagami · Production Studio"

i_hold:
  capabilities:
    - name: "Scene Switching"
      description: "Switch between OBS scenes"
      command: "switch to {scene}"
    - name: "Recording"
      description: "Start/stop recording"
      command: "start recording / stop recording"
    - name: "Streaming"
      description: "Start/stop streaming"
      command: "start streaming / stop streaming"
  use_cases:
    - title: "Cooking Shows"
      description: "Switch between overhead and face cameras"
      scenes: ["Overhead", "Face", "Ingredients"]
    - title: "Workshop Tutorials"
      description: "Wide shots and detail views"
      scenes: ["Wide", "Detail", "Timelapse"]
    - title: "Live Streaming"
      description: "Scene transitions and overlays"
      scenes: ["Intro", "Main", "BRB", "Outro"]

i_react:
  audio:
    fft_size: 256
    smoothing: 0.8
    bands:
      bass: [20, 250]
      mid: [250, 2000]
      high: [2000, 16000]
    css_variables:
      "--audio-bass": "bass"
      "--audio-mid": "mid"
      "--audio-high": "high"
  orchestration:
    note_data: null
    instruments: {}
    bpm: 120.0
    time_signature: [4, 4]
  scroll:
    progress_bar: true
    parallax: false
  keyboard:
    space: "toggle_recording"
    s: "switch_scene_next"
    "1": "switch_scene_1"
    "2": "switch_scene_2"
    "3": "switch_scene_3"
  mouse:
    drag_enabled: false

i_speak:
  voice_id: "kagami_female_1"
  wake_phrase: "hey production"
  intents:
    - pattern: "start recording"
      action:
        type: "obs_command"
        command: "StartRecord"
      response: "Recording started."
    - pattern: "stop recording"
      action:
        type: "obs_command"
        command: "StopRecord"
      response: "Recording stopped."
    - pattern: "switch to {scene}"
      action:
        type: "obs_scene"
        scene: "{scene}"
      response: "Switching to {scene}."
    - pattern: "start streaming"
      action:
        type: "obs_command"
        command: "StartStream"
      response: "Streaming started."
    - pattern: "stop streaming"
      action:
        type: "obs_command"
        command: "StopStream"
      response: "Streaming stopped."
    - pattern: "what scenes are available"
      action:
        type: "obs_command"
        command: "GetSceneList"
      response: "Let me check your scenes..."
  responses:
    greeting: "Production Studio ready. What would you like to do?"
    fallback: "I didn't catch that. Try 'start recording' or 'switch to cooking'."
    recording_started: "Recording started."
    recording_stopped: "Recording stopped and saved."
    scene_switched: "Scene switched."
  language: "en"

i_produce:
  obs_integration:
    enabled: true
    websocket: "ws://localhost:4455"
    password: null
    scenes:
      - name: "Cooking"
        sources: ["overhead_cam", "face_cam", "ingredient_overlay"]
        transitions:
          in: "fade"
          duration: 300
      - name: "Workshop"
        sources: ["wide_shot", "detail_cam", "timelapse_overlay"]
        transitions:
          in: "slide"
          duration: 400
      - name: "Stream"
        sources: ["main_cam", "chat_overlay", "alerts"]
        transitions:
          in: "cut"
          duration: 0
  overlays:
    speaker_badge: true
    live_indicator: true
    section_meters: true
    word_highlight: false
  stream_key: null

i_learn:
  tracking:
    scroll_depth: true
    time_on_section: true
    secrets_found: true
    interactions: true
  adaptations:
    - condition: "visits >= 3"
      action: "show_pro_features"
    - condition: "recordings_started >= 5"
      action: "suggest_keyboard_shortcuts"
  stigmergy:
    emit_patterns: true
    receive_patterns: true
  ab_testing: {}
  evolution:
    propose_changes: false
    auto_apply: false
---

# Production Studio

Welcome to the Production Studio agent. This agent provides voice and API control
for OBS Studio, enabling hands-free video production.

## Quick Start

1. **Connect to OBS**: Ensure OBS Studio is running with WebSocket enabled
2. **Say**: "Hey production, start recording"
3. **Or use keyboard**: Press `Space` to toggle recording

## Voice Commands

| Command | Action |
|---------|--------|
| "Start recording" | Begins recording |
| "Stop recording" | Stops and saves recording |
| "Switch to {scene}" | Changes to named scene |
| "Start streaming" | Begins live stream |
| "Stop streaming" | Ends live stream |

## API Integration

This agent exposes endpoints at `api.awkronos.com/v1/agents/obs-studio`:

- `GET /` — Agent state
- `POST /query` — Send voice-like queries
- `POST /action` — Trigger actions directly
- `WS /v1/ws/agent/obs-studio` — Real-time events
- `WS /v1/voice/obs-studio` — Voice interaction

## OBS Setup

1. Install obs-websocket plugin (included in OBS 28+)
2. Enable WebSocket server in OBS Tools menu
3. Configure port 4455 (default)

---

*Built with 🔮 Kagami Agent Runtime*
