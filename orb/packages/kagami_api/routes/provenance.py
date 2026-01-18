"""Provenance API Routes.

Provides endpoints for querying and verifying cryptographic provenance records.

Endpoints:
    GET  /api/provenance/{correlation_id}       - Get provenance chain
    GET  /api/provenance/{correlation_id}/verify - Verify chain integrity
    GET  /api/provenance/record/{record_hash}   - Get single record
    POST /api/provenance/record                 - Create manual record

Created: December 5, 2025
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from kagami.core.safety import enforce_tier1
from pydantic import BaseModel, Field

from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/provenance", tags=["provenance"])

    # =============================================================================
    # RESPONSE MODELS
    # =============================================================================

    class ProvenanceRecordResponse(BaseModel):
        """Single provenance record."""

        record_hash: str
        previous_hash: str | None
        correlation_id: str
        instance_id: str
        timestamp: float
        action: str
        context: dict[str, Any]
        output_hash: str | None
        signature: str
        scheme: str
        witnesses: list[str] = Field(default_factory=list)

    class ProvenanceChainResponse(BaseModel):
        """Full provenance chain response."""

        correlation_id: str
        record_count: int
        records: list[ProvenanceRecordResponse]
        is_valid: bool
        issues: list[str] = Field(default_factory=list)

    class VerificationResponse(BaseModel):
        """Chain verification response."""

        correlation_id: str
        is_valid: bool
        record_count: int
        issues: list[str] = Field(default_factory=list)

    class ManualRecordRequest(BaseModel):
        """Request to create a manual provenance record."""

        action: str = Field(..., description="Action type (e.g., 'rule_change')")
        context: dict[str, Any] = Field(default_factory=dict, description="Action context")
        correlation_id: str | None = Field(None, description="Optional correlation ID")
        output_hash: str | None = Field(None, description="Optional output hash")

    class ManualRecordResponse(BaseModel):
        """Response after creating manual record."""

        record_hash: str
        correlation_id: str
        signature: str

    # =============================================================================
    # ENDPOINTS
    # =============================================================================

    @router.get(
        "/{correlation_id}",
        response_model=ProvenanceChainResponse,
        responses=get_error_responses(404, 429, 500),
        summary="Get provenance chain",
        description="Retrieve all provenance records for a correlation ID",
    )
    @enforce_tier1("rate_limit")
    async def get_provenance_chain(correlation_id: str) -> ProvenanceChainResponse:
        """Get full provenance chain for a correlation ID."""
        try:
            from kagami.core.safety.provenance_chain import get_provenance_chain

            chain = get_provenance_chain()
            if not chain._initialized:
                await chain.initialize()

            records = await chain.get_chain(correlation_id)
            is_valid, issues = await chain.verify_chain(correlation_id)

            return ProvenanceChainResponse(
                correlation_id=correlation_id,
                record_count=len(records),
                records=[
                    ProvenanceRecordResponse(
                        record_hash=r.record_hash,
                        previous_hash=r.previous_hash,
                        correlation_id=r.correlation_id,
                        instance_id=r.instance_id,
                        timestamp=r.timestamp,
                        action=r.action,
                        context=r.context,
                        output_hash=r.output_hash,
                        signature=r.signature,
                        scheme=r.scheme,
                        witnesses=r.witnesses,
                    )
                    for r in records
                ],
                is_valid=is_valid,
                issues=issues,
            )

        except Exception as e:
            logger.error(f"Failed to get provenance chain: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get(
        "/{correlation_id}/verify",
        response_model=VerificationResponse,
        responses=get_error_responses(404, 429, 500),
        summary="Verify provenance chain",
        description="Verify integrity of a provenance chain",
    )
    @enforce_tier1("rate_limit")
    async def verify_provenance_chain(correlation_id: str) -> VerificationResponse:
        """Verify integrity of a provenance chain."""
        try:
            from kagami.core.safety.provenance_chain import get_provenance_chain

            chain = get_provenance_chain()
            if not chain._initialized:
                await chain.initialize()

            records = await chain.get_chain(correlation_id)
            is_valid, issues = await chain.verify_chain(correlation_id)

            return VerificationResponse(
                correlation_id=correlation_id,
                is_valid=is_valid,
                record_count=len(records),
                issues=issues,
            )

        except Exception as e:
            logger.error(f"Failed to verify provenance chain: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get(
        "/record/{record_hash}",
        response_model=ProvenanceRecordResponse,
        responses=get_error_responses(404, 429, 500),
        summary="Get single record",
        description="Retrieve a single provenance record by hash",
    )
    @enforce_tier1("rate_limit")
    async def get_provenance_record(record_hash: str) -> ProvenanceRecordResponse:
        """Get a single provenance record by hash."""
        try:
            from kagami.core.safety.provenance_chain import get_provenance_chain

            chain = get_provenance_chain()
            if not chain._initialized:
                await chain.initialize()

            record = await chain._storage.get_record(record_hash)

            if record is None:
                raise HTTPException(status_code=404, detail=f"Record not found: {record_hash}")

            return ProvenanceRecordResponse(
                record_hash=record.record_hash,
                previous_hash=record.previous_hash,
                correlation_id=record.correlation_id,
                instance_id=record.instance_id,
                timestamp=record.timestamp,
                action=record.action,
                context=record.context,
                output_hash=record.output_hash,
                signature=record.signature,
                scheme=record.scheme,
                witnesses=record.witnesses,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get provenance record: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.post(
        "/record",
        response_model=ManualRecordResponse,
        responses=get_error_responses(400, 422, 429, 500),
        summary="Create manual record",
        description="Create a manual provenance record (for non-receipt actions)",
    )
    @enforce_tier1("rate_limit")
    async def create_manual_record(request: ManualRecordRequest) -> ManualRecordResponse:
        """Create a manual provenance record."""
        try:
            from kagami.core.safety.provenance_chain import get_provenance_chain

            chain = get_provenance_chain()
            if not chain._initialized:
                await chain.initialize()

            record = await chain.record_action(
                action=request.action,
                context=request.context,
                correlation_id=request.correlation_id,
                output_hash=request.output_hash,
            )

            return ManualRecordResponse(
                record_hash=record.record_hash,
                correlation_id=record.correlation_id,
                signature=record.signature,
            )

        except Exception as e:
            logger.error(f"Failed to create provenance record: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get(
        "/status",
        responses=get_error_responses(429, 500),
        summary="Provenance status",
        description="Get provenance system status",
    )
    @enforce_tier1("rate_limit")
    async def get_provenance_status() -> dict[str, Any]:
        """Get provenance system status."""
        try:
            from kagami.core.safety.provenance_chain import get_provenance_chain

            chain = get_provenance_chain()

            return {
                "initialized": chain._initialized,
                "instance_id": chain.instance_id,
                "storage_enabled": chain._storage._enabled if chain._storage else False,
                "keypair_loaded": chain._keypair is not None,
                "scheme": chain._keypair.scheme.value if chain._keypair else None,
            }

        except Exception as e:
            return {
                "initialized": False,
                "error": str(e),
            }

    return router
