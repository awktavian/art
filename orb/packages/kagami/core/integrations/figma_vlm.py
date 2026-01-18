"""VLM-based Figma design analysis.

This module provides Visual Language Model integration for analyzing
Figma designs and enforcing Prismorphism design standards.

Pipeline:
1. Export Figma frame as PNG using figma_direct
2. Run VLM analysis via Gemini (kagami_studio.vlm.gemini)
3. Score against Prismorphism criteria
4. Return violations and suggestions

Key Features:
- Design QA automation (triggered by @design-qa comments)
- Prismorphism compliance checking
- Accessibility verification (contrast, text size)
- Component consistency analysis

Created: January 5, 2026
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class DesignAnalysisResult:
    """Result of VLM design analysis.

    Attributes:
        score: Overall design quality score (0-100).
        prismorphism_compliance: Compliance with Prismorphism standards (0-1).
        violations: List of design violations found.
        suggestions: List of improvement suggestions.
        accessibility_issues: Accessibility problems detected.
        raw_analysis: Full VLM response for debugging.
    """

    score: int = 0
    prismorphism_compliance: float = 0.0
    violations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    accessibility_issues: list[str] = field(default_factory=list)
    raw_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "score": self.score,
            "prismorphism_compliance": self.prismorphism_compliance,
            "violations": self.violations,
            "suggestions": self.suggestions,
            "accessibility_issues": self.accessibility_issues,
        }

    def to_comment(self) -> str:
        """Format as Figma comment."""
        emoji = "✅" if self.score >= 80 else "⚠️" if self.score >= 60 else "❌"
        lines = [
            f"{emoji} **Design QA Score: {self.score}/100**",
            f"Prismorphism Compliance: {self.prismorphism_compliance:.0%}",
            "",
        ]

        if self.violations:
            lines.append("**Violations:**")
            for v in self.violations[:5]:
                lines.append(f"• {v}")
            lines.append("")

        if self.accessibility_issues:
            lines.append("**Accessibility:**")
            for a in self.accessibility_issues[:3]:
                lines.append(f"• {a}")
            lines.append("")

        if self.suggestions:
            lines.append("**Suggestions:**")
            for s in self.suggestions[:3]:
                lines.append(f"• {s}")

        return "\n".join(lines)


# Prismorphism design criteria for VLM analysis
PRISMORPHISM_CRITERIA = """
Kagami's design language is Prismorphism - glassmorphism with Fano chromatic dispersion.

Core Principles:
1. SPECTRAL COLORS (7 colony colors):
   - Spark (#FF5722), Forge (#FF9800), Flow (#4DB6AC)
   - Nexus (#9C27B0), Beacon (#FFB74D), Grove (#4CAF50), Crystal (#7E57C2)

2. GLASSMORPHISM:
   - Semi-transparent backgrounds (10-60% opacity based on discovery state)
   - Subtle blur effects (backdrop-filter: blur)
   - No harsh edges - use border-radius and soft shadows

3. DISCOVERY STATES (opacity progression):
   - Rest: 0% | Glance: 10% | Interest: 25% | Focus: 40% | Engage: 60%

4. TYPOGRAPHY:
   - IBM Plex Sans/Mono (NOT Inter)
   - Clear hierarchy with proper sizing

5. MOTION:
   - Fibonacci timing (89ms, 144ms, 233ms, 377ms)
   - Smooth transitions, no jarring animations

6. ACCESSIBILITY:
   - Minimum 4.5:1 contrast ratio for text
   - Touch targets at least 44x44pt
   - Clear focus states
"""


async def analyze_figma_frame(
    file_key: str,
    node_id: str,
    *,
    export_format: str = "png",
    export_scale: float = 2.0,
) -> DesignAnalysisResult:
    """Use VLM to analyze a Figma frame for design quality.

    This function exports a frame from Figma as an image, then uses
    Gemini VLM to analyze it against Prismorphism design criteria.

    Args:
        file_key: Figma file key (e.g., "27pdTgOq30LHZuaeVYtkEN").
        node_id: Node ID of the frame to analyze (e.g., "1234:5678").
        export_format: Image format ("png", "jpg", "svg").
        export_scale: Export scale factor (1.0-4.0).

    Returns:
        DesignAnalysisResult with score, violations, and suggestions.

    Example:
        >>> result = await analyze_figma_frame(
        ...     "27pdTgOq30LHZuaeVYtkEN",
        ...     "1:2"
        ... )
        >>> print(f"Score: {result.score}/100")
    """
    try:
        # Step 1: Export frame as image from Figma
        from kagami.core.integrations.figma_direct import get_figma_client

        client = await get_figma_client()
        images_response = await client.get_file_images(
            file_key,
            [node_id],
            format=export_format,
            scale=export_scale,
        )

        # Get image URL
        images = images_response.get("images", {})
        image_url = images.get(node_id)

        if not image_url:
            logger.error(f"Failed to export Figma frame: {node_id}")
            return DesignAnalysisResult(
                score=0,
                violations=["Failed to export frame from Figma"],
            )

        # Step 2: Download image
        async with aiohttp.ClientSession() as session, session.get(image_url) as resp:
            if resp.status != 200:
                return DesignAnalysisResult(
                    score=0,
                    violations=["Failed to download exported image"],
                )
            image_data = await resp.read()

        # Step 3: Run VLM analysis
        result = await _run_vlm_analysis(image_data, export_format)

        return result

    except Exception as e:
        logger.error(f"Design analysis failed: {e}")
        return DesignAnalysisResult(
            score=0,
            violations=[f"Analysis error: {e!s}"],
        )


async def _run_vlm_analysis(
    image_data: bytes,
    image_format: str,
) -> DesignAnalysisResult:
    """Run VLM analysis on image data.

    Uses Gemini VLM via kagami_studio for design analysis.

    Args:
        image_data: Raw image bytes.
        image_format: Image format (png, jpg).

    Returns:
        Parsed DesignAnalysisResult.
    """
    try:
        # Try using kagami_studio VLM
        from kagami_studio.vlm.gemini import analyze_image_with_prompt

        prompt = f"""Analyze this UI design against Prismorphism criteria:

{PRISMORPHISM_CRITERIA}

Evaluate and return a JSON response with:
{{
    "score": <0-100 overall score>,
    "prismorphism_compliance": <0.0-1.0>,
    "violations": ["list of violations"],
    "suggestions": ["list of improvements"],
    "accessibility_issues": ["list of accessibility problems"]
}}

Be specific about colors, spacing, typography, and visual hierarchy issues.
"""

        # Encode image as base64
        image_b64 = base64.b64encode(image_data).decode("utf-8")
        mime_type = f"image/{image_format}"

        # Run VLM analysis
        response = await analyze_image_with_prompt(
            image_b64=image_b64,
            mime_type=mime_type,
            prompt=prompt,
        )

        # Parse response
        return _parse_vlm_response(response)

    except ImportError:
        logger.warning("kagami_studio.vlm not available, using fallback analysis")
        return _fallback_analysis()

    except Exception as e:
        logger.error(f"VLM analysis failed: {e}")
        return DesignAnalysisResult(
            score=50,
            violations=[f"VLM analysis error: {e!s}"],
            suggestions=["Manual review recommended"],
        )


def _parse_vlm_response(response: dict[str, Any]) -> DesignAnalysisResult:
    """Parse VLM response into DesignAnalysisResult.

    Args:
        response: Raw VLM response (may be JSON or text).

    Returns:
        Parsed DesignAnalysisResult.
    """
    try:
        # If response is already a dict with expected fields
        if isinstance(response, dict):
            return DesignAnalysisResult(
                score=int(response.get("score", 50)),
                prismorphism_compliance=float(response.get("prismorphism_compliance", 0.5)),
                violations=list(response.get("violations", [])),
                suggestions=list(response.get("suggestions", [])),
                accessibility_issues=list(response.get("accessibility_issues", [])),
                raw_analysis=response,
            )

        # If response is a string, try to extract JSON
        import json
        import re

        if isinstance(response, str):
            # Try to find JSON in response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                return _parse_vlm_response(data)

        # Fallback
        return DesignAnalysisResult(
            score=50,
            raw_analysis={"raw": str(response)},
        )

    except Exception as e:
        logger.debug(f"Failed to parse VLM response: {e}")
        return DesignAnalysisResult(score=50)


def _fallback_analysis() -> DesignAnalysisResult:
    """Fallback analysis when VLM is not available."""
    return DesignAnalysisResult(
        score=70,
        prismorphism_compliance=0.7,
        violations=["VLM analysis unavailable - manual review recommended"],
        suggestions=["Enable Gemini VLM for automated design QA"],
    )


async def analyze_design_comment(
    file_key: str,
    comment: dict[str, Any],
) -> DesignAnalysisResult | None:
    """Analyze a design based on a @design-qa comment.

    This function is triggered when a Figma comment contains @design-qa.
    It extracts the target node from the comment and runs VLM analysis.

    Args:
        file_key: Figma file key.
        comment: Comment data from Figma API.

    Returns:
        DesignAnalysisResult if analysis was successful, None otherwise.
    """
    try:
        # Extract node ID from comment's client_meta
        client_meta = comment.get("client_meta", {})
        node_id = client_meta.get("node_id")

        if not node_id:
            # Try to extract from comment's position (frame it's on)
            node_offset = client_meta.get("node_offset", {})
            node_id = node_offset.get("node_id")

        if not node_id:
            logger.warning("No node_id found in @design-qa comment")
            return None

        # Run analysis on the referenced node
        result = await analyze_figma_frame(file_key, node_id)

        return result

    except Exception as e:
        logger.error(f"Design comment analysis failed: {e}")
        return None


# Singleton for caching VLM client
_vlm_client = None


async def get_vlm_client():
    """Get or create VLM client singleton."""
    global _vlm_client
    if _vlm_client is None:
        try:
            from kagami_studio.vlm.gemini import GeminiVLMClient

            _vlm_client = GeminiVLMClient()
            await _vlm_client.initialize()
        except ImportError:
            logger.warning("GeminiVLMClient not available")
            _vlm_client = None
    return _vlm_client
