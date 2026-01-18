# Reference Image System

**Multi-image metadata and intelligent selection for optimal GPT-Image-1 generation.**

## Overview

The reference image system provides:
- **Metadata storage** for each reference image (quality, context, angle, etc.)
- **Smart selection** based on shot requirements
- **Multi-image prompting** to GPT-Image-1 for better consistency
- **Automatic discovery** from directory structures

## Quick Start

### 1. Organize Images

```
assets/characters/tim/
├── reference_1_professional.png
├── reference_2_casual.png
├── reference_3_relaxed.png
├── reference_4_morning.png
└── reference_5_outdoor.png
```

### 2. Create Metadata

Create `metadata.json` in the character directory:

```json
{
  "character_name": "Tim",
  "images": [
    {
      "path": "assets/characters/tim/reference_1_professional.png",
      "quality": "excellent",
      "context": "professional",
      "angle": "straight",
      "framing": "medium",
      "expression": "warm, confident smile",
      "lighting": "professional studio lighting, well-balanced",
      "notes": "Primary identity shot - blue jacket, formal setting",
      "weight": 1.5
    }
  ]
}
```

### 3. Use in Production

```python
from kagami.core.effectors.video import Production

# Character automatically loads reference images
tim = Production(character="tim")
tim.shot("Hello! I'm Tim.", motion="warm")
result = await tim.render()

# Multiple reference images are used for consistency
# Best images selected based on shot framing/context
```

## Metadata Fields

### Required

- **path**: Path to image file
- **quality**: `"excellent"` | `"good"` | `"fair"`
- **context**: `"professional"` | `"casual"` | `"outdoor"` | `"dining"` | `"home"` | `"action"`
- **angle**: `"straight"` | `"slight_up"` | `"slight_down"` | `"profile"` | `"three_quarter"`
- **framing**: `"closeup"` | `"medium"` | `"wide"`

### Optional

- **expression**: Description of facial expression/mood
- **lighting**: Lighting quality description
- **notes**: Additional notes
- **weight**: Selection priority (0.0-1.0, default 1.0, higher = prefer)

## Smart Selection

The system automatically selects the best reference images based on:

1. **Quality** - Prefers excellent > good > fair
2. **Context match** - Matches professional, casual, outdoor, etc.
3. **Framing match** - Matches desired camera framing
4. **Expression match** - Fuzzy matches on expression keywords
5. **Weight** - User-defined priority (1.5 = 50% more likely to be selected)
6. **Diversity** - When selecting multiple, prefers varied angles/contexts

### Example Selection

```python
from kagami.core.effectors.video import CHARACTERS
from kagami.core.effectors.video.reference_images import ImageContext

tim = CHARACTERS["tim"]

# Get single best for context
best = tim.reference_images.get_best(context=ImageContext.PROFESSIONAL)
# → reference_1_professional.png (weight=1.5, excellent quality)

# Get multiple diverse references
refs = tim.get_references(count=3, context="professional")
# → [reference_1_professional.png, reference_2_casual.png, reference_5_outdoor.png]
# Diverse angles and contexts for better generation
```

## Multi-Image Prompting

When multiple reference images are available, the system enhances prompts to GPT-Image-1:

```
CHARACTER (maintain EXACT consistency):
Face: ...
Eyes: ...
...

REFERENCE IMAGES: Multiple views of the SAME person.
Maintain PERFECT consistency across all references:
- Face structure consistent across straight, slight_down, three_quarter angles
- Same person in professional, outdoor settings
- EXACT facial features, hair, skin tone
- Synthesize MOST ACCURATE representation from all references
```

This improves:
- **Consistency** across different camera angles
- **Accuracy** by giving GPT-Image-1 multiple views
- **Quality** by combining best features from each reference

## Integration with Production System

The production system uses reference images automatically:

```python
# In Production.render()
reference_images = self.character.get_references(count=3)
# → Selects 3 best diverse references

hero = await self._image_gen.generate_hero(
    self.character,
    self.scene,
    hero,
    reference_images  # Used in GPT-Image-1 prompt
)

# Variations also use references
images = await self._image_gen.generate_all_variations(
    self.character,
    self.scene,
    framings,
    hero,
    reference_images  # Enhanced prompt for consistency
)
```

## Auto-Discovery

If `metadata.json` doesn't exist, the system auto-discovers from filenames:

```python
from kagami.core.effectors.video.reference_images import ReferenceImageSet

# Auto-discover from directory
refs = ReferenceImageSet.from_directory(
    Path("assets/characters/tim"),
    "Tim"
)

# Guesses from filename:
# - reference_1_*.png → quality=excellent
# - *professional*.png → context=professional
# - *outdoor*.png → context=outdoor
# - *dining*.png → context=dining
# - *closeup*.png → framing=closeup
```

**Always prefer explicit metadata.json for best results.**

## API Reference

### ReferenceImage

```python
@dataclass
class ReferenceImage:
    path: Path
    quality: ImageQuality = ImageQuality.GOOD
    context: ImageContext = ImageContext.CASUAL
    angle: ImageAngle = ImageAngle.STRAIGHT
    framing: Framing = Framing.MEDIUM
    expression: str = "neutral"
    lighting: str = "natural"
    notes: str = ""
    weight: float = 1.0
```

### ReferenceImageSet

```python
class ReferenceImageSet:
    def get_best(
        self,
        framing: Framing | None = None,
        context: ImageContext | None = None,
        expression: str | None = None,
        prefer_quality: bool = True,
    ) -> ReferenceImage | None
    
    def get_multiple(
        self,
        count: int = 3,
        framing: Framing | None = None,
        context: ImageContext | None = None,
        diversity: bool = True,
    ) -> list[ReferenceImage]
    
    @classmethod
    def from_directory(
        cls,
        directory: Path,
        character_name: str,
    ) -> "ReferenceImageSet"
```

### Character Integration

```python
class Character:
    reference_images: ReferenceImageSet | None
    
    def get_references(
        self,
        framing: Framing | None = None,
        context: str | None = None,
        count: int = 3,
    ) -> list[ReferenceImage]
```

## Best Practices

### Image Quality

1. **Resolution**: 1024x1024+ (square best for DALL-E, but 16:9 works for Avatar IV)
2. **Format**: PNG or JPG
3. **Lighting**: Clear, well-lit, good exposure
4. **Focus**: Sharp focus on face
5. **Variety**: Multiple angles and contexts

### Metadata Strategy

1. **Mark primary**: Highest weight (1.5) for best identity shot
2. **Quality over quantity**: 3-5 excellent images > 10 fair images
3. **Diverse contexts**: Professional, casual, outdoor, home
4. **Varied angles**: Straight, slight variations
5. **Consistent person**: All images same person!

### Weight Guidelines

- `1.5` - Primary identity shot (best quality, most representative)
- `1.3` - Excellent secondary shot
- `1.2` - Good alternative angle/context
- `1.0` - Standard quality, useful but not preferred
- `0.8` - Lower quality but acceptable
- `0.5` - Only use if nothing else matches

## Example: Complete Setup

```bash
# 1. Organize images
assets/characters/tim/
├── reference_1_professional.png  # Studio headshot
├── reference_2_casual.png        # Outdoor casual
├── reference_3_relaxed.png       # Home setting
├── reference_4_morning.png       # Natural indoor
├── reference_5_outdoor.png       # Outdoor portrait
├── tim_voice.mp3                 # Voice sample
└── metadata.json                 # Metadata file
```

```json
{
  "character_name": "Tim",
  "images": [
    {
      "path": "assets/characters/tim/reference_1_professional.png",
      "quality": "excellent",
      "context": "professional",
      "angle": "straight",
      "framing": "medium",
      "expression": "warm, confident smile",
      "lighting": "professional studio lighting",
      "weight": 1.5
    },
    {
      "path": "assets/characters/tim/reference_2_casual.png",
      "quality": "excellent",
      "context": "outdoor",
      "angle": "slight_down",
      "framing": "medium",
      "expression": "genuine smile, relaxed",
      "lighting": "natural daylight",
      "weight": 1.3
    }
  ]
}
```

```python
# 2. Use in production
from kagami.core.effectors.video import Production

# System automatically:
# - Loads metadata from assets/characters/tim/metadata.json
# - Selects best 3 images for generation
# - Enhances GPT-Image-1 prompts with multi-image context
# - Generates consistent results across all shots

tim = Production(character="tim")
tim.shot("Hello! I'm Tim Jacoby.", motion="warm")
tim.shot("Let me tell you about my project.", motion="excited")
result = await tim.render()

# Output: Consistent character across both shots using multi-image references
```

## Troubleshooting

### Images not loading

```python
# Check if metadata exists
from pathlib import Path
metadata = Path("assets/characters/tim/metadata.json")
print(metadata.exists())  # Should be True

# Manually load and inspect
from kagami.core.effectors.video.reference_images import ReferenceImageSet
refs = ReferenceImageSet.load(metadata)
print(f"Loaded {len(refs.images)} images")
for img in refs.images:
    print(f"  {img.path.name}: exists={img.exists}")
```

### Selection not working as expected

```python
# Debug selection
from kagami.core.effectors.video import CHARACTERS
from kagami.core.effectors.video.reference_images import ImageContext

tim = CHARACTERS["tim"]
refs = tim.reference_images

# Check what's being selected
best = refs.get_best(context=ImageContext.PROFESSIONAL)
print(f"Best: {best.path.name if best else 'None'}")

# Get scoring breakdown (weights + matches)
for img in refs.images:
    score = img.weight
    if img.context == ImageContext.PROFESSIONAL:
        score += 1.5
    print(f"{img.path.name}: score={score} (weight={img.weight}, context={img.context.value})")
```

---

Created: January 2, 2026
Author: Kagami Production System
