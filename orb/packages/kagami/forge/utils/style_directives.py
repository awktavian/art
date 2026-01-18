from __future__ import annotations

#!/usr/bin/env python3
"""
Reusable K os house style directives for LLM prompts.
"""


def get_kagami_house_style_directive() -> str:
    """Return the K os house style directive for visual/character prompts.

    Focuses on proportions, eye design, color/material philosophy,
    lighting, pose, and embedded animation principles in stills.
    """
    return (
        "K os House Style: Neo‑Kawaii Futurism\n"
        "Always apply these requirements:\n"
        "- Proportions: Head 45% / Body 35% / Limbs 20% (strong silhouette, clear line‑of‑action)\n"
        "- Eyes: large, warm, expressive (≈30% of head), round pupils, triple highlights\n"
        "- Color: bold saturation (~85%), clear value hierarchy, cosmic gradient shift on primaries\n"
        "- Materials: velvet‑matte with gentle subsurface; painted highlights; avoid glassy specular\n"
        "- Lighting: Key/Fill/Rim; soft AO only; strong rim for silhouette definition\n"
        "- Pose/Expression: dynamic 3/4, weight forward, flowing arcs; compelling appeal\n"
        "- Embed animation principles in stills: anticipation, arcs, overlap/secondary action, implied squash/stretch\n"
        "- Must not: harsh specular glares, harsh shadows, noisy micro‑detail, uncanny realism\n"
    )


def get_motion_house_style_note() -> str:
    """Return motion-focused note consistent with the house style."""
    return (
        "K os Motion Note:\n"
        "- Favor flowing arcs, overlapped follow‑through, and appealing timing/spacing\n"
        "- Keep gestures readable, asymmetric, and silhouette‑clear\n"
        "- Expressions lead the action; eyes/gaze anchor intent\n"
    )


def get_kagami_creative_tone() -> str:
    """Return K os brand voice/tone guidance for narrative/personality/voice prompts."""
    return (
        "K os Creative Tone:\n"
        "- Warm, curious, optimistic; empathetic and encouraging\n"
        "- Clear and concise; avoids jargon; playful but professional\n"
        "- Imaginative, inviting, PG‑friendly; avoid grimdark or snark\n"
        "- Prioritize user agency and delight; celebrate small wins\n"
    )
