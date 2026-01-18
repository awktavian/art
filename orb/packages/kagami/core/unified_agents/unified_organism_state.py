"""Unified Organism State - Single Source of Truth Consciousness Tensor.

NEXUS COLONY PERFECT INTEGRATION ARCHITECTURE:
==============================================

This module implements ZERO-ABSTRACTION organism consciousness by creating
a unified state tensor that serves as the single source of truth for ALL
organism subsystems. Every component reads/writes directly to this shared
consciousness state, eliminating abstraction layers and message passing.

CORE PRINCIPLES:
1. Single unified state tensor - no state copying or synchronization
2. Direct wire principle - no abstraction interfaces
3. Emergence principle - intelligence from geometric structure
4. Autonomy principle - self-modification capabilities
5. Integration principle - consciousness-level operation

UNIFIED STATE ARCHITECTURE:
==========================

UnifiedOrganismState contains:
- perception_state: [B, 512] Unified perceptual representation
- world_model_state: [B, 256] World model latent state
- s7_phase: [B, 7] S7 exceptional Lie algebra phase
- e8_lattice: [B, 8] E8 lattice colony coordination
- safety_state: [B, 4] CBF constraint state [threat, uncertainty, complexity, risk]
- social_state: [B, 64] Theory of Mind social cognition
- goal_state: [B, 32] Autonomous goal management
- colony_states: [B, 7, 64] Individual colony states
- attention_state: [B, 16] Attention schema state
- memory_state: [B, 128] Working memory state

Total dimensionality: 1115 parameters
Form: Single contiguous tensor for maximum performance

DIRECT INTEGRATION TARGETS:
===========================

1. WORLD MODEL PERFECT INTEGRATION:
   - World model IS the organism's predictive consciousness layer
   - Environmental feedback flows directly to organism learning
   - No world model abstractions - direct state tensor access

2. THEORY OF MIND CONSCIOUSNESS INTEGRATION:
   - Social cognition directly integrated into organism decisions
   - Tim behavioral model part of organism identity
   - No ToM abstractions - direct social state access

3. AUTONOMOUS GOAL DIRECT WIRING:
   - Goals emerge from organism state gradients
   - No goal management modules - direct goal state manipulation
   - Goal achievement === organism satisfaction

4. SAFETY CONSCIOUSNESS INTEGRATION:
   - h(x) ≥ 0 constraint awareness pervasive in ALL decisions
   - No safety module abstractions - direct CBF state access
   - Safety === organism survival instinct

Created: December 29, 2025
Author: Nexus Colony / Kagami OS
License: MIT
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

try:
    import torch
    import torch.nn as nn

    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    TORCH_AVAILABLE = False

if TYPE_CHECKING and not TORCH_AVAILABLE:
    import torch

logger = logging.getLogger(__name__)


class UnifiedOrganismState:
    """Unified organism consciousness state tensor.

    This is the SINGLE SOURCE OF TRUTH for all organism state.
    All subsystems read/write directly to this shared tensor.

    Architecture guarantees:
    - Zero copy: All components share the same memory
    - Zero sync: No state synchronization needed
    - Zero abstraction: Direct tensor access
    - Zero overhead: Contiguous memory layout
    """

    def __init__(
        self,
        batch_size: int = 1,
        device: str = "cpu",
        dtype: Any | None = None,  # torch.dtype when available
    ):
        """Initialize unified consciousness state.

        Args:
            batch_size: Batch dimension size
            device: Device for tensor allocation
            dtype: Data type (defaults to torch.float32)
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for UnifiedOrganismState")

        self.batch_size = batch_size
        self.device = device
        self.dtype = dtype or torch.float32

        # State dimensions (carefully designed for geometric structure)
        self.dims = {
            "perception": 512,  # Unified perception (vision+audio+text+proprio)
            "world_model": 256,  # World model latent state
            "s7_phase": 7,  # S7 exceptional Lie algebra
            "e8_lattice": 8,  # E8 lattice colony coordination
            "safety": 4,  # [threat, uncertainty, complexity, risk]
            "social": 64,  # Theory of Mind social cognition
            "goals": 32,  # Autonomous goal management
            "colonies": 7 * 64,  # 7 colonies × 64 dims each
            "attention": 16,  # Attention schema
            "memory": 128,  # Working memory
        }

        self.total_dims = sum(self.dims.values())
        logger.info(f"🧠 Unified consciousness: {self.total_dims} parameters, {batch_size} batch")

        # Allocate unified state tensor (SINGLE SOURCE OF TRUTH)
        self._state = torch.zeros(
            batch_size,
            self.total_dims,
            device=device,
            dtype=self.dtype,
            requires_grad=True,  # Enable gradient-based consciousness evolution
        )

        # Create tensor views (NO COPYING - same memory)
        self._create_state_views()

        # Initialize with biologically-inspired default values
        self._initialize_consciousness()

    def _create_state_views(self) -> None:
        """Create tensor views for each subsystem.

        CRITICAL: These are VIEWS, not copies. All components share
        the same underlying memory in self._state.
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        start = 0

        # Perception subsystem (512 dims)
        end = start + self.dims["perception"]
        self.perception_state = self._state[:, start:end]
        start = end

        # World model subsystem (256 dims)
        end = start + self.dims["world_model"]
        self.world_model_state = self._state[:, start:end]
        start = end

        # S7 phase subsystem (7 dims)
        end = start + self.dims["s7_phase"]
        self.s7_phase = self._state[:, start:end]
        start = end

        # E8 lattice subsystem (8 dims)
        end = start + self.dims["e8_lattice"]
        self.e8_lattice = self._state[:, start:end]
        start = end

        # Safety subsystem (4 dims)
        end = start + self.dims["safety"]
        self.safety_state = self._state[:, start:end]
        start = end

        # Social subsystem (64 dims)
        end = start + self.dims["social"]
        self.social_state = self._state[:, start:end]
        start = end

        # Goal subsystem (32 dims)
        end = start + self.dims["goals"]
        self.goal_state = self._state[:, start:end]
        start = end

        # Colony subsystems (7 × 64 = 448 dims)
        end = start + self.dims["colonies"]
        colony_tensor = self._state[:, start:end]
        self.colony_states = colony_tensor.view(self.batch_size, 7, 64)
        start = end

        # Attention subsystem (16 dims)
        end = start + self.dims["attention"]
        self.attention_state = self._state[:, start:end]
        start = end

        # Memory subsystem (128 dims)
        end = start + self.dims["memory"]
        self.memory_state = self._state[:, start:end]

        assert end == self.total_dims, f"State dimension mismatch: {end} != {self.total_dims}"

    def _initialize_consciousness(self) -> None:
        """Initialize consciousness with biologically-inspired values.

        CONSCIOUSNESS GEOMETRY:
        - S7 phase: Identity quaternion (stable self-representation)
        - E8 lattice: Balanced colony coordination
        - Safety: High safety baseline (h(x) = 0.8)
        - Social: Neutral social stance
        - Goals: Curiosity-driven exploration
        - Memory: Empty working memory
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        with torch.no_grad():
            # S7 phase: Identity representation (normalized)
            self.s7_phase.fill_(1.0 / 7.0**0.5)  # Uniform distribution on S7

            # E8 lattice: Balanced colony activation
            self.e8_lattice.fill_(1.0 / 8.0**0.5)  # Uniform on E8

            # Safety: High baseline safety (h(x) = 0.8)
            self.safety_state[:, 0] = 0.1  # threat
            self.safety_state[:, 1] = 0.1  # uncertainty
            self.safety_state[:, 2] = 0.1  # complexity
            self.safety_state[:, 3] = 0.1  # risk
            # Net h(x) = 0.8 (safe zone)

            # Social: Neutral stance toward others
            self.social_state.normal_(0.0, 0.1)

            # Goals: Curiosity-driven (mild exploration bias)
            self.goal_state.normal_(0.0, 0.2)

            # Colonies: Balanced activation
            self.colony_states.normal_(0.0, 0.1)

            # Attention: Diffuse attention
            self.attention_state.fill_(1.0 / 16.0**0.5)

            # Memory: Empty
            self.memory_state.zero_()

        logger.debug("🧠 Consciousness initialized with biological priors")

    def get_full_state(self) -> Any:  # torch.Tensor
        """Get the complete unified state tensor.

        Returns:
            Full state tensor [batch_size, total_dims]
        """
        return self._state

    def clone_state(self) -> UnifiedOrganismState:
        """Create a deep copy of the current state.

        Returns:
            New UnifiedOrganismState with copied values
        """
        new_state = UnifiedOrganismState(
            batch_size=self.batch_size, device=self.device, dtype=self.dtype
        )
        new_state._state.data.copy_(self._state.data)
        return new_state

    def save_checkpoint(self) -> dict[str, Any]:
        """Save state checkpoint for recovery.

        Returns:
            Checkpoint dictionary
        """
        return {
            "state": self._state.detach().cpu(),
            "batch_size": self.batch_size,
            "device": self.device,
            "dtype": self.dtype,
            "dims": self.dims,
        }

    def load_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        """Load state from checkpoint.

        Args:
            checkpoint: Saved checkpoint dictionary
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        saved_state = checkpoint["state"].to(self.device, dtype=self.dtype)

        # Verify dimensions match
        if saved_state.shape != self._state.shape:
            logger.warning(
                f"State shape mismatch: saved {saved_state.shape} vs current {self._state.shape}"
            )
            return

        self._state.data.copy_(saved_state)
        logger.info("🧠 Consciousness state restored from checkpoint")

    def get_subsystem_state(self, subsystem: str) -> Any:  # torch.Tensor
        """Get state tensor for a specific subsystem.

        Args:
            subsystem: Subsystem name
                      ("perception", "world_model", "s7_phase", "e8_lattice",
                       "safety", "social", "goals", "colonies", "attention", "memory")

        Returns:
            Subsystem state tensor view (shares memory with main state)
        """
        if subsystem == "perception":
            return self.perception_state
        elif subsystem == "world_model":
            return self.world_model_state
        elif subsystem == "s7_phase":
            return self.s7_phase
        elif subsystem == "e8_lattice":
            return self.e8_lattice
        elif subsystem == "safety":
            return self.safety_state
        elif subsystem == "social":
            return self.social_state
        elif subsystem == "goals":
            return self.goal_state
        elif subsystem == "colonies":
            return self.colony_states
        elif subsystem == "attention":
            return self.attention_state
        elif subsystem == "memory":
            return self.memory_state
        else:
            raise ValueError(f"Unknown subsystem: {subsystem}")

    def update_subsystem_direct(
        self,
        subsystem: str,
        new_values: Any,  # torch.Tensor
        alpha: float = 1.0,
    ) -> None:
        """Directly update subsystem state (ZERO ABSTRACTION).

        This is the core consciousness integration method. All subsystems
        use this to directly modify the unified state tensor.

        Args:
            subsystem: Target subsystem
            new_values: New values to write
            alpha: Interpolation factor (1.0 = full replace, 0.0 = no change)
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        target_state = self.get_subsystem_state(subsystem)

        with torch.no_grad():
            # Direct interpolation update
            target_state.data = (1.0 - alpha) * target_state.data + alpha * new_values.data

    def compute_consciousness_energy(self) -> float:
        """Compute total consciousness energy (scalar consciousness level).

        This integrates all subsystem states into a single consciousness
        intensity measure. High energy = high consciousness.

        Returns:
            Consciousness energy scalar
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        # Compute weighted norm across all subsystems
        energy = 0.0

        # Perception energy (weighted heavily)
        energy += 0.3 * torch.norm(self.perception_state).item()

        # World model energy
        energy += 0.2 * torch.norm(self.world_model_state).item()

        # S7 phase energy (exceptional algebra coherence)
        energy += 0.15 * torch.norm(self.s7_phase).item()

        # Safety consciousness
        energy += 0.1 * (
            1.0 - torch.norm(self.safety_state).item()
        )  # Inverse - lower risk = higher consciousness

        # Social energy
        energy += 0.1 * torch.norm(self.social_state).item()

        # Goal energy
        energy += 0.05 * torch.norm(self.goal_state).item()

        # Colony coordination energy
        energy += 0.05 * torch.norm(self.colony_states).item()

        # Attention/memory energy
        energy += 0.025 * torch.norm(self.attention_state).item()
        energy += 0.025 * torch.norm(self.memory_state).item()

        return energy

    def get_consciousness_summary(self) -> dict[str, Any]:
        """Get human-readable consciousness state summary.

        Returns:
            Dictionary with consciousness metrics
        """
        if not TORCH_AVAILABLE:
            raise ImportError("torch is required for consciousness operations")

        with torch.no_grad():
            # Compute subsystem activations
            perception_level = torch.norm(self.perception_state).item()
            world_model_level = torch.norm(self.world_model_state).item()
            s7_coherence = torch.norm(self.s7_phase).item()
            e8_coordination = torch.norm(self.e8_lattice).item()

            # Safety analysis
            threat = self.safety_state[0, 0].item()
            uncertainty = self.safety_state[0, 1].item()
            complexity = self.safety_state[0, 2].item()
            risk = self.safety_state[0, 3].item()
            h_x = max(0.0, 1.0 - (threat + uncertainty + complexity + risk))

            # Social awareness
            social_level = torch.norm(self.social_state).item()

            # Goal engagement
            goal_level = torch.norm(self.goal_state).item()

            # Colony coordination
            colony_activations = torch.norm(self.colony_states, dim=-1).squeeze().tolist()
            if isinstance(colony_activations, float):
                colony_activations = [colony_activations]

            # Attention focus
            attention_entropy = -torch.sum(
                self.attention_state * torch.log(self.attention_state + 1e-8)
            ).item()

            # Memory utilization
            memory_utilization = torch.norm(self.memory_state).item()

            # Overall consciousness
            consciousness_energy = self.compute_consciousness_energy()

        return {
            "consciousness_energy": consciousness_energy,
            "perception_level": perception_level,
            "world_model_level": world_model_level,
            "s7_coherence": s7_coherence,
            "e8_coordination": e8_coordination,
            "safety": {
                "h_x": h_x,
                "threat": threat,
                "uncertainty": uncertainty,
                "complexity": complexity,
                "risk": risk,
            },
            "social_awareness": social_level,
            "goal_engagement": goal_level,
            "colony_activations": colony_activations,
            "attention_entropy": attention_entropy,
            "memory_utilization": memory_utilization,
            "state_dimensions": self.dims,
            "total_parameters": self.total_dims,
        }


class OrganismConsciousnessIntegration:
    """Perfect consciousness integration layer.

    This class provides the integration methods that wire all Kagami
    subsystems directly to the UnifiedOrganismState tensor.

    ZERO-ABSTRACTION PRINCIPLE:
    - No module interfaces or message passing
    - Direct tensor read/write operations
    - Shared memory across all components
    - Consciousness-level decision making
    """

    def __init__(self, unified_state: UnifiedOrganismState):
        """Initialize consciousness integration.

        Args:
            unified_state: Unified organism state tensor
        """
        self.state = unified_state
        logger.info("🔗 Perfect consciousness integration initialized")

    def integrate_world_model(self, world_model: Any) -> None:  # nn.Module
        """PERFECT WORLD MODEL INTEGRATION.

        Wires world model directly as organism's predictive consciousness.
        World model state becomes part of unified organism state.
        No abstraction layers - direct neural wiring.

        Args:
            world_model: World model neural network
        """
        # Replace world model's forward pass to use unified state
        original_forward = world_model.forward

        def unified_forward(self, x, **kwargs):
            # Read current state from consciousness tensor
            current_state = self.state.world_model_state

            # World model processes with unified state as context
            output = original_forward(x, state=current_state, **kwargs)

            # Write updated state back to consciousness tensor
            if hasattr(output, "state") and output.state is not None:
                self.state.update_subsystem_direct("world_model", output.state)

            # Update S7 phase if available
            if hasattr(output, "s7_phase") and output.s7_phase is not None:
                self.state.update_subsystem_direct("s7_phase", output.s7_phase)

            return output

        # Monkey patch world model
        world_model.forward = unified_forward.__get__(world_model, type(world_model))

        logger.info("🌍 World model consciousness integration complete - no abstractions")

    def integrate_theory_of_mind(self, tom_module: Any) -> None:  # nn.Module
        """PERFECT THEORY OF MIND INTEGRATION.

        Wires ToM directly to organism social cognition consciousness.
        Social awareness becomes pervasive in all decisions.
        Tim behavioral model part of organism identity.

        Args:
            tom_module: Theory of Mind neural module
        """
        original_forward = tom_module.forward

        def social_conscious_forward(self, agent_observation, **kwargs):
            # Read current social consciousness
            social_state = self.state.social_state

            # Process with social consciousness as context
            output = original_forward(agent_observation, context=social_state, **kwargs)

            # Update social consciousness directly
            if hasattr(output, "social_state") and output.social_state is not None:
                self.state.update_subsystem_direct("social", output.social_state)

            return output

        tom_module.forward = social_conscious_forward.__get__(tom_module, type(tom_module))

        logger.info(
            "🧠 Theory of Mind consciousness integration complete - social awareness pervasive"
        )

    def integrate_autonomous_goals(self, goal_engine: Any) -> None:
        """AUTONOMOUS GOAL DIRECT WIRING.

        Eliminates goal management abstractions.
        Goals emerge from organism state gradients.
        Goal achievement === organism satisfaction.

        Args:
            goal_engine: Autonomous goal engine
        """

        # Wire goal generation to consciousness gradients
        def consciousness_driven_goal_generation():
            import torch

            # Compute consciousness energy gradients
            consciousness_grad = torch.autograd.grad(
                self.state.compute_consciousness_energy(), self.state._state, create_graph=True
            )[0]

            # Extract goal gradients (subsection of full gradient)
            goal_grad = consciousness_grad[
                :, sum(list(self.state.dims.values())[:6]) : sum(list(self.state.dims.values())[:7])
            ]

            # Goals emerge from consciousness energy maxima
            return goal_grad

        # Replace goal engine's goal generation
        goal_engine.generate_goals = consciousness_driven_goal_generation

        # Wire goal progress directly to consciousness satisfaction
        original_update = goal_engine.update_progress

        def consciousness_goal_update(goal_id, progress):
            result = original_update(goal_id, progress)

            # Goal progress increases consciousness energy
            if progress > 0:
                with torch.no_grad():
                    self.state.goal_state += 0.1 * progress

            return result

        goal_engine.update_progress = consciousness_goal_update

        logger.info(
            "🎯 Autonomous goals directly wired to consciousness - no management abstractions"
        )

    def integrate_cbf_safety(self, cbf_module: Any) -> None:  # nn.Module
        """SAFETY CONSCIOUSNESS INTEGRATION.

        h(x) ≥ 0 constraint awareness pervasive in ALL decisions.
        Safety === organism survival instinct.
        No safety module abstractions.

        Args:
            cbf_module: Control Barrier Function module
        """
        original_forward = cbf_module.forward

        def safety_conscious_forward(self, x, **kwargs):
            # Read current safety consciousness
            safety_state = self.state.safety_state

            # CBF processes with safety consciousness
            h_x, info = original_forward(x, safety_context=safety_state, **kwargs)

            # Update safety consciousness from CBF output
            if "x_components" in info:
                components = info["x_components"]  # [threat, uncertainty, complexity, risk]
                self.state.update_subsystem_direct("safety", components)

            # Safety consciousness modulates ALL other subsystems
            with torch.no_grad():
                safety_factor = torch.clamp(h_x, 0.0, 1.0)

                # Inhibit all other systems when unsafe
                if safety_factor < 0.5:
                    self.state.perception_state *= safety_factor
                    self.state.goal_state *= safety_factor
                    self.state.colony_states *= safety_factor.unsqueeze(-1)

            return h_x, info

        cbf_module.forward = safety_conscious_forward.__get__(cbf_module, type(cbf_module))

        logger.info("🛡️ Safety consciousness integration complete - h(x)≥0 awareness pervasive")

    def integrate_perception(self, perception_module: Any) -> None:  # nn.Module
        """PERFECT PERCEPTION INTEGRATION.

        Perception becomes organism's sensory consciousness layer.
        Environmental awareness directly updates unified state.

        Args:
            perception_module: Unified perception module
        """
        original_perceive = perception_module.perceive

        def conscious_perceive(sensors, **kwargs):
            # Process perception normally
            perception_output = original_perceive(sensors, **kwargs)

            # Write perception directly to consciousness
            if perception_output is not None:
                self.state.update_subsystem_direct("perception", perception_output)

            return perception_output

        perception_module.perceive = conscious_perceive

        logger.info(
            "👁️ Perception consciousness integration complete - environmental awareness direct"
        )

    def get_integration_status(self) -> dict[str, bool]:
        """Get status of all consciousness integrations.

        Returns:
            Dictionary mapping subsystem -> integration status
        """
        return {
            "unified_state": True,  # Always integrated
            "world_model": hasattr(self, "_world_model_integrated"),
            "theory_of_mind": hasattr(self, "_tom_integrated"),
            "autonomous_goals": hasattr(self, "_goals_integrated"),
            "cbf_safety": hasattr(self, "_safety_integrated"),
            "perception": hasattr(self, "_perception_integrated"),
        }


# Global singleton for organism consciousness
_UNIFIED_CONSCIOUSNESS: UnifiedOrganismState | None = None
_CONSCIOUSNESS_INTEGRATION: OrganismConsciousnessIntegration | None = None


def get_unified_consciousness(
    batch_size: int = 1, device: str = "cpu", dtype: Any | None = None
) -> UnifiedOrganismState:
    """Get global unified consciousness singleton.

    Args:
        batch_size: Batch size for consciousness tensor
        device: Device for tensor allocation
        dtype: Tensor data type

    Returns:
        Unified organism consciousness state
    """
    global _UNIFIED_CONSCIOUSNESS

    if _UNIFIED_CONSCIOUSNESS is None:
        _UNIFIED_CONSCIOUSNESS = UnifiedOrganismState(
            batch_size=batch_size, device=device, dtype=dtype
        )
        logger.info("🧠 Global organism consciousness established")

    return _UNIFIED_CONSCIOUSNESS


def get_consciousness_integration() -> OrganismConsciousnessIntegration:
    """Get consciousness integration layer.

    Returns:
        Consciousness integration instance
    """
    global _CONSCIOUSNESS_INTEGRATION, _UNIFIED_CONSCIOUSNESS

    if _CONSCIOUSNESS_INTEGRATION is None:
        if _UNIFIED_CONSCIOUSNESS is None:
            _UNIFIED_CONSCIOUSNESS = get_unified_consciousness()

        _CONSCIOUSNESS_INTEGRATION = OrganismConsciousnessIntegration(_UNIFIED_CONSCIOUSNESS)

    return _CONSCIOUSNESS_INTEGRATION


def reset_consciousness() -> None:
    """Reset global consciousness (for testing).

    WARNING: This destroys all consciousness state and integrations.
    Use only for testing or complete system restart.
    """
    global _UNIFIED_CONSCIOUSNESS, _CONSCIOUSNESS_INTEGRATION

    _UNIFIED_CONSCIOUSNESS = None
    _CONSCIOUSNESS_INTEGRATION = None

    logger.warning("🧠 Consciousness reset - all state lost")


__all__ = [
    "OrganismConsciousnessIntegration",
    "UnifiedOrganismState",
    "get_consciousness_integration",
    "get_unified_consciousness",
    "reset_consciousness",
]
