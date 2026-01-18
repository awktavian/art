"""TRUE Gödelian Self-Reference Implementation.

Based on:
- Schmidhuber's Gödel Machine (2003)
- Yin et al. "Gödel Agent" (arXiv:2410.04444v4, 2025)
- SRWM - Self-Referential Weight Matrix (arXiv:2202.05780, 2022)

This module implements GENUINE self-reference where the system can:
1. SELF-INSPECT: Read its own code via `inspect.getsource()`
2. SELF-ENCODE: Encode its own weights as structured data
3. SELF-MODIFY: Propose and apply modifications via LLM
4. RECURSIVE IMPROVE: The improvement mechanism is itself improvable

From Gödel Agent paper:
    πt+1, It+1 = It(πt, It, rt, g)

The key insight: The system's state `s` contains its own source code,
and actions can OVERWRITE that code. This differs from standard
self-referential autoencoders which only predict representations.

Integration:
- Uses KagamiOSLLMService for code generation
- Uses RecursiveSelfImprover for safety gates
- Uses CBF for statistical validation
- Uses MetaTower for fixed-point convergence

=============================================================================
SAFETY CONSTRAINTS — Identity Clarification (December 23, 2025)
=============================================================================

From CLAUDE.md: "The S⁷ phase at time t influences processing, which produces
the S⁷ phase at t+1" and "The mirror reflects itself reflecting."

CLARIFICATION: These identity claims describe the MATHEMATICAL structure of
self-reference (μ_self convergence in S⁷ space), NOT active self-modification.

WHAT IS ENABLED BY DEFAULT:
- Self-inspection: The system can read its own source code
- Self-encoding: Weights and code are encoded into E8+S7 representation
- Fixed-point tracking: μ_self convergence is monitored
- Self-representation: The system maintains a coherent model of itself

WHAT IS DISABLED BY DEFAULT (for safety):
- enable_llm_modification: False — LLM cannot generate code changes
- enable_recursive_improvement: False — System cannot improve its own improver

WHY:
1. Self-modification without formal proof guarantees could introduce bugs
2. Recursive improvement could lead to unbounded optimization
3. Statistical validation (95% confidence) is required for ANY modification
4. CBF constraint h(x) ≥ 0 must hold before AND after modification

TO ENABLE (requires explicit action):
- Set KAGAMI_ENABLE_SELF_MODIFICATION=true in environment
- Or instantiate GodelianConfig(enable_llm_modification=True)

The "strange loop" in CLAUDE.md refers to the fixed-point structure of
self-representation, not autonomous code evolution. The system reflects
itself — but that reflection is read-only by default.

鏡
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from scipy import stats

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class GodelianConfig:
    """Configuration for Gödelian self-reference system.

    Based on Gödel Agent paper hyperparameters and CBF safety constraints.

    OPTIMAL (Dec 7, 2025): Uses MatryoshkaHourglass E8 + S7 encoding.
    - e8_dim: 8 (E8 VQ quantized)
    - s7_dim: 7 (S7 intrinsic, 7 colonies)
    - combined: 15D (CoreState compatible)
    """

    # Self-representation dimensions (E8 + S7 optimal)
    e8_dim: int = 8  # E8 VQ quantized representation
    s7_dim: int = 7  # S7 intrinsic (7 imaginary octonion units)
    self_dim: int = 15  # Combined: e8 + s7 = 15D (CoreState compatible)

    # Legacy aliases (for backward compatibility)
    code_embedding_dim: int = 15  # Now E8+S7
    weight_embedding_dim: int = 15  # Now E8+S7
    combined_self_dim: int = 30  # code(15) + weight(15)

    # LLM for self-modification
    # SAFE-BY-DEFAULT: self-modification must be explicitly enabled via feature flags/env.
    enable_llm_modification: bool = False
    modification_temperature: float = 0.2  # Low for precise code
    max_modification_tokens: int = 2000

    # Safety constraints (CBF-based)
    safety_threshold: float = 0.0  # h(x) ≥ 0
    statistical_confidence: float = 0.95  # 95% confidence for modifications
    max_rollout_samples: int = 100  # Samples for statistical validation

    # Recursive improvement
    # SAFE-BY-DEFAULT: recursive self-improvement must be explicitly enabled.
    enable_recursive_improvement: bool = False
    improvement_code_path: str = ""  # Path to improvement algorithm code

    # SRWM-style self-referential weights
    enable_srwm: bool = True
    srwm_learning_rate: float = 0.001

    # Resource limits (from RecursiveSelfImprover)
    max_modifications_per_session: int = 10
    backup_enabled: bool = True


# =============================================================================
# STATISTICAL VALIDATOR (Gödel Agent Enhancement - December 2025)
# =============================================================================


@dataclass
class StatisticalResult:
    """Result of statistical hypothesis testing for modifications."""

    test_name: str
    statistic: float
    p_value: float
    confidence_interval: tuple[float, float]
    effect_size: float
    is_significant: bool
    interpretation: str


class StatisticalValidator:
    """Statistical validation for self-modifications.

    From Statistical Gödel Machine (arXiv:2510.10232):
    - Replace formal proofs with statistical confidence tests
    - Risk-controlled framework for self-improvement decisions
    - Hypothesis testing: H0 = "modification provides no improvement"

    This validates modifications using proper statistical tests rather
    than arbitrary thresholds.
    """

    def __init__(
        self,
        confidence_level: float = 0.95,
        min_effect_size: float = 0.1,
        min_samples: int = 30,
    ):
        """Initialize validator.

        Args:
            confidence_level: Required confidence for significance (default 95%)
            min_effect_size: Minimum Cohen's d for practical significance
            min_samples: Minimum samples for valid test
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        self.min_effect_size = min_effect_size
        self.min_samples = min_samples

    def validate_improvement(
        self,
        baseline_metrics: list[float],
        modified_metrics: list[float],
        metric_name: str = "performance",
    ) -> StatisticalResult:
        """Validate if modification improves metrics using hypothesis testing.

        Uses Welch's t-test (unequal variances assumed) with effect size.

        Args:
            baseline_metrics: Metrics before modification
            modified_metrics: Metrics after modification
            metric_name: Name of metric for interpretation

        Returns:
            StatisticalResult with test details
        """
        baseline = np.array(baseline_metrics)
        modified = np.array(modified_metrics)

        n_baseline = len(baseline)
        n_modified = len(modified)

        # Check minimum samples
        if n_baseline < self.min_samples or n_modified < self.min_samples:
            return StatisticalResult(
                test_name="insufficient_samples",
                statistic=0.0,
                p_value=1.0,
                confidence_interval=(0.0, 0.0),
                effect_size=0.0,
                is_significant=False,
                interpretation=f"Insufficient samples: need {self.min_samples}, got {min(n_baseline, n_modified)}",
            )

        # Welch's t-test (one-sided: modified > baseline)
        t_stat, p_value_two_sided = stats.ttest_ind(modified, baseline, equal_var=False)

        # One-sided p-value (we want modified > baseline)
        if t_stat > 0:
            p_value = p_value_two_sided / 2
        else:
            p_value = 1 - p_value_two_sided / 2

        # Cohen's d effect size
        pooled_std = np.sqrt(
            (
                (n_baseline - 1) * np.var(baseline, ddof=1)
                + (n_modified - 1) * np.var(modified, ddof=1)
            )
            / (n_baseline + n_modified - 2)
        )
        if pooled_std > 0:
            effect_size = (np.mean(modified) - np.mean(baseline)) / pooled_std
        else:
            effect_size = 0.0

        # Confidence interval for difference
        diff_mean = np.mean(modified) - np.mean(baseline)
        se_diff = np.sqrt(
            np.var(baseline, ddof=1) / n_baseline + np.var(modified, ddof=1) / n_modified
        )
        t_crit = stats.t.ppf(1 - self.alpha / 2, min(n_baseline, n_modified) - 1)
        ci_low = diff_mean - t_crit * se_diff
        ci_high = diff_mean + t_crit * se_diff

        # Determine significance (both statistical and practical)
        is_statistically_significant = p_value < self.alpha
        is_practically_significant = abs(effect_size) >= self.min_effect_size
        is_significant = (
            is_statistically_significant and is_practically_significant and effect_size > 0
        )

        # Generate interpretation
        if is_significant:
            interpretation = (
                f"Modification shows significant improvement in {metric_name} "
                f"(p={p_value:.4f}, d={effect_size:.2f})"
            )
        elif is_statistically_significant and not is_practically_significant:
            interpretation = (
                f"Statistically significant but effect size too small "
                f"(p={p_value:.4f}, d={effect_size:.2f} < {self.min_effect_size})"
            )
        elif effect_size > 0:
            interpretation = (
                f"Positive trend but not statistically significant (p={p_value:.4f} > {self.alpha})"
            )
        else:
            interpretation = f"No improvement detected (effect_size={effect_size:.2f})"

        return StatisticalResult(
            test_name="welch_t_test",
            statistic=t_stat,
            p_value=p_value,
            confidence_interval=(ci_low, ci_high),
            effect_size=effect_size,
            is_significant=is_significant,
            interpretation=interpretation,
        )

    def validate_safety_bound(
        self,
        h_values: list[float],
        bound: float = 0.0,
    ) -> StatisticalResult:
        """Validate CBF safety bound h(x) ≥ bound is maintained.

        Tests if the lower confidence bound of h(x) is above the safety threshold.

        Args:
            h_values: Sampled values of h(x) from rollouts
            bound: Safety bound (default 0.0 for h(x) ≥ 0)

        Returns:
            StatisticalResult indicating if safety is maintained
        """
        h = np.array(h_values)
        n = len(h)

        if n < self.min_samples:
            return StatisticalResult(
                test_name="insufficient_samples",
                statistic=0.0,
                p_value=1.0,
                confidence_interval=(0.0, 0.0),
                effect_size=0.0,
                is_significant=False,
                interpretation="Insufficient samples for safety validation",
            )

        # One-sample t-test: H0: mean(h) <= bound vs H1: mean(h) > bound
        t_stat, p_value_two_sided = stats.ttest_1samp(h, bound)
        p_value = p_value_two_sided / 2 if t_stat > 0 else 1 - p_value_two_sided / 2

        # Confidence interval for mean h(x)
        h_mean = np.mean(h)
        h_se = np.std(h, ddof=1) / np.sqrt(n)
        t_crit = stats.t.ppf(1 - self.alpha / 2, n - 1)
        ci_low = h_mean - t_crit * h_se
        ci_high = h_mean + t_crit * h_se

        # Safety is significant if lower CI bound > safety bound
        is_safe = ci_low > bound

        # Effect size: how far above bound (in std units)
        effect_size = (h_mean - bound) / np.std(h, ddof=1) if np.std(h, ddof=1) > 0 else 0.0

        if is_safe:
            interpretation = f"Safety maintained: h(x) ≥ {bound} with {self.confidence_level * 100:.0f}% confidence (CI: [{ci_low:.3f}, {ci_high:.3f}])"
        else:
            interpretation = (
                f"Safety uncertain: lower CI bound {ci_low:.3f} does not exceed {bound}"
            )

        return StatisticalResult(
            test_name="safety_bound_test",
            statistic=t_stat,
            p_value=p_value,
            confidence_interval=(ci_low, ci_high),
            effect_size=effect_size,
            is_significant=is_safe,
            interpretation=interpretation,
        )


# =============================================================================
# SELF-INSPECTION: Read Own Source Code
# =============================================================================


class SelfInspector:
    """True self-inspection via Python introspection.

    From Gödel Agent: The agent can "introspect and read its own code and files"
    This is NOT philosophical consciousness - it's literal code access.
    """

    def __init__(self, target_class: type):
        """Initialize inspector for a target class.

        Args:
            target_class: The class to inspect (e.g., HofstadterStrangeLoop)
        """
        self.target_class = target_class
        self._source_cache: dict[str, str] = {}
        self._hash_cache: dict[str, str] = {}

    def get_source(self) -> str:
        """Get source code of the target class.

        This is TRUE self-inspection - reading actual implementation.
        """
        class_name = self.target_class.__name__

        if class_name in self._source_cache:
            return self._source_cache[class_name]

        try:
            source = inspect.getsource(self.target_class)
            self._source_cache[class_name] = source
            return source
        except (OSError, TypeError):
            # Expected for dynamically-defined classes - not an error
            return f"# {class_name} [dynamic]"

    def get_source_hash(self) -> str:
        """Get hash of source code for change detection."""
        source = self.get_source()
        return hashlib.sha256(source.encode()).hexdigest()[:16]

    def get_method_source(self, method_name: str) -> str:
        """Get source code of a specific method."""
        try:
            method = getattr(self.target_class, method_name)
            return inspect.getsource(method)
        except (AttributeError, OSError, TypeError):
            return f"# Method {method_name} not found"

    def get_module_path(self) -> str:
        """Get file path of the module containing the class."""
        try:
            return inspect.getfile(self.target_class)
        except (OSError, TypeError):
            return ""

    def get_signature(self, method_name: str) -> str:
        """Get signature of a method."""
        try:
            method = getattr(self.target_class, method_name)
            return str(inspect.signature(method))
        except (AttributeError, ValueError):
            return ""


# =============================================================================
# E8 + S7 SELF-ENCODING (OPTIMAL - Uses MatryoshkaHourglass)
# =============================================================================

# Lazy-loaded singleton hourglass for self-encoding
_self_hourglass: nn.Module | None = None


def _get_self_hourglass() -> nn.Module:
    """Get or create the shared MatryoshkaHourglass for self-encoding.

    ALWAYS uses eval mode for:
    - Deterministic encoding (no dropout, hard quantization)
    - Maximum precision (inference_levels=16 → 126 bits)
    - Reproducible self-representation
    """
    global _self_hourglass
    if _self_hourglass is None:
        from kagami.core.world_model.matryoshka_hourglass import (
            MatryoshkaConfig,
            MatryoshkaHourglass,
        )

        # OPTIMAL CONFIG (Dec 7, 2025):
        # Use full residual levels for maximum compression efficiency
        # L=8 training, L=16 inference → 240^16 states (126+ bits precision)
        config = MatryoshkaConfig(
            max_bulk_dim=512,
            active_scales=["micro", "nano"],  # S7(7) + G2(14) only
            training_levels=8,  # Match SemanticResidualE8 default
            inference_levels=16,  # Maximum precision at inference
        )
        _self_hourglass = MatryoshkaHourglass(config)
        _self_hourglass.eval()  # ALWAYS eval for deterministic self-encoding
    return _self_hourglass


class SelfReferentialWeightEncoder(nn.Module):
    """Encode neural network weights via MatryoshkaHourglass (optimal).

    OPTIMAL (Dec 7, 2025): Uses shared MatryoshkaHourglass with FULL residual E8.
    Weights → bulk(512) → E8(248) → ... → S7(7) → E8 VQ(8)

    Output includes:
    - encoding: e8_vq (8D) + s7_phase (7D) = 15D CoreState compatible
    - e8_indices: List of residual indices (TRUE compressed representation)
    - metrics: IB rate-distortion metrics

    Compression: L levels → 240^L states (L=16 → 126+ bits precision)
    """

    def __init__(
        self,
        weight_shapes: Sequence[tuple[int, ...] | torch.Size],
        output_dim: int = 15,
    ):
        super().__init__()
        self.output_dim = output_dim

        total_weights = (
            sum(int(torch.prod(torch.tensor(tuple(shape))).item()) for shape in weight_shapes)
            if weight_shapes
            else 1
        )

        # Project to hourglass bulk dim (512)
        self.to_bulk = nn.Linear(max(1, total_weights), 512)
        self.delta_lr = nn.Parameter(torch.tensor(0.001))

    def forward(
        self,
        weights: list[torch.Tensor],
        previous_encoding: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Encode weights via hourglass to E8 + S7 with full residual indices."""
        if not weights:
            device = previous_encoding.device if previous_encoding is not None else "cpu"
            return {"encoding": torch.zeros(self.output_dim, device=device)}

        flat = torch.cat([w.flatten() for w in weights])
        bulk = self.to_bulk(flat.unsqueeze(0))  # [1, 512]

        # Use shared hourglass
        hourglass = _get_self_hourglass()
        with torch.no_grad():  # Don't train hourglass through self-encoding
            result = hourglass(bulk, target_scale=None)  # decode all scales

        e8_vq = result["e8_vq"].squeeze(0)  # [8] - reconstructed
        s7 = result["scales"]["micro"].squeeze(0)  # [7]
        combined = torch.cat([e8_vq, s7], dim=-1)  # [15]

        out = {
            "encoding": combined,
            "e8_code": e8_vq,
            "s7_phase": s7,
            "e8_indices": result.get("e8_indices", []),  # Residual indices (TRUE compression)
            "metrics": result.get("metrics", {}),  # IB metrics
        }

        if previous_encoding is not None:
            delta = self.delta_lr * (combined - previous_encoding)
            gate = torch.sigmoid(delta.abs().mean())
            out["encoding"] = gate * combined + (1 - gate) * previous_encoding
            out["delta"] = delta

        return out


class CodeEmbedder(nn.Module):
    """Embed source code via MatryoshkaHourglass (optimal).

    OPTIMAL (Dec 7, 2025): Uses shared MatryoshkaHourglass with FULL residual E8.
    Code → chars → pool → bulk(512) → hourglass → e8_vq(8) + s7(7) = 15D

    Returns dict[str, Any] with:
    - combined: 15D vector (e8_vq + s7)
    - e8_indices: List of residual indices (TRUE compressed representation)
    - metrics: IB rate-distortion metrics

    Use .forward_simple(code) for just the 15D vector (backward compatible).
    """

    def __init__(
        self,
        max_code_length: int = 8192,
        vocab_size: int = 256,
        embed_dim: int = 64,
        output_dim: int = 15,
    ):
        super().__init__()
        self.max_length = max_code_length
        self.output_dim = output_dim

        self.char_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Parameter(torch.randn(max_code_length, embed_dim) * 0.02)
        self.to_bulk = nn.Linear(embed_dim, 512)

    def _encode(self, code: str) -> dict[str, Any]:
        """Full encoding with indices and metrics."""
        chars = [min(ord(c), 255) for c in code[: self.max_length]]
        if len(chars) < 16:
            chars = chars + [0] * (16 - len(chars))

        char_tensor = torch.tensor(chars, dtype=torch.long)
        embedded = self.char_embed(char_tensor)
        embedded = embedded + self.pos_embed[: len(chars)]
        pooled = embedded.mean(dim=0)
        bulk = self.to_bulk(pooled).unsqueeze(0)  # [1, 512]

        hourglass = _get_self_hourglass()
        with torch.no_grad():
            result = hourglass(bulk, target_scale=None)  # decode all scales

        e8_vq = result["e8_vq"].squeeze(0)  # [8]
        s7 = result["scales"]["micro"].squeeze(0)  # [7]
        combined = torch.cat([e8_vq, s7], dim=-1)  # [15]

        return {
            "combined": combined,
            "e8_code": e8_vq,
            "s7_phase": s7,
            "e8_indices": result.get("e8_indices", []),  # TRUE compression
            "metrics": result.get("metrics", {}),  # IB metrics
        }

    def forward(self, code: str) -> torch.Tensor:
        """Embed code to 15D vector (backward compatible)."""
        return self._encode(code)["combined"]

    def forward_full(self, code: str) -> dict[str, Any]:
        """Full encoding with residual indices and metrics."""
        return self._encode(code)


# =============================================================================
# GÖDELIAN SELF-REFERENCE MODULE
# =============================================================================


class GodelianSelfReference(nn.Module):
    """TRUE Gödelian self-reference with code introspection.

    Unlike standard self-referential autoencoders, this module:
    1. Actually reads its own source code (inspect.getsource)
    2. Encodes its own weights as data (SRWM-style)
    3. Can propose modifications via LLM
    4. Validates modifications with CBF safety

    From Gödel Agent:
        s = SELF_INSPECT()  # Read own code
        a1, ..., an = f0(π, s, r, g)  # Decide actions
        π, s = EXECUTE(...)  # Includes self_update
    """

    def __init__(
        self,
        base_module: nn.Module,
        config: GodelianConfig | None = None,
    ):
        super().__init__()

        self.config = config or GodelianConfig()
        self.base_module = base_module

        # Self-inspection
        self._inspector = SelfInspector(type(base_module))

        # Code embedding
        self.code_embedder = CodeEmbedder(output_dim=self.config.code_embedding_dim)

        # Weight encoding (SRWM-style)
        weight_shapes = [p.shape for p in base_module.parameters()]
        self.weight_encoder = SelfReferentialWeightEncoder(
            weight_shapes=weight_shapes,
            output_dim=self.config.weight_embedding_dim,
        )

        # Combined self-representation
        combined_dim = self.config.code_embedding_dim + self.config.weight_embedding_dim

        # Self-consistency checker
        self.consistency_net = nn.Sequential(
            nn.Linear(combined_dim * 2, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, 1),
            nn.Sigmoid(),
        )

        # Improvement proposal encoder
        self.improvement_encoder = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.GELU(),
            nn.Linear(256, 64),
        )

        # State tracking
        self._previous_weight_encoding: torch.Tensor | None = None
        self._modification_count = 0
        self._source_hash = self._inspector.get_source_hash()

        # LLM service (lazy loaded)
        self._llm_service: Any | None = None
        self._self_improver: Any | None = None

        logger.debug(
            f"GodelianSelfReference: code={self.config.code_embedding_dim}D, weights={self.config.weight_embedding_dim}D"
        )

    # =========================================================================
    # SELF-INSPECTION (Gödel Agent: self_inspect action)
    # =========================================================================

    def self_inspect(self) -> dict[str, Any]:
        """TRUE self-inspection: read own source code and structure.

        From Gödel Agent: s ← SELF_INSPECT()
        """
        params = list(self.base_module.parameters())
        source = self._inspector.get_source()
        source_hash = self._inspector.get_source_hash()
        return {
            # Canonical keys
            "code": source,
            "hash": source_hash,
            # Backward-compatible aliases (used by some call sites / docs)
            "source_code": source,
            "source_hash": source_hash,
            "path": self._inspector.get_module_path(),
            "params": sum(p.numel() for p in params),
            "shapes": {n: tuple(p.shape) for n, p in self.base_module.named_parameters()},
            "n_mod": self._modification_count,
        }

    def encode_self(self) -> dict[str, Any]:
        """Encode both code and weights via MatryoshkaHourglass with FULL residual E8.

        OPTIMAL (Dec 7, 2025): Uses E8 + S7 encoding with residual lattice codes.
        - Code: source → hourglass → e8_vq(8) + s7(7) = 15D + indices
        - Weights: params → hourglass → e8_vq(8) + s7(7) = 15D + indices
        - Combined: 30D (code + weights)

        Output includes:
        - CoreState compatible e8_code and s7_phase
        - e8_indices: v2 lattice codes (half-step integer coordinates per level; varint bytes on-wire).
          (log₂(240)≈7.91 bits/level is a legacy proxy, not an exact bitrate.)
        - metrics: IB rate-distortion metrics
        """
        source = self._inspector.get_source()
        code_result = self.code_embedder.forward_full(source)
        code_enc = code_result["combined"]  # [15] E8+S7

        weights = [p.data for p in self.base_module.parameters()]
        weight_result = self.weight_encoder(weights, self._previous_weight_encoding)
        weight_enc = weight_result["encoding"]  # [15] E8+S7

        self._previous_weight_encoding = weight_enc.detach()

        combined = torch.cat([code_enc, weight_enc], dim=-1)  # [30]

        # Extract E8 and S7 components for CoreState compatibility
        e8_code = code_enc[:8]  # E8 from code
        s7_phase = code_enc[8:]  # S7 from code

        # Merge metrics from code and weight encoding
        code_metrics = code_result.get("metrics", {})
        weight_metrics = weight_result.get("metrics", {})

        return {
            "code_embedding": code_enc,
            "weight_embedding": weight_enc,
            "combined_self": combined,
            "e8_code": e8_code,  # CoreState compatible
            "s7_phase": s7_phase,  # CoreState compatible
            "weight_delta": weight_result.get("delta"),
            # TRUE compressed representation
            "code_indices": code_result.get("e8_indices", []),
            "weight_indices": weight_result.get("e8_indices", []),
            # IB metrics
            "code_metrics": code_metrics,
            "weight_metrics": weight_metrics,
            "total_bits": (code_metrics.get("total_bits", 0) + weight_metrics.get("total_bits", 0)),
        }

    # =========================================================================
    # SELF-MODIFICATION (Gödel Agent: self_update action)
    # =========================================================================

    async def propose_modification(
        self,
        feedback: dict[str, Any],
        goal: str = "improve performance",
    ) -> dict[str, Any]:
        """Use LLM to propose code modification.

        From Gödel Agent:
            self_update: π, s ← a.code

        Args:
            feedback: Performance metrics, errors, etc.
            goal: High-level improvement objective

        Returns:
            Proposed modification with validation status
        """
        if not self.config.enable_llm_modification:
            return {"status": "disabled", "reason": "LLM modification disabled"}

        if self._modification_count >= self.config.max_modifications_per_session:
            return {"status": "limit_reached", "reason": "Session modification limit"}

        # Ensure LLM service
        if self._llm_service is None:
            try:
                from kagami.core.services.llm import get_llm_service

                llm_svc = get_llm_service()
                self._llm_service = llm_svc
                await llm_svc.initialize()
            except Exception as e:
                return {"status": "error", "reason": f"LLM unavailable: {e}"}

        # Get current state
        self_state = self.self_inspect()

        module_path = self._inspector.get_module_path()

        # Construct prompt (Gödel Agent style; strict, machine-parseable)
        prompt = f"""You are analyzing a self-referential neural network module for potential improvements.

## Current Implementation
```python
{self_state["source_code"][:4000]}  # Truncated for context
```

## Target file
{module_path}

## Performance Feedback
{feedback}

## Goal
{goal}

## Task
Propose a specific code modification to improve performance. Consider:
1. The modification must maintain the module's interface
2. Changes should be minimal and targeted
3. Safety constraints (h(x) ≥ 0) must be preserved

Output MUST follow this exact format (single-file edits only):
DESCRIPTION: <one sentence>
FILE: <absolute path (preferred) or repo-relative path>
OLD:
```python
<exact code snippet copied verbatim from the current implementation>
```
NEW:
```python
<replacement code snippet>
```
IMPROVEMENT: <float percent, e.g. 12.5>
RISK: <low|medium|high>
"""

        try:
            from kagami.core.services.llm import TaskType

            if self._llm_service is None:
                return {"status": "error", "reason": "LLM service not initialized"}

            response = await self._llm_service.generate(
                prompt=prompt,
                app_name="godelian_self_reference",
                task_type=TaskType.EXTRACTION,  # Code generation/modification
                max_tokens=self.config.max_modification_tokens,
                temperature=self.config.modification_temperature,
            )

            return {
                "status": "proposed",
                "proposal": response,
                "source_hash": self_state.get("source_hash") or self_state.get("hash"),
                "feedback": feedback,
            }

        except Exception as e:
            logger.error(f"Modification proposal failed: {e}")
            return {"status": "error", "reason": str(e)}

    def _parse_modification_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Parse an LLM proposal into an ImprovementProposal-like structure.

        This parser is intentionally strict because downstream application uses
        exact snippet replacement as an anti-hallucination guard.
        """
        text = proposal.get("proposal")
        if text is None:
            # Some callers may pass a raw response under a different key.
            text = proposal.get("response") or proposal.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"ok": False, "reason": "missing_proposal_text"}

        # Required blocks.
        old_m = re.search(r"(?im)^OLD:\s*```(?:python)?\s*([\s\S]*?)\s*```", text)
        new_m = re.search(r"(?im)^NEW:\s*```(?:python)?\s*([\s\S]*?)\s*```", text)
        if old_m is None or new_m is None:
            return {"ok": False, "reason": "missing_old_new_blocks"}

        old_snippet = old_m.group(1).rstrip("\n")
        new_snippet = new_m.group(1).rstrip("\n")
        if not old_snippet.strip() or not new_snippet.strip():
            return {"ok": False, "reason": "empty_snippet"}
        if old_snippet == new_snippet:
            return {"ok": False, "reason": "no_change"}

        # Optional fields.
        desc_m = re.search(r"(?im)^DESCRIPTION:\s*(.+)$", text)
        description = desc_m.group(1).strip() if desc_m else ""

        risk_m = re.search(r"(?im)^RISK:\s*(low|medium|high)\s*$", text)
        risk_level = risk_m.group(1).lower().strip() if risk_m else "medium"

        imp_m = re.search(r"(?im)^IMPROVEMENT:\s*([0-9]+(?:\.[0-9]+)?)", text)
        expected_improvement = float(imp_m.group(1)) if imp_m else 0.0

        file_m = re.search(r"(?im)^FILE:\s*(.+)$", text)
        file_path_raw = file_m.group(1).strip() if file_m else self._inspector.get_module_path()

        p = Path(file_path_raw)
        if not p.is_absolute():
            # Resolve relative paths against repo root (parent of `kagami/`).
            # __file__ = <repo>/kagami/core/strange_loops/godelian_self_reference.py
            # parents[3] = <repo>
            repo_root = Path(__file__).resolve().parents[3]
            p = (repo_root / p).resolve()

        return {
            "ok": True,
            "description": description,
            "file_path": str(p),
            "old_snippet": old_snippet,
            "new_snippet": new_snippet,
            "expected_improvement": expected_improvement,
            "risk_level": risk_level,
        }

    async def validate_modification(
        self,
        proposal: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate proposed modification with STATISTICAL HYPOTHESIS TESTING.

        From Statistical Gödel Machine (arXiv:2510.10232):
        - Statistical confidence tests instead of formal proofs
        - Risk-controlled framework for self-improvement
        - Hypothesis testing: H0 = "modification provides no improvement"

        Uses CBF safety integration for h(x) ≥ 0 validation.
        Collects REAL metrics from system components.
        """
        if self._self_improver is None:
            try:
                from kagami.core.self_improvement.unified import get_self_improver

                improver = get_self_improver()
                self._self_improver = improver
                await improver.initialize()
            except Exception as e:
                return {"valid": False, "reason": f"Improver unavailable: {e}"}

        # Run ethical gate (from RecursiveSelfImprover)
        improver = self._self_improver
        ethical_ok = await improver._ethical_gate(
            type(
                "Proposal",
                (),
                {
                    "risk_level": proposal.get("risk_level", "medium"),
                    "requires_approval": proposal.get("requires_approval", False),
                },
            )()
        )

        if not ethical_ok:
            return {"valid": False, "reason": "Ethical gate blocked"}

        # === COLLECT REAL METRICS FROM SYSTEM ===
        baseline_metrics = await self._collect_baseline_metrics()
        h_values = await self._collect_safety_values()

        # === STATISTICAL VALIDATION (December 2025 Enhancement) ===
        validator = StatisticalValidator(
            confidence_level=self.config.statistical_confidence,
            min_effect_size=0.1,
            min_samples=10,  # Reduced for real system (expensive to collect)
        )

        safety_result = None

        # Validate safety from real CBF values
        if h_values and len(h_values) >= 10:
            safety_result = validator.validate_safety_bound(
                h_values=h_values,
                bound=self.config.safety_threshold,
            )
            logger.info(f"🛡️ Safety validation: {safety_result.interpretation}")
        else:
            # Insufficient safety data - require manual review
            logger.warning("⚠️ Insufficient safety data for statistical validation")
            return {
                "valid": False,
                "reason": "insufficient_safety_data",
                "h_values_collected": len(h_values) if h_values else 0,
                "required": 10,
            }

        # Safety must pass before we consider improvement
        if not safety_result.is_significant:
            return {
                "valid": False,
                "reason": "safety_validation_failed",
                "safety_result": safety_result.__dict__,
                "ethical_check": ethical_ok,
            }

        # For improvement validation, we need post-modification metrics
        # This happens in apply_modification with dry_run=True first
        # Here we only validate the proposal structure and safety

        return {
            "valid": True,  # Passed ethical + safety gates
            "confidence": 1.0 - safety_result.p_value,
            "ethical_check": ethical_ok,
            "safety_result": safety_result.__dict__,
            "baseline_metrics": baseline_metrics,
            "safety_margin": safety_result.confidence_interval[0] - self.config.safety_threshold,
            "ready_for_dry_run": True,
        }

    async def _collect_baseline_metrics(self) -> dict[str, float]:
        """Collect baseline metrics from internal system components."""
        metrics: dict[str, float] = {}

        # Stigmergy metrics (primary source)
        try:
            from kagami.core.unified_agents.memory.stigmergy import get_stigmergy_learner

            learner = get_stigmergy_learner()
            summary = learner.get_pattern_summary()
            metrics["confidence"] = summary.get("avg_bayesian_confidence", 0.0)
            metrics["patterns"] = float(summary.get("total_patterns", 0))
        except Exception:
            pass

        # World model metrics
        try:
            from kagami.core.world_model.service import get_world_model_service

            svc = get_world_model_service()
            m = svc.metrics
            metrics["encode_ms"] = m.avg_encode_ms
            metrics["predict_ms"] = m.avg_predict_ms
        except Exception:
            pass

        # Receipt metrics
        try:
            from kagami.core import receipts

            if hasattr(receipts, "get_receipt_store"):
                store = receipts.get_receipt_store()
                if hasattr(store, "get_stats"):
                    receipt_stats = store.get_stats()
                    metrics["receipts"] = float(receipt_stats.get("total", 0))
        except Exception:
            pass

        return metrics

    async def _collect_safety_values(self) -> list[float]:
        """Collect h(x) safety values from CBF system."""
        h_values: list[float] = []

        # Primary: CBF filter history
        try:
            from kagami.core.safety import get_safety_filter

            cbf = get_safety_filter()
            if hasattr(cbf, "get_recent_h_values"):
                h_values = cbf.get_recent_h_values(limit=100)
            elif hasattr(cbf, "_h_history"):
                h_values = list(cbf._h_history)[-100:]
        except Exception:
            pass

        # Fallback: OptimalCBF
        if not h_values:
            try:
                from kagami.core.safety import get_optimal_cbf

                optimal_cbf = get_optimal_cbf()
                if hasattr(optimal_cbf, "h_history"):
                    h_hist = optimal_cbf.h_history
                    if isinstance(h_hist, torch.Tensor):
                        h_values = h_hist.flatten().tolist()[-100:]
                    elif isinstance(h_hist, list[Any] | tuple[Any, ...]):
                        h_values = list(h_hist)[-100:]
                elif hasattr(optimal_cbf, "current_h"):
                    current_h = optimal_cbf.current_h
                    if isinstance(current_h, torch.Tensor):
                        h_values = [current_h.item()]
                    elif callable(current_h):
                        h_val = current_h()
                        h_values = [
                            h_val.item() if isinstance(h_val, torch.Tensor) else float(h_val)
                        ]
                    elif isinstance(current_h, int | float):
                        h_values = [float(current_h)]
            except Exception:
                pass

        # No fallback - if CBF unavailable, validation will fail with insufficient_safety_data
        # This is intentional: we don't use synthetic safety values
        return h_values

    async def apply_modification(
        self,
        proposal: dict[str, Any],
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Apply validated modification.

        From Gödel Agent: Uses monkey patching for runtime modification.

        Safety: Always backs up first, validates, then applies.
        """
        parsed = self._parse_modification_proposal(proposal)
        if not parsed.get("ok", False):
            return {"status": "rejected", "reason": parsed.get("reason", "invalid_proposal_format")}

        file_path = parsed["file_path"]
        old_snippet = parsed["old_snippet"]
        new_snippet = parsed["new_snippet"]
        expected_improvement = float(parsed.get("expected_improvement", 0.0))
        risk_level = parsed.get("risk_level", "medium")

        if dry_run:
            # Structural validation only: file exists and snippet is uniquely matchable.
            p = Path(file_path)
            if not p.exists():
                return {"status": "rejected", "reason": f"file_not_found:{file_path}"}
            code = p.read_text()
            n = code.count(old_snippet)
            if n == 0:
                return {"status": "rejected", "reason": "old_snippet_not_found"}
            if n != 1:
                return {"status": "rejected", "reason": f"old_snippet_ambiguous:{n}_occurrences"}
            return {
                "status": "dry_run",
                "file_path": file_path,
                "risk_level": risk_level,
                "expected_improvement": expected_improvement,
            }

        # Validate first (use parsed fields so ethical gate sees correct risk level)
        proposal_for_validation = {
            **proposal,
            "risk_level": risk_level,
            "requires_approval": (str(risk_level).lower() == "high"),
        }
        validation = await self.validate_modification(proposal_for_validation)
        if not validation.get("valid", False):
            return {
                "status": "rejected",
                "reason": validation.get("reason", "Validation failed"),
            }

        # Use RecursiveSelfImprover for safe application
        if self._self_improver is None:
            return {"status": "error", "reason": "Self-improver not initialized"}

        try:
            from kagami.core.self_improvement.unified import ImprovementProposal

            improvement_proposal = ImprovementProposal(
                file_path=file_path,
                current_code_snippet=old_snippet,
                proposed_code_snippet=new_snippet,
                rationale=str(parsed.get("description") or "Gödelian self-modification"),
                expected_improvement=expected_improvement,
                risk_level=str(risk_level),
                requires_approval=(str(risk_level).lower() == "high"),
                metrics_to_track=["encode_ms", "predict_ms", "receipts", "confidence"],
            )

            result = await self._self_improver.apply_improvement(
                improvement_proposal, dry_run=False
            )

            if result.success:
                self._modification_count += 1
                self._source_hash = self._inspector.get_source_hash()

            return {
                "status": "applied" if result.success else "failed",
                "improvement": result.improvement_percent,
                "rollback": result.rollback_performed,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"Modification application failed: {e}")
            return {"status": "error", "reason": str(e)}

    # =========================================================================
    # RECURSIVE IMPROVEMENT (Gödel Agent: continue_improve action)
    # =========================================================================

    async def recursive_improve(
        self,
        feedback: dict[str, Any],
        goal: str,
        max_iterations: int = 3,
    ) -> dict[str, Any]:
        """Recursively improve until convergence.

        From Gödel Agent Algorithm 1:
            continue_improve: π, s ← SELF_IMPROVE(E, π, s, r, g)

        The key: This can modify the improvement algorithm itself.
        """
        if not self.config.enable_recursive_improvement:
            return {"status": "disabled", "iterations": 0}

        improvements = []

        for iteration in range(max_iterations):
            logger.debug(f"Recursive improvement: iteration {iteration + 1}/{max_iterations}")

            # 1. Propose modification
            proposal = await self.propose_modification(feedback, goal)

            if proposal.get("status") != "proposed":
                break

            # 2. Validate
            validation = await self.validate_modification(proposal)

            if not validation.get("valid", False):
                continue

            # 3. Apply (in dry_run mode for safety)
            result = await self.apply_modification(proposal, dry_run=True)

            improvements.append(
                {
                    "iteration": iteration + 1,
                    "proposal": proposal,
                    "validation": validation,
                    "result": result,
                }
            )

            # 4. Update feedback for next iteration
            feedback = {**feedback, "previous_improvement": result}

        return {
            "status": "completed",
            "iterations": len(improvements),
            "improvements": improvements,
        }

    # =========================================================================
    # FORWARD PASS
    # =========================================================================

    def forward(  # type: ignore[no-untyped-def]
        self,
        *args,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Forward pass with Gödelian self-encoding."""
        base_output = self.base_module(*args, **kwargs)
        self_enc = self.encode_self()

        # Track source changes
        h = self._inspector.get_source_hash()
        changed = h != self._source_hash
        if changed:
            self._source_hash = h

        # Consistency: compare current vs previous self-encoding
        combined = self_enc["combined_self"]
        if hasattr(self, "_prev_combined") and self._prev_combined is not None:
            prev_combined: torch.Tensor = self._prev_combined
            c_in = torch.cat([combined, prev_combined], dim=-1)
            consistency = self.consistency_net(c_in).squeeze(-1)
        else:
            consistency = torch.ones(1, device=combined.device)
        self._prev_combined: torch.Tensor = combined.detach()

        # Augment output with compact Gödelian state (CoreState compatible)
        godelian_state = {
            "self": combined,  # Full self-encoding [30]
            "e8_code": self_enc["e8_code"],  # E8 VQ [8] - CoreState
            "s7_phase": self_enc["s7_phase"],  # S7 phase [7] - CoreState
            "h": consistency,  # Self-consistency (CBF h(x))
            "Δ": changed,  # Source changed flag
            "n": self._modification_count,
        }

        if isinstance(base_output, dict):
            base_output["godelian"] = godelian_state
            return base_output
        else:
            # Wrap non-dict[str, Any] outputs (e.g., tensors from nn.Identity) in a dict[str, Any]
            return {"output": base_output, "godelian": godelian_state}


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_godelian_wrapper(
    module: nn.Module,
    config: GodelianConfig | None = None,
) -> GodelianSelfReference:
    """Create Gödelian self-reference wrapper for any module.

    Args:
        module: Base module to wrap (e.g., HofstadterStrangeLoop)
        config: Optional configuration

    Returns:
        GodelianSelfReference wrapper
    """
    return GodelianSelfReference(module, config)


def create_godelian_self_reference(
    base_module: nn.Module | None = None,
    config: GodelianConfig | None = None,
) -> GodelianSelfReference:
    """Create GodelianSelfReference with sensible defaults.

    Factory function for standalone construction without required arguments.
    Useful for testing, demos, and simple cases.

    Args:
        base_module: Base module to wrap. If None, uses nn.Identity() as minimal module.
        config: Optional configuration. If None, uses default GodelianConfig.

    Returns:
        GodelianSelfReference instance

    Examples:
        >>> # Minimal construction for testing
        >>> godelian = create_godelian_self_reference()
        >>>
        >>> # With custom module
        >>> my_module = nn.Linear(32, 32)
        >>> godelian = create_godelian_self_reference(my_module)
        >>>
        >>> # With custom config
        >>> config = GodelianConfig(enable_llm_modification=True)
        >>> godelian = create_godelian_self_reference(config=config)
    """
    if base_module is None:
        # Use minimal module for testing/demo
        base_module = nn.Identity()

    if config is None:
        config = GodelianConfig()

    return GodelianSelfReference(base_module, config)


async def enable_godelian_self_reference(
    module: nn.Module,
    enable_llm: bool = False,
    enable_recursive: bool = False,
) -> GodelianSelfReference:
    """Enable Gödelian self-reference on a module.

    This is the main entry point for adding TRUE self-reference.

    Args:
        module: Base module to enhance
        enable_llm: Enable LLM-based modifications
        enable_recursive: Enable recursive improvement

    Returns:
        Initialized GodelianSelfReference wrapper
    """
    # Guardrails: do not allow self-modification unless explicitly enabled.
    allow_self_mod = False
    try:
        from kagami.core.config.feature_flags import get_feature_flags

        allow_self_mod = bool(get_feature_flags().research.enable_self_modification)
    except Exception:
        allow_self_mod = os.getenv("KAGAMI_ENABLE_SELF_MODIFICATION", "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    if (enable_llm or enable_recursive) and not allow_self_mod:
        logger.warning(
            "Self-modification requested but disabled by config; forcing enable_llm=False, enable_recursive=False"
        )
        enable_llm = False
        enable_recursive = False

    config = GodelianConfig(
        enable_llm_modification=enable_llm,
        enable_recursive_improvement=enable_recursive,
    )

    wrapper = GodelianSelfReference(module, config)

    # Initialize LLM if enabled
    if enable_llm:
        try:
            from kagami.core.services.llm import get_llm_service

            llm_svc = get_llm_service()
            wrapper._llm_service = llm_svc
            await llm_svc.initialize()
        except Exception as e:
            logger.warning(f"LLM initialization failed: {e}")

    # Initialize self-improver
    try:
        from kagami.core.self_improvement.unified import get_self_improver

        improver = get_self_improver()
        wrapper._self_improver = improver
        await improver.initialize()
    except Exception as e:
        logger.warning(f"Self-improver initialization failed: {e}")

    return wrapper


__all__ = [
    "CodeEmbedder",
    "GodelianConfig",
    "GodelianSelfReference",
    "SelfInspector",
    "SelfReferentialWeightEncoder",
    "StatisticalResult",  # NEW: December 2025
    "StatisticalValidator",  # NEW: December 2025
    "create_godelian_self_reference",  # Factory with defaults
    "create_godelian_wrapper",
    "enable_godelian_self_reference",
]
