"""Quality Validation Module (Consolidated).

MIGRATED: January 5, 2026
From: packages/code_quality_validation/
From: packages/crystal_validation_framework/
To: packages/kagami/core/quality/

Provides code quality validation and testing infrastructure.
"""

from .code_quality import (
    CodeQualityValidator,
    QualityLevel,
    QualityResult,
    QualityTool,
)
from .crystal_validation import (
    CrystalValidationFramework,
    TestResult,
    ValidationScope,
)

__all__ = [
    "CodeQualityValidator",
    "CrystalValidationFramework",
    "QualityLevel",
    "QualityResult",
    "QualityTool",
    "TestResult",
    "ValidationScope",
]
