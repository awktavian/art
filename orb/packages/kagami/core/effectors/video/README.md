# Video Effector — Honest Capabilities

## What Actually Works

### 1. Avatar Video Generation (HeyGen + ElevenLabs)

**REAL**: Generates talking avatar videos from identity images.

```python
from kagami.core.effectors.video import speak

# Generate a video of Kagami speaking
result = await speak("Hello Tim!")
# Returns: Path to .mp4 video file
```

**Limitations**:
- Fixed studio lighting (cannot match to scene)
- Front-facing camera only
- Single character per video
- Motion presets only (warm, friendly, serious)

### 2. Multi-Shot Production (director.py)

**REAL**: Sequences multiple HeyGen videos together.

```python
from kagami.core.effectors.video import Production

prod = Production(character="kagami")
prod.shot("Hello!")         # Shot 1
prod.shot("How are you?")   # Shot 2
result = await prod.render()
```

**Limitations**:
- Each shot is rendered separately by HeyGen
- No camera movement between shots
- Cuts only, no transitions

### 3. Background Generation (compositor.py)

**REAL**: Generates AI background images with optional zoompan motion.

```python
from kagami.core.effectors.video.compositor import BackgroundGenerator

bg = BackgroundGenerator()
video = await bg.generate_with_motion(
    "Modern living room, warm afternoon light",
    camera_motion="slow_zoom_in",
    duration=10.0,
)
```

**What it actually does**:
1. GPT-Image-1 generates ONE static image
2. FFmpeg zoompan creates "motion" (Ken Burns effect)

**Limitations**:
- NOT real video generation
- Cannot generate true motion (waves, fire, etc.)
- Just panning/zooming across static image

### 4. Chroma Key Compositing (compositor.py)

**REAL**: Composites green screen videos onto backgrounds.

```python
from kagami.core.effectors.video.compositor import LayerCompositor

compositor = LayerCompositor()
result = compositor.composite([
    Layer(path=background_video, layer_type=LayerType.BACKGROUND),
    Layer(path=character_video, layer_type=LayerType.CHARACTER, 
          chroma_key="0x00FF00", position=(400, 300)),
])
```

**Limitations**:
- Characters have fixed HeyGen lighting (won't match background)
- No shadow generation
- Green spill possible at edges
- Cutout aesthetic (not integrated)

### 5. Color Filters (cinematography.py)

**REAL**: FFmpeg color grading filters.

```python
from kagami.core.effectors.video.cinematography import ColorGrader, ColorGrade, FilmStock

grader = ColorGrader()
grade = ColorGrade(
    film_stock=FilmStock.KODAK_5219,
    saturation=1.1,
    temperature=10,  # Warmer
    grain=0.02,
)
output = grader.apply_grade(video, grade, output_path)
```

**What it actually does**:
- Shifts color balance
- Adjusts saturation/contrast
- Adds noise (fake "film grain")
- Adds vignette

**Limitations**:
- Cannot relight scene
- Cannot change shadow direction
- "Film stock" is just color filter preset


## What's Fake / Removed

The following features were **deleted** because they didn't work:

| File | Claimed Feature | Reality |
|------|-----------------|---------|
| `hdri_lighting.py` | Scene relighting | Dead code, never called |
| `deep_compositing.py` | Depth-aware blending | No depth data available |
| `aov_system.py` | Multi-pass compositing | No render passes exist |
| `genesis_bridge.py` | 3D rendering | Genesis not integrated |
| `distributed_rendering.py` | Cloud rendering | Not implemented |
| `narrative_camera.py` | Story-driven camera | Can't control HeyGen camera |
| `asset_library.py` | Versioned assets | Unnecessary overhead |


## Honest Approach to Video Production

Given these limitations, here's how to make decent videos:

### 1. Use Single-Character Shots with Cuts

Don't try to composite multiple characters. Film each separately and edit.

```
Shot 1: Kagami speaks (HeyGen)
Shot 2: Becky responds (HeyGen)  
Shot 3: Kagami reacts (HeyGen)
```

### 2. Match Lighting via Prompts

Since we can't relight, match lighting in generation prompts:

```python
# Background prompt
"Living room with warm afternoon light from LEFT side window"

# When generating character (future: instruct HeyGen)
# "Warm key light from LEFT, matching afternoon sun"
```

### 3. Accept the Aesthetic

The output will look like:
- AI-generated backgrounds
- Cutout characters pasted on top
- Color graded to match somewhat

This is fine for:
- Social media content
- Quick demos
- Proof of concept

Not suitable for:
- Cinematic productions
- VFX that needs to look "real"
- Multi-character interaction scenes


## Files in This Module

```
video/
├── __init__.py          # Exports
├── avatar_iv.py         # HeyGen API wrapper ✅
├── cinematography.py    # Color filters ✅ (honest now)
├── common.py            # Types
├── compositor.py        # Chroma key ✅ (honest now)
├── director.py          # Production sequencing ✅
├── identity.py          # Image selection ✅
├── preview.py           # Preview rendering
├── unified_av.py        # Primary interface ✅
├── voices.py            # Voice definitions ✅
└── README.md            # This file
```
