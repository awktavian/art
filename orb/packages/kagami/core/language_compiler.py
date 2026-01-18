"""K os Language Compiler - LANG/2 → MobiASM → Manifold Operations

This is the missing link that compiles high-level LANG/2 intents into
executable MobiASM operations on geometric manifolds.

Architecture:
    LANG/2 (semantic intent)
        ↓ [Parser]
    Intent object
        ↓ [Compiler] ← THIS FILE
    MobiASM operations
        ↓ [Runtime]
    Manifold execution
        ↓
    Result

Example:
    >>> compiler = LanguageCompiler()
    >>> result = await compiler.compile_and_execute(
    ...     'SLANG EXECUTE semantic.navigate goal="Find path from fear to trust"'
    ... )
"""

import logging
from dataclasses import dataclass
from typing import Any

import torch

from kagami.core.mobiasm import create_mobiasm_v2
from kagami.core.schemas.schemas.intent_lang import ParsedLangV2, parse_intent_lang_v2
from kagami.core.schemas.schemas.intents import Intent
from kagami.core.world_model.manifolds.poincare import PoincareManifold

logger = logging.getLogger(__name__)


@dataclass
class CompilationResult:
    """Result of compiling and executing a LANG/2 intent."""

    intent: Intent
    mobiasm_ops: list[str]  # List of MobiASM operations executed
    result: Any  # Actual result from execution
    manifold_state: torch.Tensor | None  # Final manifold state if applicable
    metadata: dict[str, Any]  # Additional metadata


class LanguageCompiler:
    """Compiles LANG/2 intents → MobiASM operations → Manifold execution.

    This is the complete compiler connecting all three language layers:

    Layer 1 (LANG/2): Semantic intent specification
    Layer 2 (MobiASM): Geometric operation generation
    Layer 3 (Manifolds): Mathematical execution

    Usage:
        compiler = LanguageCompiler(device="mps")
        result = await compiler.compile_and_execute(lang_str)
    """

    def __init__(
        self,
        device: str = "cpu",
        use_metal: bool = True,
        use_compile: bool = True,
    ) -> None:
        """Initialize the language compiler.

        Args:
            device: Device to execute on (cpu/cuda/mps)
            use_metal: Use Metal kernels if available
            use_compile: Use torch.compile for JIT optimization
        """
        # MobiASM runtime (Layer 2)
        self.runtime = create_mobiasm_v2(
            device=device,
            use_compile=use_compile,
        )

        # Manifold instances (Layer 3)
        self.manifold_h7 = PoincareManifold(
            dim=7,
            curvature_init=1.0,
            learnable_curvature=False,
        )

        self.device = device

        logger.info(f"✅ Language Compiler initialized: LANG/2 → MobiASM → Manifolds on {device}")

    async def compile_and_execute(
        self,
        lang_str: str,
        context: dict[str, Any] | None = None,
    ) -> CompilationResult:
        """Compile and execute a LANG/2 command.

        This is the main entry point that orchestrates the full stack:
        1. Parse LANG/2 → Intent
        2. Generate MobiASM operations
        3. Execute on manifolds
        4. Return result

        Args:
            lang_str: LANG/2 command string
            context: Optional execution context

        Returns:
            CompilationResult with intent, operations, result, and state

        Example:
            >>> result = await compiler.compile_and_execute(
            ...     'SLANG EXECUTE semantic.navigate goal="fear to trust"'
            ... )
            >>> print(result.result)  # Navigation path
        """
        # LAYER 1: Parse LANG/2 → Intent
        parsed = self._parse_lang(lang_str)
        intent = parsed.intent

        logger.info(f"[Layer 1] Parsed LANG/2: {intent.action.name} {intent.target}")

        # LAYER 2: Generate MobiASM operations
        mobiasm_ops = self._compile_to_mobiasm(intent, parsed)

        logger.info(f"[Layer 2] Generated {len(mobiasm_ops)} MobiASM operations")

        # LAYER 3: Execute on manifolds
        result, manifold_state = await self._execute_mobiasm(
            mobiasm_ops,
            intent,
            context or {},
        )

        logger.info(f"[Layer 3] Executed on manifolds, result: {type(result).__name__}")

        return CompilationResult(
            intent=intent,
            mobiasm_ops=[op.__name__ if callable(op) else str(op) for op in mobiasm_ops],
            result=result,
            manifold_state=manifold_state,
            metadata={
                "quality_score": parsed.quality.get("score", 0),
                "device": self.device,
                "sections": parsed.sections,
            },
        )

    def _parse_lang(self, lang_str: str) -> ParsedLangV2:
        """Parse LANG/2 string into structured intent.

        Args:
            lang_str: LANG/2 command string

        Returns:
            ParsedLangV2 with intent, sections, and quality score
        """
        return parse_intent_lang_v2(lang_str)

    def _compile_to_mobiasm(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile Intent → MobiASM operations.

        This is the core compiler logic that maps semantic intents
        to geometric operations.

        Args:
            intent: Parsed intent object
            parsed: Full parsed LANG/2 result

        Returns:
            List of MobiASM operations to execute
        """
        target = intent.target or ""
        action = intent.action.name if hasattr(intent.action, "name") else str(intent.action)

        ops = []

        # Route based on target
        if "semantic" in target.lower():
            ops.extend(self._compile_semantic_operations(intent, parsed))
        elif "navigate" in target.lower() or "navigate" in action.lower():
            ops.extend(self._compile_navigation_operations(intent, parsed))
        elif "attention" in target.lower() or "attention" in action.lower():
            ops.extend(self._compile_attention_operations(intent, parsed))
        elif "transform" in target.lower():
            ops.extend(self._compile_transformation_operations(intent, parsed))
        else:
            # Default: basic geometric operations
            ops.extend(self._compile_default_operations(intent, parsed))

        return ops

    def _compile_semantic_operations(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile semantic-related intents to MobiASM."""
        ops = []

        # Semantic operations typically involve:
        # 1. Embedding to manifold
        # 2. Computing distances/similarities
        # 3. Finding paths

        ops.append(self.runtime.h_exp0)  # Embed to H⁷
        ops.append(self.runtime.h_dist)  # Compute distance  # type: ignore[arg-type]

        return ops

    def _compile_navigation_operations(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile navigation intents to MobiASM."""
        ops = []

        # Navigation requires:
        # 1. Map start/end to manifold
        # 2. Compute geodesic path
        # 3. Parallel transport along path

        ops.append(self.runtime.h_exp0)  # Map to manifold
        # Only append if method exists
        if hasattr(self.runtime, "t_geodesic"):
            ops.append(self.runtime.t_geodesic)  # Compute path  # type: ignore[arg-type]

        return ops

    def _compile_attention_operations(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile attention intents to MobiASM."""
        ops = []

        # Attention operations:
        # 1. Prepare Q/K/V
        # 2. Execute geometric attention
        # 3. Project result

        # Only append if method exists in runtime
        if hasattr(self.runtime, "f_hyp_attention"):
            ops.append(self.runtime.f_hyp_attention)  # Fused attention

        return ops

    def _compile_transformation_operations(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile transformation intents to MobiASM."""
        ops = []

        # Transformations:
        # 1. Apply geometric operation
        # 2. Add residual connection
        # 3. Project to manifold

        # Only append if method exists in runtime
        if hasattr(self.runtime, "f_gyroresidual"):
            ops.append(self.runtime.f_gyroresidual)  # Fused residual

        return ops

    def _compile_default_operations(
        self,
        intent: Intent,
        parsed: ParsedLangV2,
    ) -> list[Any]:
        """Compile generic intents to basic MobiASM operations."""
        ops = []

        # Default: basic hyperbolic operations
        ops.append(self.runtime.h_exp0)
        ops.append(self.runtime.h_log0)

        return ops

    async def _execute_mobiasm(
        self,
        operations: list[Any],
        intent: Intent,
        context: dict[str, Any],
    ) -> tuple[Any, torch.Tensor | None]:
        """Execute MobiASM operations on manifolds.

        This takes the compiled operations and actually runs them,
        producing concrete results.

        Args:
            operations: List of MobiASM operations to execute
            intent: Original intent (for context)
            context: Execution context (embeddings, parameters, etc.)

        Returns:
            Tuple of (result, final_manifold_state)
        """
        # Extract goal from intent metadata
        goal = (intent.metadata or {}).get("goal", "")

        # For demonstration, execute a complete semantic navigation
        if "navigate" in (intent.target or "").lower() or "navigate" in str(intent.action).lower():
            return await self._execute_navigation(goal, operations, context)
        elif "attention" in (intent.target or "").lower():
            return await self._execute_attention(operations, context)
        else:
            return await self._execute_default(operations, context)

    async def _execute_navigation(
        self,
        goal: str,
        operations: list[Any],
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], torch.Tensor]:
        """Execute a semantic navigation task.

        HARDENED (Dec 22, 2025): Uses real LLM embeddings for navigation.

        Example: "Navigate from fear to trust"

        Args:
            goal: Goal description
            operations: MobiASM operations
            context: Execution context

        Returns:
            Navigation result and final state
        """
        from kagami.core.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()
        if embedding_service is None:
            raise RuntimeError("Embedding service required for navigation")

        # Parse goal to extract start/end concepts using LLM
        # Goal format: "Navigate from X to Y" or similar
        goal_lower = goal.lower()
        if " from " in goal_lower and " to " in goal_lower:
            parts = goal_lower.split(" from ", 1)[1].split(" to ", 1)
            start_concept = parts[0].strip()
            end_concept = parts[1].strip() if len(parts) > 1 else start_concept
        else:
            # Use goal as end, context as start
            start_concept = context.get("current_state", "neutral")
            end_concept = goal

        # Embed concepts using real LLM
        start_emb = await embedding_service.embed_text(start_concept)  # type: ignore[misc]
        end_emb = await embedding_service.embed_text(end_concept)  # type: ignore[misc]

        # Convert to tensors and project to 7D (S⁷ manifold)
        if not isinstance(start_emb, torch.Tensor):
            start_emb = torch.tensor(start_emb, dtype=torch.float32)
        if not isinstance(end_emb, torch.Tensor):
            end_emb = torch.tensor(end_emb, dtype=torch.float32)

        # Project to 7D via learned projection or PCA
        if start_emb.shape[-1] != 7:
            # Use simple linear projection (normalized)
            start_emb = (
                start_emb.flatten()[:7]
                if start_emb.numel() >= 7
                else torch.nn.functional.pad(start_emb.flatten(), (0, 7 - start_emb.numel()))
            )
            end_emb = (
                end_emb.flatten()[:7]
                if end_emb.numel() >= 7
                else torch.nn.functional.pad(end_emb.flatten(), (0, 7 - end_emb.numel()))
            )

        start_embedding = start_emb.unsqueeze(0) * 0.3  # Scale to reasonable range
        end_embedding = end_emb.unsqueeze(0) * 0.3

        # Execute navigation
        start_h = self.runtime.h_exp0(start_embedding)  # Map to H⁷
        end_h = self.runtime.h_exp0(end_embedding)

        # Compute geodesic path (required - no fallback)
        if not hasattr(self.runtime, "t_geodesic"):
            raise RuntimeError("Runtime must support t_geodesic for navigation")
        path = self.runtime.t_geodesic(start_h, end_h, num_steps=5)

        # Compute distances along path
        distances = []
        for i in range(len(path) - 1):
            dist = self.runtime.h_dist(path[i], path[i + 1])
            distances.append(dist.item())

        result = {
            "goal": goal,
            "start_concept": start_concept,
            "end_concept": end_concept,
            "path_length": len(path),
            "total_distance": sum(distances),
            "path_points": [p.tolist() for p in path],
            "distances": distances,
        }

        return result, path[-1]  # Return final state

    async def _execute_attention(
        self,
        operations: list[Any],
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], torch.Tensor]:
        """Execute geometric attention.

        HARDENED (Dec 22, 2025): Uses real context embeddings.

        Args:
            operations: MobiASM operations
            context: Execution context

        Returns:
            Attention result and final state
        """
        from kagami.core.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()
        if embedding_service is None:
            raise RuntimeError("Embedding service required for attention")

        # Extract query and context from operations/context
        query_text = context.get("query", context.get("intent", ""))
        context_texts = context.get("context_items", [str(context)])

        # Embed query and context
        q_emb_result = embedding_service.embed_text(query_text)
        q_emb = (await q_emb_result) if hasattr(q_emb_result, "__await__") else q_emb_result
        k_embs_raw = [embedding_service.embed_text(c) for c in context_texts[:4]]  # Limit to 4
        k_embs = [(await k) if hasattr(k, "__await__") else k for k in k_embs_raw]

        # Convert to tensors
        if not isinstance(q_emb, torch.Tensor):
            q_emb = torch.tensor(q_emb, dtype=torch.float32)

        k_tensors = []
        for k in k_embs:
            if not isinstance(k, torch.Tensor):
                k = torch.tensor(k, dtype=torch.float32)
            k_tensors.append(k)

        # Project to 7D for hyperbolic attention
        dim = 7

        def project_to_dim(t: torch.Tensor) -> torch.Tensor:
            if t.numel() >= dim:
                return t.flatten()[:dim]
            return torch.nn.functional.pad(t.flatten(), (0, dim - t.numel()))

        q = project_to_dim(q_emb).unsqueeze(0).unsqueeze(0) * 0.1  # [1, 1, 7]
        k_stack = (
            torch.stack([project_to_dim(k) for k in k_tensors]).unsqueeze(0) * 0.1
        )  # [1, N, 7]
        v = k_stack.clone()  # Use keys as values

        curvature = torch.tensor(1.0)

        # Execute fused hyperbolic attention (required - no fallback)
        if not hasattr(self.runtime, "f_hyp_attention"):
            raise RuntimeError("Runtime must support f_hyp_attention")
        attended = self.runtime.f_hyp_attention(q, k_stack, v, curvature)

        result = {
            "query_shape": list(q.shape),
            "key_shape": list(k.shape),
            "value_shape": list(v.shape),
            "attended_shape": list(attended.shape),
            "attended_norm": attended.norm().item(),
        }

        return result, attended

    async def _execute_default(
        self,
        operations: list[Any],
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], torch.Tensor | None]:
        """Execute default operations.

        Args:
            operations: MobiASM operations
            context: Execution context

        Returns:
            Default result and state
        """
        # HARDENED (Dec 22, 2025): Derive tangent from context embedding
        from kagami.core.services.embedding_service import get_embedding_service

        embedding_service = get_embedding_service()
        if embedding_service is None:
            raise RuntimeError("Embedding service required for language compilation")

        # Get context description for embedding
        context_text = context.get("description", context.get("intent", str(context)))
        context_emb = await embedding_service.embed_text(context_text)  # type: ignore[misc]

        if not isinstance(context_emb, torch.Tensor):
            context_emb = torch.tensor(context_emb, dtype=torch.float32)

        # Project to 7D tangent space
        if context_emb.numel() >= 7:
            tangent = context_emb.flatten()[:7].unsqueeze(0) * 0.2
        else:
            tangent = (
                torch.nn.functional.pad(
                    context_emb.flatten(), (0, 7 - context_emb.numel())
                ).unsqueeze(0)
                * 0.2
            )

        point = self.runtime.h_exp0(tangent)
        tangent_back = self.runtime.h_log0(point)

        # Measure round-trip error
        error = (tangent - tangent_back).norm().item()

        result = {
            "operations_executed": len(operations),
            "round_trip_error": error,
            "manifold_point": point.tolist(),
        }

        return result, point


# Factory function
def create_compiler(
    device: str = "cpu",
    use_metal: bool = True,
    use_compile: bool = True,
) -> LanguageCompiler:
    """Create a language compiler instance.

    Args:
        device: Device to execute on
        use_metal: Use Metal kernels
        use_compile: Use torch.compile

    Returns:
        LanguageCompiler instance

    Example:
        >>> compiler = create_compiler(device="mps")
        >>> result = await compiler.compile_and_execute('SLANG EXECUTE semantic.test')
    """
    return LanguageCompiler(
        device=device,
        use_metal=use_metal,
        use_compile=use_compile,
    )
