"""Colony-Memory Bridge — Deep Unification of Agent Kernel and World Model.

CREATED: December 1, 2025

This module bridges the gap between:
- FractalAgent execution (6-phase kernel)
- MDL-based program selection (learned complexity heuristics)
- OrganismRSSM (shared colony state)
- HopfieldE8Memory (geometric memory addressing)
- KagamiWorldModel (world dynamics)

ARCHITECTURE:
=============
```
                    ┌─────────────────────────────────────┐
                    │        FractalAgent                 │
                    │        (6-Phase Kernel)             │
                    └──────────────┬──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │     ColonyMemoryBridge              │ ← THIS MODULE
                    │  (Unified Memory + Colony Access)   │
                    └──────────────┬──────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  OrganismRSSM   │     │  ProgramLibrary  │     │ HopfieldE8Memory │
│  (Colony State) │◄───►│ (Program Memory) │◄───►│ (Geometric Mem)  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
         │                         │                         │
         └─────────────────────────┴─────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────┐
                    │        KagamiWorldModel             │
                    │     (Dynamics & Prediction)         │
                    └─────────────────────────────────────┘
```

KEY INNOVATIONS:
================
1. **Unified Memory Access**: All memory operations route through E8 lattice addressing
2. **Colony-Aware State**: Agent state is offset from colony's shared RSSM state
3. **MDL Selection**: Action selection uses program library with MDL prior
4. **Learning Closure**: Task outcomes update all layers (colony RSSM, program complexity, Hopfield memory)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, cast

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ColonyMemoryConfig:
    """Configuration for Colony-Memory Bridge."""

    # Colony state
    use_organism_rssm: bool = True
    colony_state_dim: int = 14  # H14 (G2)

    # Memory
    use_hopfield_memory: bool = True
    memory_query_dim: int = 14  # G2 input
    memory_value_dim: int = 128

    # MDL Program Selection
    use_mdl_selection: bool = True
    mdl_temperature: float = 1.0

    # Learning
    learning_rate: float = 0.01
    colony_update_rate: float = 0.1  # How much colony state changes per outcome
    complexity_lr: float = 0.01  # MDL complexity update rate


# =============================================================================
# UNIFIED MEMORY ACCESS
# =============================================================================


class UnifiedMemoryAccess:
    """Unified access to all memory systems via E8 lattice addressing.

    UPDATED (Dec 2, 2025): Library should be passed in for gradient flow.

    All memory operations use E8 roots as the addressing scheme:
    - Query (14D G2) → Project (8D octonion) → E8 attention (240 slots)
    - Retrieval returns both Hopfield content AND program embeddings
    """

    def __init__(
        self,
        config: ColonyMemoryConfig | None = None,
        library: Any = None,  # ProgramLibrary (ResidualCatastropheProgramLibrary)
    ):
        self.config = config or ColonyMemoryConfig()

        # Lazy-loaded components
        self._hopfield: Any = None
        self._solomonoff: Any = library  # Use passed library if available
        self._organism_rssm: Any = None

        self._initialized = False

    def set_library(self, library: Any) -> None:
        """Set the program library for gradient flow."""
        self._solomonoff = library

    def _ensure_initialized(self) -> None:
        """Lazy-load all memory components (Split Architecture Dec 2025)."""
        if self._initialized:
            return

        try:
            from kagami.core.world_model.colony_rssm import get_organism_rssm
            from kagami.core.world_model.memory import (
                EpisodicMemory,
                EpisodicMemoryConfig,
                ProgramLibrary,
                ProgramLibraryConfig,
            )

            # Episodic Memory: 256D values (matches RSSM h)
            memory_config = EpisodicMemoryConfig(
                num_slots=240,
                value_dim=self.config.memory_value_dim,  # 256D
                query_dim=self.config.memory_query_dim,
            )
            self._hopfield = EpisodicMemory(memory_config)

            # Program Library: 52D F₄ embeddings (optimal for actions)
            program_config = ProgramLibraryConfig(
                num_base_programs=240,
                program_dim=52,  # F₄ dimension
                query_dim=self.config.memory_query_dim,
            )
            self._solomonoff = ProgramLibrary(program_config)

            # Get OrganismRSSM (shared singleton)
            self._organism_rssm = get_organism_rssm()

            self._initialized = True
            logger.debug("Split Memory Architecture initialized")

        except Exception as e:
            logger.warning(f"Split Memory Architecture partial init: {e}")
            self._initialized = True  # Mark as initialized to avoid repeated failures

    def retrieve(
        self,
        query: torch.Tensor,
        domain: str = "forge",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """Unified retrieval from all memory systems.

        Args:
            query: Query tensor (14D G2 or variable size)
            domain: Colony domain for context
            top_k: Number of top results

        Returns:
            Dict with:
            - hopfield_content: Retrieved memory content from E8 slots
            - program_embedding: Selected program from ProgramLibrary
            - colony_state: Current colony RSSM state
            - attention_weights: E8 attention distribution
        """
        self._ensure_initialized()

        result = {
            "hopfield_content": None,
            "program_embedding": None,
            "colony_state": None,
            "attention_weights": None,
            "selected_program_idx": -1,
        }

        # Ensure query is proper shape
        if query.dim() == 1:
            query = query.unsqueeze(0)

        # Pad/truncate to 14D (G2)
        if query.shape[-1] != 14:
            if query.shape[-1] > 14:
                query = query[..., :14]
            else:
                query = F.pad(query, (0, 14 - query.shape[-1]))

        # 1. Hopfield E8 Memory Retrieval
        if self._hopfield is not None:
            try:
                hopfield_result = self._hopfield(query)
                result["hopfield_content"] = hopfield_result["retrieved_content"]
                result["attention_weights"] = hopfield_result["attention"]
            except Exception as e:
                logger.debug(f"Hopfield retrieval failed: {e}")

        # 2. MDL-based Program Selection
        if self._solomonoff is not None:
            try:
                from kagami.core.world_model.memory import ColonyGenome

                # Get colony genome
                DOMAIN_TO_IDX = {
                    "spark": 0,
                    "forge": 1,
                    "flow": 2,
                    "nexus": 3,
                    "beacon": 4,
                    "grove": 5,
                    "crystal": 6,
                }
                colony_idx = DOMAIN_TO_IDX.get(domain, 1)
                genome = ColonyGenome.for_colony(colony_idx)

                # Select program
                solomonoff_result = self._solomonoff.select(
                    query=query,
                    colony_genome=genome,
                    extended_dna=[],
                    top_k=top_k,
                )

                result["program_embedding"] = solomonoff_result["embedding"]
                result["selected_program_idx"] = int(
                    solomonoff_result["top_k_indices"][0, 0].item()
                )

            except Exception as e:
                logger.debug(f"MDL program selection failed: {e}")

        # 3. Colony RSSM State
        if self._organism_rssm is not None:
            try:
                if domain in self._organism_rssm.colonies:
                    colony_rssm = self._organism_rssm.get_colony(domain)
                    result["colony_state"] = {  # type: ignore[assignment]
                        "h": colony_rssm.state.h.clone(),
                        "z": colony_rssm.state.z.clone(),
                        "agent_count": len(colony_rssm.state.agents),
                    }
            except Exception as e:
                logger.debug(f"Colony state retrieval failed: {e}")

        return result

    def write(
        self,
        key: torch.Tensor,
        value: torch.Tensor,
        domain: str = "forge",
        success: bool = True,
        program_idx: int = -1,
    ) -> dict[str, Any]:
        """Unified write to all memory systems.

        Args:
            key: Key tensor (what to remember)
            value: Value tensor (content to store)
            domain: Colony domain
            success: Whether this was a successful outcome
            program_idx: Which program was used (-1 if unknown)

        Returns:
            Write statistics
        """
        self._ensure_initialized()

        stats = {
            "hopfield_updated": False,
            "solomonoff_updated": False,
            "colony_updated": False,
        }

        # Ensure proper shapes
        if key.dim() == 1:
            key = key.unsqueeze(0)
        if value.dim() == 1:
            value = value.unsqueeze(0)

        # 1. Hopfield Memory Update (Hebbian learning)
        if self._hopfield is not None:
            try:
                # Pad key to 14D
                if key.shape[-1] != 14:
                    if key.shape[-1] > 14:
                        key_14d = key[..., :14]
                    else:
                        key_14d = F.pad(key, (0, 14 - key.shape[-1]))
                else:
                    key_14d = key

                # Pad value to memory_value_dim
                if value.shape[-1] != self.config.memory_value_dim:
                    if value.shape[-1] > self.config.memory_value_dim:
                        value_mem = value[..., : self.config.memory_value_dim]
                    else:
                        value_mem = F.pad(
                            value, (0, self.config.memory_value_dim - value.shape[-1])
                        )
                else:
                    value_mem = value

                self._hopfield.write_hebbian(key_14d, value_mem)
                stats["hopfield_updated"] = True

            except Exception as e:
                logger.debug(f"Hopfield write failed: {e}")

        # 2. MDL Complexity Update
        if self._solomonoff is not None and program_idx >= 0:
            try:
                reward = 1.0 if success else 0.0
                self._solomonoff.update_complexity(program_idx, reward)
                stats["solomonoff_updated"] = True
            except Exception as e:
                logger.debug(f"MDL complexity update failed: {e}")

        # 3. Colony RSSM Update
        if self._organism_rssm is not None:
            try:
                if domain in self._organism_rssm.colonies:
                    colony_rssm = self._organism_rssm.get_colony(domain)
                    reward = 1.0 if success else 0.0
                    colony_rssm.step_all_agents(reward=reward)
                    stats["colony_updated"] = True
            except Exception as e:
                logger.debug(f"Colony update failed: {e}")

        return stats


# =============================================================================
# COLONY MEMORY BRIDGE
# =============================================================================


class ColonyMemoryBridge:
    """Bridge between FractalAgent execution and unified memory.

    This is the main integration point. It:
    1. Provides memory access during agent execution
    2. Updates all memory systems on task outcomes
    3. Routes queries through colony-aware addressing
    """

    def __init__(self, config: ColonyMemoryConfig | None = None):
        self.config = config or ColonyMemoryConfig()
        self._memory = UnifiedMemoryAccess(self.config)

        # Metrics
        self.total_queries = 0
        self.total_writes = 0
        self.last_access = 0.0

        logger.debug("ColonyMemoryBridge initialized")

    def get_agent_context(
        self,
        agent: Any,
        task: Any,
    ) -> dict[str, Any]:
        """Get memory context for agent execution.

        Called during PERCEIVE phase to enrich task context with memory.

        Args:
            agent: Agent executing the task
            task: Task being executed

        Returns:
            Context dict[str, Any] with memory content and colony state
        """
        self.total_queries += 1
        self.last_access = time.time()

        # Build query from task
        query = self._build_query(agent, task)

        # Get domain from agent DNA
        domain = agent.dna.domain.value if hasattr(agent.dna, "domain") else "forge"

        # Retrieve from unified memory
        memory_result = self._memory.retrieve(query, domain=domain)

        return {
            "memory": memory_result,
            "domain": domain,
            "query_embedding": query,
        }

    def record_outcome(
        self,
        agent: Any,
        task: Any,
        success: bool,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Record task outcome to all memory systems.

        Called during CONVERGE phase to update memory.

        Args:
            agent: Agent that executed the task
            task: Task that was executed
            success: Whether execution succeeded
            result: Execution result

        Returns:
            Update statistics
        """
        self.total_writes += 1
        self.last_access = time.time()

        # Build key-value pair for memory
        key = self._build_query(agent, task)
        value = self._build_outcome_embedding(result, success)

        # Get domain and program info
        domain = agent.dna.domain.value if hasattr(agent.dna, "domain") else "forge"
        program_idx = task.context.get("selected_program_idx", -1)

        # Write to unified memory
        stats = self._memory.write(
            key=key,
            value=value,
            domain=domain,
            success=success,
            program_idx=program_idx,
        )

        return stats

    def get_action_candidates(
        self,
        agent: Any,
        task: Any,
        num_candidates: int = 5,
    ) -> list[dict[str, Any]]:
        """Get candidate actions using MDL-based program selection.

        Called during SIMULATE phase to generate candidate actions.
        Uses the program library to select likely-successful programs.

        Args:
            agent: Agent making the decision
            task: Task being executed
            num_candidates: Number of candidates to return

        Returns:
            List of candidate action dicts
        """
        query = self._build_query(agent, task)
        domain = agent.dna.domain.value if hasattr(agent.dna, "domain") else "forge"

        # Retrieve programs
        memory_result = self._memory.retrieve(query, domain=domain, top_k=num_candidates)

        candidates = []

        if memory_result["program_embedding"] is not None:
            # Use program embedding to generate candidates
            program_emb = memory_result["program_embedding"]

            # Simple candidate generation: perturb program embedding
            for i in range(num_candidates):
                noise = torch.randn_like(program_emb) * 0.1 * (i + 1)
                candidate_emb = program_emb + noise

                candidates.append(
                    {
                        "action_type": task.action,
                        "program_embedding": candidate_emb.squeeze(0),
                        "program_idx": memory_result["selected_program_idx"],
                        "confidence": 1.0 / (1.0 + i * 0.2),  # Decreasing confidence
                        "params": task.params,
                    }
                )
        else:
            # Fallback: simple candidates from task
            for _i in range(num_candidates):
                candidates.append(
                    {
                        "action_type": task.action,
                        "confidence": 0.5,
                        "params": task.params,
                    }
                )

        return candidates

    def _build_query(self, agent: Any, task: Any) -> torch.Tensor:
        """Build query tensor from agent and task."""
        # Use semantic pointer if available
        if hasattr(agent, "semantic_pointer") and agent.semantic_pointer is not None:
            pointer = agent.semantic_pointer
            if isinstance(pointer, list):
                pointer = torch.tensor(pointer, dtype=torch.float32)
            if pointer.dim() == 1:
                pointer = pointer.unsqueeze(0)
            return cast(torch.Tensor, pointer)

        # Fallback: hash task to create query
        import hashlib

        task_str = f"{task.action}:{task.params!s}"
        task_hash = hashlib.sha256(task_str.encode()).digest()
        query = torch.tensor(
            [float(b) / 255.0 for b in task_hash[:14]],
            dtype=torch.float32,
        ).unsqueeze(0)
        return query

    def _build_outcome_embedding(
        self,
        result: dict[str, Any],
        success: bool,
    ) -> torch.Tensor:
        """Build outcome embedding for memory storage."""
        # Simple embedding based on outcome
        dim = self.config.memory_value_dim

        embedding = torch.zeros(1, dim)

        # Encode success/failure
        embedding[0, 0] = 1.0 if success else -1.0

        # Encode valence if available
        valence = result.get("valence", 0.0)
        embedding[0, 1] = valence

        # Encode confidence if available
        confidence = result.get("brain_confidence", 0.5)
        embedding[0, 2] = confidence

        # Encode duration if available
        duration = result.get("duration", 0.0)
        embedding[0, 3] = min(duration / 10.0, 1.0)  # Normalize

        return embedding

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            "total_queries": self.total_queries,
            "total_writes": self.total_writes,
            "last_access": self.last_access,
            "memory_initialized": self._memory._initialized,
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================


_colony_memory_bridge: ColonyMemoryBridge | None = None


def get_colony_memory_bridge() -> ColonyMemoryBridge:
    """Get singleton ColonyMemoryBridge instance."""
    global _colony_memory_bridge
    if _colony_memory_bridge is None:
        _colony_memory_bridge = ColonyMemoryBridge()
    return _colony_memory_bridge


def reset_colony_memory_bridge() -> None:
    """Reset the singleton."""
    global _colony_memory_bridge
    _colony_memory_bridge = None


__all__ = [
    "ColonyMemoryBridge",
    "ColonyMemoryConfig",
    "UnifiedMemoryAccess",
    "get_colony_memory_bridge",
    "reset_colony_memory_bridge",
]
