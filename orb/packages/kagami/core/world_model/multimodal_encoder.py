"""Multimodal Encoder — Vision/Audio (Text via Kagami Service).

Encodes vision and audio modalities to the world model's semantic space.
Text encoding delegates directly to the Kagami Embedding Service.

CANONICAL ARCHITECTURE:
- Text: kagami.core.services.embedding_service (SINGLE SOURCE)
- Vision: ContrastiveMultimodalFusion + hierarchical encoder
- Audio: Audio processing + contrastive fusion

All outputs are 512D (KAGAMI_EMBED_DIM) for world model compatibility.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Protocol, cast

import numpy as np
import torch
import torch.nn as nn
from numpy.typing import NDArray
from torch import Tensor

logger = logging.getLogger(__name__)

FloatArray = NDArray[np.float32]

# Canonical dimension (matches world model bulk)
KAGAMI_EMBED_DIM = 512


class MultimodalFusionProtocol(Protocol):
    def encode_image(self, images: Tensor) -> Tensor: ...

    def encode_audio(self, audio: Tensor) -> Tensor: ...


class HierarchicalEncoderProtocol(Protocol):
    def encode(self, images: Tensor) -> Mapping[str, np.ndarray[Any, Any]]: ...


class MultimodalEncoder(nn.Module):
    """Multimodal encoder for vision/audio.

    Text encoding uses Kagami Embedding Service directly.
    Vision/audio use specialized encoders.

    All outputs are 512D (KAGAMI_EMBED_DIM).
    """

    def __init__(self, embedding_dim: int = KAGAMI_EMBED_DIM) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim

        # Text: Use Kagami Embedding Service directly (NO wrapper)
        import importlib

        get_embedding_service = importlib.import_module(
            "kagami.core.services.embedding_service"
        ).get_embedding_service
        self._embedding_service = get_embedding_service()
        logger.info(
            f"✅ MultimodalEncoder: Text via Kagami Embedding Service "
            f"({self._embedding_service.model_name})"
        )

        # Vision/Audio: ContrastiveMultimodalFusion
        self._multimodal_fusion: MultimodalFusionProtocol | None = None
        self._fusion_proj: nn.Linear | None = None
        try:
            from kagami.core.multimodal.contrastive_fusion import get_multimodal_fusion

            fusion = get_multimodal_fusion(embedding_dim=512)
            self._multimodal_fusion = cast(MultimodalFusionProtocol, fusion)

            if embedding_dim != 512:
                self._fusion_proj = nn.Linear(512, self.embedding_dim)

            logger.info("✅ Vision/Audio encoder: ContrastiveMultimodalFusion active")
        except Exception as e:
            logger.warning(f"⚠️ Multimodal fusion unavailable: {e}")

        # Hierarchical Vision (optional)
        self._hierarchical_encoder: HierarchicalEncoderProtocol | None = None
        self._hier_proj: nn.Linear | None = None
        try:
            from kagami.core.multimodal.hierarchical_encoder import get_hierarchical_encoder

            hierarchical = get_hierarchical_encoder(input_channels=3)
            self._hierarchical_encoder = cast(HierarchicalEncoderProtocol, hierarchical)

            if embedding_dim != 512:
                self._hier_proj = nn.Linear(512, self.embedding_dim)

            logger.info("✅ Hierarchical vision encoder active")
        except Exception as e:
            logger.debug(f"Hierarchical encoder unavailable (optional): {e}")

    def encode_text(self, text: str | list[str], dimension: int | None = None) -> FloatArray:
        """Encode text to embedding vector.

        Uses Kagami Embedding Service directly (no wrapper).

        Args:
            text: Single text or list[Any] of texts
            dimension: Target dimension (default: embedding_dim)

        Returns:
            Embeddings [N, D] or [D]
        """
        target_dim = dimension or self.embedding_dim
        is_single = isinstance(text, str)
        texts = [text] if is_single else text

        # Use Kagami Embedding Service directly
        result = self._embedding_service.embed_batch(texts, dimension=target_dim)

        if is_single:
            return result[0]
        return result

    def embed_text(self, text: str) -> FloatArray:
        """Alias for encode_text (compatibility)."""
        return self.encode_text(text)

    def _generate_degradation_signal(self, batch_size: int, device: torch.device) -> Tensor:
        """Generate sensory degradation signal (sensor failure indicator).

        FIXED (Dec 6, 2025): Changed from random noise to deterministic signal.
        Random noise was poisoning gradients during training when sensors fail.

        The degradation signal is:
        - All zeros except first dimension = -1e6 (detectable marker)
        - Downstream code can check `x[:, 0] < -1e5` to detect degradation
        - No gradient noise pollution
        """
        signal = torch.zeros(batch_size, self.embedding_dim, device=device)
        signal[:, 0] = -1e6  # Marker in first dimension
        return signal

    def encode_vision(
        self, images: Tensor | np.ndarray[Any, Any], use_hierarchical: bool = False
    ) -> Tensor:
        """Encode images to shared embedding dimension."""
        if isinstance(images, np.ndarray[Any, Any]):
            images = torch.from_numpy(images.astype(np.float32))
        else:
            images = images.float()

        if images.dim() == 3:
            images = images.unsqueeze(0)

        batch_size = images.shape[0]
        device = images.device

        # Hierarchical encoder (detailed features)
        if use_hierarchical and self._hierarchical_encoder:
            try:
                features = self._hierarchical_encoder.encode(images)
                high_np = features.get("high")
                if high_np is not None:
                    high_emb = torch.from_numpy(high_np.astype(np.float32)).to(device)
                    if self._hier_proj:
                        high_emb = self._hier_proj(high_emb)
                    return high_emb
            except Exception as e:
                logger.warning(f"Hierarchical encoding failed: {e}")

        # Contrastive fusion (general features)
        if self._multimodal_fusion:
            try:
                emb = self._multimodal_fusion.encode_image(images)
                if self._fusion_proj:
                    emb = self._fusion_proj(emb.float())
                return cast(Tensor, emb)  # type: ignore[redundant-cast]
            except Exception as e:
                logger.warning(f"Vision encoding failed: {e}")

        # GRACEFUL DEGRADATION (not a fallback): Emit signal indicating failure
        # This follows control theory best practice: emit observable failure signal
        logger.warning("⚠️ Vision sensors failed, emitting degradation signal")
        return self._generate_degradation_signal(batch_size, device)

    def encode_audio(self, audio_spectrograms: Tensor) -> Tensor:
        """Encode audio spectrograms."""
        batch_size = audio_spectrograms.shape[0]
        device = audio_spectrograms.device

        if self._multimodal_fusion:
            try:
                emb = self._multimodal_fusion.encode_audio(audio_spectrograms)
                if self._fusion_proj:
                    emb = self._fusion_proj(emb.float())
                return cast(Tensor, emb)  # type: ignore[redundant-cast]
            except Exception as e:
                logger.warning(f"Audio encoding failed: {e}")

        return self._generate_degradation_signal(batch_size, device)

    def embed_to_e8_bytes(self, text: str) -> bytes:
        """Compress text to E8 Crystal Bytes."""
        try:
            from kagami.core.matryoshka_fiber_bundle import get_matryoshka_bundle

            semantic = self.encode_text(text, dimension=self.embedding_dim)
            semantic_t = torch.from_numpy(semantic).float().unsqueeze(0)

            bundle = get_matryoshka_bundle()
            return bundle.to_bytes(semantic_t)

        except Exception as e:
            logger.error(f"E8 byte compression failed: {e}")
            return b"\xf5"

    def decode_from_e8_bytes(self, byte_data: bytes, target_dim: int | None = None) -> FloatArray:
        """Decompress E8 Crystal Bytes back to semantic vector."""
        try:
            from kagami.core.matryoshka_fiber_bundle import get_matryoshka_bundle

            bundle = get_matryoshka_bundle()
            dim = target_dim or self.embedding_dim

            tensor_out = bundle.from_bytes(byte_data, target_dim=dim)
            return cast(FloatArray, tensor_out.squeeze(0).detach().cpu().numpy())

        except Exception as e:
            logger.error(f"E8 byte decompression failed: {e}")
            return np.zeros(target_dim or self.embedding_dim, dtype=np.float32)


# Singleton
_multimodal_encoder: MultimodalEncoder | None = None


def get_multimodal_encoder(embedding_dim: int = KAGAMI_EMBED_DIM) -> MultimodalEncoder:
    """Get or create multimodal encoder."""
    global _multimodal_encoder
    if _multimodal_encoder is None:
        _multimodal_encoder = MultimodalEncoder(embedding_dim=embedding_dim)
    return _multimodal_encoder


__all__ = [
    "KAGAMI_EMBED_DIM",
    "MultimodalEncoder",
    "get_multimodal_encoder",
]
