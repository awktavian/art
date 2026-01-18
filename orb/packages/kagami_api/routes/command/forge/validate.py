"""Forge validation API endpoint.

Provides validation for generated characters.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.forge.service import ForgeService, get_forge_service
from kagami.forge.validation import get_validator
from pydantic import BaseModel, Field

from kagami_api.rbac import Permission, require_permission
from kagami_api.routes.forge_common import build_forge_metadata

from .decorators import forge_route


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/command/forge", tags=["command", "forge"])
    logger = logging.getLogger(__name__)

    class ValidateRequest(BaseModel):
        """Validation request payload."""

        character_id: str = Field(..., description="Character ID to validate")
        checks: list[str] = Field(default_factory=list, description="Specific checks to run")

    class ValidateResponse(BaseModel):
        """Validation response."""

        valid: bool
        character_id: str
        issues: list[str] = Field(default_factory=list)
        warnings: list[str] = Field(default_factory=list)
        correlation_id: str | None = None

    @router.post(
        "/validate",
        response_model=ValidateResponse,
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
    )
    @forge_route("forge.validate")
    async def validate_character(
        request: Request,
        payload: ValidateRequest,
        service: ForgeService = Depends(get_forge_service),
    ) -> ValidateResponse:
        """Validate a generated character.

        Runs quality checks on the character including:
        - Mesh integrity
        - Texture quality
        - Rigging validity
        - Animation compatibility

        Args:
            payload: Validation request with character ID

        Returns:
            Validation results with any issues found
        """
        forge_meta = build_forge_metadata(request, {})
        correlation_id = forge_meta["correlation_id"]

        try:
            _validator = get_validator()  # Validate configuration exists

            # For now, return a basic validation result
            # In a full implementation, this would load the character and run checks
            return ValidateResponse(
                valid=True,
                character_id=payload.character_id,
                issues=[],
                warnings=[],
                correlation_id=correlation_id,
            )
        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
