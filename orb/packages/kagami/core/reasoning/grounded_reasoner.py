from __future__ import annotations

"""Grounded Reasoning - Language Aligned to Latent Objects

Ensures LLM reasoning references actual entities in the geometric manifold:
- Extract objects from H⁷×S⁷ latent space
- Align language tokens to latent objects
- Generate plans that point to real geometric entities
- Train with contrastive alignment loss

Based on:
- CLIP (Radford et al., 2021): Contrastive vision-language
- GLIP (Li et al., 2022): Grounded language-image pretraining
- Flamingo (Alayrac et al., 2022): Cross-attention grounding
"""
import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class GroundedReasoner(nn.Module):
    """LLM reasoning grounded in latent manifold objects.

    Architecture:
        Manifold → Object extraction → Cross-attention ← LLM tokens
        └─────────────────────────────┘
              Alignment loss
    """

    def __init__(
        self,
        manifold_dim: int = 15,
        llm_hidden_dim: int = 768,
        num_objects: int = 16,
        device: str = "cpu",
    ) -> None:
        """Initialize grounded reasoner.

        Args:
            manifold_dim: H⁷×S⁷ dimension
            llm_hidden_dim: LLM hidden state dimension
            num_objects: Maximum objects to extract
            device: Computation device
        """
        super().__init__()

        self.manifold_dim = manifold_dim
        self.llm_hidden_dim = llm_hidden_dim
        self.num_objects = num_objects
        self.device = device

        # === Object Extraction from Manifold ===
        self.object_extractor = nn.Sequential(
            nn.Linear(manifold_dim, 128),
            nn.GELU(),
            nn.Linear(128, 256),
            nn.GELU(),
            nn.Linear(256, 512),  # Object features
        ).to(device)

        # === Cross-Modal Projections ===
        # Project between LLM hidden states and latent manifold
        self.text_to_latent = nn.Linear(llm_hidden_dim, manifold_dim).to(device)
        self.latent_to_text = nn.Linear(manifold_dim, llm_hidden_dim).to(device)

        # === Cross-Attention: Language ↔ Objects ===
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=llm_hidden_dim,
            num_heads=8,
            batch_first=True,
        ).to(device)

        # === Object-Text Alignment (Contrastive) ===
        self.temperature = nn.Parameter(torch.tensor(0.07))  # CLIP-style temp

        # === Object Projection to Common Space ===
        # Projects object features (512D) to manifold space for alignment
        self.object_to_latent = nn.Linear(512, manifold_dim).to(device)

        logger.info(
            f"✅ Grounded Reasoner initialized: "
            f"manifold={manifold_dim}D, llm={llm_hidden_dim}D, objects={num_objects}"
        )

    def extract_objects(self, x_latent: torch.Tensor) -> torch.Tensor:
        """Extract object features from latent manifold state.

        Args:
            x_latent: Latent state [B, manifold_dim] or [B, seq, manifold_dim]

        Returns:
            Object features [B, num_objects, 512]
        """
        # Pool sequence dimension if present
        if x_latent.dim() == 3:
            x_latent = x_latent.mean(dim=1)  # [B, manifold_dim]

        # Extract object features
        obj_features = self.object_extractor(x_latent)  # [B, 512]

        # Expand to num_objects (simple: replicate with noise)
        objects = obj_features.unsqueeze(1).repeat(1, self.num_objects, 1)

        # Add positional variation
        pos_embedding = torch.randn_like(objects) * 0.1
        objects = objects + pos_embedding

        return objects  # type: ignore  # External lib

    def ground_language_to_objects(
        self,
        language_tokens: torch.Tensor,
        object_features: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Ground language tokens to latent objects via cross-attention.

        Args:
            language_tokens: LLM hidden states [B, seq_len, llm_hidden_dim]
            object_features: Object features [B, num_objects, 512]

        Returns:
            grounded_tokens: Language with object context [B, seq_len, llm_hidden_dim]
            attention_weights: [B, seq_len, num_objects]
        """
        # Project objects to LLM space
        obj_in_llm_space = self.latent_to_text(
            self.text_to_latent(object_features)  # Round-trip for alignment
        )

        # Cross-attention: language queries, objects as keys/values
        grounded, attn_weights = self.cross_attention(
            query=language_tokens,
            key=obj_in_llm_space,
            value=obj_in_llm_space,
            need_weights=True,
        )

        return grounded, attn_weights

    def contrastive_alignment_loss(
        self,
        language_emb: torch.Tensor,
        object_emb: torch.Tensor,
        labels: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Contrastive loss for language-object alignment.

        Similar to CLIP: maximize similarity of matching pairs,
        minimize for non-matching pairs.

        Args:
            language_emb: Language embeddings [B, llm_hidden_dim]
            object_emb: Object embeddings [B, 512]
            labels: Ground-truth matches [B] (if available)

        Returns:
            Contrastive alignment loss
        """
        # Project to common space (manifold)
        lang_latent = self.text_to_latent(language_emb)  # [B, manifold_dim]
        obj_latent = self.object_to_latent(object_emb)  # [B, manifold_dim]

        # Normalize to unit sphere for cosine similarity
        lang_latent = F.normalize(lang_latent, dim=-1)
        obj_latent = F.normalize(obj_latent, dim=-1)

        # Cosine similarity matrix
        logits = (lang_latent @ obj_latent.T) / self.temperature

        # Symmetric contrastive loss (both directions)
        if labels is None:
            # Self-supervised: assume diagonal is correct
            labels = torch.arange(lang_latent.shape[0], device=self.device)

        loss_lang_to_obj = F.cross_entropy(logits, labels)
        loss_obj_to_lang = F.cross_entropy(logits.T, labels)

        return (loss_lang_to_obj + loss_obj_to_lang) / 2

    async def reason_grounded(
        self,
        x_latent: torch.Tensor,
        task_description: str,
        llm_service: Any | None = None,
    ) -> dict[str, Any]:
        """Generate grounded plan from latent state and task.

        Args:
            x_latent: Current manifold state
            task_description: Task in natural language
            llm_service: LLM for generation (optional)

        Returns:
            {
                'plan_text': str,
                'objects': Extracted objects,
                'grounding_quality': float,
            }
        """
        # Extract objects from manifold
        objects = self.extract_objects(x_latent)

        # Generate plan using LLM
        if llm_service:
            try:
                from kagami.core.services.llm.service import TaskType

                # Build prompt with object context
                object_summary = f"Detected {self.num_objects} objects in the environment"

                prompt = f"""Task: {task_description}

Environment context:
- {object_summary}
- Manifold state dimension: {self.manifold_dim}

Generate a step-by-step plan to accomplish this task using the detected objects.
Be specific and actionable.

Plan:"""

                response = await llm_service.generate(
                    prompt=prompt,
                    app_name="grounded_reasoner",
                    task_type=TaskType.PLANNING,
                    max_tokens=300,
                    temperature=0.7,
                )

                plan_text = (
                    response.get("text", "").strip()
                    if isinstance(response, dict)
                    else str(response)
                )

            except Exception as e:
                logger.warning(f"LLM plan generation failed: {e}")
                plan_text = f"Plan for: {task_description} (grounded to {self.num_objects} objects)"
        else:
            plan_text = f"[Grounded plan for: {task_description}]"

        # Compute grounding quality (how well objects explain state)
        grounding_quality = self._compute_grounding_quality(x_latent, objects)

        return {
            "plan_text": plan_text,
            "objects": objects,
            "grounding_quality": grounding_quality,
            "num_objects": self.num_objects,
        }

    def _compute_grounding_quality(
        self,
        x_latent: torch.Tensor,
        objects: torch.Tensor,
    ) -> float:
        """Measure how well objects explain latent state.

        High quality = objects capture most information in x_latent
        """
        # Reconstruction quality
        if x_latent.dim() == 3:
            x_latent = x_latent.mean(dim=1)

        try:
            # Project objects back to latent space
            # Use cross-attention aggregation
            if objects.dim() == 3:
                objects = objects.mean(dim=1)  # Pool objects

            # Compute alignment via cosine similarity
            x_norm = torch.nn.functional.normalize(x_latent, dim=-1)
            obj_norm = torch.nn.functional.normalize(objects, dim=-1)

            # Average cosine similarity
            similarity = (x_norm * obj_norm).sum(dim=-1).mean()
            quality = float(similarity.item())

            # Quality in [0, 1]: high similarity = good grounding
            quality = (quality + 1.0) / 2.0  # Map [-1, 1] to [0, 1]

            return max(0.0, min(1.0, quality))

        except Exception as e:
            logger.debug(f"Grounding quality computation failed: {e}")
            return 0.0  # Poor grounding on computation failure


def create_grounded_reasoner(
    manifold_dim: int = 15,
    llm_hidden_dim: int = 768,
    device: str = "cpu",
) -> GroundedReasoner:
    """Factory function for grounded reasoner.

    Returns:
        GroundedReasoner instance

    Example:
        >>> reasoner = create_grounded_reasoner()
        >>> x = torch.randn(1, 15)  # Manifold state
        >>> result = reasoner.reason_grounded(x, "Click the button")
        >>> print(result['plan_text'])
        >>> print(f"Objects extracted: {result['num_objects']}")
    """
    return GroundedReasoner(
        manifold_dim=manifold_dim,
        llm_hidden_dim=llm_hidden_dim,
        device=device,
    )
