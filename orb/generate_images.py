#!/usr/bin/env python3
"""Generate Kagami Orb showcase images using gpt-image-1.5.

Uses existing kagami_studio.generation.image module.

CANONICAL DESIGN - All images must use this exact specification:
- Base: SQUARE walnut wood base, 180mm, brass trim on front edge, recessed circular center
- Orb: 120mm GLOSSY BLACK sphere, TWO horizontal brass/gold bands around equator
- Window: Large circular gold-framed infinity mirror showing LED tunnel effect
- Levitation: Orb floats 15mm above base
- Background: Dark charcoal studio with subtle gold particles

Run: cd ~/projects/kagami && python ~/projects/art/orb/generate_images.py
"""

import asyncio
import sys
from pathlib import Path

# Add kagami packages to path
sys.path.insert(0, str(Path.home() / "projects/kagami/packages"))

from kagami_studio.generation.image import generate_image

# Output directory
OUTPUT_DIR = Path.home() / "projects/art/orb/images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# CANONICAL DESIGN SPECIFICATION
# All images MUST maintain this exact product design for consistency
CANONICAL_BASE = """
EXACT DESIGN REQUIREMENTS - DO NOT DEVIATE:
- Base: SQUARE walnut wood base, 180mm, with brass trim on front edge, recessed circular center for levitation
- Orb: 120mm GLOSSY BLACK spherical shell with TWO horizontal brass/gold accent bands around equator
- Infinity Mirror: Large circular window on front showing LED ring creating infinite tunnel depth effect
- Levitation: Orb floats 15mm above base
- Background: Dark charcoal studio background with subtle gold particles
- Style: Premium product photography, soft studio lighting, photorealistic, magazine quality
- Camera: Front 3/4 view showing base and orb clearly
"""

# Colony color definitions (hex codes for reference)
COLONY_COLORS = {
    "spark": ("#FF6B35", "phoenix orange"),
    "forge": ("#FFB347", "forge amber gold"),
    "flow": ("#4ECDC4", "ocean teal cyan"),
    "nexus": ("#9B59B6", "bridge purple violet"),
    "beacon": ("#D4AF37", "tower gold"),
    "grove": ("#27AE60", "forest emerald green"),
    "crystal": ("#E0E0E0", "diamond white silver"),
}


async def generate_canonical(name: str, led_color: str, led_desc: str) -> Path | None:
    """Generate image with strict canonical design, only LED color varies."""
    prompt = f"""
{CANONICAL_BASE}
- LED Color: {led_desc} ({led_color}) glowing LEDs in the infinity mirror, {led_color} reflections creating depth
- The infinity tunnel shows concentric rings of {led_color} light receding to a central point
"""
    output_path = OUTPUT_DIR / f"{name}.png"
    
    if output_path.exists():
        print(f"⏭️  Skipping {name} (already exists)")
        return output_path
    
    print(f"🖼️  Generating: {name} ({led_color})...")
    result = await generate_image(
        prompt=prompt.strip(),
        width=1920,
        height=1080,
        output_path=str(output_path),
        quality="high",
    )
    if result:
        print(f"   ✅ Saved: {result}")
    else:
        print(f"   ❌ Failed: {name}")
    return result


async def generate_hero_closeup() -> Path | None:
    """Generate extreme macro of the infinity mirror effect."""
    prompt = """
Extreme macro closeup photograph of the infinity mirror window on the orb:
- Circular gold-framed window showing concentric rings of warm amber gold LEDs
- Multiple reflections receding into infinite depth, each ring smaller than the last
- Chrome reflective inner surface visible
- Shallow depth of field with beautiful bokeh
- Premium macro photography, sharp focus on LED pattern
- Warm amber gold color temperature
"""
    output_path = OUTPUT_DIR / "hero_closeup.png"
    
    if output_path.exists():
        print(f"⏭️  Skipping hero_closeup (already exists)")
        return output_path
    
    print("🖼️  Generating: hero_closeup...")
    result = await generate_image(prompt.strip(), 1920, 1080, str(output_path), "high")
    if result:
        print(f"   ✅ Saved: {result}")
    return result


async def generate_environment(name: str, env_desc: str, led_color: str = "warm amber gold") -> Path | None:
    """Generate environment shot maintaining canonical design."""
    prompt = f"""
{CANONICAL_BASE}
- LED Color: {led_color} LEDs in the infinity mirror creating cozy glow
- Environment: {env_desc}
- Camera: Side angle showing full orb and base in environment context
"""
    output_path = OUTPUT_DIR / f"{name}.png"
    
    if output_path.exists():
        print(f"⏭️  Skipping {name} (already exists)")
        return output_path
    
    print(f"🖼️  Generating: {name}...")
    result = await generate_image(prompt.strip(), 1920, 1080, str(output_path), "high")
    if result:
        print(f"   ✅ Saved: {result}")
    return result


async def generate_all_images():
    """Generate all orb showcase images with canonical design."""
    print("🎨 Generating Kagami Orb images with gpt-image-1.5...")
    print(f"📁 Output: {OUTPUT_DIR}\n")
    print("=" * 60)
    print("CANONICAL DESIGN: Square walnut base + black orb + gold bands")
    print("=" * 60 + "\n")

    # Hero images
    await generate_canonical("hero_orb", "warm amber gold", "warm amber and gold")
    await generate_hero_closeup()
    
    # All 7 colony colors
    for colony, (hex_code, desc) in COLONY_COLORS.items():
        await generate_canonical(f"colonies_{colony}", hex_code, desc)
    
    # Environment shots
    await generate_environment(
        "env_living_room",
        "Modern living room with fireplace in background, cozy evening atmosphere, lifestyle product photography",
    )
    
    # State images
    await generate_canonical("state_listening", "#4ECDC4", "ocean teal cyan listening mode")

    print("\n" + "=" * 60)
    print("✨ Generation complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(generate_all_images())
