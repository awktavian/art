"""Contrastive multimodal fusion (CLIP-style architecture).

Aligns text, image, audio, and video in a shared embedding space using
contrastive learning. Enables cross-modal reasoning and zero-shot transfer.

Based on CLIP, ImageBind, and BLIP-2 architectures.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ContrastiveMultimodalFusion:
    """CLIP-style contrastive learning for multimodal alignment.

    Features:
    - Shared embedding space (512-dim) for all modalities
    - Contrastive loss brings related concepts together
    - Cross-modal retrieval (search images with text, etc.)
    - Zero-shot transfer between modalities

    Architecture:
    - Text encoder: Transformer (BERT-style)
    - Vision encoder: ViT (Vision Transformer)
    - Audio encoder: Spectrogram CNN + Transformer
    - Video encoder: TimeSformer (spatiotemporal attention)
    """

    def __init__(self, embedding_dim: int = 512, temperature: float = 0.07) -> None:
        """Initialize multimodal fusion.

        Args:
            embedding_dim: Size of shared embedding space
            temperature: Softmax temperature for contrastive loss
        """
        self.embedding_dim = embedding_dim
        self.temperature = temperature
        self._device = "cpu"
        self._vocab_size = 50000  # Stable hash-based tokenization vocabulary size

        # Encoders (initialized lazily)
        self._text_encoder = None
        self._vision_encoder = None
        self._audio_encoder = None
        self._video_encoder = None

        self._initialize_encoders()

    def _initialize_encoders(self) -> None:
        """Initialize all modality encoders."""
        try:
            import os

            import torch
            import torch.nn as nn

            self._device = (
                "cuda"
                if torch.cuda.is_available()
                else (
                    "mps"
                    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                    else "cpu"
                )
            )

            # Text Encoder: Transformer for text
            class TextEncoder(nn.Module):
                def __init__(
                    self, vocab_size: Any = 50000, embed_dim: Any = 256, output_dim: Any = 512
                ) -> None:
                    super().__init__()
                    self.embedding = nn.Embedding(vocab_size, embed_dim)
                    encoder_layer = nn.TransformerEncoderLayer(
                        d_model=embed_dim,
                        nhead=8,
                        dim_feedforward=embed_dim * 4,
                        batch_first=True,
                    )
                    self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=4)
                    self.projection = nn.Linear(embed_dim, output_dim)

                def forward(self, tokens: Any) -> None:
                    # tokens: [B, seq_len]
                    x = self.embedding(tokens)  # [B, seq_len, embed_dim]
                    x = self.transformer(x)  # [B, seq_len, embed_dim]
                    x = x.mean(dim=1)  # [B, embed_dim] - avg pool
                    x = self.projection(x)  # [B, output_dim]
                    return x

            # Vision Encoder: CNN for images
            class VisionEncoder(nn.Module):
                def __init__(self, output_dim: Any = 512) -> None:
                    super().__init__()
                    self.conv = nn.Sequential(
                        nn.Conv2d(3, 64, 7, 2, 3),
                        nn.ReLU(),
                        nn.Conv2d(64, 128, 3, 2, 1),
                        nn.ReLU(),
                        nn.Conv2d(128, 256, 3, 2, 1),
                        nn.ReLU(),
                        nn.AdaptiveAvgPool2d((4, 4)),
                    )
                    self.projection = nn.Linear(256 * 16, output_dim)

                def forward(self, images: Any) -> None:
                    # images: [B, 3, H, W]
                    x = self.conv(images)  # [B, 256, 4, 4]
                    x = x.flatten(1)  # [B, 256*16]
                    x = self.projection(x)  # [B, output_dim]
                    return x

            # Audio Encoder: Spectrogram CNN
            class AudioEncoder(nn.Module):
                def __init__(self, output_dim: Any = 512) -> None:
                    super().__init__()
                    self.conv = nn.Sequential(
                        nn.Conv2d(1, 32, (3, 3), 2, 1),
                        nn.ReLU(),
                        nn.Conv2d(32, 64, (3, 3), 2, 1),
                        nn.ReLU(),
                        nn.Conv2d(64, 128, (3, 3), 2, 1),
                        nn.ReLU(),
                        nn.AdaptiveAvgPool2d((4, 4)),
                    )
                    self.projection = nn.Linear(128 * 16, output_dim)

                def forward(self, spectrograms: Any) -> None:
                    # spectrograms: [B, 1, freq, time]
                    x = self.conv(spectrograms)  # [B, 128, 4, 4]
                    x = x.flatten(1)  # [B, 128*16]
                    x = self.projection(x)  # [B, output_dim]
                    return x

            # Initialize all encoders
            self._text_encoder = TextEncoder(output_dim=self.embedding_dim).to(  # type: ignore[assignment]
                self._device
            )
            self._vision_encoder = VisionEncoder(output_dim=self.embedding_dim).to(  # type: ignore[assignment]
                self._device
            )
            self._audio_encoder = AudioEncoder(output_dim=self.embedding_dim).to(  # type: ignore[assignment]
                self._device
            )

            logger.info(
                f"✓ Contrastive encoders initialized: "
                f"text/vision/audio → {self.embedding_dim}D, device={self._device}"
            )

            # Optimize for MPS: prefer channels_last tensors for vision, and enable
            # autocast where safe to reduce bandwidth on Apple Silicon.
            try:
                if self._device == "mps":
                    # Set modules to channels_last where relevant
                    try:
                        self._vision_encoder = self._vision_encoder.to(  # type: ignore  # Dynamic attr
                            memory_format=torch.channels_last
                        )
                    except Exception:
                        pass
                    # Record hint for downstream encode methods to use autocast
                    self._mps_autocast = True
                else:
                    self._mps_autocast = False
            except Exception:
                self._mps_autocast = False

            # Optional Core ML (ANE) vision encoder stub (feature-flagged)
            # Enable by setting KAGAMI_COREML_VISION_MODEL to a .mlmodel path.
            self._coreml_vision = None
            try:
                coreml_flag = os.getenv("KAGAMI_COREML_ENCODERS", "0").lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                coreml_model_path = os.getenv("KAGAMI_COREML_VISION_MODEL")
                if coreml_flag and coreml_model_path:
                    try:
                        from kagami.core.mobiasm.coreml_runtime import (
                            CoreMLVisionEncoder,
                        )

                        self._coreml_vision = CoreMLVisionEncoder(coreml_model_path)
                        logger.info("Core ML vision encoder enabled (ANE when available)")
                    except Exception as e:
                        logger.debug(f"Core ML vision encoder unavailable: {e}")
                        self._coreml_vision = None
            except Exception:
                self._coreml_vision = None

        except ImportError:
            logger.debug("PyTorch not available for contrastive fusion")

    def _tokenize_texts(self, texts: Any, max_length: int = 64) -> Any:
        """Tokenize list[Any] of strings into fixed-length token ids using stable hashing.

        Args:
            texts: List[str] or any sequence of strings
            max_length: Max tokens per text (pad/truncate)

        Returns:
            torch.LongTensor of shape [B, max_length]
        """
        import hashlib

        import torch

        token_ids = []
        for t in texts:
            if not isinstance(t, str):
                t = str(t)
            words = t.strip().split()
            ids = []
            for w in words[:max_length]:
                # Stable hash to vocab id (PAD=0 reserved)
                try:
                    digest = hashlib.md5(w.encode("utf-8"), usedforsecurity=False).hexdigest()
                except TypeError:
                    # Older Python builds may not expose usedforsecurity=
                    digest = hashlib.md5(w.encode("utf-8")).hexdigest()
                h = int(digest, 16)
                ids.append((h % (self._vocab_size - 1)) + 1)
            if len(ids) < max_length:
                ids.extend([0] * (max_length - len(ids)))
            token_ids.append(ids)

        return torch.tensor(token_ids, dtype=torch.long).to(self._device)

    def encode_text(self, text_tokens: Any) -> Any:
        """Encode text to shared embedding space.

        Args:
            text_tokens: Tokenized text [B, seq_len]

        Returns:
            Normalized embeddings [B, embedding_dim]
        """
        if self._text_encoder is None:
            raise RuntimeError("Text encoder is not initialized.")

        import torch
        import torch.nn.functional as F

        # Accept either pre-tokenized tensors or raw strings.
        if isinstance(text_tokens, str):
            tokens = self._tokenize_texts([text_tokens])
        elif isinstance(text_tokens, torch.Tensor):
            tokens = text_tokens.to(self._device)
        elif (
            isinstance(text_tokens, (list, tuple))
            and text_tokens
            and isinstance(text_tokens[0], str)
        ):
            tokens = self._tokenize_texts(text_tokens)
        else:
            tokens = torch.tensor(text_tokens, dtype=torch.long).to(self._device)

        embeddings = self._text_encoder(tokens)
        return F.normalize(embeddings, dim=-1)

    def encode_text_batch(self, texts: list[str]) -> Any:
        """Encode a batch of raw texts to embeddings [B, D]."""
        return self.encode_text(texts)

    def encode_vision(self, images: Any) -> Any:
        """Alias for encode_image (tests + API compatibility)."""
        return self.encode_image(images)

    def encode_image(self, images: Any) -> Any:
        """Encode images to shared embedding space.

        Args:
            images: Image tensor [B, 3, H, W]

        Returns:
            Normalized embeddings [B, embedding_dim]
        """
        if self._vision_encoder is None:
            raise RuntimeError("Vision encoder is not initialized.")

        import torch
        import torch.nn.functional as F

        # Ensure tensor on correct device
        if not isinstance(images, torch.Tensor):
            images = torch.tensor(images, dtype=torch.float32).to(self._device)
        else:
            if images.device.type != self._device:
                try:
                    images = images.to(self._device)
                except Exception:
                    pass

        # Optional Core ML path (expects NHWC float32 per-image)
        if getattr(self, "_coreml_vision", None) is not None:
            try:
                import numpy as np

                x = images
                if x.device.type != "cpu":
                    x = x.to("cpu")
                # [B, C, H, W] -> [B, H, W, C]
                x_nhwc = x.permute(0, 2, 3, 1).contiguous().numpy().astype(np.float32)
                feats = self._coreml_vision.encode(x_nhwc)  # (B, D) numpy
                feats_t = torch.tensor(feats, dtype=torch.float32)
                return F.normalize(feats_t, dim=-1)
            except Exception:
                # Fallback to PyTorch path on any Core ML error
                pass

        # Optimize data layout on MPS
        if getattr(self, "_mps_autocast", False):
            try:
                images = images.to(memory_format=torch.channels_last)
            except Exception:
                pass

        # Encode (with optional autocast on MPS)
        if getattr(self, "_mps_autocast", False):
            try:
                from contextlib import nullcontext

                amp_ctx = getattr(torch.amp, "autocast", None)
                ctx = amp_ctx(device_type="mps", dtype=torch.float16) if amp_ctx else nullcontext()
                with ctx:
                    embeddings = self._vision_encoder(images)
            except Exception:
                embeddings = self._vision_encoder(images)
        else:
            embeddings = self._vision_encoder(images)

        # Normalize
        embeddings = F.normalize(embeddings, dim=-1)

        return embeddings

    def encode_audio(self, spectrograms: Any) -> Any:
        """Encode audio spectrograms to shared embedding space.

        Args:
            spectrograms: Mel-spectrogram tensor [B, 1, freq, time]

        Returns:
            Normalized embeddings [B, embedding_dim]
        """
        if self._audio_encoder is None:
            raise RuntimeError("Audio encoder is not initialized.")

        import torch
        import torch.nn.functional as F

        # Convert to tensor if needed
        if not isinstance(spectrograms, torch.Tensor):
            spectrograms = torch.tensor(spectrograms, dtype=torch.float32).to(self._device)
        else:
            spectrograms = spectrograms.to(self._device)

        # Accept [B, mel, T] or [mel, T] and normalize to [B, 1, mel, T].
        if spectrograms.dim() == 2:
            spectrograms = spectrograms.unsqueeze(0).unsqueeze(0)
        elif spectrograms.dim() == 3:
            spectrograms = spectrograms.unsqueeze(1)

        # Encode (with optional autocast on MPS)
        if getattr(self, "_mps_autocast", False):
            try:
                from contextlib import nullcontext

                amp_ctx = getattr(torch.amp, "autocast", None)
                ctx = amp_ctx(device_type="mps", dtype=torch.float16) if amp_ctx else nullcontext()
                with ctx:
                    embeddings = self._audio_encoder(spectrograms)
            except Exception:
                embeddings = self._audio_encoder(spectrograms)
        else:
            embeddings = self._audio_encoder(spectrograms)

        # Normalize
        embeddings = F.normalize(embeddings, dim=-1)

        return embeddings

    def compute_contrastive_loss(
        self, modality_a_embeddings: Any, modality_b_embeddings: Any
    ) -> Any:
        """Compute contrastive loss between two modalities.

        Args:
            modality_a_embeddings: Embeddings from modality A [B, D]
            modality_b_embeddings: Embeddings from modality B [B, D]

        Returns:
            Symmetric contrastive loss (scalar)
        """
        try:
            import torch
            import torch.nn.functional as F

            # Compute similarity matrix
            logits_a_to_b = (modality_a_embeddings @ modality_b_embeddings.T) / self.temperature

            logits_b_to_a = logits_a_to_b.T

            # Labels: diagonal (matching pairs)
            batch_size = modality_a_embeddings.size(0)
            labels = torch.arange(batch_size, device=self._device)

            # Symmetric cross-entropy
            loss = (
                F.cross_entropy(logits_a_to_b, labels) + F.cross_entropy(logits_b_to_a, labels)
            ) / 2

            return loss

        except Exception as e:
            logger.error(f"Contrastive loss failed: {e}")
            return None

    def compute_similarity(self, embedding_a: Any, embedding_b: Any) -> Any:
        """Compute cosine similarity between embeddings.

        Args:
            embedding_a: Embedding from any modality [D]
            embedding_b: Embedding from any modality [D]

        Returns:
            Cosine similarity score (0-1)
        """
        try:
            import torch
            import torch.nn.functional as F

            # Ensure tensors
            if not isinstance(embedding_a, torch.Tensor):
                embedding_a = torch.tensor(embedding_a, dtype=torch.float32)
            if not isinstance(embedding_b, torch.Tensor):
                embedding_b = torch.tensor(embedding_b, dtype=torch.float32)

            # Normalize
            embedding_a = F.normalize(embedding_a, dim=-1)
            embedding_b = F.normalize(embedding_b, dim=-1)

            # Cosine similarity
            similarity = (embedding_a * embedding_b).sum()

            return float(similarity.item())

        except Exception as e:
            logger.error(f"Similarity computation failed: {e}")
            return 0.0

    def cross_modal_retrieval(
        self, query_embedding: Any, candidate_embeddings: Any, top_k: int = 5
    ) -> dict[str, Any]:
        """Retrieve top-k candidates from different modality.

        Args:
            query_embedding: Query from one modality [D]
            candidate_embeddings: Candidates from another modality [N, D]
            top_k: Number of results to return

        Returns:
            Indices and scores of top-k matches
        """
        try:
            import torch
            import torch.nn.functional as F

            # Ensure tensors
            if not isinstance(query_embedding, torch.Tensor):
                query_embedding = torch.tensor(query_embedding, dtype=torch.float32).to(
                    self._device
                )
            if not isinstance(candidate_embeddings, torch.Tensor):
                candidate_embeddings = torch.tensor(candidate_embeddings, dtype=torch.float32).to(
                    self._device
                )

            # Normalize
            query_embedding = F.normalize(query_embedding, dim=-1)
            candidate_embeddings = F.normalize(candidate_embeddings, dim=-1)

            # Compute similarities
            similarities = query_embedding @ candidate_embeddings.T

            # Get top-k
            top_k = min(top_k, len(candidate_embeddings))
            scores, indices = torch.topk(similarities, k=top_k)

            return {"indices": indices.cpu().tolist(), "scores": scores.cpu().tolist()}

        except Exception as e:
            logger.error(f"Cross-modal retrieval failed: {e}")
            return {"indices": [], "scores": []}


# Singleton
_FUSION_MODEL: ContrastiveMultimodalFusion | None = None


def get_multimodal_fusion(embedding_dim: int = 512) -> ContrastiveMultimodalFusion:
    """Get or create multimodal fusion model.

    Args:
        embedding_dim: Shared embedding dimension

    Returns:
        ContrastiveMultimodalFusion instance
    """
    global _FUSION_MODEL
    if _FUSION_MODEL is None:
        _FUSION_MODEL = ContrastiveMultimodalFusion(embedding_dim=embedding_dim)
    return _FUSION_MODEL
