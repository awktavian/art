# Video Production Skill

**THE Single System — Unified video creation from topic to published content.**

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE SINGLE SYSTEM                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   TOPIC                                                         │
│     │                                                           │
│     ▼                                                           │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ topic_generator.py                                      │   │
│   │ LLM: Topic → Script                                     │   │
│   │ • Tone presets (educational_funny, professional, etc.)  │   │
│   │ • Duration-based slide count                            │   │
│   │ • Positive imagery guidelines                           │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ SCRIPT (list[dict])                                       │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ llm_slide_generator.py + slide_content.py               │   │
│   │ LLM: Script → SlideDesigns                              │   │
│   │ • Layout selection (hero, two-column, quote, etc.)      │   │
│   │ • Visual hints → Image prompts                          │   │
│   │ • Speaker personality integration                       │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ DESIGNS                                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ slide_design.py                                         │   │
│   │ HTML/CSS Generation                                     │   │
│   │ • Gradient themes (dark_blue, midnight, ocean, etc.)    │   │
│   │ • Fibonacci timing animations                           │   │
│   │ • IBM Plex Sans typography                              │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ HTML                                                      │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ slides.py                                               │   │
│   │ Playwright Rendering                                    │   │
│   │ • Real-time video capture                               │   │
│   │ • Time-scaling to match TTS duration                    │   │
│   │ • Parallel hero image generation (DALL-E)               │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ VIDEO                                                     │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ characters/voice.py                                     │   │
│   │ TTS Generation (ElevenLabs v3)                          │   │
│   │ • Word-level timestamps (GROUND TRUTH)                  │   │
│   │ • Pause tags for non-dialogue                           │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ AUDIO + TIMINGS                                           │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ subtitles/kinetic.py                                    │   │
│   │ ASS Subtitle Generation                                 │   │
│   │ • Word timings from TTS                                 │   │
│   │ • IBM Plex Sans styling                                 │   │
│   │ • 5px outline, 3px shadow                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼ SUBTITLES                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ compositor.py                                           │   │
│   │ FFmpeg Composition                                      │   │
│   │ • Video + Audio + Subtitles → Final MP4                 │   │
│   │ • CRF 12, preset slow, tune animation                   │   │
│   │ • movflags +faststart for web                           │   │
│   └─────────────────────────────────────────────────────────┘   │
│     │                                                           │
│     ▼                                                           │
│   FINAL MP4                                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```python
from kagami_studio.production import quick_video

# One-liner: Topic → Video
result = await quick_video(
    topic="The Science of Farts",
    duration=60,
    tone="educational_funny",
    deploy_name="farts",  # Optional: deploy to ~/projects/art/
)

print(f"Video: {result['video_path']}")
```

---

## Core API

### generate_script_from_topic()

```python
from kagami_studio.production import generate_script_from_topic

script = await generate_script_from_topic(
    topic="Why cats purr",
    duration=45,
    tone="educational_funny",  # or: educational, entertaining, professional, inspirational, storytelling
    speaker="tim",
)
```

### produce_video()

```python
from kagami_studio.production import produce_video

result = await produce_video(
    script=script,
    speaker="tim",
    generate_images=True,        # DALL-E hero images
    burn_ass_subtitles=True,     # Perfect sync
    reuse_images=False,          # Fresh images
)
```

---

## Critical: TTS as Ground Truth

**All timing derives from TTS word timestamps:**

1. TTS generates audio with `with_timestamps=True`
2. Word timings are parsed into slide timings
3. Slides are time-scaled to match audio duration
4. ASS subtitles use the same word timings
5. **Result: Perfect sync, always**

---

## Encoding Quality

```python
# Defaults in compositor.py
"-c:v", "libx264",
"-preset", "slow",          # Quality over speed
"-crf", "12",               # Near-lossless
"-tune", "animation",       # Optimized for graphics
"-profile:v", "high",       # Maximum compatibility
"-pix_fmt", "yuv420p",      # Universal playback
"-c:a", "aac",
"-b:a", "256k",             # High quality audio
"-movflags", "+faststart",  # Web streaming
```

---

## Image Generation Safety

All image prompts are automatically suffixed with:

```
Avoid: skulls, skeletons, bones, x-rays, medical imagery,
anatomy diagrams, creepy faces, distorted features,
horror elements, dark disturbing content.
```

---

## Deployment

```bash
# Quick deploy
python scripts/quick_video.py "Topic" --deploy project-name

# Manual steps:
# 1. Copy to ~/projects/art/{project}/
# 2. Transcode for mobile: ffmpeg -c:v libx265 -crf 23 -vf scale=1280:720
# 3. Upload to GCS: gsutil cp *.mp4 gs://kagami-media-public/
# 4. Push to git: cd ~/projects/art && git add . && git commit && git push
```

---

## Files (THE Single System)

| File | Purpose | LOC |
|------|---------|-----|
| `production/__init__.py` | Main orchestrator | 977 |
| `production/topic_generator.py` | Topic → Script | 398 |
| `production/script.py` | Script dataclasses | 392 |
| `production/llm_slide_generator.py` | LLM slide design | 1139 |
| `production/slide_content.py` | Content enhancement | 605 |
| `production/slide_design.py` | HTML/CSS generation | 2002 |
| `production/slides.py` | Playwright rendering | 539 |
| `production/compositor.py` | FFmpeg composition | 560 |
| `subtitles/kinetic.py` | ASS subtitles | ~200 |
| `characters/voice.py` | TTS with timestamps | ~300 |
| `generation/image.py` | DALL-E integration | 232 |

---

## Deleted (Legacy)

- ~~`production/visual_craft.py`~~ — Dead code
- ~~`documentary/`~~ — Separate unused system
- ~~Scattered production code~~ — All consolidated

---

## Recent Breakthroughs (2025-2026)

**Industry context for THE Single System:**

| Model | Capability | Our Advantage |
|-------|------------|---------------|
| **Runway Gen-4** | 10s text-to-video | We do 60s+ with perfect sync |
| **Google Veo 3** | Audio sync, 1080p | We have TTS ground truth |
| **Kling 2.1** | Quality modes | We have CRF 12 quality |
| **LTX-2** | 4K, open source | We have Playwright control |
| **LTX Studio** | Script→storyboard→video | We do this end-to-end |

---

## Key Insight

**Videos replace static images.**

The pipeline is fast enough (~2min for 60s video) that video should be the **default** for any visual content. Anywhere you'd generate a static hero image, consider a video instead.

---

## Documentary Mode

**Deep research on documentary craft — structures, techniques, and the masters.**

### Documentary Master Classes

#### King of Kong: A Fistful of Quarters (2007)
**Director:** Seth Gordon | **Runtime:** 79 minutes | **Budget:** ~$1M

| Technique | Implementation | Effect |
|-----------|----------------|--------|
| **Underdog Structure** | Steve Wiebe = everyman challenger | We root for vulnerability |
| **Villain Without Evil** | Billy Mitchell = SO confident | His hot sauce, his mullet, his entourage |
| **High Stakes from Nothing** | It's "just" Donkey Kong | Emotional stakes > logical stakes |
| **Cinema Verite** | Handheld, candid, unscripted | Authenticity over polish |
| **Music as GPS** | 80s nostalgia + classical drama | Tells us when to feel |
| **Editing as Argument** | 300 hours → 79 minutes | Every cut is a thesis |

**The Billy Mitchell Scandal:** The villain was ACTUALLY cheating. 2018: footage analyzed, showed MAME emulator artifacts. All scores stripped, banned. Reality exceeded the documentary's narrative.

#### Stories We Tell (2012)
**Director:** Sarah Polley | **The gold standard for family archive docs**

Revolutionary techniques:
1. **Recreated Home Movies** — Cast actors, shot on Super 8, 40% real / 60% recreation. Viewers can't tell the difference.
2. **Meta-Documentary** — Shows filmmaking process itself. "Who controls the story?"
3. **Multiple Unreliable Narrators** — Same events, different perspectives. Contradictions are the point.

**Lesson:** The documentary isn't about finding truth — it's about showing how we construct it.

#### Tarnation (2003)
**Director:** Jonathan Caouette | **Budget:** $218.32 (!)

- Made entirely in iMovie with 20+ years of personal footage
- Archive as raw material, collage editing, text as visual element
- **Lesson:** You don't need money. You need raw material and emotional truth.

#### 30 for 30 Formula (ESPN)
1. **Humanize the Icon** — Athletes as people, not performers
2. **Cultural Context** — Sports as lens on society
3. **Archival Immersion** — Deep archive + sound design
4. **Narrative Tension** — Build up → conflict → resolution
5. **Emotional Resonance** — Universal themes through specific stories

---

### Documentary Structure

#### Three-Act Structure

```
ACT ONE (Setup) — 25%
├── Introduce world and characters
├── Establish stakes
└── Inciting incident

ACT TWO (Confrontation) — 50%
├── Rising action, obstacles
├── Character development
├── Midpoint reversal
└── All hope seems lost

ACT THREE (Resolution) — 25%
├── Climax
├── Resolution
└── Reflection/meaning
```

#### Hero's Journey (Documentary Adaptation)

| Stage | Documentary Application |
|-------|------------------------|
| Ordinary World | Establish subject before "the call" |
| Call to Adventure | The event/question that starts the story |
| Tests/Allies/Enemies | The middle — challenges and helpers |
| Ordeal | The crisis, the confrontation, the truth |
| Return with Elixir | Sharing the wisdom gained |

---

### Documentary Techniques

#### Interview Craft

| Technique | Purpose |
|-----------|---------|
| **Active Listening** | Let them talk, follow threads |
| **Open-Ended Questions** | "Tell me about..." not "Did you..." |
| **Comfortable Environment** | Their home > your studio |
| **Silence** | Let them fill it — gold emerges |

#### Editing Principles

| Technique | Effect |
|-----------|--------|
| **Montage** | Compress time, show patterns |
| **Juxtaposition** | Meaning through contrast |
| **Rhythm** | Fast cuts = tension, slow = reflection |
| **J-Cut/L-Cut** | Smooth transitions, maintain flow |

#### Music & Sound Design

**Music Functions:**
- Establish era (80s synth = 80s)
- Signal emotion (strings = gravitas)
- Create tension (drone, rising pitch)
- Nostalgia trigger (period-specific songs)

**Sound Design:** Room tone, foley, ambient, silence for impact.

---

### Family Archive Documentaries

| Film | Approach |
|------|----------|
| **Stories We Tell** | Recreation + multiple perspectives |
| **Tarnation** | Raw personal archive, collage |
| **Dick Johnson Is Dead** | Staged scenarios + real emotion |
| **Shirkers** | Mystery of lost footage |

**What Makes Them Work:**
1. **Universality Through Specificity** — YOUR family → EVERY family
2. **Time as Material** — Past and present in conversation
3. **The Camera as Character** — Why did we record this?
4. **Absence as Presence** — What's NOT in the footage

---

### VHS Aesthetic

**Why It Resonates:**
- Texture of memory — imperfection = authenticity
- Era signifier — instantly dates footage
- Intimacy — home video = unguarded moments
- Mortality — degrading medium = time passing

**Technical Characteristics:** 240-480 lines resolution, chroma bleeding, tracking artifacts, dropout lines, tape warble in audio.

| Approach | When to Use |
|----------|-------------|
| **Full 4K Restoration** | Clean presentation, modern context |
| **Preserved Artifacts** | Authentic period feel, nostalgia |
| **Hybrid** | Clean footage, add texture in transitions |

---

### Narration Styles

| Style | Best For | Examples |
|-------|----------|----------|
| **First Person ("I")** | Personal stories, filmmaker as subject | Michael Moore, Morgan Spurlock |
| **Third Person ("They")** | Historical, expository, journalism | Ken Burns, Werner Herzog |
| **No Narration** | Events speak for themselves | "June 17th, 1994" (30 for 30) |

---

### Documentary Production with kagami_studio

1. **VLM Analysis** — Gemini analyzes footage
2. **Enhancement** — Topaz 4K restoration
3. **Depth Extraction** — 3D Ken Burns motion
4. **Transcription** — Word-level timing
5. **Typography** — Emotion-based text effects
6. **Web Artifacts** — Interactive DCC players

---

*"One pipeline. Perfect sync. Every time."*
