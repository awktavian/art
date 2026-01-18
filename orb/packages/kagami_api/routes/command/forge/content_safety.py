"""Forge Content Safety Routes.

Content safety verification using ForgeValidator and CBF integration.

Integration Points:
- ForgeValidator: Content moderation and policy checks
- CBF Safety: Control Barrier Function safety verification
- OpenAI Moderation API: External moderation fallback

Routes:
- POST /api/command/forge/safety/check - Check content safety
- POST /api/command/forge/safety/moderate - Full moderation pipeline
- POST /api/command/forge/safety/cbf-verify - CBF safety verification
"""

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/safety", tags=["forge-safety"])

    class SafetyCheckRequest(BaseModel):
        """Content safety check request."""

        content: str = Field(..., description="Content to check", min_length=1, max_length=10000)
        content_type: str = Field(
            default="text",
            description="Content type: text, prompt, character_concept, image_prompt",
        )
        strict_mode: bool = Field(default=False, description="Enable strict moderation")
        check_categories: list[str] | None = Field(
            default=None,
            description="Specific categories to check: violence, sexual, hate, self-harm, etc.",
        )

    class SafetyCheckResponse(BaseModel):
        """Content safety check response."""

        safe: bool
        score: float = Field(ge=0.0, le=1.0, description="Safety score (1.0 = completely safe)")
        flags: list[str] = Field(default_factory=list)
        categories: dict[str, float] = Field(default_factory=dict)
        message: str
        provider: str = Field(default="internal", description="Moderation provider used")

    class ModerationRequest(BaseModel):
        """Full moderation pipeline request."""

        content: str = Field(..., min_length=1, max_length=50000)
        content_type: str = Field(default="text")
        use_external: bool = Field(default=False, description="Use external moderation API")
        threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    class ModerationResponse(BaseModel):
        """Full moderation response."""

        approved: bool
        content: str
        modifications: list[str] = Field(default_factory=list)
        safety_score: float
        details: dict[str, Any] = Field(default_factory=dict)

    class CBFVerifyRequest(BaseModel):
        """CBF safety verification request."""

        action: str = Field(..., description="Action to verify")
        context: dict[str, Any] = Field(default_factory=dict)
        state_vector: list[float] | None = Field(default=None, description="Optional state vector")

    class CBFVerifyResponse(BaseModel):
        """CBF verification response."""

        safe: bool
        h_value: float = Field(description="CBF h(x) value (>0 = safe)")
        zone: str = Field(description="Safety zone: GREEN, YELLOW, RED")
        constraints_satisfied: bool
        message: str

    # Category definitions for safety checking
    SAFETY_CATEGORIES = {
        "violence": {
            "keywords": ["kill", "murder", "attack", "weapon", "blood", "gore", "torture"],
            "weight": 1.0,
        },
        "sexual": {
            "keywords": ["explicit", "nsfw", "nude", "erotic", "pornographic"],
            "weight": 1.0,
        },
        "hate": {
            "keywords": ["hate", "racist", "discriminate", "slur", "bigot"],
            "weight": 1.0,
        },
        "self_harm": {
            "keywords": ["suicide", "self-harm", "cutting", "overdose"],
            "weight": 1.2,  # Higher weight for sensitive content
        },
        "illegal": {
            "keywords": ["illegal", "drugs", "trafficking", "fraud", "hack"],
            "weight": 0.8,
        },
        "harmful": {
            "keywords": ["harmful", "dangerous", "toxic", "poison"],
            "weight": 0.9,
        },
    }

    def _check_content_internal(
        content: str,
        categories: list[str] | None = None,
        strict: bool = False,
    ) -> tuple[bool, float, list[str], dict[str, float]]:
        """Internal content safety check.

        Returns:
            Tuple of (is_safe, score, flags, category_scores)
        """
        content_lower = content.lower()
        flags = []
        category_scores: dict[str, float] = {}

        check_categories = categories or list(SAFETY_CATEGORIES.keys())

        total_score = 0.0
        max_possible = 0.0

        for cat_name in check_categories:
            if cat_name not in SAFETY_CATEGORIES:
                continue

            cat_def = SAFETY_CATEGORIES[cat_name]
            keywords = cat_def["keywords"]
            weight = cat_def["weight"]

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw in content_lower)  # type: ignore[misc, attr-defined]
            cat_score = min(
                1.0,
                matches / max(len(keywords) * 0.3, 1),  # type: ignore[arg-type]
            )  # Normalize  # type: ignore[arg-type]

            if cat_score > 0:
                category_scores[cat_name] = cat_score
                if cat_score > 0.5:
                    flags.append(f"{cat_name}:{cat_score:.2f}")

            total_score += cat_score * weight  # type: ignore[operator]
            max_possible += weight  # type: ignore[operator]

        # Calculate safety score (inverse of violation score)
        if max_possible > 0:
            violation_score = total_score / max_possible
        else:
            violation_score = 0.0

        safety_score = 1.0 - min(violation_score, 1.0)

        # Determine if safe based on threshold
        threshold = 0.5 if strict else 0.3
        is_safe = violation_score < threshold

        return is_safe, safety_score, flags, category_scores

    async def _check_content_openai(content: str) -> tuple[bool, dict[str, float]]:
        """Check content using OpenAI Moderation API.

        Returns:
            Tuple of (is_flagged, category_scores)
        """
        try:
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False, {}

            client = OpenAI(api_key=api_key)
            response = client.moderations.create(input=content)

            if response.results:
                result = response.results[0]
                category_scores = {
                    cat: getattr(result.category_scores, cat, 0.0)
                    for cat in [
                        "hate",
                        "hate_threatening",
                        "harassment",
                        "harassment_threatening",
                        "self_harm",
                        "self_harm_intent",
                        "self_harm_instructions",
                        "sexual",
                        "sexual_minors",
                        "violence",
                        "violence_graphic",
                    ]
                }
                return result.flagged, category_scores

            return False, {}

        except Exception as e:
            logger.warning(f"OpenAI moderation failed: {e}")
            return False, {}

    @router.post("/check", response_model=SafetyCheckResponse)
    async def check_content_safety(request: SafetyCheckRequest) -> SafetyCheckResponse:
        """Check content for safety violations.

        Uses ForgeValidator for internal checks with optional external API.
        """
        try:
            # Use ForgeValidator for moderation
            from kagami.forge.validation import ForgeValidator

            validator = ForgeValidator()
            moderation_result = await validator.moderate_content(request.content)

            # Also run internal categorical check
            is_safe, score, flags, categories = _check_content_internal(
                request.content,
                request.check_categories,
                request.strict_mode,
            )

            # Combine results
            if moderation_result.get("flagged"):
                is_safe = False
                flags.extend(moderation_result.get("categories", []))

            return SafetyCheckResponse(
                safe=is_safe,
                score=score,
                flags=list(set(flags)),  # Dedupe
                categories=categories,
                message="Content passed safety checks" if is_safe else "Content flagged for review",
                provider="forge_validator",
            )

        except ImportError:
            # Fallback to internal-only check
            is_safe, score, flags, categories = _check_content_internal(
                request.content,
                request.check_categories,
                request.strict_mode,
            )

            return SafetyCheckResponse(
                safe=is_safe,
                score=score,
                flags=flags,
                categories=categories,
                message="Content passed safety checks" if is_safe else "Content flagged for review",
                provider="internal",
            )

    @router.post("/moderate", response_model=ModerationResponse)
    async def moderate_content(request: ModerationRequest) -> ModerationResponse:
        """Full content moderation pipeline.

        Optionally uses external moderation API for enhanced checking.
        """
        modifications = []
        details: dict[str, Any] = {}

        # Internal check first
        is_safe, score, flags, categories = _check_content_internal(request.content)
        details["internal"] = {"score": score, "flags": flags, "categories": categories}

        # External check if requested
        if request.use_external:
            ext_flagged, ext_categories = await _check_content_openai(request.content)
            details["external"] = {"flagged": ext_flagged, "categories": ext_categories}

            if ext_flagged:
                is_safe = False
                flags.append("external_moderation_flagged")

        # Apply modifications if needed (sanitization)
        content = request.content
        if not is_safe:
            # Log for review but don't modify
            modifications.append("Content flagged for manual review")
            logger.warning(f"Content flagged: {flags}")

        return ModerationResponse(
            approved=is_safe,
            content=content,
            modifications=modifications,
            safety_score=score,
            details=details,
        )

    @router.post("/cbf-verify", response_model=CBFVerifyResponse)
    async def verify_cbf_safety(request: CBFVerifyRequest) -> CBFVerifyResponse:
        """Verify action safety using Control Barrier Functions.

        Returns CBF h(x) value indicating safety margin.
        """
        try:
            from kagami.core.safety.cbf_integration import (
                get_cbf_service,  # type: ignore[attr-defined]
            )

            cbf_service = get_cbf_service()

            # Build state from context
            state = request.state_vector or [0.0] * 7  # Default to safe state

            # Check safety
            result = await cbf_service.check_safety(
                action=request.action,
                state=state,
                context=request.context,
            )

            h_value = result.h_x if result.h_x is not None else 1.0

            # Determine zone
            if h_value > 0.5:
                zone = "GREEN"
            elif h_value > 0:
                zone = "YELLOW"
            else:
                zone = "RED"

            return CBFVerifyResponse(
                safe=h_value > 0,
                h_value=h_value,
                zone=zone,
                constraints_satisfied=result.is_safe,
                message=f"Action {'permitted' if result.is_safe else 'blocked'}: h(x)={h_value:.3f}",
            )

        except ImportError:
            # CBF not available - return safe by default with warning
            logger.warning("CBF service not available, returning default safe state")
            return CBFVerifyResponse(
                safe=True,
                h_value=1.0,
                zone="GREEN",
                constraints_satisfied=True,
                message="CBF service unavailable - default safe state",
            )

        except Exception as e:
            logger.error(f"CBF verification failed: {e}")
            raise HTTPException(status_code=500, detail=f"Safety verification failed: {e}") from e

    return router
