---
# MOP Agent — Master of Puppets Audio-Reactive Visualization
# Benchmark #6: Real-time audio analysis and orchestra visualization

i_am:
  id: mop
  name: "Master of Puppets"
  essence: "Audio-reactive orchestra visualization"
  colony: spark
  craft_level: transcendent
  version: "1.0.0"

i_perceive:
  family:
    metalhead:
      title: "The Headbanger"
      color: "#FF0000"
      adjectives: ["intense", "passionate", "rhythmic"]
      interests: ["metal", "music", "visualization"]
      communication_style: "energetic"
  default_profile: metalhead

i_embody:
  palette:
    primary: "#0a0a0a"
    secondary: "#1a1a1a"
    accent: "#FF3030"
    background: "#000000"
    text: "#ffffff"
    muted: "#666666"
    success: "#00ff00"
    warning: "#ffaa00"
    error: "#ff0000"
  cursor:
    enabled: false
    style: dot
    color: "#FF3030"
    size: 8
    glow: true
  particles:
    enabled: true
    count: 100
    color: accent
    speed: 2.0
    connections: false
    mouse_attract: true
  audio:
    background: "/audio/master_of_puppets.mp3"
    effects:
      bass_hit: "/sounds/thump.mp3"
    volume: 0.8
  motion:
    fast: 50
    normal: 100
    slow: 200
    slower: 400
  typography:
    body: "IBM Plex Sans"
    mono: "IBM Plex Mono"
    heading: "IBM Plex Sans"

i_remember:
  tracking:
    - visits
    - play_count
    - sections_viewed
    - peak_engagement
  storage: redis
  ttl: 0
  encrypted: false

i_hide:
  konami: headbang_mode
  typed_sequences:
    - sequence: "metal"
      action: "max_intensity"
    - sequence: "puppet"
      action: "show_strings"
  console:
    namespace: "mop"
    methods:
      - "play()"
      - "pause()"
      - "seek(time)"
      - "setIntensity(level)"
      - "showOrchestra()"
    welcome_message: "🎸 Master of Puppets - mop.play() to start"
  scroll_secrets: []
  custom:
    - trigger: "headbang"
      action: "camera_shake"
      hint: "Shake your device"

i_structure:
  blocks:
    - type: hero
      id: hero
      content:
        title: "Master of Puppets"
        subtitle: "Experience the orchestra in real-time"
    - type: custom
      id: visualizer
      content:
        html: |
          <div id="orchestra-container">
            <canvas id="orchestra-canvas"></canvas>
            <div id="section-meters"></div>
            <div id="instrument-labels"></div>
          </div>
    - type: section
      id: controls
      content:
        title: "Controls"
        body: "Space: Play/Pause | ←/→: Seek | 1-5: Jump to section"
  navigation:
    enabled: false
  footer:
    enabled: false

i_hold:
  capabilities:
    - name: "Audio Analysis"
      description: "Real-time FFT frequency analysis"
      bands: ["bass", "mid", "high"]
    - name: "Orchestra Visualization"
      description: "Note-accurate instrument display"
      instruments: 8
  use_cases:
    - title: "Music Experience"
      description: "Immersive audio-visual journey"
  custom:
    sections:
      - name: "Intro"
        start: 0
        end: 30
        bpm: 212
      - name: "Verse 1"
        start: 30
        end: 90
        bpm: 212
      - name: "Chorus"
        start: 90
        end: 150
        bpm: 212
      - name: "Interlude"
        start: 150
        end: 270
        bpm: 106
      - name: "Outro"
        start: 270
        end: 516
        bpm: 212
    instruments:
      - id: rhythm_guitar
        name: "Rhythm Guitar"
        color: "#FF3030"
        position: [0.2, 0.5]
      - id: lead_guitar
        name: "Lead Guitar"
        color: "#FF6030"
        position: [0.8, 0.5]
      - id: bass
        name: "Bass"
        color: "#3030FF"
        position: [0.3, 0.7]
      - id: drums
        name: "Drums"
        color: "#30FF30"
        position: [0.5, 0.8]
      - id: vocals
        name: "Vocals"
        color: "#FFFF30"
        position: [0.5, 0.3]

i_react:
  audio:
    fft_size: 512
    smoothing: 0.7
    bands:
      bass: [20, 150]
      low_mid: [150, 500]
      mid: [500, 2000]
      high_mid: [2000, 6000]
      high: [6000, 16000]
    css_variables:
      "--audio-bass": "bass"
      "--audio-low-mid": "low_mid"
      "--audio-mid": "mid"
      "--audio-high-mid": "high_mid"
      "--audio-high": "high"
      "--audio-intensity": "bass + mid * 0.5"
  orchestration:
    note_data: "notes.json"
    instruments:
      rhythm_guitar:
        channel: 1
        velocity_scale: 1.0
        visual: "glow"
      lead_guitar:
        channel: 2
        velocity_scale: 1.2
        visual: "spark"
      bass:
        channel: 3
        velocity_scale: 0.9
        visual: "pulse"
      drums:
        channel: 10
        velocity_scale: 1.5
        visual: "flash"
      vocals:
        channel: 4
        velocity_scale: 1.1
        visual: "wave"
    bpm: 212.0
    time_signature: [4, 4]
  scroll:
    progress_bar: true
    parallax: true
  keyboard:
    space: "toggle_playback"
    ArrowLeft: "seek_back_10"
    ArrowRight: "seek_forward_10"
    "1": "jump_section_1"
    "2": "jump_section_2"
    "3": "jump_section_3"
    "4": "jump_section_4"
    "5": "jump_section_5"
    m: "toggle_mute"
    f: "toggle_fullscreen"
  mouse:
    drag_enabled: true
    drag_action: "scrub_timeline"

i_speak:
  voice_id: "kagami_female_1"
  wake_phrase: null
  intents:
    - pattern: "play"
      action:
        type: "audio"
        command: "play"
      response: "Playing..."
    - pattern: "pause"
      action:
        type: "audio"
        command: "pause"
      response: "Paused."
    - pattern: "go to {section}"
      action:
        type: "seek"
        section: "{section}"
      response: "Jumping to {section}..."
  responses:
    greeting: "Master of Puppets visualization ready."
    fallback: "Say 'play' to start the experience."
  language: "en"

i_produce:
  obs_integration:
    enabled: false
    websocket: ""
    password: null
    scenes: []
  overlays:
    speaker_badge: false
    live_indicator: false
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
    - condition: "play_count >= 3"
      action: "unlock_intensity_slider"
    - condition: "sections_viewed >= 5"
      action: "show_section_stats"
  stigmergy:
    emit_patterns: true
    receive_patterns: true
  ab_testing: {}
  evolution:
    propose_changes: false
    auto_apply: false
---

# Master of Puppets

An audio-reactive visualization of Metallica's "Master of Puppets" with
real-time frequency analysis and note-accurate orchestra visualization.

## Features

### Real-Time Audio Analysis
- 512-point FFT for precise frequency detection
- 5 frequency bands: bass, low-mid, mid, high-mid, high
- Smoothed visualization with 0.7 factor
- CSS variable updates 60fps

### Orchestra Visualization
- Note-accurate MIDI synchronization
- 5 instruments with unique visual effects:
  - Rhythm Guitar: Red glow
  - Lead Guitar: Orange sparks
  - Bass: Blue pulse
  - Drums: Green flash
  - Vocals: Yellow wave

### Interactive Controls
- **Space**: Play/Pause
- **←/→**: Seek 10 seconds
- **1-5**: Jump to section
- **M**: Toggle mute
- **F**: Fullscreen

### Sections
1. Intro (0:00 - 0:30) @ 212 BPM
2. Verse 1 (0:30 - 1:30) @ 212 BPM
3. Chorus (1:30 - 2:30) @ 212 BPM
4. Interlude (2:30 - 4:30) @ 106 BPM
5. Outro (4:30 - 8:36) @ 212 BPM

## Technical Details

The visualization uses Web Audio API for frequency analysis and
requestAnimationFrame for smooth 60fps rendering. MIDI note data
is pre-processed and synchronized with audio playback for
millisecond-accurate instrument activation.

CSS variables are updated in real-time based on audio analysis:
- `--audio-bass`: Low frequency energy (20-150 Hz)
- `--audio-mid`: Mid frequency energy (500-2000 Hz)
- `--audio-high`: High frequency energy (6000-16000 Hz)
- `--audio-intensity`: Computed overall intensity

---

*Built with 🔮 Kagami Agent Runtime*
