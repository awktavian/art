"""Fano-Constrained Attention Meta-Learner for Colony Collaboration.

This module implements a meta-learner that uses the Fano plane structure as an
inductive bias for colony attention. Instead of allowing all 7×7 = 49 colony pairs
to attend to each other, only the 21 pairs on Fano lines can form connections.

KEY INSIGHT:
    Standard multi-head attention: 49 edges (fully connected)
    Fano-constrained attention:    21 edges (only Fano connections)

This provides mathematical structure to colony collaboration:
- Fano lines encode proven composition patterns (e.g., Spark × Forge = Flow)
- Attention weights learn which lines are important for each task
- MAML enables rapid adaptation to new task types

ARCHITECTURE:
    1. Task encoder: task description → task embedding
    2. Fano attention: colony outputs attend only along Fano lines
    3. Line importance predictor: task → which Fano lines matter
    4. MAML meta-training: learn good initialization for fast adaptation

References:
- Fano plane: 7 points, 7 lines, exactly 21 point pairs
- MAML: Finn et al. (2017) "Model-Agnostic Meta-Learning"
- Octonion multiplication table provides initialization prior

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.fano_plane import (
    FANO_SIGNS,
    get_fano_lines_zero_indexed,
)

logger = logging.getLogger(__name__)


class FanoMetaLearner(nn.Module):
    """Meta-learner for Fano line selection using constrained attention.

    This module learns:
    1. Which Fano lines are relevant for different task types
    2. How to weight colony outputs along each Fano line
    3. Task-specific attention patterns (via MAML)

    The Fano structure provides strong inductive bias:
    - Only 21 of 49 possible colony pairs can interact
    - These 21 pairs encode proven composition patterns
    - Initialized from octonion multiplication table

    Example:
        meta_learner = FanoMetaLearner(d_model=256, num_heads=7)

        # During meta-training
        colony_outputs = torch.randn(batch, 7, 256)
        task_emb = torch.randn(batch, 256)
        fused = meta_learner(colony_outputs, task_emb)

        # MAML meta-training
        support_tasks = [...]
        query_tasks = [...]
        meta_loss = meta_learner.meta_train_step(support_tasks, query_tasks)

        # Task-specific line selection
        best_line, confidence = meta_learner.select_best_line(task_emb)
    """

    def __init__(
        self,
        d_model: int = 256,
        num_heads: int = 7,  # One head per Fano line
        num_colonies: int = 7,
        dropout: float = 0.1,
        inner_lr: float = 0.01,
        device: str | None = None,
    ) -> None:
        """Initialize Fano-constrained meta-learner.

        Args:
            d_model: Dimension of colony outputs and task embeddings
            num_heads: Number of attention heads (should be 7 for Fano lines)
            num_colonies: Number of colonies (should be 7)
            dropout: Dropout probability
            inner_lr: Learning rate for MAML inner loop
            device: Device for computation (None = auto-detect)
        """
        super().__init__()

        self.d_model = d_model
        self.num_heads = num_heads
        self.num_colonies = num_colonies
        self.dropout = dropout
        self.inner_lr = inner_lr

        # Device detection
        if device is None:
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")
        else:
            self.device = torch.device(device)

        # Fano line structure (0-indexed for tensor operations)
        self.fano_lines = get_fano_lines_zero_indexed()  # 7 lines, 3 colonies each

        # Task encoder: task description → task embedding
        self.task_encoder = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, d_model),
        )

        # Per-line attention weights (initialized from octonion multiplication table)
        # Shape: [7 lines, 3 colonies per line]
        # These are the meta-learned parameters that MAML will adapt
        self.fano_attention_weights = nn.Parameter(self._initialize_from_octonion_table())

        # Line importance predictor: task → [7] line weights
        # Learns which Fano lines are most relevant for each task type
        self.line_predictor = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model // 2, 7),
        )

        # Output projection: fused representation → final output
        self.output_proj = nn.Linear(d_model, d_model)

        self.dropout_layer = nn.Dropout(dropout)

        # MAML tracking
        self._meta_iterations = 0
        self._tasks_trained = 0

        self.to(self.device)

        logger.info(
            f"✅ FanoMetaLearner initialized: "
            f"d_model={d_model}, heads={num_heads}, "
            f"device={self.device}, inner_lr={inner_lr}"
        )

    def _initialize_from_octonion_table(self) -> torch.Tensor:
        """Initialize attention weights from octonion multiplication signs.

        The Fano line (i,j,k) encodes the multiplication: e_i × e_j = ε * e_k
        where ε ∈ {+1, -1} is the sign from the multiplication table.

        We use these signs as initialization priors:
        - Positive sign → positive weight (reinforcing)
        - Negative sign → negative weight (competing)
        - Small random noise for symmetry breaking

        Returns:
            weights: [7, 3] tensor of initial attention weights
        """
        weights = torch.zeros(7, 3)

        for line_idx, (i, j, k) in enumerate(self.fano_lines):
            # Get multiplication signs for this Fano line
            # Note: fano_lines are 0-indexed, FANO_SIGNS uses 1-indexed
            i1, j1, k1 = i + 1, j + 1, k + 1

            # Get signs for the three cyclic products on this line:
            # e_i × e_j = ε₁ * e_k
            # e_j × e_k = ε₂ * e_i
            # e_k × e_i = ε₃ * e_j
            sign_ij = FANO_SIGNS.get((i1, j1), (None, 1.0))[1]
            sign_jk = FANO_SIGNS.get((j1, k1), (None, 1.0))[1]
            sign_ki = FANO_SIGNS.get((k1, i1), (None, 1.0))[1]

            # Initialize weights with signs + small random noise
            # The signs provide structure, noise breaks symmetry
            weights[line_idx, 0] = sign_ij + 0.01 * torch.randn(1).item()
            weights[line_idx, 1] = sign_jk + 0.01 * torch.randn(1).item()
            weights[line_idx, 2] = sign_ki + 0.01 * torch.randn(1).item()

        return weights

    def forward(
        self,
        colony_outputs: torch.Tensor,  # [batch, 7, d_model]
        task_embedding: torch.Tensor,  # [batch, d_model]
        mask: torch.Tensor | None = None,  # [batch, 7, 7] optional mask
    ) -> torch.Tensor:
        """Compute Fano-constrained attention over colony outputs.

        This is the core forward pass:
        1. Encode task to get task-specific representation
        2. Predict which Fano lines are important for this task
        3. For each Fano line, compute weighted combination of 3 colonies
        4. Weight line outputs by task-specific importance
        5. Project to final output

        Args:
            colony_outputs: Outputs from 7 colonies [batch, 7, d_model]
            task_embedding: Embedding of current task [batch, d_model]
            mask: Optional mask for colony availability [batch, 7, 7]

        Returns:
            fused_output: Task-specific fusion of colony outputs [batch, d_model]
        """
        colony_outputs.shape[0]

        # Encode task
        task_enc = self.task_encoder(task_embedding)  # [batch, d_model]

        # Predict line importance for this task
        line_logits = self.line_predictor(task_enc)  # [batch, 7]
        line_weights = F.softmax(line_logits, dim=-1)  # [batch, 7]

        # Compute attention for each Fano line

        line_outputs: list[torch.Tensor] = []
        for line_idx, (i, j, k) in enumerate(self.fano_lines):
            # Get colonies on this line
            out_i = colony_outputs[:, i, :]  # [batch, d_model]
            out_j = colony_outputs[:, j, :]  # [batch, d_model]
            out_k = colony_outputs[:, k, :]  # [batch, d_model]

            # Fano-specific attention weights (learned via MAML)
            w = F.softmax(self.fano_attention_weights[line_idx], dim=0)  # [3]

            # Weighted combination of the 3 colonies on this line
            line_out = w[0] * out_i + w[1] * out_j + w[2] * out_k
            line_outputs.append(line_out)

        # Stack line outputs
        line_outputs_stacked = torch.stack(line_outputs, dim=1)  # [batch, 7, d_model]

        # Weight by task-specific line importance
        fused = (line_outputs_stacked * line_weights.unsqueeze(-1)).sum(dim=1)  # [batch, d_model]

        # Apply dropout and output projection
        fused = self.dropout_layer(fused)
        fused = self.output_proj(fused)

        output_tensor: torch.Tensor = fused
        return output_tensor

    def meta_train_step(
        self,
        support_tasks: list[dict[str, Any]],
        query_tasks: list[dict[str, Any]],
        num_inner_steps: int = 5,
    ) -> torch.Tensor:
        """MAML inner loop: adapt to support set[Any], test on query set[Any].

        This implements the core MAML algorithm:
        1. Clone current parameters
        2. Adapt on support set[Any] (few gradient steps)
        3. Evaluate on query set[Any]
        4. Backpropagate through the adaptation process

        Args:
            support_tasks: List of support examples
                Each task: {"colony_outputs": [batch, 7, d], "task_emb": [batch, d], "target": [batch, d]}
            query_tasks: List of query examples (same format)
            num_inner_steps: Number of gradient steps for adaptation

        Returns:
            meta_loss: Loss after adaptation (to be minimized)
        """
        # Track losses
        support_loss_val: torch.Tensor
        query_loss_val: torch.Tensor

        # Inner loop: adapt on support set[Any]
        # We need to track gradients through the adaptation process
        adapted_weights = self.fano_attention_weights.clone()

        for _ in range(num_inner_steps):
            support_loss_val = torch.tensor(0.0, device=self.device, requires_grad=True)

            for task in support_tasks:
                # Forward pass with current adapted weights
                pred = self._forward_with_weights(
                    task["colony_outputs"],
                    task["task_emb"],
                    adapted_weights,
                )
                support_loss_val = support_loss_val + F.mse_loss(pred, task["target"])

            support_loss_val = support_loss_val / len(support_tasks)

            # Gradient descent on weights (inner loop)
            # create_graph=True to enable second-order gradients (MAML requirement)
            grad = torch.autograd.grad(support_loss_val, adapted_weights, create_graph=True)[0]
            adapted_weights = adapted_weights - self.inner_lr * grad

        # Outer loop: evaluate on query set[Any] with adapted weights
        query_loss_val = torch.tensor(0.0, device=self.device, requires_grad=True)
        for task in query_tasks:
            pred = self._forward_with_weights(
                task["colony_outputs"],
                task["task_emb"],
                adapted_weights,
            )
            query_loss_val = query_loss_val + F.mse_loss(pred, task["target"])

        query_loss_val = query_loss_val / len(query_tasks)

        self._tasks_trained += len(support_tasks) + len(query_tasks)
        self._meta_iterations += 1

        if self._meta_iterations % 10 == 0:
            logger.info(
                f"MAML meta-iteration {self._meta_iterations}: "
                f"query_loss={query_loss_val.item():.4f}"
            )

        return query_loss_val

    def _forward_with_weights(
        self,
        colony_outputs: torch.Tensor,
        task_embedding: torch.Tensor,
        weights: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass with explicit attention weights (for MAML adaptation).

        This is like the normal forward pass but uses provided weights instead
        of self.fano_attention_weights. Needed for MAML inner loop.

        Args:
            colony_outputs: [batch, 7, d_model]
            task_embedding: [batch, d_model]
            weights: [7, 3] Fano attention weights to use

        Returns:
            output: [batch, d_model]
        """
        colony_outputs.shape[0]

        # Encode task
        task_enc = self.task_encoder(task_embedding)

        # Predict line importance
        line_logits = self.line_predictor(task_enc)
        line_weights = F.softmax(line_logits, dim=-1)

        # Compute attention for each Fano line with provided weights
        line_outputs = []
        for line_idx, (i, j, k) in enumerate(self.fano_lines):
            out_i = colony_outputs[:, i, :]
            out_j = colony_outputs[:, j, :]
            out_k = colony_outputs[:, k, :]

            # Use provided weights instead of self.fano_attention_weights
            w = F.softmax(weights[line_idx], dim=0)

            line_out = w[0] * out_i + w[1] * out_j + w[2] * out_k
            line_outputs.append(line_out)

        line_outputs_stacked_adapted = torch.stack(line_outputs, dim=1)
        fused = (line_outputs_stacked_adapted * line_weights.unsqueeze(-1)).sum(dim=1)
        fused = self.dropout_layer(fused)
        output = self.output_proj(fused)

        output_final: torch.Tensor = output
        return output_final

    def select_best_line(
        self,
        task_embedding: torch.Tensor,  # [batch, d_model] or [d_model]
    ) -> tuple[int, float]:
        """Select which Fano line is most relevant for a task.

        This can be used for task routing:
        - Identify which 3 colonies should collaborate
        - Predict which composition pattern will be most effective

        Args:
            task_embedding: Task representation [batch, d_model] or [d_model]

        Returns:
            line_idx: Index of best Fano line (0-6)
            confidence: Softmax probability for that line
        """
        # Handle both batched and unbatched inputs
        if task_embedding.dim() == 1:
            task_embedding = task_embedding.unsqueeze(0)

        task_enc = self.task_encoder(task_embedding)
        line_logits = self.line_predictor(task_enc)
        line_probs = F.softmax(line_logits, dim=-1)

        best_line = line_probs.argmax(dim=-1)
        best_prob = line_probs.max(dim=-1)[0]

        # Return scalar values (take first item if batched)
        line_idx_int: int = int(best_line[0].item())
        confidence_float: float = float(best_prob[0].item())
        return line_idx_int, confidence_float

    def get_attention_matrix(self) -> torch.Tensor:
        """Get 7×7 attention matrix showing Fano constraints.

        This visualizes the sparse attention structure:
        - Non-zero entries only for colony pairs on Fano lines
        - Zero entries for non-connected pairs
        - Shows which 21 of 49 possible connections are active

        Returns:
            attention: [7, 7] Matrix with non-zero only on Fano connections
        """
        attention = torch.zeros(7, 7, device=self.device)

        for line_idx, (i, j, k) in enumerate(self.fano_lines):
            # Get normalized weights for this line
            w = F.softmax(self.fano_attention_weights[line_idx], dim=0)

            # Bidirectional connections on Fano line
            # (i,j), (j,k), (k,i) and their transposes
            attention[i, j] = w[0]
            attention[j, i] = w[0]
            attention[j, k] = w[1]
            attention[k, j] = w[1]
            attention[k, i] = w[2]
            attention[i, k] = w[2]

        return attention

    def get_line_info(self, line_idx: int) -> dict[str, Any]:
        """Get information about a specific Fano line.

        Useful for debugging and visualization.

        Args:
            line_idx: Index of Fano line (0-6)

        Returns:
            info: Dictionary with line information
        """
        if not 0 <= line_idx < 7:
            raise ValueError(f"Line index must be 0-6, got {line_idx}")

        i, j, k = self.fano_lines[line_idx]
        i1, j1, k1 = i + 1, j + 1, k + 1  # Convert to 1-indexed

        # Get multiplication structure
        sign_ij = FANO_SIGNS.get((i1, j1), (None, 1.0))[1]
        sign_jk = FANO_SIGNS.get((j1, k1), (None, 1.0))[1]
        sign_ki = FANO_SIGNS.get((k1, i1), (None, 1.0))[1]

        # Get learned weights
        weights = F.softmax(self.fano_attention_weights[line_idx], dim=0)

        return {
            "line_idx": line_idx,
            "colonies": (i, j, k),
            "multiplication_signs": {
                f"e_{i1} × e_{j1}": f"{'+' if sign_ij > 0 else '-'}e_{k1}",
                f"e_{j1} × e_{k1}": f"{'+' if sign_jk > 0 else '-'}e_{i1}",
                f"e_{k1} × e_{i1}": f"{'+' if sign_ki > 0 else '-'}e_{j1}",
            },
            "learned_weights": weights.detach().cpu().tolist(),
        }

    def get_task_line_importance(
        self,
        task_embedding: torch.Tensor,  # [batch, d_model] or [d_model]
    ) -> torch.Tensor:
        """Get importance scores for all Fano lines given a task.

        Args:
            task_embedding: Task representation

        Returns:
            importance: [7] tensor of line importance scores
        """
        if task_embedding.dim() == 1:
            task_embedding = task_embedding.unsqueeze(0)

        task_enc = self.task_encoder(task_embedding)
        line_logits = self.line_predictor(task_enc)
        line_probs = F.softmax(line_logits, dim=-1)

        return line_probs.squeeze(0)

    def save_checkpoint(self, path: str) -> None:
        """Save meta-learned model checkpoint.

        Args:
            path: Path to save checkpoint
        """
        checkpoint = {
            "model_state": self.state_dict(),
            "meta_iterations": self._meta_iterations,
            "tasks_trained": self._tasks_trained,
            "config": {
                "d_model": self.d_model,
                "num_heads": self.num_heads,
                "num_colonies": self.num_colonies,
                "dropout": self.dropout,
                "inner_lr": self.inner_lr,
            },
        }
        torch.save(checkpoint, path)
        logger.info(
            f"💾 FanoMetaLearner checkpoint saved to {path} ({self._tasks_trained} tasks trained)"
        )

    def load_checkpoint(self, path: str) -> None:
        """Load meta-learned model checkpoint.

        Args:
            path: Path to load checkpoint from

        Security:
            Uses weights_only=False to load non-tensor checkpoint metadata
            (meta_iterations, tasks_trained counters).
            ONLY use with checkpoints from trusted sources.
            Malicious checkpoints can execute arbitrary code during deserialization.
        """
        # SECURITY: weights_only=False allows loading metadata fields
        # Only use with checkpoints from trusted sources
        logger.debug(f"Loading FanoMetaLearner checkpoint from {path} (weights_only=False)")
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)  # nosec B614
        self.load_state_dict(checkpoint["model_state"])
        self._meta_iterations = checkpoint.get("meta_iterations", 0)
        self._tasks_trained = checkpoint.get("tasks_trained", 0)
        logger.info(f"📂 FanoMetaLearner loaded from {path} ({self._tasks_trained} tasks trained)")


def visualize_fano_structure(meta_learner: FanoMetaLearner) -> str:
    """Generate ASCII visualization of Fano attention structure.

    Args:
        meta_learner: Trained FanoMetaLearner instance

    Returns:
        visualization: ASCII art showing Fano line structure
    """
    attention = meta_learner.get_attention_matrix()

    lines = ["Fano Attention Matrix (7×7, only 21 of 49 entries non-zero):", ""]

    # Header
    lines.append("     " + "  ".join(f"c{i}" for i in range(7)))
    lines.append("   " + "-" * 30)

    # Matrix rows
    for i in range(7):
        row_str = f"c{i} |"
        for j in range(7):
            val = attention[i, j].item()
            if abs(val) < 1e-6:
                row_str += "  . "
            else:
                row_str += f" {val:4.2f}"
        lines.append(row_str)

    lines.append("")
    lines.append("Legend:")
    lines.append("  . = no connection (not on any Fano line)")
    lines.append("  # = connection weight (on a Fano line)")

    return "\n".join(lines)


__all__ = [
    "FanoMetaLearner",
    "visualize_fano_structure",
]
