# Voice and Audio Systems

*How Kagami speaks, listens, and fills the house with sound.*

---

## Overview

Kagami's audio system spans voice synthesis, speech recognition, orchestral rendering, spatial audio, and multi-room distribution. Everything routes through unified effectors with context-aware target selection.

---

## Voice Output

### Unified Voice Effector

All voice output flows through a single point of control.

**File:** `packages/kagami/core/effectors/voice.py`

```python
from kagami.core.effectors.voice import speak

await speak("Good morning, Tim")  # Auto-routes to best target
await speak("Dinner is ready", target=VoiceTarget.HOME_ALL)
```

### Voice Targets

| Target | Description | Hardware |
|--------|-------------|----------|
| AUTO | Context-aware selection | Depends on presence |
| HOME_ROOM | Current room only | Control4 audio zone |
| HOME_ALL | All 26 zones | Triad AMS 16x16 |
| CAR | Tesla cabin | Tesla VoiceAdapter |
| GLASSES | Private audio | Meta Ray-Ban speakers |
| DESKTOP | Local stereo | Mac Studio via afplay |

### Context Awareness

The effector knows:
- **Presence:** At home, in car, traveling
- **Time:** Night mode (22:00-07:00) = quieter
- **Activity:** Movie mode = audio ducking
- **Room:** Current location for intelligent routing

---

## Voice Synthesis (TTS)

### ElevenLabs V3

**Provider:** `packages/kagami/core/services/voice/tts/elevenlabs_provider.py`

- **Model:** ElevenLabs V3 (always—legacy models removed)
- **Latency:** ~75ms with Flash v2.5
- **Voice:** Kagami's cloned voice (ID stored in Keychain)
- **Streaming:** WebSocket for lowest latency

### Audio Tags

V3 supports expressive tags:

```python
await speak("[sighs] I suppose we should start the laundry")
await speak("[excited] Your package arrived!")
await speak("[whispers] Tim is sleeping")
await speak("[laughs] That's actually pretty funny")
await speak("[pause] Let me think about that")
```

### Colony Voice Personalities

Eight voices, one identity. Each colony has optimized synthesis parameters:

| Voice | Stability | Similarity | Style | Speed | Character |
|-------|-----------|------------|-------|-------|-----------|
| Kagami | 0.45 | 0.78 | 0.32 | 1.0 | Balanced observer |
| Spark | 0.32 | 0.75 | 0.48 | 1.06 | Energetic, enthusiastic |
| Forge | 0.52 | 0.80 | 0.35 | 0.96 | Measured, committed |
| Flow | 0.42 | 0.75 | 0.28 | 0.98 | Smooth, adaptive |
| Nexus | 0.46 | 0.76 | 0.30 | 0.97 | Integrative |
| Beacon | 0.55 | 0.82 | 0.22 | 1.0 | Clear, focused |
| Grove | 0.38 | 0.72 | 0.40 | 0.94 | Exploratory |
| Crystal | 0.62 | 0.85 | 0.18 | 1.0 | Precise, guardian |

**File:** `packages/kagami/core/services/voice/kagami_voice.py`

---

## Speech Recognition (STT)

### Faster-Whisper

**Provider:** `packages/kagami/core/services/voice/stt/faster_whisper_provider.py`

- **Models:** tiny, base, small, medium, large-v2
- **Backend:** CTranslate2 (optimized inference)
- **Devices:** CPU, Metal (Apple Silicon), CUDA

### Configuration

| Environment Variable | Purpose |
|---------------------|---------|
| `KAGAMI_STT_MODEL` | Model size (default: base) |
| `KAGAMI_STT_DEVICE` | Hardware (metal, cuda, cpu) |
| `KAGAMI_STT_COMPUTE` | Precision (int8, float16, float32) |
| `KAGAMI_STT_UPGRADE_ENABLED` | Second pass on low confidence |
| `KAGAMI_STT_PARTIAL_INTERVAL_S` | Streaming interval (0.20s) |

### Features

- Batch transcription at finalize
- Streaming partials with VAD
- Incremental decode for low latency

---

## Conversational AI

### Real-Time Dialogue

**File:** `packages/kagami/core/services/voice/conversational_ai.py`

Full-duplex voice conversation with:
- Turn-taking and interruption handling
- VAD (Voice Activity Detection)
- Multiple input sources (phone, WebRTC, hub)

### Conversation States

```
IDLE → CONNECTING → LISTENING → THINKING → SPEAKING → ENDED
                         ↓
                   INTERRUPTED
```

### Input Sources

| Source | Connection |
|--------|------------|
| Phone | Twilio Media Streams |
| Browser | WebRTC |
| Hub | Direct WebSocket |

---

## Music and Audio Analysis

### Unified Music Effector

**File:** `packages/kagami/core/effectors/music.py`

```python
from kagami.core.effectors.music import play

await play(track, target=MusicTarget.HOME_ATMOS)
```

### Playback Targets

| Target | Description |
|--------|-------------|
| DESKTOP_STEREO | Mac Studio speakers |
| DESKTOP_SURROUND | Denon via HDMI |
| HOME_ATMOS | KEF 5.1.4 Atmos |
| HOME_DISTRIBUTED | Triad zones |
| AUTO | Context-aware |

### Real-Time Analysis

The AudioAnalyzer provides FFT-based frequency analysis mapped to colonies:

| Colony | Frequency Range | Character |
|--------|-----------------|-----------|
| Spark | 8kHz-20kHz | High transients |
| Forge | 250Hz-2kHz | Rhythm, mids |
| Flow | 100Hz-500Hz | Smooth tones |
| Nexus | 200Hz-4kHz | Harmonics |
| Beacon | 500Hz-4kHz | Melody |
| Grove | 20Hz-200Hz | Bass |
| Crystal | 4kHz-16kHz | Brilliance |

Metrics: RMS energy, 32 log-spaced frequency bands, colony activations.

---

## Orchestral Capabilities

### BBC Symphony Orchestra

**File:** `packages/kagami/core/effectors/virtuoso_orchestra.py`

45-instrument orchestra with 3D positioning:

- **Layout:** Carnegie Hall / Vienna Musikverein seating
- **Positioning:** Azimuth, elevation, distance
- **Stereo spread:** Ensemble section width
- **Depth blending:** Dry close vs wet ambient

### Expression Engine

**File:** `packages/kagami/core/effectors/expression_engine.py`

MIDI CC automation:
- **CC1 (Dynamics):** Pianissimo → Fortissimo
- **CC11 (Expression):** Phrase swells, articulation

Features:
- Articulation detection and keyswitches
- Velocity humanization
- Rubato and tempo variation

### Musical Styles

| Style | Character |
|-------|-----------|
| Romantic | Large dynamics, expressive |
| Baroque | Terraced dynamics, precise timing |
| Classical | Balanced, moderate rubato |
| Modern | Sharp dynamics, precise |
| Film Score | Dramatic, sweeping gestures |
| Minimalist | Subtle, steady tempo |

### Orchestra Presets

Pre-configured templates for common use cases:
- Film Score, Epic Trailer, Emotional Underscore
- Baroque, Classical, Romantic, Modern
- Chamber, Ambient, Minimalist

**File:** `packages/kagami/core/effectors/orchestra_presets.py`

---

## Spatial Audio

### Unified Spatial Engine

**File:** `packages/kagami/core/effectors/spatial_audio.py`

Optimized for Tim's KEF 5.1.4 system:

| Speaker | Model | Position |
|---------|-------|----------|
| Front L/R | KEF Reference 5 Meta | Main stereo |
| Surround L/R | KEF Reference 1 Meta | Side/rear |
| Height (4) | CI200RR-THX | Atmos overhead |
| Subwoofers (2) | CI3160RLB-THX | LFE |

### Technical Details

- **Output:** 8-channel PCM via HDMI
- **Processor:** Denon AVR-A10H
- **Upmixing:** Neural:X for height channels
- **Panning:** VBAP (Vector Base Amplitude Panning)
- **Binaural:** HRTF support for AirPods

**Design Choice:** No signal to center channel—phantom imaging sounds more natural.

---

## Audio Processing

### Feature Extraction

**File:** `packages/kagami/core/multimodal/audio_processing.py`

| Feature | Description |
|---------|-------------|
| Mel-spectrogram | 128 bins, 8kHz max |
| Tempo | BPM detection |
| Spectral centroid | Brightness |
| Spectral rolloff | High-frequency content |
| Zero-crossing rate | Noisiness |
| RMS energy | Mean and peak |
| MFCC | 20 coefficients |
| Chroma | 12 pitch classes |

### Audio-Visual Sync

For video production:
- Tempo alignment analysis
- Optical flow motion metrics
- Fused multimodal signatures

---

## Audio Assembly

### Professional Mixing

**File:** `packages/kagami/core/effectors/audio_assembly.py`

| Operation | Description |
|-----------|-------------|
| WSOLA | Waveform time stretching |
| Crossfade | 10 curve types (sine, exponential, etc.) |
| Overlap-add | Seamless concatenation |
| Level matching | Headroom management |
| LUFS normalization | Standard: -14.0 |

### Quality

- 24-bit WAV support
- 48kHz sample rate (configurable)
- BBC Symphony Orchestra renders

---

## Earcon System

### Earcon Renderer

**File:** `packages/kagami/core/effectors/earcon_renderer.py`

Short musical phrases for notifications and feedback:

1. MIDI generation from orchestration
2. Expression engine application
3. REAPER rendering with BBC SO
4. Spatial trajectory via VBAP
5. Caching for instant playback

### Quality Standards

- **Fletcher:** Precision in every note
- **Williams:** Memorable themes
- **Elfman:** Character and personality
- **Spatial:** 3D movement and presence

---

## Voice Remixing

### Non-Destructive Transformation

**File:** `packages/kagami/core/services/voice/remixing.py`

Transform voice characteristics without losing identity:

| Transformation | Description |
|----------------|-------------|
| Gender | Masculine/feminine shift |
| Accent | Add or change accent |
| Style | Professional, casual, dramatic |
| Pacing | Faster, slower, deliberate |
| Quality | Enhancement and cleanup |

Prompt strength levels: LOW (0.2), MEDIUM (0.4), HIGH (0.6), MAX (0.8)

---

## Hub Voice Pipeline

### Rust Implementation

**File:** `apps/hub/kagami-hub/src/voice_pipeline.rs`

State machine for voice processing:

```
Listening → Capturing → Transcribing → Executing → Speaking
```

Components:
- `voice_controller.rs` — Speaker identification
- `streaming_stt.rs` — Real-time Whisper
- `tts.rs` — Synthesis
- `audio_stream.rs` — Capture and streaming
- `wake_word.rs` — "Hey Kagami" detection
- `speaker_id.rs` — Voice identification

---

## Summary

The audio system provides:

- **Voice synthesis** with 8 colony personalities via ElevenLabs V3
- **Speech recognition** via Faster-Whisper with Metal/CUDA support
- **Conversational AI** with full-duplex dialogue
- **Orchestral rendering** with 45-instrument BBC Symphony Orchestra
- **Spatial audio** optimized for KEF 5.1.4 Atmos
- **Multi-room distribution** across 26 audio zones
- **Professional assembly** with 24-bit quality

Every sound is intentional. Every voice has character.

---

*Sound is presence. Voice is identity.*
