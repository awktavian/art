"""K OS (Kagami OS) Services Module.

Provides core services used across the system:
- KagamiEmbeddingService: SINGLE SOURCE OF TRUTH for all embeddings
- CaptchaService: hCaptcha solving for anti-bot bypassing

CANONICAL DIMENSION: 512D
========================
All embeddings use 512D to match the world model bulk dimension.
This is enforced by the Kagami Embedding Service.

EXTRACTED TO TOP-LEVEL (December 2025):
=======================================
- kagami.forge: 3D/Mascot generation service (125 files)

SUBMODULE STRUCTURE:
====================
services/
├── embedding_service.py    # Canonical embedding service
├── llm/                    # LLM services (40+ files)
│   ├── service.py          # Main LLM service
│   ├── config.py           # Model configurations
│   ├── model_resolver.py   # Model routing / selection
│   └── structured/         # Structured output
├── captcha/                # Captcha solving (2captcha, etc.)
├── composio/               # External actions
├── voice/                  # STT/TTS
└── world/                  # World simulation (Emu)

OPTIMIZED (Dec 28, 2025): Lazy imports to avoid 800ms+ boot cost from torch/kagami_math
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Canonical embedding dimension (matches world model bulk)
KAGAMI_EMBED_DIM = 512

# OPTIMIZED: Lazy imports via __getattr__ to avoid 800ms+ boot cost
if TYPE_CHECKING:
    from kagami.core.services.captcha import (
        CaptchaConfig,
        CaptchaProvider,
        CaptchaService,
        get_captcha_service,
    )
    from kagami.core.services.email_helper import (
        EmailDraft,
        EmailHelper,
        EmailSearchResult,
        get_email_helper,
    )
    from kagami.core.services.embedding_service import (
        EmbeddingService,
        EmbeddingServiceConfig,
        get_embedding_service,
        reset_embedding_service,
    )

    KagamiEmbeddingService = EmbeddingService


def __getattr__(name: str) -> Any:
    """Lazy import heavy service modules."""
    # Embedding service
    if name in ("EmbeddingService", "KagamiEmbeddingService"):
        from kagami.core.services.embedding_service import EmbeddingService

        return EmbeddingService
    if name == "EmbeddingServiceConfig":
        from kagami.core.services.embedding_service import EmbeddingServiceConfig

        return EmbeddingServiceConfig
    if name in ("get_embedding_service", "get_kagami_embedding_service"):
        from kagami.core.services.embedding_service import get_embedding_service

        return get_embedding_service
    if name == "reset_embedding_service":
        from kagami.core.services.embedding_service import reset_embedding_service

        return reset_embedding_service

    # Captcha solving service
    if name == "CaptchaService":
        from kagami.core.services.captcha import CaptchaService

        return CaptchaService
    if name == "CaptchaConfig":
        from kagami.core.services.captcha import CaptchaConfig

        return CaptchaConfig
    if name == "CaptchaProvider":
        from kagami.core.services.captcha import CaptchaProvider

        return CaptchaProvider
    if name == "get_captcha_service":
        from kagami.core.services.captcha import get_captcha_service

        return get_captcha_service

    # Email helper service
    if name == "EmailHelper":
        from kagami.core.services.email_helper import EmailHelper

        return EmailHelper
    if name == "EmailDraft":
        from kagami.core.services.email_helper import EmailDraft

        return EmailDraft
    if name == "EmailSearchResult":
        from kagami.core.services.email_helper import EmailSearchResult

        return EmailSearchResult
    if name == "get_email_helper":
        from kagami.core.services.email_helper import get_email_helper

        return get_email_helper

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "KAGAMI_EMBED_DIM",
    "CaptchaConfig",
    "CaptchaProvider",
    "CaptchaService",
    "EmailDraft",
    "EmailHelper",
    "EmailSearchResult",
    "EmbeddingService",
    "EmbeddingServiceConfig",
    "KagamiEmbeddingService",
    "get_captcha_service",
    "get_email_helper",
    "get_embedding_service",
    "get_kagami_embedding_service",
    "reset_embedding_service",
]
