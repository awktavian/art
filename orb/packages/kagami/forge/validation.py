"""Forge Validation - Input and output validation for quality assurance.

Implements quality gates following K2 safety constraints.
"""

import logging
from typing import Any

from kagami.forge.observability.metrics import VALIDATION_FAILURES_TOTAL
from kagami.forge.schema import CharacterRequest, Mesh, QualityLevel

logger = logging.getLogger(__name__)


class ForgeValidator:
    """Validation for Forge requests and results."""

    def __init__(self) -> None:
        self._moderation_client = None

    def validate_request(self, request: CharacterRequest) -> list[str]:
        """Validate character generation request.

        Args:
            request: CharacterRequest to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Concept validation
        if not request.concept or len(request.concept.strip()) < 3:
            errors.append("Concept must be at least 3 characters")
            VALIDATION_FAILURES_TOTAL.labels(module="request", reason="concept_too_short").inc()

        if len(request.concept) > 500:
            errors.append("Concept must be 500 characters or less")
            VALIDATION_FAILURES_TOTAL.labels(module="request", reason="concept_too_long").inc()

        # Quality level validation
        try:
            if request.quality_level not in [
                QualityLevel.LOW,
                QualityLevel.MEDIUM,
                QualityLevel.HIGH,
                QualityLevel.ULTRA,
            ]:
                errors.append(f"Invalid quality_level: {request.quality_level}")
                VALIDATION_FAILURES_TOTAL.labels(
                    module="request", reason="invalid_quality_level"
                ).inc()
        except Exception:
            pass  # quality_level might not be set[Any]

        return errors

    async def moderate_content(self, text: str) -> dict[str, Any]:
        """Check content for policy violations.

        Args:
            text: Text to moderate

        Returns:
            dict[str, Any] with flagged (bool), reason (str), categories (list[Any])
        """
        # Lightweight moderation - can be enhanced with external API
        flagged_terms = [
            "explicit",
            "violent",
            "illegal",
            "harmful",
        ]  # Basic filter

        text_lower = text.lower()
        violations = [term for term in flagged_terms if term in text_lower]

        if violations:
            VALIDATION_FAILURES_TOTAL.labels(module="moderation", reason="policy_violation").inc()
            return {
                "flagged": True,
                "reason": f"Contains prohibited terms: {', '.join(violations)}",
                "categories": violations,
            }

        return {"flagged": False, "reason": None, "categories": []}

    def validate_mesh(self, mesh: Mesh) -> dict[str, Any]:
        """Validate generated mesh quality.

        Args:
            mesh: Mesh to validate

        Returns:
            dict[str, Any] with issues (list[Any]), warnings (list[Any]), score (float)
        """
        issues = []
        warnings: list[str] = []

        try:
            # Vertex count check
            vertex_count = len(mesh.vertices) if hasattr(mesh, "vertices") else 0
            if vertex_count == 0:
                issues.append("Mesh has no vertices")
                VALIDATION_FAILURES_TOTAL.labels(module="mesh", reason="no_vertices").inc()
            elif vertex_count > 100000:
                warnings.append(f"High vertex count: {vertex_count}")

            # Face count check
            face_count = len(mesh.faces) if hasattr(mesh, "faces") else 0
            if face_count == 0:
                issues.append("Mesh has no faces")
                VALIDATION_FAILURES_TOTAL.labels(module="mesh", reason="no_faces").inc()

            # UV check
            has_uvs = getattr(mesh, "has_uvs", False) or (
                hasattr(mesh, "visual")
                and hasattr(mesh.visual, "uv")
                and mesh.visual.uv is not None
            )
            if not has_uvs:
                warnings.append("Mesh missing UV coordinates")

            # Manifold check
            is_non_manifold = getattr(mesh, "is_non_manifold", False)
            if is_non_manifold:
                issues.append("Non-manifold geometry detected")
                VALIDATION_FAILURES_TOTAL.labels(module="mesh", reason="non_manifold").inc()

        except Exception as e:
            logger.warning(f"Mesh validation failed: {e}")
            issues.append(f"Validation error: {e}")

        # Calculate quality score
        score = 1.0
        score -= len(issues) * 0.3  # Major issues
        score -= len(warnings) * 0.1  # Minor warnings
        score = max(0.0, min(1.0, score))

        return {"issues": issues, "warnings": warnings, "score": score}

    def validate_result(self, result: Any) -> dict[str, Any]:
        """Validate complete generation result.

        Args:
            result: Generation result to validate

        Returns:
            dict[str, Any] with overall_score, issues, warnings
        """
        issues: list[str] = []
        warnings: list[str] = []
        scores: list[float] = []

        try:
            # Check if result has data
            if not hasattr(result, "data") or result.data is None:
                issues.append("Result has no data")
                VALIDATION_FAILURES_TOTAL.labels(module="result", reason="no_data").inc()
                return {"overall_score": 0.0, "issues": issues, "warnings": warnings}

            # Check mesh if present
            if "mesh" in result.data:
                mesh_validation = self.validate_mesh(result.data["mesh"])
                issues.extend(mesh_validation["issues"])
                warnings.extend(mesh_validation["warnings"])
                scores.append(mesh_validation["score"])

            # Calculate overall score
            overall_score = sum(scores) / len(scores) if scores else 0.5

        except Exception as e:
            logger.error(f"Result validation failed: {e}", exc_info=True)
            issues.append(f"Validation error: {e}")
            overall_score = 0.0

        return {"overall_score": overall_score, "issues": issues, "warnings": warnings}


# Singleton instance
_validator: ForgeValidator | None = None


def get_validator() -> ForgeValidator:
    """Get singleton validator instance."""
    global _validator
    if _validator is None:
        _validator = ForgeValidator()
    return _validator
