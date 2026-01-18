"""Semantic Intent Router - ML-based semantic similarity routing.

Routes intents using embedding similarity instead of string matching.
More robust, handles paraphrasing, works cross-linguistically.

ARCHITECTURE (Dec 15, 2025):
  KagamiOS uses TWO routers:
  1. SemanticIntentRouter (this file - ML-based, semantic similarity)
  2. IntentRouter (rule-based, deterministic, safety-integrated)

  They are COMPLEMENTARY, not redundant. See ROUTER_ARCHITECTURE.md.

UNIQUE CAPABILITIES:
  - Handles paraphrasing ("organize schedule" → "chat")
  - Cross-lingual support (via multilingual embeddings)
  - Confidence scores for routing decisions
  - Extended handler types (symbolic, visual, causal, sensorimotor)

LIMITATIONS:
  - Cannot deterministically infer app from action patterns
  - No CBF safety integration (relies on IntentRouter fallback)
  - Requires embedding service (heavyweight)
  - Non-deterministic (embedding model dependent)

FALLBACK BEHAVIOR:
  When this router returns handler_type="app" but app_name=None,
  process_intent_v2.py falls back to IntentRouter for deterministic inference.

Created: November 2, 2025
Updated: December 15, 2025 (architecture documentation)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


class SemanticIntentRouter:
    """Route intents using semantic similarity instead of keywords."""

    # Handler capability descriptions (used as semantic prototypes)
    HANDLER_CAPABILITIES = {
        "chat": [
            "have a conversation",
            "chat with me",
            "discuss a topic",
            "answer questions",
            "natural language interaction",
        ],
        "symbolic": [
            "solve a constraint problem",
            "prove a theorem",
            "verify an invariant",
            "logical reasoning",
            "formal verification",
            "answer logic questions",
            "satisfy constraints",
        ],
        "sensorimotor": [
            "perceive the environment",
            "take physical action",
            "move and interact",
            "embodied interaction",
            "vision and motor control",
        ],
        "visual": [
            "analyze an image",
            "understand a screenshot",
            "detect UI elements",
            "visual reasoning",
            "computer vision",
        ],
        "causal": [
            "find the root cause",
            "what causes what",
            "causal relationship",
            "why did this happen",
            "counterfactual reasoning",
            "what if analysis",
        ],
        "app": [
            "execute specific function",
            "call an API",
            "perform application action",
            "run a command",
        ],
    }

    def __init__(self, embedding_service: Any = None) -> None:
        """Initialize semantic router.

        Args:
            embedding_service: Service for computing embeddings
        """
        self.embedding_service = embedding_service
        self._handler_embeddings: dict[str, torch.Tensor] = {}
        self._initialized = False

        logger.info("SemanticIntentRouter initialized")

    def _get_embedding_service(self) -> Any:
        """Lazy-load embedding service."""
        if self.embedding_service is None:
            try:
                from kagami.core.world_model.multimodal_encoder import get_multimodal_encoder

                self.embedding_service = get_multimodal_encoder()
            except Exception as e:
                logger.critical(f"Embedding service unavailable: {e}. Mandatory component missing.")
                raise RuntimeError("Embedding service is mandatory in Full Operation Mode.") from e

        return self.embedding_service

    async def _initialize_handler_embeddings(self) -> None:
        """Pre-compute embeddings for handler capabilities."""
        if self._initialized:
            return

        embedding_service = self._get_embedding_service()

        for handler_type, descriptions in self.HANDLER_CAPABILITIES.items():
            # Compute embeddings for all descriptions
            embeddings = []
            for desc in descriptions:
                try:
                    embeddings.append(await self._encode_text(embedding_service, desc))
                except Exception as e:
                    logger.debug(f"Embedding failed for '{desc}': {e}")

            if embeddings:
                # Average embeddings as prototype
                prototype = torch.stack(embeddings).mean(dim=0)
                self._handler_embeddings[handler_type] = prototype

        self._initialized = True
        logger.info(f"Initialized {len(self._handler_embeddings)} handler prototypes")

    async def route(self, intent: dict[str, Any]) -> dict[str, Any]:
        """Route intent to handler using semantic similarity.

        Args:
            intent: Intent dict[str, Any]

        Returns:
            Route decision with handler type and confidence
        """
        await self._initialize_handler_embeddings()

        # Extract intent text
        action = intent.get("action", intent.get("intent", ""))
        params = intent.get("args", {}) or intent.get("params", {})

        # Build full intent description
        intent_text = str(action)
        if params:
            # Add param hints
            param_str = " ".join(str(v) for v in params.values() if v)
            intent_text = f"{intent_text} {param_str}"

        # Compute intent embedding
        embedding_service = self._get_embedding_service()
        try:
            intent_embedding = await self._encode_text(embedding_service, intent_text)
        except Exception as e:
            logger.error(f"Intent embedding failed: {e}")
            return {
                "handler_type": "app",  # Default to app handler
                "confidence": 0.0,
                "reason": f"embedding_failed: {e}",
            }

        # Compute similarities to all handler prototypes
        similarities: dict[str, float] = {}
        for handler_type, prototype in self._handler_embeddings.items():
            similarity = torch.cosine_similarity(
                intent_embedding.unsqueeze(0), prototype.unsqueeze(0), dim=1
            ).item()
            similarities[handler_type] = float(similarity)

        # Select best handler
        best_handler, confidence = max(similarities.items(), key=lambda item: item[1])

        logger.debug(
            f"Semantic routing: '{action}' → {best_handler} (confidence: {confidence:.3f})"
        )

        return {
            "handler_type": best_handler,
            "confidence": confidence,
            "all_scores": similarities,
            "app_name": None if best_handler != "app" else self._infer_app(intent),
        }

    def _infer_app(self, intent: dict[str, Any]) -> str | None:
        """Infer app name from intent."""
        # Check explicit app field
        if "app" in intent:
            return str(intent["app"])

        # Try to infer from action
        action = intent.get("action", "")
        if "." in str(action):
            # Format: app.action
            return str(action).split(".")[0]

        return None

    async def _encode_text(self, service: Any, text: str) -> torch.Tensor:
        """Encode text into a normalized torch tensor."""
        # Ensure service initialized when it exposes initialize()
        initializer = getattr(service, "initialize", None)
        if callable(initializer):
            try:
                maybe = initializer()
                if asyncio.iscoroutine(maybe):
                    await maybe
            except Exception as err:
                logger.debug(f"Embedding service initialization skipped: {err}")

        vector: Any
        try:
            if hasattr(service, "embed_text_async"):
                vector = await service.embed_text_async(text)  # Matryoshka async path
            elif hasattr(service, "embed_text"):
                vector = service.embed_text(text)
            elif hasattr(service, "encode"):
                vector = service.encode(text)
            else:
                vector = np.zeros(384, dtype=np.float32)
        except Exception as err:
            logger.error(f"Embedding failed for '{text}': {err}")
            raise RuntimeError(f"Embedding failed for '{text}': {err}") from err

        if isinstance(vector, torch.Tensor):
            tensor = vector.float()
        else:
            tensor = torch.tensor(np.asarray(vector, dtype=np.float32), dtype=torch.float32)

        norm = tensor.norm()
        if torch.isfinite(norm) and norm > 0:
            tensor = tensor / norm
        return tensor


__all__ = ["SemanticIntentRouter"]
