from __future__ import annotations

"""Forge API request/response DTOs.

Data Transfer Objects for the Forge character generation API.
Provides validated request schemas with quality tier support.

Quality Tiers:
    - preview: Fast (~2.5s), low cost, for iteration
    - draft: Medium (~6s), medium cost, for review
    - final: Slow (~12s), high cost, production quality

Usage:
    request = ForgeGenerateRequest(
        concept="A wise wizard",
        quality_mode="draft",
        export_formats=["glb", "png"]
    )

    # Check if confirmation needed
    if request.requires_confirmation():
        raise NeedsConfirmation()

    # Convert to internal CharacterRequest
    char_req = request.to_character_request(request_id, extra_metadata)
"""

from typing import Any

from kagami.forge.schema import CharacterRequest, ExportFormat, QualityLevel
from pydantic import BaseModel, Field, field_validator

# Quality mode → internal QualityLevel mapping
_QUALITY_MODE_TO_LEVEL = {
    "preview": QualityLevel.LOW,  # Fast iteration
    "draft": QualityLevel.MEDIUM,  # Review quality
    "final": QualityLevel.HIGH,  # Production quality
}

# Estimated time and cost hints for each quality mode
_QUALITY_MODE_HINTS = {
    "preview": {"eta_ms": 2500, "cost": "low"},  # ~2.5 seconds
    "draft": {"eta_ms": 6000, "cost": "medium"},  # ~6 seconds
    "final": {"eta_ms": 12000, "cost": "high"},  # ~12 seconds
}


class ForgeGenerateRequest(BaseModel):
    """Validated Forge /generate payload.

    Request schema for character generation. Validates concept, normalizes
    quality mode, and provides helper methods for the generation pipeline.

    Attributes:
        concept: Character description (required, min 1 char)
        export_formats: Output formats like ["glb", "png"]
        quality_mode: "preview" | "draft" | "final"
        personality_brief: Optional personality hints
        backstory_brief: Optional backstory hints
        confirm: Must be True for final quality
        room_id: Optional room for auto-insert
        auto_insert: If True, insert into room on completion
        metadata: Custom metadata passed through
        validate_after: Run validation after generation
    """

    concept: str = Field(..., min_length=1, description="Character description")
    export_formats: list[str] = Field(default_factory=list, description="Output formats")
    quality_mode: str = Field("preview", description="preview|draft|final")
    personality_brief: str | None = Field(None, description="Personality hints")
    backstory_brief: str | None = Field(None, description="Backstory hints")
    confirm: bool = Field(False, description="Confirmation for final quality")
    room_id: str | None = Field(None, description="Room for auto-insert")
    auto_insert: bool = Field(False, description="Insert into room on completion")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")
    validate_after: bool = Field(False, description="Run validation after generation")

    @field_validator("concept")
    @classmethod
    def _trim_concept(cls, value: str) -> str:
        """Trim whitespace from concept, reject if empty."""
        v = value.strip()
        if not v:
            raise ValueError("concept is required")
        return v

    @field_validator("quality_mode")
    @classmethod
    def _normalize_quality_mode(cls, value: str) -> str:
        """Normalize quality_mode to lowercase, default to preview if invalid."""
        normalized = (value or "preview").strip().lower()
        if normalized not in _QUALITY_MODE_TO_LEVEL:
            return "preview"
        return normalized

    def requires_confirmation(self) -> bool:
        """Check if user confirmation is required.

        Returns True if quality_mode is 'final' and confirm is False.
        Final quality is expensive and requires explicit confirmation.
        """
        return self.quality_mode == "final" and not self.confirm

    def quality_profile(self) -> tuple[int, str]:
        """Get estimated time and cost for this quality mode.

        Returns:
            Tuple of (eta_ms, cost_tier) e.g. (6000, "medium")
        """
        hints = _QUALITY_MODE_HINTS.get(self.quality_mode, _QUALITY_MODE_HINTS["preview"])
        return hints["eta_ms"], hints["cost"]  # type: ignore[return-value]

    def export_format_enums(self) -> list[ExportFormat]:
        """Convert export_formats strings to ExportFormat enums.

        Invalid format names are silently ignored.

        Returns:
            List of valid ExportFormat enum values
        """
        result: list[ExportFormat] = []
        for name in self.export_formats:
            try:
                result.append(ExportFormat(name))
            except Exception:
                continue  # Skip invalid format names
        return result

    def to_character_request(
        self, request_id: str, extra_metadata: dict[str, Any]
    ) -> CharacterRequest:
        """Convert to internal CharacterRequest for the generation pipeline.

        Args:
            request_id: Unique ID for this generation request
            extra_metadata: Additional metadata to merge (e.g., user info)

        Returns:
            CharacterRequest ready for the Forge generator
        """
        combined_metadata = {**extra_metadata, **(self.metadata or {})}
        return CharacterRequest(
            request_id=request_id,
            concept=self.concept,
            personality_brief=self.personality_brief,
            backstory_brief=self.backstory_brief,
            export_formats=self.export_format_enums(),
            quality_level=_QUALITY_MODE_TO_LEVEL.get(self.quality_mode, QualityLevel.LOW),
            metadata=combined_metadata,
        )


__all__ = ["ForgeGenerateRequest"]
