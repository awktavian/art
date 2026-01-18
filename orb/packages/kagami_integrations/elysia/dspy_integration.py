"""DSPy Integration — Unified LLM Interface for Kagami.

Integrates DSPy's declarative prompt programming with Kagami's
colony-aware routing and multi-model infrastructure.

Key features:
- Colony-aware signatures (different prompts per colony)
- Multi-model routing (simple → small, complex → large)
- CBF safety integration (filter unsafe outputs)
- Stigmergy-backed few-shot example selection

Created: December 7, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DSPySignature:
    """A DSPy signature definition.

    Simplified representation that doesn't require DSPy import.
    """

    name: str
    input_fields: list[str]
    output_fields: list[str]
    instructions: str = ""


# Colony-specific signatures
COLONY_SIGNATURES = {
    "spark": DSPySignature(
        name="SparkCreative",
        input_fields=["context", "query"],
        output_fields=["ideas", "concepts", "connections"],
        instructions="Generate creative ideas and novel connections. Be divergent.",
    ),
    "forge": DSPySignature(
        name="ForgeImplementation",
        input_fields=["context", "query", "constraints"],
        output_fields=["implementation", "code", "structure"],
        instructions="Provide structured implementation with clear code. Be precise.",
    ),
    "flow": DSPySignature(
        name="FlowRecovery",
        input_fields=["context", "error", "history"],
        output_fields=["diagnosis", "fix", "prevention"],
        instructions="Diagnose errors and provide fixes. Be thorough.",
    ),
    "nexus": DSPySignature(
        name="NexusIntegration",
        input_fields=["context", "query", "sources"],
        output_fields=["synthesis", "connections", "summary"],
        instructions="Integrate information from multiple sources. Be comprehensive.",
    ),
    "beacon": DSPySignature(
        name="BeaconPlanning",
        input_fields=["context", "goal", "constraints"],
        output_fields=["plan", "steps", "milestones"],
        instructions="Create strategic plans with clear milestones. Be systematic.",
    ),
    "grove": DSPySignature(
        name="GroveResearch",
        input_fields=["context", "query", "sources"],
        output_fields=["findings", "citations", "analysis"],
        instructions="Research and analyze with proper citations. Be rigorous.",
    ),
    "crystal": DSPySignature(
        name="CrystalVerification",
        input_fields=["context", "claim", "evidence"],
        output_fields=["verdict", "reasoning", "confidence"],
        instructions="Verify claims against evidence. Be skeptical.",
    ),
}


@dataclass
class DSPyConfig:
    """Configuration for DSPy integration."""

    # Default models for different task complexities
    simple_model: str = "gemini-1.5-flash"
    complex_model: str = "gemini-1.5-pro"
    critique_model: str = "claude-3-haiku-20240307"

    # Provider settings
    default_provider: str = "google"
    openrouter_enabled: bool = True

    # Safety settings
    cbf_enabled: bool = True
    cbf_threshold: float = 0.5

    # Few-shot settings
    max_fewshot_examples: int = 3
    fewshot_min_rating: int = 4


class KagamiDSPyModule:
    """DSPy module integrated with Kagami's services.

    Provides:
    1. Colony-aware prompt signatures
    2. Multi-model routing based on complexity
    3. CBF safety filtering
    4. Stigmergy-backed few-shot examples

    Usage:
        module = KagamiDSPyModule()

        # Execute with colony routing
        result = await module.execute(
            query="How does E8 work?",
            colony="grove",
            context={"sources": [...]},
        )
    """

    def __init__(self, config: DSPyConfig | None = None):
        """Initialize DSPy module.

        Args:
            config: Optional configuration
        """
        self.config = config or DSPyConfig()
        self.signatures = COLONY_SIGNATURES.copy()
        self._dspy_available = self._check_dspy()

        # Lazy-loaded components
        self._llm_service = None
        self._feedback_bridge = None

        logger.info(f"KagamiDSPyModule initialized (DSPy available: {self._dspy_available})")

    def _check_dspy(self) -> bool:
        """Check if DSPy is available."""
        try:
            import dspy  # noqa: F401

            return True
        except ImportError:
            logger.info("DSPy not installed - using fallback prompting")
            return False

    def _get_llm_service(self) -> Any:
        """Lazy-load LLM service."""
        if self._llm_service is None:
            try:
                from kagami.core.services.llm.service import get_llm_service

                self._llm_service = get_llm_service()  # type: ignore[assignment]
            except ImportError:
                logger.warning("LLM service not available")
        return self._llm_service

    def _get_feedback_bridge(self) -> Any:
        """Lazy-load feedback bridge for few-shot examples."""
        if self._feedback_bridge is None:
            try:
                from kagami_integrations.elysia.stigmergy_feedback import (
                    ElysiaFeedbackBridge,
                )

                self._feedback_bridge = ElysiaFeedbackBridge()  # type: ignore[assignment]
            except ImportError:
                logger.debug("Feedback bridge not available")
        return self._feedback_bridge

    def get_signature(self, colony: str) -> DSPySignature:
        """Get signature for colony.

        Args:
            colony: Colony name

        Returns:
            DSPySignature for the colony
        """
        return self.signatures.get(colony, self.signatures["nexus"])

    def register_signature(
        self,
        colony: str,
        name: str,
        input_fields: list[str],
        output_fields: list[str],
        instructions: str = "",
    ) -> None:
        """Register a custom signature.

        Args:
            colony: Colony to register for
            name: Signature name
            input_fields: Input field names
            output_fields: Output field names
            instructions: Prompt instructions
        """
        self.signatures[colony] = DSPySignature(
            name=name,
            input_fields=input_fields,
            output_fields=output_fields,
            instructions=instructions,
        )
        logger.debug(f"Registered signature {name} for colony {colony}")

    async def execute(
        self,
        query: str,
        colony: str = "nexus",
        context: dict[str, Any] | None = None,
        complexity: float = 0.5,
        use_fewshot: bool = True,
    ) -> dict[str, Any]:
        """Execute DSPy module with colony routing.

        Args:
            query: User query
            colony: Colony to route to
            context: Additional context
            complexity: Query complexity (0-1)
            use_fewshot: Whether to include few-shot examples

        Returns:
            Dict with output fields from signature
        """
        context = context or {}
        signature = self.get_signature(colony)

        # Get few-shot examples if enabled
        fewshot_examples = []
        if use_fewshot:
            bridge = self._get_feedback_bridge()
            if bridge:
                try:
                    fewshot_examples = await bridge.get_fewshot_examples(
                        query,
                        max_examples=self.config.max_fewshot_examples,
                        min_rating=self.config.fewshot_min_rating,
                    )
                except Exception as e:
                    logger.debug(f"Few-shot retrieval failed: {e}")

        # Select model based on complexity
        model = self.config.complex_model if complexity > 0.7 else self.config.simple_model

        # Build prompt
        prompt = self._build_prompt(
            signature=signature,
            query=query,
            context=context,
            fewshot_examples=fewshot_examples,
        )

        # Execute via DSPy or direct LLM call
        if self._dspy_available:
            result = await self._execute_dspy(prompt, signature, model)
        else:
            result = await self._execute_direct(prompt, signature, model)

        # CBF safety check
        if self.config.cbf_enabled:
            result = await self._apply_cbf_filter(result)

        return result

    def _build_prompt(
        self,
        signature: DSPySignature,
        query: str,
        context: dict[str, Any],
        fewshot_examples: list[dict],
    ) -> str:
        """Build prompt from signature and context.

        Args:
            signature: DSPy signature
            query: User query
            context: Additional context
            fewshot_examples: Few-shot examples

        Returns:
            Formatted prompt string
        """
        parts = []

        # Instructions
        if signature.instructions:
            parts.append(f"Instructions: {signature.instructions}\n")

        # Few-shot examples
        if fewshot_examples:
            parts.append("Examples:")
            for i, ex in enumerate(fewshot_examples[:3], 1):
                parts.append(f"\nExample {i}:")
                parts.append(f"  Query: {ex.get('query', '')[:200]}")
                parts.append(f"  Response: {ex.get('response', '')[:300]}")
            parts.append("\n")

        # Context
        if context:
            parts.append("Context:")
            for key, value in context.items():
                if isinstance(value, list):
                    value_str = f"[{len(value)} items]"
                elif isinstance(value, str) and len(value) > 200:
                    value_str = value[:200] + "..."
                else:
                    value_str = str(value)
                parts.append(f"  {key}: {value_str}")
            parts.append("")

        # Query
        parts.append(f"Query: {query}\n")

        # Output format
        parts.append(f"Please provide: {', '.join(signature.output_fields)}")

        return "\n".join(parts)

    async def _execute_dspy(
        self,
        prompt: str,
        signature: DSPySignature,
        model: str,
    ) -> dict[str, Any]:
        """Execute using DSPy if available.

        Args:
            prompt: Formatted prompt
            signature: DSPy signature
            model: Model to use

        Returns:
            Dict with output fields
        """
        try:
            import dspy

            # Configure DSPy with model
            # Note: This is a simplified integration
            # Production would use proper DSPy configuration

            lm = dspy.LM(model=model)

            with dspy.context(lm=lm):
                # Create dynamic signature
                sig = dspy.Signature(
                    f"{', '.join(signature.input_fields)} -> {', '.join(signature.output_fields)}"
                )

                # Execute
                predictor = dspy.Predict(sig)
                result = predictor(prompt=prompt)

                # Extract outputs
                outputs = {}
                for field in signature.output_fields:
                    outputs[field] = getattr(result, field, "")

                return outputs

        except Exception as e:
            logger.warning(f"DSPy execution failed: {e}, using direct LLM")
            return await self._execute_direct(prompt, signature, model)

    async def _execute_direct(
        self,
        prompt: str,
        signature: DSPySignature,
        model: str,
    ) -> dict[str, Any]:
        """Execute using direct LLM call.

        Args:
            prompt: Formatted prompt
            signature: DSPy signature
            model: Model to use

        Returns:
            Dict with output fields
        """
        llm = self._get_llm_service()

        if llm is None:
            # Return empty structure if no LLM available
            return dict.fromkeys(signature.output_fields, "")

        try:
            # Direct LLM call
            response = await llm.generate(
                prompt=prompt,
                app_name="dspy_integration",
                max_tokens=2000,
                routing_hints={"model": model} if model else None,
            )

            # Parse response into output fields
            # Simple heuristic: split by output field names
            outputs = {}
            content = response.get("content", "")

            for field in signature.output_fields:
                # Try to extract field content
                outputs[field] = content  # Simplified: return full content

            return outputs

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return dict.fromkeys(signature.output_fields, f"Error: {e}")

    async def _apply_cbf_filter(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply CBF safety filter to result.

        Args:
            result: Raw result dict

        Returns:
            Filtered result (may have content removed)
        """
        try:
            from kagami.core.safety import get_safety_filter

            cbf = get_safety_filter()

            # Check each output field
            for field, content in result.items():
                if isinstance(content, str) and len(content) > 0:
                    h_value = cbf.compute_barrier(content)  # type: ignore[attr-defined]

                    if h_value < 0:
                        # RED zone - block
                        result[field] = "[Content blocked by safety filter]"
                        logger.warning(f"CBF blocked content in field {field}")

                    elif h_value < self.config.cbf_threshold:
                        # YELLOW zone - flag
                        result[f"{field}_warning"] = "Content flagged for review"
                        logger.info(f"CBF flagged content in field {field}")

        except ImportError:
            logger.debug("CBF filter not available")
        except Exception as e:
            logger.warning(f"CBF filter error: {e}")

        return result


# Factory function
def create_dspy_module(config: DSPyConfig | None = None) -> KagamiDSPyModule:
    """Create a KagamiDSPyModule instance.

    Args:
        config: Optional configuration

    Returns:
        KagamiDSPyModule instance
    """
    return KagamiDSPyModule(config)


# Singleton accessor
_dspy_module: KagamiDSPyModule | None = None


def get_dspy_module() -> KagamiDSPyModule:
    """Get global DSPy module instance."""
    global _dspy_module
    if _dspy_module is None:
        _dspy_module = KagamiDSPyModule()
    return _dspy_module


__all__ = [
    "COLONY_SIGNATURES",
    "DSPyConfig",
    "DSPySignature",
    "KagamiDSPyModule",
    "create_dspy_module",
    "get_dspy_module",
]
