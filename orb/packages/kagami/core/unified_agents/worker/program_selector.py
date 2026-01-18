"""Program Selection - MDL-based program selection from E₈ library.

Extracted from GeometricWorker to reduce god class complexity.

This module handles:
- Differentiable program selection
- MDL-based library queries
- Action encoding for program lookup
- Program embedding preparation

Created: December 21, 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import torch
import torch.nn.functional as F

if TYPE_CHECKING:
    from kagami.core.world_model.memory import ProgramLibrary

logger = logging.getLogger(__name__)


class ProgramSelector:
    """Selects programs from E₈ library using MDL-based scoring.

    Uses P(program | action) ∝ similarity × 2^{-K(program)}
    """

    def __init__(
        self,
        colony_idx: int,
        use_program_library: bool = True,
        max_programs: int = 10,
    ):
        """Initialize program selector.

        Args:
            colony_idx: Colony assignment (0-6)
            use_program_library: Whether to use program selection
            max_programs: Maximum programs to consider
        """
        self.colony_idx = colony_idx
        self.use_program_library = use_program_library
        self.max_programs = max_programs

        # Lazy-loaded library reference
        self._program_library: ProgramLibrary | None = None

    def set_program_library(self, library: ProgramLibrary | None) -> None:
        """Set the program library for gradient flow.

        Args:
            library: Program library instance (shared across workers)
        """
        self._program_library = library

    @property
    def program_library(self) -> ProgramLibrary | None:
        """Get program library (lazy loaded).

        NOTE: For gradient flow during training, set[Any] _program_library to
        model._program_library via set_program_library().
        """
        if self._program_library is None and self.use_program_library:
            try:
                from kagami.core.world_model.memory import ProgramLibrary

                logger.warning(
                    "⚠️ ProgramSelector: Creating standalone library. "
                    "For gradient flow, use set_program_library(model._program_library)."
                )
                self._program_library = ProgramLibrary()
            except ImportError:
                logger.warning("ProgramLibrary not available")
        return self._program_library

    def select_program(self, state: torch.Tensor) -> dict[str, Any]:
        """Select a program from the library based on current state.

        This is the differentiable program selection interface used by
        ColonyRSSM.step_all_agents() for Markov blanket integration.

        Args:
            state: [14] internal state (z from colony or derived)

        Returns:
            Dict with program_embedding and selection info
        """
        # If library is wired, use it for differentiable selection
        if self.program_library is not None:
            try:
                result = self.program_library.query(  # type: ignore[operator]
                    state,
                    colony_type=self.colony_idx,
                    max_results=1,
                )
                if result is not None:
                    # Get program embedding from result (handle both .embedding and .program attrs)
                    raw_emb = getattr(result, "embedding", None)
                    if raw_emb is None:
                        raw_emb = getattr(result, "program", None)
                    if raw_emb is None:
                        raw_emb = state

                    # CRITICAL: Always truncate to 8D for E8 action space
                    # Programs are 52D (F₄), but action space is 8D (E₈ octonion)
                    if raw_emb.shape[-1] > 8:
                        program_emb = raw_emb[..., :8]
                    elif raw_emb.shape[-1] < 8:
                        program_emb = F.pad(raw_emb, (0, 8 - raw_emb.shape[-1]))
                    else:
                        program_emb = raw_emb

                    return {
                        "program_embedding": program_emb,
                        "program_index": result.index if hasattr(result, "index") else 0,
                        "complexity": result.complexity if hasattr(result, "complexity") else 0.0,
                    }
            except Exception:
                pass

        # Default: use state itself as program embedding (truncate to 8D)
        return {
            "program_embedding": state[:8]
            if state.shape[-1] >= 8
            else F.pad(state, (0, 8 - state.shape[-1])),
            "program_index": 0,
            "complexity": 0.0,
        }

    async def select_program_async(
        self,
        action: str,
        params: dict[str, Any],
    ) -> int | None:
        """Select program from MDL-based library (async version).

        Uses P(program | action) ∝ similarity × 2^{-K(program)}

        Args:
            action: Action name
            params: Action parameters

        Returns:
            E₈ program index (0-239) or None
        """
        if self.program_library is None:
            return None

        try:
            # Encode action as query
            query = self._encode_action(action, params)

            # Query library
            program = self.program_library.query(  # type: ignore[operator]
                query,
                colony_type=self.colony_idx,
                max_results=1,
            )

            return program.index if program else None

        except Exception as e:
            logger.debug(f"Program selection failed: {e}")
            return None

    def _encode_action(self, action: str, params: dict[str, Any]) -> torch.Tensor:
        """Encode action as 8D vector for program lookup.

        Args:
            action: Action name
            params: Action parameters

        Returns:
            [8] normalized encoding vector
        """
        # Simple hash-based encoding
        action_hash = hash(action)
        param_hash = hash(str(sorted(params.items())))

        combined = action_hash ^ param_hash

        # Convert to 8D
        encoding = torch.tensor(
            [((combined >> (i * 8)) & 0xFF) / 127.5 - 1.0 for i in range(8)], dtype=torch.float32
        )

        return F.normalize(encoding, dim=0)


__all__ = ["ProgramSelector"]
