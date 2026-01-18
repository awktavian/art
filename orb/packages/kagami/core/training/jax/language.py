"""JAX Language Integration - Language-Conditioned RSSM for Phase 6.

PORTED FROM:
- world_model/language_reasoning.py (LanguageEncoder, StateDescriptor, Grounder)

This module enables:
1. Text → Latent grounding ("make it cozy" → target state)
2. Latent → Text captioning (state → "lights are dim")
3. Cross-modal fusion (HiVG-style hierarchical attention)
4. Entity grounding (LED-WM-style colony attention)

Architecture (HiVG + LED-WM):
==============================
```
Text ─────────────────────────────┐
         │                        │
         ▼                        │
    TextEncoder                   │
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────┐
│ HierarchicalCrossModalFusion (HiVG)     │
│                                          │
│    language_emb ───┬─── h (RSSM state)  │
│                    │                     │
│                ┌───▼───┐                │
│                │ Cross │ × N layers     │
│                │ Attn  │                │
│                └───────┘                │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ EntityGrounding (LED-WM style)          │
│                                          │
│    language_emb → colony attention      │
│    Maps to 7 specific colonies          │
└─────────────────────────────────────────┘
         │
         ▼
    h_conditioned (language-grounded state)
```

References:
- SigLIP 2: Vision-language encoder
- HiVG: Hierarchical Visual Grounding (CVPR 2024)
- LED-WM: Language-Entity-Driven World Models (NeurIPS 2023)

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import jax
import jax.numpy as jnp
from flax import linen as nn

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class LanguageConfig:
    """Configuration for language integration.

    frozen=True for JAX static_argnums compatibility.
    """

    # Dimensions (match RSSM)
    latent_dim: int = 384  # RSSM hidden dim
    language_dim: int = 768  # Text embedding dim
    hidden_dim: int = 512  # Fusion hidden dim

    # Architecture
    num_fusion_layers: int = 3  # Cross-attention layers
    num_heads: int = 8  # Attention heads
    dropout: float = 0.1

    # Grounding
    num_concepts: int = 1024  # Learned concept vocabulary
    num_colonies: int = 7  # Colony count for entity grounding

    # Captioning
    vocab_size: int = 32000  # Output vocabulary
    max_length: int = 64  # Max caption length

    # E8 integration
    e8_dim: int = 8  # For E8 colony projections


# =============================================================================
# TEXT ENCODER (Learned, not pretrained LLM for TPU efficiency)
# =============================================================================


class TextEncoder(nn.Module):
    """Learned text encoder for TPU training.

    Rather than loading a pretrained LLM (expensive on TPU), we train
    a lightweight encoder end-to-end with the RSSM.

    Architecture:
        Token IDs → Embedding → Transformer → Mean pooling → Projection
    """

    config: LanguageConfig

    @nn.compact
    def __call__(
        self,
        token_ids: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Encode text tokens to embedding.

        Args:
            token_ids: [B, L] token indices
            mask: [B, L] attention mask (1=attend, 0=ignore)
            training: Whether in training mode

        Returns:
            [B, language_dim] text embeddings
        """
        cfg = self.config
        B, L = token_ids.shape

        # Token embedding
        embed = nn.Embed(
            num_embeddings=cfg.vocab_size,
            features=cfg.language_dim,
            name="token_embed",
        )(token_ids)  # [B, L, D]

        # Positional encoding (learned)
        pos_embed = self.param(
            "pos_embed",
            nn.initializers.normal(stddev=0.02),
            (1, L, cfg.language_dim),
        )
        embed = embed + pos_embed[:, :L]

        # Transformer layers
        for i in range(3):  # 3 lightweight layers
            # Self-attention
            residual = embed
            embed = nn.LayerNorm(name=f"ln1_{i}")(embed)

            # Create causal mask if needed
            attn_mask = None
            if mask is not None:
                # [B, L] -> [B, 1, 1, L] for broadcasting
                attn_mask = mask[:, None, None, :]

            embed = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.language_dim,
                dropout_rate=cfg.dropout,
                deterministic=not training,
                name=f"attn_{i}",
            )(embed, embed, mask=attn_mask)
            embed = embed + residual

            # FFN
            residual = embed
            embed = nn.LayerNorm(name=f"ln2_{i}")(embed)
            embed = nn.Dense(cfg.language_dim * 4, name=f"ffn1_{i}")(embed)
            embed = nn.gelu(embed)
            embed = nn.Dense(cfg.language_dim, name=f"ffn2_{i}")(embed)
            if training:
                embed = nn.Dropout(rate=cfg.dropout)(embed, deterministic=False)
            embed = embed + residual

        # Mean pooling with mask
        if mask is not None:
            mask_expanded = mask[:, :, None]  # [B, L, 1]
            embed = (embed * mask_expanded).sum(axis=1) / (mask_expanded.sum(axis=1) + 1e-8)
        else:
            embed = embed.mean(axis=1)

        return embed  # [B, language_dim]


# =============================================================================
# CROSS-MODAL FUSION (HiVG-style)
# =============================================================================


class CrossModalAttention(nn.Module):
    """Cross-modal attention between language and state.

    Based on HiVG (Hierarchical Visual Grounding).
    """

    config: LanguageConfig

    @nn.compact
    def __call__(
        self,
        state: jnp.ndarray,
        language: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Cross-attention: state attends to language.

        Args:
            state: [B, D_state] or [B, T, D_state] state features
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            Fused state features, same shape as input state
        """
        cfg = self.config

        # Ensure 3D for attention
        state_3d = state if state.ndim == 3 else state[:, None, :]
        B, T, D = state_3d.shape

        # Expand language to match state time dim
        lang_expanded = language[:, None, :].repeat(T, axis=1)  # [B, T, D_lang]

        # Project to common space
        q = nn.Dense(cfg.hidden_dim, name="q_proj")(state_3d)  # [B, T, H]
        k = nn.Dense(cfg.hidden_dim, name="k_proj")(lang_expanded)  # [B, T, H]
        v = nn.Dense(cfg.hidden_dim, name="v_proj")(lang_expanded)  # [B, T, H]

        # Multi-head attention
        fused = nn.MultiHeadDotProductAttention(
            num_heads=cfg.num_heads,
            qkv_features=cfg.hidden_dim,
            dropout_rate=cfg.dropout,
            deterministic=not training,
            name="cross_attn",
        )(q, k, v)

        # Project back to state dim
        fused = nn.Dense(D, name="out_proj")(fused)

        # Residual connection
        result = state_3d + fused

        # Return same shape as input
        return result if state.ndim == 3 else result.squeeze(1)


class HierarchicalCrossModalFusion(nn.Module):
    """Multi-layer cross-modal fusion (HiVG architecture).

    Applies N layers of cross-attention between state and language,
    with intermediate normalization and residual connections.
    """

    config: LanguageConfig

    @nn.compact
    def __call__(
        self,
        state: jnp.ndarray,
        language: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Apply hierarchical fusion.

        Args:
            state: [B, D] or [B, T, D] state features
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            Language-conditioned state features
        """
        cfg = self.config

        for i in range(cfg.num_fusion_layers):
            # LayerNorm before attention
            state = nn.LayerNorm(name=f"ln_{i}")(state)

            # Cross-modal attention
            state = CrossModalAttention(cfg, name=f"cross_{i}")(state, language, training)

        return state


# =============================================================================
# ENTITY GROUNDING (LED-WM style)
# =============================================================================


class EntityGrounding(nn.Module):
    """Ground language to specific colonies (LED-WM style).

    Maps language embeddings to attention weights over the 7 colonies,
    enabling fine-grained control over which colonies attend to text.

    Architecture:
        language_emb → MLP → softmax → [B, 7] colony weights
    """

    config: LanguageConfig

    @nn.compact
    def __call__(
        self,
        language: jnp.ndarray,
        training: bool = True,
    ) -> jnp.ndarray:
        """Compute colony attention weights from language.

        Args:
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            [B, 7] colony attention weights (softmax normalized)
        """
        cfg = self.config

        # MLP to predict colony weights
        x = nn.Dense(cfg.hidden_dim, name="mlp1")(language)
        x = nn.gelu(x)
        if training:
            x = nn.Dropout(rate=cfg.dropout)(x, deterministic=False)
        x = nn.Dense(cfg.hidden_dim // 2, name="mlp2")(x)
        x = nn.gelu(x)
        x = nn.Dense(cfg.num_colonies, name="mlp3")(x)

        # Softmax over colonies
        weights = jax.nn.softmax(x, axis=-1)  # [B, 7]

        return weights


# =============================================================================
# CONCEPT VOCABULARY
# =============================================================================


class ConceptVocabulary(nn.Module):
    """Learned concept embeddings for grounding.

    A vocabulary of 1024 learned concept embeddings that bridge
    discrete language concepts to continuous state space.
    """

    config: LanguageConfig

    def setup(self):
        """Initialize concept embeddings."""
        cfg = self.config

        # Concept embeddings
        self.concept_embed = nn.Embed(
            num_embeddings=cfg.num_concepts,
            features=cfg.latent_dim,
            name="concept_embed",
        )

        # Projection from language to concept selection
        self.concept_selector = nn.Sequential(
            [
                nn.Dense(cfg.hidden_dim),
                nn.gelu,
                nn.Dense(cfg.num_concepts),
            ]
        )

    @nn.compact
    def __call__(
        self,
        language: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Map language to concept-grounded representation.

        Args:
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            concept_embedding: [B, D_state] grounded embedding
            concept_weights: [B, num_concepts] soft concept selection
        """
        cfg = self.config

        # Compute soft concept selection
        logits = nn.Sequential(
            [
                nn.Dense(cfg.hidden_dim),
                nn.gelu,
                nn.Dense(cfg.num_concepts),
            ],
            name="concept_selector",
        )(language)

        # Soft attention over concepts
        weights = jax.nn.softmax(logits / 0.1, axis=-1)  # Temperature 0.1

        # Weighted sum of concept embeddings
        all_concepts = self.param(
            "concepts",
            nn.initializers.normal(stddev=0.02),
            (cfg.num_concepts, cfg.latent_dim),
        )
        embedding = jnp.einsum("bc,cd->bd", weights, all_concepts)

        return embedding, weights


# =============================================================================
# STATE CAPTIONER
# =============================================================================


class StateCaptioner(nn.Module):
    """Generate text descriptions from state.

    Autoregressive decoder that generates captions from state embeddings.
    """

    config: LanguageConfig

    @nn.compact
    def __call__(
        self,
        state: jnp.ndarray,
        target_ids: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Generate caption logits from state.

        Args:
            state: [B, D_state] state embedding
            target_ids: [B, L] target token IDs (for teacher forcing)
            training: Whether in training mode

        Returns:
            [B, L, vocab_size] logits for each position
        """
        cfg = self.config
        B = state.shape[0]

        if target_ids is None:
            # During inference, start with BOS token
            L = cfg.max_length
            target_ids = jnp.zeros((B, L), dtype=jnp.int32)
        else:
            L = target_ids.shape[1]

        # Token embedding
        token_embed = nn.Embed(
            num_embeddings=cfg.vocab_size,
            features=cfg.language_dim,
            name="token_embed",
        )(target_ids)  # [B, L, D]

        # Add positional encoding
        pos_embed = self.param(
            "pos_embed",
            nn.initializers.normal(stddev=0.02),
            (1, cfg.max_length, cfg.language_dim),
        )
        token_embed = token_embed + pos_embed[:, :L]

        # Project state to match language dim
        state_proj = nn.Dense(cfg.language_dim, name="state_proj")(state)  # [B, D]
        state_proj = state_proj[:, None, :]  # [B, 1, D]

        # Concatenate state as first token
        decoder_input = jnp.concatenate([state_proj, token_embed[:, :-1]], axis=1)

        # Causal transformer decoder
        # Create causal mask
        causal_mask = jnp.tril(jnp.ones((L, L)))
        causal_mask = causal_mask[None, None, :, :]  # [1, 1, L, L]

        x = decoder_input
        for i in range(3):  # 3 decoder layers
            residual = x
            x = nn.LayerNorm(name=f"ln1_{i}")(x)
            x = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.language_dim,
                dropout_rate=cfg.dropout,
                deterministic=not training,
                name=f"attn_{i}",
            )(x, x, mask=causal_mask)
            x = x + residual

            residual = x
            x = nn.LayerNorm(name=f"ln2_{i}")(x)
            x = nn.Dense(cfg.language_dim * 4, name=f"ffn1_{i}")(x)
            x = nn.gelu(x)
            x = nn.Dense(cfg.language_dim, name=f"ffn2_{i}")(x)
            x = x + residual

        # Final projection to vocabulary
        logits = nn.Dense(cfg.vocab_size, name="output")(x)  # [B, L, V]

        return logits


# =============================================================================
# LANGUAGE-CONDITIONED RSSM WRAPPER
# =============================================================================


class LanguageConditionedRSSM(nn.Module):
    """Wrap RSSM with language conditioning for Phase 6 training.

    This module adds language conditioning to an existing RSSM:
    1. Encodes text to embedding
    2. Fuses language with RSSM state via hierarchical cross-attention
    3. Grounds language to specific colonies
    4. Can generate captions from state
    """

    config: LanguageConfig

    def setup(self):
        """Initialize language components."""
        cfg = self.config

        self.text_encoder = TextEncoder(cfg)
        self.fusion = HierarchicalCrossModalFusion(cfg)
        self.entity_grounding = EntityGrounding(cfg)
        self.concept_vocab = ConceptVocabulary(cfg)
        self.captioner = StateCaptioner(cfg)

    def encode_text(
        self,
        token_ids: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Encode text to embedding.

        Args:
            token_ids: [B, L] token indices
            mask: [B, L] attention mask
            training: Whether in training mode

        Returns:
            [B, language_dim] text embeddings
        """
        return self.text_encoder(token_ids, mask, training)

    def condition_state(
        self,
        h: jnp.ndarray,
        language: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Condition RSSM state on language.

        Args:
            h: [B, 7, H] colony hidden states
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            h_conditioned: [B, 7, H] language-conditioned state
            colony_weights: [B, 7] per-colony language attention
        """
        B, num_colonies, H = h.shape

        # Get colony attention weights
        colony_weights = self.entity_grounding(language, training)  # [B, 7]

        # Apply hierarchical fusion per colony
        # Reshape to [B*7, H] for efficient processing
        h_flat = h.reshape(B * num_colonies, H)
        language_expanded = language[:, None, :].repeat(num_colonies, axis=1)
        language_flat = language_expanded.reshape(B * num_colonies, -1)

        # Fuse each colony state with language
        h_fused = self.fusion(h_flat, language_flat, training)
        h_fused = h_fused.reshape(B, num_colonies, H)

        # Weight by colony attention
        weights_expanded = colony_weights[:, :, None]  # [B, 7, 1]
        h_conditioned = h + h_fused * weights_expanded

        return h_conditioned, colony_weights

    def ground_language(
        self,
        language: jnp.ndarray,
        training: bool = True,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Ground language to concept embedding.

        Args:
            language: [B, D_lang] language embedding
            training: Whether in training mode

        Returns:
            target_state: [B, D_state] target state embedding
            concept_weights: [B, num_concepts] concept attention
        """
        return self.concept_vocab(language, training)

    def caption_state(
        self,
        h: jnp.ndarray,
        target_ids: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Generate caption from state.

        Args:
            h: [B, 7, H] colony hidden states
            target_ids: [B, L] target tokens (for training)
            training: Whether in training mode

        Returns:
            [B, L, vocab_size] caption logits
        """
        # Pool colony states
        h_pooled = h.mean(axis=1)  # [B, H]
        return self.captioner(h_pooled, target_ids, training)


# =============================================================================
# LANGUAGE LOSS FUNCTIONS
# =============================================================================


def compute_grounding_loss(
    pred_state: jnp.ndarray,
    target_state: jnp.ndarray,
) -> jnp.ndarray:
    """Compute state grounding loss (MSE).

    Args:
        pred_state: [B, D] predicted state from language
        target_state: [B, D] ground truth state

    Returns:
        Scalar loss
    """
    return jnp.mean((pred_state - target_state) ** 2)


def compute_captioning_loss(
    logits: jnp.ndarray,
    target_ids: jnp.ndarray,
    mask: jnp.ndarray | None = None,
) -> jnp.ndarray:
    """Compute caption cross-entropy loss.

    Args:
        logits: [B, L, V] predicted logits
        target_ids: [B, L] target token IDs
        mask: [B, L] loss mask (1=compute, 0=ignore)

    Returns:
        Scalar loss
    """
    # Compute cross-entropy
    vocab_size = logits.shape[-1]
    log_probs = jax.nn.log_softmax(logits, axis=-1)

    # Get target log probs
    B, L = target_ids.shape
    target_onehot = jax.nn.one_hot(target_ids, vocab_size)
    loss_per_token = -jnp.sum(log_probs * target_onehot, axis=-1)  # [B, L]

    # Apply mask
    if mask is not None:
        loss_per_token = loss_per_token * mask
        return jnp.sum(loss_per_token) / (jnp.sum(mask) + 1e-8)
    else:
        return jnp.mean(loss_per_token)


def compute_contrastive_loss(
    state_embed: jnp.ndarray,
    text_embed: jnp.ndarray,
    temperature: float = 0.07,
) -> jnp.ndarray:
    """Compute contrastive loss (InfoNCE / CLIP-style).

    Args:
        state_embed: [B, D] state embeddings
        text_embed: [B, D] text embeddings
        temperature: Softmax temperature

    Returns:
        Scalar loss
    """
    # L2 normalize
    state_embed = state_embed / (jnp.linalg.norm(state_embed, axis=-1, keepdims=True) + 1e-8)
    text_embed = text_embed / (jnp.linalg.norm(text_embed, axis=-1, keepdims=True) + 1e-8)

    # Cosine similarity matrix
    logits = jnp.matmul(state_embed, text_embed.T) / temperature  # [B, B]

    # InfoNCE loss (symmetric)
    B = logits.shape[0]
    labels = jnp.arange(B)

    loss_s2t = jnp.mean(-jax.nn.log_softmax(logits, axis=1)[jnp.arange(B), labels])
    loss_t2s = jnp.mean(-jax.nn.log_softmax(logits, axis=0)[labels, jnp.arange(B)])

    return (loss_s2t + loss_t2s) / 2


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_language_module(
    latent_dim: int = 384,
    language_dim: int = 768,
    num_fusion_layers: int = 3,
) -> LanguageConditionedRSSM:
    """Create language integration module.

    Args:
        latent_dim: RSSM hidden dimension
        language_dim: Text embedding dimension
        num_fusion_layers: Number of cross-attention layers

    Returns:
        Configured LanguageConditionedRSSM
    """
    config = LanguageConfig(
        latent_dim=latent_dim,
        language_dim=language_dim,
        num_fusion_layers=num_fusion_layers,
    )
    return LanguageConditionedRSSM(config)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "ConceptVocabulary",
    "CrossModalAttention",
    "EntityGrounding",
    "HierarchicalCrossModalFusion",
    "LanguageConditionedRSSM",
    "LanguageConfig",
    "StateCaptioner",
    "TextEncoder",
    "compute_captioning_loss",
    "compute_contrastive_loss",
    "compute_grounding_loss",
    "create_language_module",
]
