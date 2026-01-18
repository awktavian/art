"""Gemini-Enhanced Language Grounding for General LLM World Model.

CREATED: January 5, 2026
REVISED: January 5, 2026 - General LLM, not domain-specific

This module implements GENERAL language grounding using Gemini embeddings
as a teacher signal. The goal is to make Kagami a general-purpose LLM,
not just a smart home controller.

ARCHITECTURE:
=============
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GENERAL LLM GROUNDING PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   TRAINING DATA (General Text Corpora)                                      │
│   ├── Wikipedia, Books, Web (knowledge)                                     │
│   ├── Instruction pairs (capability)                                        │
│   ├── Code (reasoning)                                                      │
│   └── Multimodal captions (grounding)                                       │
│                                                                             │
│   Text ────────────▶ Gemini Embedding API ────────────▶ Teacher (768-3072D) │
│                      (gemini-embedding-001)                                 │
│                      Can run: local, TPU VM, or batch API                   │
│                                                                             │
│                              ↓ Alignment Loss                               │
│                              MSE + InfoNCE + VICReg                         │
│                                                                             │
│   World State ─────▶ Student Projection ──────────────▶ Student (768D)     │
│   (OrganismRSSM)     (TPU-trainable)                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

WHAT WE EMBED:
==============
For a GENERAL LLM, we align the world model with embeddings of:

1. **General Text** - So the world model understands language
   - "The cat sat on the mat"
   - "Explain quantum entanglement"
   - "Write a Python function that..."

2. **Instruction-Response Pairs** - So it can follow instructions
   - ("Summarize this text", "<summary>")
   - ("What is the capital of France?", "Paris")

3. **State-Description Pairs** - So it can describe world states
   - (physics_state, "Ball moving right at 5 m/s")
   - (smart_home_state, "Living room: lights at 50%")

4. **Action-Description Pairs** - So it can understand actions
   - (action_vector, "Turn on the lights")
   - (control_signal, "Accelerate forward")

CLOUD COMPUTATION:
==================
Embeddings can be computed:
1. **TPU VM directly** - Call Gemini API during training (online)
2. **Pre-computed in GCS** - Load from cloud storage (offline)
3. **Vertex AI Batch** - Process large datasets asynchronously

References:
- Gemini Embedding API: https://ai.google.dev/gemini-api/docs/embeddings
- PaLM-E: https://arxiv.org/abs/2303.03378
- RT-2: https://arxiv.org/abs/2307.15818
- VICReg: https://arxiv.org/abs/2105.04906
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)

# Try to import Gemini SDK
try:
    from google import genai
    from google.genai import types

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class GeminiGroundingConfig:
    """Configuration for Gemini-enhanced general language grounding.

    Attributes:
        embedding_model: Gemini embedding model to use.
        embedding_dim: Output dimensionality (768, 1536, or 3072).
        task_type: Embedding task type for Gemini API.
        cache_dir: Directory to cache embeddings (local or GCS).
        batch_size: Batch size for embedding API calls.
        use_contrastive: Whether to use contrastive loss in addition to MSE.
        use_vicreg: Whether to use VICReg loss for regularization.
        contrastive_temperature: Temperature for InfoNCE loss.
        distillation_weight: Weight for MSE distillation loss.
        alignment_weight: Weight for contrastive alignment loss.
        vicreg_sim_weight: VICReg invariance weight.
        vicreg_var_weight: VICReg variance weight.
        vicreg_cov_weight: VICReg covariance weight.
        projection_hidden: Hidden dimension for projection head.
        compute_location: Where to compute embeddings ("api", "tpu", "gcs").
    """

    # Gemini API settings
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768  # 768 for efficiency, 3072 for quality
    task_type: str = "SEMANTIC_SIMILARITY"

    # Caching (GCS path for cloud, local path for development)
    cache_dir: str = "gs://kagami-training-schizodactyl-2026/embeddings"
    batch_size: int = 64

    # Loss configuration
    use_contrastive: bool = True
    use_vicreg: bool = True  # VICReg prevents collapse
    contrastive_temperature: float = 0.07
    distillation_weight: float = 1.0
    alignment_weight: float = 0.5
    vicreg_sim_weight: float = 25.0
    vicreg_var_weight: float = 25.0
    vicreg_cov_weight: float = 1.0

    # Projection architecture
    projection_hidden: int = 512
    projection_layers: int = 2
    dropout: float = 0.1

    # Compute location
    compute_location: str = "api"  # "api", "tpu", "gcs"


# =============================================================================
# EMBEDDING CACHE (LOCAL + GCS)
# =============================================================================


class EmbeddingCache:
    """Cache for embeddings supporting both local and GCS storage.

    For general LLM training, we need to cache MILLIONS of embeddings.
    GCS provides scalable cloud storage for this.
    """

    def __init__(self, cache_dir: str = "~/.kagami/embeddings") -> None:
        """Initialize the embedding cache.

        Args:
            cache_dir: Directory to store cached embeddings.
                       Can be local path or gs:// GCS path.
        """
        self.cache_dir = cache_dir
        self._is_gcs = cache_dir.startswith("gs://")
        self._memory_cache: dict[str, torch.Tensor] = {}
        self._gcs_client = None

        if not self._is_gcs:
            Path(cache_dir).expanduser().mkdir(parents=True, exist_ok=True)

    def _get_gcs_client(self) -> Any:
        """Get or create GCS client."""
        if self._gcs_client is None:
            try:
                from google.cloud import storage

                self._gcs_client = storage.Client()
            except ImportError:
                logger.warning("google-cloud-storage not installed")
                return None
        return self._gcs_client

    def _hash_text(self, text: str) -> str:
        """Generate hash for text content."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _parse_gcs_path(self, path: str) -> tuple[str, str]:
        """Parse gs:// path into bucket and blob."""
        path = path.replace("gs://", "")
        parts = path.split("/", 1)
        bucket = parts[0]
        blob = parts[1] if len(parts) > 1 else ""
        return bucket, blob

    def get(self, text: str) -> torch.Tensor | None:
        """Retrieve cached embedding for text."""
        text_hash = self._hash_text(text)

        # Check memory cache first
        if text_hash in self._memory_cache:
            return self._memory_cache[text_hash]

        if self._is_gcs:
            return self._get_from_gcs(text_hash)
        else:
            return self._get_from_local(text_hash)

    def _get_from_local(self, text_hash: str) -> torch.Tensor | None:
        """Get embedding from local cache."""
        cache_path = Path(self.cache_dir).expanduser() / f"{text_hash}.pt"
        if cache_path.exists():
            try:
                embedding = torch.load(cache_path, weights_only=True)
                self._memory_cache[text_hash] = embedding
                return embedding
            except Exception as e:
                logger.warning(f"Failed to load cached embedding: {e}")
        return None

    def _get_from_gcs(self, text_hash: str) -> torch.Tensor | None:
        """Get embedding from GCS cache."""
        client = self._get_gcs_client()
        if client is None:
            return None

        bucket_name, prefix = self._parse_gcs_path(self.cache_dir)
        blob_path = f"{prefix}/{text_hash}.pt" if prefix else f"{text_hash}.pt"

        try:
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)

            if blob.exists():
                data = blob.download_as_bytes()
                import io

                embedding = torch.load(io.BytesIO(data), weights_only=True)
                self._memory_cache[text_hash] = embedding
                return embedding
        except Exception as e:
            logger.debug(f"GCS cache miss: {e}")

        return None

    def put(self, text: str, embedding: torch.Tensor) -> None:
        """Store embedding in cache."""
        text_hash = self._hash_text(text)
        self._memory_cache[text_hash] = embedding.cpu()

        if self._is_gcs:
            self._put_to_gcs(text_hash, embedding)
        else:
            self._put_to_local(text_hash, embedding)

    def _put_to_local(self, text_hash: str, embedding: torch.Tensor) -> None:
        """Save embedding to local cache."""
        cache_path = Path(self.cache_dir).expanduser() / f"{text_hash}.pt"
        try:
            torch.save(embedding.cpu(), cache_path)
        except Exception as e:
            logger.warning(f"Failed to save embedding to cache: {e}")

    def _put_to_gcs(self, text_hash: str, embedding: torch.Tensor) -> None:
        """Save embedding to GCS cache."""
        client = self._get_gcs_client()
        if client is None:
            return

        bucket_name, prefix = self._parse_gcs_path(self.cache_dir)
        blob_path = f"{prefix}/{text_hash}.pt" if prefix else f"{text_hash}.pt"

        try:
            import io

            buffer = io.BytesIO()
            torch.save(embedding.cpu(), buffer)
            buffer.seek(0)

            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            blob.upload_from_file(buffer)
        except Exception as e:
            logger.warning(f"Failed to save embedding to GCS: {e}")

    def get_batch(self, texts: list[str]) -> tuple[list[torch.Tensor | None], list[str]]:
        """Get cached embeddings for batch of texts.

        Returns:
            Tuple of (cached embeddings or None, texts needing computation).
        """
        results: list[torch.Tensor | None] = []
        uncached: list[str] = []

        for text in texts:
            cached = self.get(text)
            results.append(cached)
            if cached is None:
                uncached.append(text)

        return results, uncached


# =============================================================================
# GEMINI EMBEDDING SERVICE (CLOUD-NATIVE)
# =============================================================================


class GeminiEmbeddingService:
    """Service for generating embeddings using Gemini API.

    Supports computing embeddings:
    - Locally via API calls
    - On TPU VM via API calls
    - From pre-computed GCS cache
    - Via Vertex AI Batch API for large scale
    """

    def __init__(
        self,
        config: GeminiGroundingConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize the Gemini embedding service.

        Args:
            config: Configuration for the service.
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var).
        """
        self.config = config or GeminiGroundingConfig()
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._client: Any | None = None
        self._cache = EmbeddingCache(self.config.cache_dir)
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        """Lazy initialize Gemini client."""
        if self._initialized:
            return self._client is not None

        if not GEMINI_AVAILABLE:
            logger.warning("Gemini SDK not available. Install with: pip install google-genai")
            self._initialized = True
            return False

        if not self._api_key:
            logger.warning("GEMINI_API_KEY not set. Using fallback embeddings.")
            self._initialized = True
            return False

        try:
            self._client = genai.Client(api_key=self._api_key)
            self._initialized = True
            logger.info(f"Gemini embedding service initialized: {self.config.embedding_model}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            self._initialized = True
            return False

    async def embed_texts(self, texts: list[str]) -> torch.Tensor:
        """Generate embeddings for a list of texts.

        Uses caching to minimize API calls. Can be called from anywhere
        (local machine, TPU VM, etc.) as long as there's internet access.

        Args:
            texts: List of texts to embed.

        Returns:
            Tensor of shape [N, embedding_dim] with embeddings.
        """
        if not self._ensure_initialized() or self._client is None:
            # Return random embeddings as fallback
            logger.warning("Using random embeddings (Gemini unavailable)")
            return torch.randn(len(texts), self.config.embedding_dim)

        # Check cache
        cached_results, uncached_texts = self._cache.get_batch(texts)

        # Embed uncached texts
        if uncached_texts:
            try:
                # Call Gemini API (works from TPU VM too!)
                response = self._client.models.embed_content(
                    model=self.config.embedding_model,
                    contents=uncached_texts,
                    config=types.EmbedContentConfig(
                        task_type=self.config.task_type,
                        output_dimensionality=self.config.embedding_dim,
                    ),
                )

                # Extract embeddings
                new_embeddings = [
                    torch.tensor(e.values, dtype=torch.float32) for e in response.embeddings
                ]

                # Cache new embeddings
                for text, emb in zip(uncached_texts, new_embeddings, strict=False):
                    self._cache.put(text, emb)

                # Fill in cached_results
                uncached_idx = 0
                for i, cached in enumerate(cached_results):
                    if cached is None:
                        cached_results[i] = new_embeddings[uncached_idx]
                        uncached_idx += 1

            except Exception as e:
                logger.error(f"Gemini embedding API error: {e}")
                # Fill uncached with random embeddings
                for i, cached in enumerate(cached_results):
                    if cached is None:
                        cached_results[i] = torch.randn(self.config.embedding_dim)

        # Stack all embeddings
        embeddings = torch.stack([e for e in cached_results if e is not None])
        return embeddings

    def embed_texts_sync(self, texts: list[str]) -> torch.Tensor:
        """Synchronous wrapper for embed_texts."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.embed_texts(texts))


# =============================================================================
# VICREG LOSS (Prevents Representation Collapse)
# =============================================================================


class VICRegLoss(nn.Module):
    """VICReg loss for non-contrastive representation learning.

    From Bardes et al. "VICReg" (2022). Prevents collapse without
    requiring negative samples. Essential for general LLM grounding.
    """

    def __init__(
        self,
        sim_weight: float = 25.0,
        var_weight: float = 25.0,
        cov_weight: float = 1.0,
    ):
        super().__init__()
        self.sim_weight = sim_weight
        self.var_weight = var_weight
        self.cov_weight = cov_weight

    def forward(
        self,
        z1: torch.Tensor,
        z2: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Compute VICReg loss.

        Args:
            z1: First set of embeddings [B, D]
            z2: Second set of embeddings [B, D]

        Returns:
            Dictionary with loss components.
        """
        # Invariance loss (MSE)
        sim_loss = F.mse_loss(z1, z2)

        # Variance loss (prevent collapse)
        std_z1 = torch.sqrt(z1.var(dim=0) + 1e-4)
        std_z2 = torch.sqrt(z2.var(dim=0) + 1e-4)
        var_loss = torch.mean(F.relu(1 - std_z1)) + torch.mean(F.relu(1 - std_z2))

        # Covariance loss (decorrelation)
        z1_centered = z1 - z1.mean(dim=0)
        z2_centered = z2 - z2.mean(dim=0)
        cov_z1 = (z1_centered.T @ z1_centered) / (z1.shape[0] - 1)
        cov_z2 = (z2_centered.T @ z2_centered) / (z2.shape[0] - 1)

        # Off-diagonal covariance
        off_diag_cov_z1 = cov_z1.pow(2).sum() - cov_z1.diag().pow(2).sum()
        off_diag_cov_z2 = cov_z2.pow(2).sum() - cov_z2.diag().pow(2).sum()
        cov_loss = (off_diag_cov_z1 + off_diag_cov_z2) / z1.shape[1]

        total = self.sim_weight * sim_loss + self.var_weight * var_loss + self.cov_weight * cov_loss

        return {
            "vicreg_total": total,
            "vicreg_sim": sim_loss,
            "vicreg_var": var_loss,
            "vicreg_cov": cov_loss,
        }


# =============================================================================
# PROJECTION HEAD (World Model → Language Space)
# =============================================================================


class LanguageProjection(nn.Module):
    """Project world model states to language embedding space.

    This is the key component that aligns the world model with
    the general LLM. It learns to project RSSM states into
    Gemini's semantic space.
    """

    def __init__(
        self,
        wm_dim: int,
        config: GeminiGroundingConfig | None = None,
    ) -> None:
        """Initialize the projection head.

        Args:
            wm_dim: World model state dimension (e.g., 903 for full OrganismRSSM).
            config: Configuration for grounding.
        """
        super().__init__()
        self.wm_dim = wm_dim
        self.config = config or GeminiGroundingConfig()

        # Build projection MLP
        layers: list[nn.Module] = []
        in_dim = wm_dim

        for i in range(self.config.projection_layers):
            out_dim = (
                self.config.projection_hidden
                if i < self.config.projection_layers - 1
                else self.config.embedding_dim
            )
            layers.extend(
                [
                    nn.Linear(in_dim, out_dim),
                    nn.LayerNorm(out_dim),
                ]
            )
            if i < self.config.projection_layers - 1:
                layers.extend(
                    [
                        nn.GELU(),
                        nn.Dropout(self.config.dropout),
                    ]
                )
            in_dim = out_dim

        self.projection = nn.Sequential(*layers)

        # Learnable temperature for contrastive loss
        self._log_temperature = nn.Parameter(
            torch.tensor([float(-torch.log(torch.tensor(self.config.contrastive_temperature)))])
        )

    @property
    def temperature(self) -> torch.Tensor:
        """Get current temperature (clamped)."""
        return torch.exp(-self._log_temperature).clamp(0.01, 1.0)

    def forward(self, wm_state: torch.Tensor) -> torch.Tensor:
        """Project world model state to language embedding space.

        Args:
            wm_state: World model state [B, wm_dim].

        Returns:
            Projected embedding [B, embedding_dim].
        """
        return self.projection(wm_state)


# =============================================================================
# GROUNDING LOSS (MSE + InfoNCE + VICReg)
# =============================================================================


class GroundingLoss(nn.Module):
    """Loss function for general language grounding.

    Combines:
    1. MSE Distillation: Align student to teacher embeddings
    2. InfoNCE: Contrastive cross-modal matching
    3. VICReg: Prevent representation collapse
    """

    def __init__(self, config: GeminiGroundingConfig | None = None) -> None:
        """Initialize the loss function."""
        super().__init__()
        self.config = config or GeminiGroundingConfig()

        if self.config.use_vicreg:
            self.vicreg = VICRegLoss(
                sim_weight=self.config.vicreg_sim_weight,
                var_weight=self.config.vicreg_var_weight,
                cov_weight=self.config.vicreg_cov_weight,
            )

    def forward(
        self,
        student_embeddings: torch.Tensor,
        teacher_embeddings: torch.Tensor,
        temperature: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute grounding loss.

        Args:
            student_embeddings: Projected world model embeddings [B, D].
            teacher_embeddings: Gemini teacher embeddings [B, D].
            temperature: Optional temperature for contrastive loss.

        Returns:
            Dictionary with loss components and total loss.
        """
        # Normalize embeddings
        student_norm = F.normalize(student_embeddings, p=2, dim=-1)
        teacher_norm = F.normalize(teacher_embeddings, p=2, dim=-1)

        losses: dict[str, torch.Tensor] = {}

        # 1. MSE Distillation Loss
        mse_loss = F.mse_loss(student_embeddings, teacher_embeddings)
        losses["mse_loss"] = mse_loss * self.config.distillation_weight

        # 2. Contrastive Loss (InfoNCE)
        if self.config.use_contrastive:
            temp = temperature if temperature is not None else self.config.contrastive_temperature

            # Compute similarity matrix
            logits = torch.mm(student_norm, teacher_norm.t()) / temp

            # Labels are diagonal (matching pairs)
            labels = torch.arange(logits.size(0), device=logits.device)

            # Cross-entropy loss
            contrastive_loss = F.cross_entropy(logits, labels)
            losses["contrastive_loss"] = contrastive_loss * self.config.alignment_weight

        # 3. VICReg Loss (prevent collapse)
        if self.config.use_vicreg:
            vicreg_losses = self.vicreg(student_norm, teacher_norm)
            losses.update(vicreg_losses)

        # Total loss
        losses["total_loss"] = sum(v for k, v in losses.items() if "total" not in k)

        return losses


# =============================================================================
# COMPLETE GROUNDING MODULE
# =============================================================================


class GeminiGroundingModule(nn.Module):
    """Complete module for general language grounding.

    This is the main interface for language grounding. It:
    1. Gets text embeddings from Gemini (cloud API)
    2. Projects world model states to language space
    3. Computes alignment losses

    Can be used on TPU - Gemini API calls work from TPU VMs!
    """

    def __init__(
        self,
        wm_dim: int,
        config: GeminiGroundingConfig | None = None,
        device: str | torch.device = "cpu",
    ) -> None:
        """Initialize the grounding module.

        Args:
            wm_dim: World model state dimension.
            config: Configuration for grounding.
            device: Device for computations.
        """
        super().__init__()
        self.config = config or GeminiGroundingConfig()
        self._device = torch.device(device)

        # Components
        self.embedding_service = GeminiEmbeddingService(self.config)
        self.projection = LanguageProjection(wm_dim, self.config)
        self.loss_fn = GroundingLoss(self.config)

        self.to(self._device)

    def forward(
        self,
        wm_states: torch.Tensor,
        texts: list[str] | None = None,
        teacher_embeddings: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Forward pass for training.

        Args:
            wm_states: World model states [B, wm_dim].
            texts: Optional list of text descriptions (will call Gemini API).
            teacher_embeddings: Pre-computed teacher embeddings [B, D].

        Returns:
            Dictionary with losses and projected embeddings.
        """
        # Project world model states
        student_embeddings = self.projection(wm_states)

        # Get teacher embeddings
        if teacher_embeddings is None:
            if texts is None:
                raise ValueError("Either texts or teacher_embeddings must be provided")
            teacher_embeddings = self.embedding_service.embed_texts_sync(texts)
            teacher_embeddings = teacher_embeddings.to(self._device)

        # Compute loss
        losses = self.loss_fn(
            student_embeddings,
            teacher_embeddings,
            temperature=self.projection.temperature,
        )

        losses["student_embeddings"] = student_embeddings
        losses["teacher_embeddings"] = teacher_embeddings

        return losses

    @torch.no_grad()
    def embed_states(self, wm_states: torch.Tensor) -> torch.Tensor:
        """Embed world model states into language space (inference).

        Args:
            wm_states: World model states [B, wm_dim].

        Returns:
            Embeddings in language space [B, embedding_dim].
        """
        return self.projection(wm_states)

    @torch.no_grad()
    def embed_texts(self, texts: list[str]) -> torch.Tensor:
        """Get Gemini embeddings for texts (inference).

        Args:
            texts: List of texts to embed.

        Returns:
            Gemini embeddings [N, embedding_dim].
        """
        return self.embedding_service.embed_texts_sync(texts)

    @torch.no_grad()
    def similarity(self, wm_state: torch.Tensor, texts: list[str]) -> torch.Tensor:
        """Compute similarity between world state and texts.

        Args:
            wm_state: World model state [wm_dim] or [1, wm_dim].
            texts: List of texts to compare.

        Returns:
            Similarity scores [N] (higher = more similar).
        """
        if wm_state.dim() == 1:
            wm_state = wm_state.unsqueeze(0)

        state_emb = F.normalize(self.embed_states(wm_state), p=2, dim=-1)
        text_embs = F.normalize(self.embed_texts(texts), p=2, dim=-1)

        return torch.mm(state_emb, text_embs.t()).squeeze(0)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def get_gemini_grounding_module(
    wm_dim: int = 903,  # Default: 128*7 (colonies) + 7 (S7)
    device: str = "cpu",
    **config_kwargs: Any,
) -> GeminiGroundingModule:
    """Create a Gemini grounding module.

    Args:
        wm_dim: World model state dimension.
        device: Device for computations.
        **config_kwargs: Additional config overrides.

    Returns:
        Configured GeminiGroundingModule.
    """
    config = GeminiGroundingConfig(**config_kwargs)
    return GeminiGroundingModule(wm_dim, config, device)


# =============================================================================
# CLOUD BATCH EMBEDDING
# =============================================================================


async def precompute_embeddings_batch(
    texts: list[str],
    output_path: str,
    config: GeminiGroundingConfig | None = None,
    batch_size: int = 100,
) -> None:
    """Pre-compute Gemini embeddings for a large text dataset.

    Saves to GCS for use during TPU training.

    Args:
        texts: List of texts to embed.
        output_path: GCS path to save embeddings (e.g., gs://bucket/embeddings.pt).
        config: Configuration for embedding service.
        batch_size: Batch size for API calls.
    """
    config = config or GeminiGroundingConfig()
    service = GeminiEmbeddingService(config)

    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = await service.embed_texts(batch)
        all_embeddings.append(embeddings)
        logger.info(f"Embedded {min(i + batch_size, len(texts))}/{len(texts)} texts")

        # Small delay to avoid rate limits
        await asyncio.sleep(0.1)

    # Stack and save
    all_embeddings_tensor = torch.cat(all_embeddings, dim=0)

    # Save to GCS or local
    if output_path.startswith("gs://"):
        import io

        from google.cloud import storage

        client = storage.Client()
        path = output_path.replace("gs://", "")
        bucket_name, blob_path = path.split("/", 1)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        buffer = io.BytesIO()
        torch.save(
            {
                "embeddings": all_embeddings_tensor,
                "texts": texts,
                "config": {
                    "model": config.embedding_model,
                    "dim": config.embedding_dim,
                    "task_type": config.task_type,
                },
            },
            buffer,
        )
        buffer.seek(0)
        blob.upload_from_file(buffer)
    else:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "embeddings": all_embeddings_tensor,
                "texts": texts,
                "config": {
                    "model": config.embedding_model,
                    "dim": config.embedding_dim,
                    "task_type": config.task_type,
                },
            },
            output_path_obj,
        )

    logger.info(f"Saved {len(texts)} embeddings to {output_path}")


def load_precomputed_embeddings(path: str) -> dict[str, Any]:
    """Load pre-computed embeddings from GCS or local path.

    Args:
        path: Path to embeddings file.

    Returns:
        Dictionary with embeddings, texts, and config.
    """
    if path.startswith("gs://"):
        import io

        from google.cloud import storage

        client = storage.Client()
        path_clean = path.replace("gs://", "")
        bucket_name, blob_path = path_clean.split("/", 1)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        data = blob.download_as_bytes()
        return torch.load(io.BytesIO(data), weights_only=False)
    else:
        return torch.load(path, weights_only=False)


# =============================================================================
# TPU TRAINING PIPELINE
# =============================================================================


def create_tpu_grounding_pipeline(
    wm_dim: int = 903,
    config: GeminiGroundingConfig | None = None,
) -> dict[str, Any]:
    """Create a grounding pipeline optimized for TPU training.

    This creates components that can run on TPU. The Gemini API
    can be called directly from the TPU VM for online embedding.

    Args:
        wm_dim: World model state dimension.
        config: Configuration for grounding.

    Returns:
        Dictionary with pipeline components.
    """
    config = config or GeminiGroundingConfig()

    return {
        "config": config,
        "embedding_service": GeminiEmbeddingService(config),
        "projection": LanguageProjection(wm_dim, config),
        "loss_fn": GroundingLoss(config),
        "wm_dim": wm_dim,
    }


# Backwards compatibility aliases
GeminiEmbeddingCache = EmbeddingCache
GeminiGroundingProjection = LanguageProjection
GeminiGroundingLoss = GroundingLoss
GeminiGroundingTrainer = None  # Removed - use ConsolidatedTrainer
precompute_gemini_embeddings = precompute_embeddings_batch
