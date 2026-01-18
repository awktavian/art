#!/usr/bin/env python3
"""Demo: ElevenLabs Voice Remixing Integration.

Demonstrates how to use voice remixing to create voice variants:
1. Preview remix transformations
2. Create permanent voice variants
3. Use presets for common transformations
4. Integrate with dialogue generation

Usage:
    python examples/demo_voice_remixing.py

Requirements:
    - ElevenLabs API key in keychain (elevenlabs_api_key)
    - Kagami voice ID in keychain (elevenlabs_kagami_voice_id)

Created: January 4, 2026
"""

import asyncio
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))


async def demo_list_voices() -> None:
    """Demo: List available voices for remixing."""
    print("\n" + "=" * 60)
    print("1. LIST REMIXABLE VOICES")
    print("=" * 60)

    from kagami.core.services.voice.remixing import get_voice_remixer

    remixer = await get_voice_remixer()
    voices = await remixer.list_remixable_voices()

    print(f"\nFound {len(voices)} remixable voices:\n")
    for v in voices[:10]:  # Show first 10
        kagami_marker = " [KAGAMI]" if v.is_kagami else ""
        print(f"  • {v.name}{kagami_marker}")
        print(f"    ID: {v.voice_id[:16]}...")
        print(f"    Category: {v.category}")
        if v.description:
            print(f"    Description: {v.description[:50]}...")
        print()


async def demo_preview_remix() -> None:
    """Demo: Preview a voice remix before applying."""
    print("\n" + "=" * 60)
    print("2. PREVIEW VOICE REMIX")
    print("=" * 60)

    from kagami.core.services.voice.remixing import (
        get_voice_remixer,
        PromptStrength,
    )

    remixer = await get_voice_remixer()

    # Get Kagami's voice ID
    if not remixer._kagami_voice_id:
        print("  [SKIP] Kagami voice ID not configured")
        return

    print("\nRemixing Kagami's voice with 'warmer British accent'...")
    print(f"  Voice ID: {remixer._kagami_voice_id}")
    print(f"  Prompt Strength: {PromptStrength.MEDIUM.value} ({PromptStrength.MEDIUM.value_float})")

    try:
        previews = await remixer.preview_remix(
            voice_id=remixer._kagami_voice_id,
            description="Make the voice warmer with a subtle British accent",
            prompt_strength=PromptStrength.MEDIUM,
        )

        print(f"\n  Generated {len(previews)} preview(s):")
        for i, preview in enumerate(previews):
            print(f"\n  Preview {i + 1}:")
            print(f"    Generated ID: {preview.generated_voice_id[:16]}...")
            if preview.preview_path:
                print(f"    Audio saved: {preview.preview_path}")
            if preview.audio_data:
                print(f"    Audio size: {len(preview.audio_data):,} bytes")

    except Exception as e:
        print(f"  [ERROR] {e}")


async def demo_quick_remix() -> None:
    """Demo: Use presets for quick remixing."""
    print("\n" + "=" * 60)
    print("3. QUICK REMIX WITH PRESETS")
    print("=" * 60)

    from kagami.core.services.voice.remixing import REMIX_PRESETS

    print("\nAvailable presets:\n")

    categories = {
        "Gender/Age": ["younger", "older", "more_masculine", "more_feminine"],
        "Style": ["whisper", "dramatic", "professional", "casual", "energetic", "calm"],
        "Accent": ["british", "american", "australian"],
        "Quality": ["warmer", "clearer", "richer"],
    }

    for category, presets in categories.items():
        print(f"  {category}:")
        for preset in presets:
            if preset in REMIX_PRESETS:
                info = REMIX_PRESETS[preset]
                print(f"    • {preset}: {info['description']}")
                print(f"      (strength: {info['prompt_strength']})")
        print()


async def demo_remix_workflow() -> None:
    """Demo: Full remix workflow (preview → select → apply)."""
    print("\n" + "=" * 60)
    print("4. FULL REMIX WORKFLOW")
    print("=" * 60)

    from kagami.core.services.voice.remixing import get_voice_remixer

    remixer = await get_voice_remixer()

    if not remixer._kagami_voice_id:
        print("  [SKIP] Kagami voice ID not configured")
        return

    print("\nWorkflow: Create 'Kagami Whisper' voice variant")
    print("  1. Generate previews")
    print("  2. Select best preview")
    print("  3. Create permanent voice")

    print("\n  [DRY RUN - not executing to save API credits]")
    print("\n  Code to execute:")
    print("""
    # Generate previews
    previews = await remixer.preview_remix(
        voice_id="your_voice_id",
        description="Make the voice softer and more intimate",
        prompt_strength=0.7,
    )

    # Listen to previews (play preview.preview_path)
    # Select the best one (index 0 in this case)
    selected = previews[0]

    # Create permanent voice
    new_voice_id = await remixer.apply_remix(
        name="Kagami Whisper",
        generated_voice_id=selected.generated_voice_id,
    )

    print(f"Created voice: {new_voice_id}")
    """)


async def demo_dialogue_integration() -> None:
    """Demo: Integrate remixing with dialogue generation."""
    print("\n" + "=" * 60)
    print("5. DIALOGUE INTEGRATION")
    print("=" * 60)

    print("\nRemixing can create character voice variants for dialogue:")
    print("""
    from kagami.core.services.voice.dialogue import (
        remix_speaker_voice,
        create_voice_variant,
        DialogueGenerator,
        Speaker,
    )

    # Get dialogue generator
    gen = await get_dialogue_generator()
    kagami = gen.get_kagami_speaker()

    # Create a dramatic variant
    kagami_dramatic = await remix_speaker_voice(
        speaker=kagami,
        description="Make the voice more theatrical and dramatic",
        new_name="Kagami (Dramatic)",
        prompt_strength=0.6,
    )

    # Use in dialogue
    lines = [
        DialogueLine(kagami, "Welcome to the story."),
        DialogueLine(kagami_dramatic, "[dramatically] And NOW... the CLIMAX!"),
        DialogueLine(kagami, "Thank you for listening."),
    ]

    result = await gen.generate(lines)
    """)


async def demo_effector_output() -> None:
    """Demo: Voice output through UnifiedVoiceEffector."""
    print("\n" + "=" * 60)
    print("6. UNIFIED VOICE EFFECTOR")
    print("=" * 60)

    print("\nAll voice output routes through UnifiedVoiceEffector:")
    print("""
    from kagami.core.effectors.voice import speak, VoiceTarget

    # Auto-route (context-aware)
    await speak("Hello Tim")

    # Specific room
    await speak("Dinner is ready", rooms=["Kitchen"])

    # All zones
    await speak("Goodnight", target=VoiceTarget.HOME_ALL)

    # With colony conditioning
    await speak("[excited] Great news!", colony="spark")
    """)

    print("\nVoice targets available:")
    from kagami.core.effectors.voice import VoiceTarget

    for target in VoiceTarget:
        print(f"  • {target.value}: {target.name}")


async def main() -> None:
    """Run all demos."""
    print("\n" + "=" * 60)
    print("ELEVENLABS VOICE REMIXING DEMO")
    print("=" * 60)

    await demo_list_voices()
    await demo_preview_remix()
    await demo_quick_remix()
    await demo_remix_workflow()
    await demo_dialogue_integration()
    await demo_effector_output()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)

    # Show final stats
    from kagami.core.services.voice.remixing import get_voice_remixer

    remixer = await get_voice_remixer()
    stats = remixer.get_stats()
    print("\nRemixer stats:")
    print(f"  Cached voices: {stats['cached_voices']}")
    print(f"  Previews generated: {stats['previews_generated']}")
    print(f"  Voices created: {stats['voices_created']}")


if __name__ == "__main__":
    asyncio.run(main())
