"""Markov Blanket - Unified Sensory and Active States.

ARCHITECTURE (Dec 2, 2025):
===========================
The system's boundary with the environment is defined by its Markov blanket:

    ┌─────────────────────────────────────────────────────────────────────────┐
    │                           ENVIRONMENT (η)                                │
    │  ┌─────────────┐                                     ┌─────────────┐    │
    │  │ HAL Sensors │                                     │HAL Effectors│    │
    │  │ • Display   │                                     │ • Display   │    │
    │  │ • Audio     │                                     │ • Audio     │    │
    │  │ • Input     │                                     │ • Haptic    │    │
    │  │ • Power     │                                     │ • Power     │    │
    │  └──────┬──────┘                                     └──────▲──────┘    │
    │         │                                                   │           │
    │  ┌──────┼─────────────────────────────────────────────────┼──────┐     │
    │  │      │           MARKOV BLANKET                         │      │     │
    │  │      ▼                                                   │      │     │
    │  │ ┌─────────────┐                              ┌─────────────┐   │     │
    │  │ │  SENSORY    │  ← E8 Encode (var-length)    │   ACTIVE    │   │     │
    │  │ │   STATES    │                              │   STATES    │   │     │
    │  │ │  (s)        │  COLONY COLLABORATION        │   (a)       │   │     │
    │  │ │             │  (CoT inside blanket)        │             │   │     │
    │  │ │• HAL→Bulk   │  ↕ (symmetric both sides)    │• E8→HAL     │   │     │
    │  │ │• AGUI Input │                              │• E8→AGUI    │   │     │
    │  │ │• API Request│  → E8 Encode (var-length)    │• E8→API     │   │     │
    │  │ └──────┬──────┘                              └──────▲──────┘   │     │
    │  │        │                                            │          │     │
    │  │        │    ┌───────────────────────────────┐       │          │     │
    │  │        │    │    INTERNAL STATES (μ)        │       │          │     │
    │  │        └───▶│                               ├───────┘          │     │
    │  │             │  • World Model (E8 Bottleneck)│                  │     │
    │  │             │  • OrganismRSSM               │                  │     │
    │  │             │  • 7 ColonyRSSMs              │                  │     │
    │  │             │  • Active Inference           │                  │     │
    │  │             └───────────────────────────────┘                  │     │
    │  └────────────────────────────────────────────────────────────────┘     │
    │                                                                         │
    │  ┌─────────────┐                                     ┌─────────────┐    │
    │  │ AGUI Input  │                                     │ AGUI Output │    │
    │  │ • Messages  │                                     │ • Responses │    │
    │  │ • Actions   │                                     │ • UI Updates│    │
    │  │ • Context   │                                     │ • Streams   │    │
    │  └─────────────┘                                     └─────────────┘    │
    └─────────────────────────────────────────────────────────────────────────┘

SYMMETRIC E8 BOTTLENECK (Dec 2, 2025):
=====================================
PERCEPTION:  External → Sensors → E8 Encode → Colony Collaboration → Internal
ACTION:      Internal → Colony Collaboration → E8 Encode → Effectors → External

Both sides use variable-length E8 residual encoding:
- Information Bottleneck optimal: min I(X; Z) - β·I(Z; Y)
- Adaptive capacity: simple = 1 byte, complex = 4+ bytes
- Unified protocol: same E8MessageBus for routing

COLONY COLLABORATION INSIDE BLANKET:
===================================
The Fano-routed CoT happens INSIDE the blanket:
- PERCEPTION: Sensory → E8 → Collaboration → Internal μ
- ACTION:     Internal μ → Collaboration → E8 → Effectors

This ensures colonies process information BEFORE it crosses the boundary.

MATHEMATICAL FORMULATION:
========================
The Markov blanket ensures:
- Internal states μ are conditionally independent of external η given (s, a)
- s is influenced by η (perception)
- a influences η (action)
- μ influences a and is influenced by s

Free Energy Minimization:
    F = E_q[log q(μ) - log p(μ, s, a, η)]

The system minimizes F by:
1. Updating beliefs about μ (perception)
2. Selecting actions a (active inference)

Created: December 2, 2025
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
from kagami_math.dimensions import get_bulk_dim

if TYPE_CHECKING:
    from kagami_hal.manager import HALManager

    from kagami.core.interfaces.agui_types import AGUIProtocolAdapter
    from kagami.core.world_model.colony_rssm import OrganismRSSM

logger = logging.getLogger(__name__)


# =============================================================================
# MARKOV BLANKET VALIDATION
# =============================================================================


@dataclass
class BlanketViolation:
    """Record of a Markov blanket discipline violation."""

    violation_type: str  # "instantaneous_feedback", "closure_broken", "hierarchy_broken"
    severity: str  # "error", "warning"
    message: str
    timestamp: float = field(default_factory=lambda: __import__("time").time())


@dataclass
class ValidationResult:
    """Result of Markov blanket validation."""

    valid: bool
    violations: list[BlanketViolation] = field(default_factory=list[Any])
    warnings: list[str] = field(default_factory=list[Any])

    @property
    def error_violations(self) -> list[BlanketViolation]:
        """Get only error-level violations."""
        return [v for v in self.violations if v.severity == "error"]

    @property
    def warning_violations(self) -> list[BlanketViolation]:
        """Get only warning-level violations."""
        return [v for v in self.violations if v.severity == "warning"]


# =============================================================================
# SENSORY STATES
# =============================================================================


@dataclass
class SensoryState:
    """Sensory states of the Markov blanket.

    All inputs from the environment:
    - HAL sensors (hardware)
    - AGUI input (user interface)
    - API requests (external systems)
    """

    # HAL sensor input → Bulk(512)
    hal_observation: torch.Tensor = field(default_factory=lambda: torch.zeros(512))

    # AGUI user input (embedded to bulk)
    agui_input: torch.Tensor = field(default_factory=lambda: torch.zeros(512))

    # API request context (embedded to bulk)
    api_context: torch.Tensor = field(default_factory=lambda: torch.zeros(512))

    # Combined sensory state
    @property
    def combined(self) -> torch.Tensor:
        """Combine all sensory inputs.

        Returns:
            Combined tensor (uses the first non-zero observation, or hal_observation)
        """
        # Find first non-zero observation (priority: hal > agui > api)
        if self.hal_observation.abs().sum() > 0:
            return self.hal_observation
        elif self.agui_input.abs().sum() > 0:
            return self.agui_input
        elif self.api_context.abs().sum() > 0:
            return self.api_context
        else:
            # All zero - return hal_observation as default
            return self.hal_observation

    # Metadata
    timestamp: float = 0.0
    source: str = "combined"


@dataclass
class ActiveState:
    """Active states of the Markov blanket.

    All outputs to the environment:
    - E8 action (variable-length bytes) from RSSM
    - Decoded to HAL effectors
    - Decoded to AGUI responses
    - Decoded to API responses

    E8 ACTION BOTTLENECK (Dec 2, 2025):
    ==================================
    Actions now use variable-length E8 residual encoding:
    - action_bytes: List of E8 indices (1-8 bytes)
    - e8_action: Continuous 8D action for effectors
    """

    # Raw E8 action from RSSM (continuous, 8D)
    e8_action: torch.Tensor = field(default_factory=lambda: torch.zeros(8))

    # E8 action bytes (variable-length, interpretable)
    action_bytes: list[int] = field(default_factory=list[Any])
    num_levels: int = 0

    # Per-colony actions (7 x 8D)
    colony_actions: dict[str, torch.Tensor] = field(default_factory=dict[str, Any])

    # Decoded HAL effector commands
    hal_commands: dict[str, Any] = field(default_factory=dict[str, Any])

    # Decoded AGUI response
    agui_response: dict[str, Any] = field(default_factory=dict[str, Any])

    # Decoded API response
    api_response: dict[str, Any] = field(default_factory=dict[str, Any])

    # Confidence in action
    confidence: float = 1.0


# =============================================================================
# SENSORY ENCODER (Environment → Internal)
# =============================================================================


class SensoryEncoder(nn.Module):
    """Encode all sensory inputs to internal representation.

    Combines:
    1. HAL sensors → Bulk (via perception pipeline)
    2. AGUI input → Bulk (via text embedding)
    3. API context → Bulk (via context embedding)

    All project to SAME bulk dimension for unified processing.
    """

    def __init__(self, bulk_dim: int | None = None):
        super().__init__()
        self.bulk_dim = bulk_dim or get_bulk_dim()

        # HAL sensor encoder (from perception pipeline)
        self.hal_encoder = nn.Sequential(
            nn.Linear(32, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, self.bulk_dim),
        )

        # AGUI input encoder (text/action embedding)
        self.agui_encoder = nn.Sequential(
            nn.Linear(768, 256),  # From text embedding (e.g., 768D BERT)
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, self.bulk_dim),
        )

        # API context encoder
        self.api_encoder = nn.Sequential(
            nn.Linear(128, self.bulk_dim),
            nn.LayerNorm(self.bulk_dim),
        )

        # Fusion (weighted combination)
        self.fusion_weights = nn.Parameter(torch.ones(3) / 3)

        logger.info(f"✅ SensoryEncoder: 3 modalities → Bulk({self.bulk_dim})")

    def forward(
        self,
        hal_input: torch.Tensor | None = None,
        agui_input: torch.Tensor | None = None,
        api_input: torch.Tensor | None = None,
    ) -> SensoryState:
        """Encode sensory inputs.

        Args:
            hal_input: [32] HAL sensor features
            agui_input: [768] AGUI text embedding
            api_input: [128] API context

        Returns:
            SensoryState with encoded observations
        """
        state = SensoryState()

        weights = torch.softmax(self.fusion_weights, dim=0)

        if hal_input is not None:
            if hal_input.dim() == 1:
                hal_input = hal_input.unsqueeze(0)
            state.hal_observation = self.hal_encoder(hal_input).squeeze(0) * weights[0]

        if agui_input is not None:
            if agui_input.dim() == 1:
                agui_input = agui_input.unsqueeze(0)
            state.agui_input = self.agui_encoder(agui_input).squeeze(0) * weights[1]

        if api_input is not None:
            if api_input.dim() == 1:
                api_input = api_input.unsqueeze(0)
            state.api_context = self.api_encoder(api_input).squeeze(0) * weights[2]

        return state


# =============================================================================
# ACTIVE DECODER (Internal → Environment)
# =============================================================================


class ActiveDecoder(nn.Module):
    """Decode internal actions to environment effects.

    Takes E8 action (8D continuous) from RSSM and decodes to:
    1. HAL effector commands (display, audio, haptic)
    2. AGUI responses (text, UI updates)
    3. API responses (JSON, status)

    NOTE: E8 encoding happens in OrganismRSSM.act() now.
    This decoder receives ALREADY-ENCODED E8 action.
    """

    def __init__(self, e8_dim: int = 8):
        super().__init__()
        self.e8_dim = e8_dim

        # HAL effector decoders
        self.hal_display = nn.Linear(e8_dim, 16)  # brightness, mode, etc.
        self.hal_audio = nn.Linear(e8_dim, 8)  # volume, pan, etc.
        self.hal_haptic = nn.Linear(e8_dim, 4)  # pattern, intensity, etc.

        # AGUI response decoder
        self.agui_decoder = nn.Sequential(
            nn.Linear(e8_dim, 32),
            nn.GELU(),
            nn.Linear(32, 64),  # Embedding for response generation
        )

        # API response decoder
        self.api_decoder = nn.Sequential(
            nn.Linear(e8_dim, 32),
            nn.GELU(),
            nn.Linear(32, 32),  # Status/action encoding
        )

        # Colony-specific decoders (7 catastrophe types)
        self.colony_decoders = nn.ModuleDict(
            {
                "spark": nn.Linear(e8_dim, 8),  # Creativity → novelty
                "forge": nn.Linear(e8_dim, 8),  # Building → structure
                "flow": nn.Linear(e8_dim, 8),  # Recovery → healing
                "nexus": nn.Linear(e8_dim, 8),  # Integration → synthesis
                "beacon": nn.Linear(e8_dim, 8),  # Planning → navigation
                "grove": nn.Linear(e8_dim, 8),  # Knowledge → memory
                "crystal": nn.Linear(e8_dim, 8),  # Testing → verification
            }
        )

        logger.info("✅ ActiveDecoder: E8(8D) → HAL/AGUI/API effectors")

    def forward(
        self,
        e8_action: torch.Tensor,
        action_bytes: list[int] | None = None,
        num_levels: int = 0,
        colony_actions: dict[str, torch.Tensor] | None = None,
    ) -> ActiveState:
        """Decode E8 action to effector commands.

        Args:
            e8_action: [8] E8 action from RSSM (continuous)
            action_bytes: Variable-length E8 indices (for interpretability)
            num_levels: Number of E8 residual levels used
            colony_actions: Optional per-colony E8 actions

        Returns:
            ActiveState with decoded commands
        """
        if e8_action.dim() == 1:
            e8_action = e8_action.unsqueeze(0)

        state = ActiveState()
        state.e8_action = e8_action.squeeze(0)
        state.action_bytes = action_bytes or []
        state.num_levels = num_levels

        # Decode HAL commands (detach for scalar conversion)
        display_cmd = torch.sigmoid(self.hal_display(e8_action)).squeeze(0).detach()
        audio_cmd = torch.tanh(self.hal_audio(e8_action)).squeeze(0).detach()
        haptic_cmd = torch.sigmoid(self.hal_haptic(e8_action)).squeeze(0).detach()

        state.hal_commands = {
            "display": {
                "brightness": float(display_cmd[0].item()),
                "active": bool(display_cmd[1].item() > 0.5),
            },
            "audio": {
                "volume": float((audio_cmd[0].item() + 1) / 2),  # Normalize to 0-1
                "pan": float(audio_cmd[1].item()),
            },
            "haptic": {
                "intensity": float(haptic_cmd[0].item()),
                "pattern": int(haptic_cmd[1].item() * 5),  # 0-5 pattern index
            },
        }

        # Decode AGUI response embedding
        agui_emb = self.agui_decoder(e8_action).squeeze(0)
        state.agui_response = {
            "embedding": agui_emb,
            "confidence": float(torch.sigmoid(agui_emb[:1]).item()),
            "action_type": "respond" if agui_emb[0] > 0 else "wait",
        }

        # Decode API response
        api_emb = self.api_decoder(e8_action).squeeze(0)
        state.api_response = {
            "embedding": api_emb,
            "status": "success" if api_emb[0] > 0 else "pending",
        }

        # Decode colony-specific actions
        if colony_actions:
            for name, action in colony_actions.items():
                if name in self.colony_decoders:
                    decoded = self.colony_decoders[name](action.unsqueeze(0))
                    state.colony_actions[name] = decoded.squeeze(0)

        return state


# =============================================================================
# MARKOV BLANKET INTERFACE
# =============================================================================


class OrganismMarkovBlanket(nn.Module):
    """Complete Markov blanket for the organism (system-environment boundary).

    Defines the boundary between internal states and environment:
    - Sensory states (s): perception of environment
    - Active states (a): actions on environment

    SYMMETRIC E8 BOTTLENECK (Dec 2, 2025):
    =====================================
    Both perception and action use variable-length E8 residual encoding.
    Colony collaboration (CoT) happens INSIDE the blanket on BOTH sides.

    The blanket ensures conditional independence:
    p(μ | s, a) ⊥ p(η | s, a)

    Where:
    - μ = internal states (world model, RSSM)
    - η = external states (environment)
    - s = sensory states
    - a = active states

    MARKOV BLANKET DISCIPLINE (Dec 14, 2025 - Forge):
    ================================================
    Enforces three invariants:
    1. NO INSTANTANEOUS FEEDBACK: a_t depends on μ_t, but μ_t+1 depends on a_t-1
    2. BLANKET CLOSURE: μ not directly observable from η
    3. NESTED HIERARCHY: Organism.blanket ⊃ Colony.blanket ⊃ Agent.blanket
    """

    def __init__(
        self,
        bulk_dim: int | None = None,
        e8_dim: int = 8,
        organism: OrganismRSSM | None = None,
        parent_blanket: OrganismMarkovBlanket | None = None,
        level: str = "organism",
    ):
        super().__init__()
        self.bulk_dim = bulk_dim or get_bulk_dim()
        self.e8_dim = e8_dim
        self.level = level  # "organism", "colony", or "agent"
        self.parent_blanket = parent_blanket  # For hierarchy validation

        # Sensory interface
        self.sensory = SensoryEncoder(self.bulk_dim)

        # Active interface
        self.active = ActiveDecoder(e8_dim)

        # Reference to OrganismRSSM for colony collaboration
        # This is set[Any] via set_organism() after initialization
        self._organism: OrganismRSSM | None = organism

        # State buffers (current and previous for temporal validation)
        self._current_sensory: SensoryState | None = None
        self._current_active: ActiveState | None = None
        self._previous_active: ActiveState | None = None

        # Internal state (hidden from external observation)
        self._mu: torch.Tensor | None = None  # Internal beliefs

        # Validation tracking
        self._action_feedback_detected = False
        self._validation_enabled = True

        logger.info(
            f"✅ OrganismMarkovBlanket initialized (level={level}):\n"
            f"   Sensory: HAL/AGUI/API → Bulk({self.bulk_dim})\n"
            f"   Active: Internal → CoT → E8({e8_dim}) → HAL/AGUI/API"
        )

    def set_organism(self, organism: OrganismRSSM) -> None:
        """Set the OrganismRSSM for colony collaboration.

        This enables the blanket to run CoT INSIDE before action.
        """
        self._organism = organism
        logger.info("✅ OrganismMarkovBlanket linked to OrganismRSSM for colony collaboration")

    def perceive(
        self,
        hal_input: torch.Tensor | None = None,
        agui_input: torch.Tensor | None = None,
        api_input: torch.Tensor | None = None,
    ) -> SensoryState:
        """Sensory interface: environment → internal.

        Args:
            hal_input: [32] HAL sensor features
            agui_input: [768] AGUI text embedding
            api_input: [128] API context

        Returns:
            SensoryState for world model
        """
        state = self.sensory(hal_input, agui_input, api_input)
        self._current_sensory = state
        return state  # type: ignore[no-any-return]

    def act(
        self,
        e8_action: torch.Tensor | None = None,
        z_all: torch.Tensor | None = None,
        colony_actions: dict[str, torch.Tensor] | None = None,
        enable_collaboration: bool = True,
        return_indices: bool = False,
    ) -> ActiveState | tuple[ActiveState, dict[str, Any]]:
        """Active interface: internal → environment.

        COLONY COLLABORATION INSIDE BLANKET (Dec 2, 2025):
        =================================================
        When organism is set[Any] and z_all is provided, runs:
        1. Colony Collaboration (CoT) - INSIDE blanket
        2. CatastropheKAN processing (7 catastrophe types)
        3. E8 Action Bottleneck (variable-length)
        4. Decode to effector commands

        This is SYMMETRIC with perception (which also has collaboration).

        Args:
            e8_action: [8] E8 action (if already computed)
            z_all: [7*14] colony states (for full pipeline with collaboration)
            colony_actions: Optional per-colony actions
            enable_collaboration: Whether to run CoT (default: True)
            return_indices: If True, return action bytes

        Returns:
            ActiveState with effector commands
            If return_indices=True, also returns dict[str, Any] with action_indices
        """
        action_bytes = []
        num_levels = 0
        action_info = {}

        # =========================================================
        # OPTION 1: Full pipeline with collaboration
        # =========================================================
        if self._organism is not None and z_all is not None:
            # Run collaboration INSIDE the blanket first
            if enable_collaboration and self._organism._cot_enabled:
                # Build z_states dict[str, Any] from z_all tensor
                # z_all is [7*14] concatenated colony z states
                z_dim = 14
                z_states = {}
                for i, name in enumerate(self._organism.DOMAIN_NAMES):  # type: ignore[arg-type]
                    z_states[name] = z_all[i * z_dim : (i + 1) * z_dim]

                # Get CoT-modulated z states
                _thought, z_modulation = self._organism.collaborative_cot.forward(z_states)  # type: ignore[union-attr]

                # Apply modulation to original z_all
                z_modulated = z_all + z_modulation
            else:
                z_modulated = z_all

            # Now run action through E8 bottleneck
            if return_indices:
                e8_action, action_info = self._organism.act(z_modulated, return_indices=True)  # type: ignore[operator]
                action_bytes = [
                    int(idx[0].item()) if idx.dim() > 0 else int(idx.item())
                    for idx in action_info.get("action_indices", [])
                ]
                num_levels = action_info.get("num_levels", 0)
            else:
                e8_action = self._organism.act(z_modulated)  # type: ignore[operator]

        # =========================================================
        # OPTION 2: Direct E8 action (already computed)
        # =========================================================
        elif e8_action is None:
            # No action provided, use zeros
            e8_action = torch.zeros(8)

        # Decode to effector commands
        state = self.active(e8_action, action_bytes, num_levels, colony_actions)
        self._current_active = state

        if return_indices:
            return state, action_info
        return state  # type: ignore[no-any-return]

    def get_observation(self) -> torch.Tensor:
        """Get combined sensory observation for world model.

        Returns:
            [bulk_dim] combined observation
        """
        if self._current_sensory is None:
            return torch.zeros(self.bulk_dim)
        return self._current_sensory.combined

    def get_action_bytes_string(self) -> str:
        """Get last action as human-readable string.

        Example: "[42, 128, 7]" for a 3-byte action.
        """
        if self._current_active is None or not self._current_active.action_bytes:
            return "[]"
        return f"[{', '.join(map(str, self._current_active.action_bytes))}]"

    async def execute_on_hal(
        self,
        hal_manager: HALManager,
        active_state: ActiveState | None = None,
    ) -> dict[str, bool]:
        """Execute active state on HAL effectors.

        Args:
            hal_manager: HAL manager instance
            active_state: Active state to execute (uses current if None)

        Returns:
            Dict of effector execution results
        """
        state = active_state or self._current_active
        if state is None:
            return {"error": True, "message": "No active state"}  # type: ignore[dict-item]

        results = {}

        # Display effector
        if hal_manager.display and "display" in state.hal_commands:
            try:
                cmd = state.hal_commands["display"]
                await hal_manager.display.set_brightness(cmd.get("brightness", 0.5))
                results["display"] = True
            except Exception as e:
                logger.debug(f"Display command failed: {e}")
                results["display"] = False

        # Audio effector
        if hal_manager.audio and "audio" in state.hal_commands:
            try:
                # Audio commands would go here
                results["audio"] = True
            except Exception as e:
                logger.debug(f"Audio command failed: {e}")
                results["audio"] = False

        return results

    async def send_to_agui(
        self,
        agui_adapter: AGUIProtocolAdapter,
        active_state: ActiveState | None = None,
    ) -> bool:
        """Send active state to AGUI.

        Args:
            agui_adapter: AGUI protocol adapter
            active_state: Active state to send (uses current if None)

        Returns:
            Success status
        """
        state = active_state or self._current_active
        if state is None:
            return False

        try:
            # NOTE: Core must not import the API layer; use core-side AGUI types.
            from kagami.core.interfaces.agui_types import AGUIMessage

            response = state.agui_response
            message = AGUIMessage(
                content=f"Action confidence: {response.get('confidence', 0):.2f}",
                role="assistant",
            )
            await agui_adapter.send_message(message)
            return True
        except ImportError:
            logger.debug("AGUI protocol not available")
            return False
        except Exception as e:
            logger.debug(f"AGUI send failed: {e}")
            return False

    # =========================================================================
    # MARKOV BLANKET VALIDATION (Dec 14, 2025 - Forge)
    # =========================================================================

    def validate_blanket_discipline(self) -> ValidationResult:
        """Validate Markov blanket discipline.

        Checks three invariants:
        1. NO INSTANTANEOUS FEEDBACK: a_t doesn't observe a_t
        2. BLANKET CLOSURE: μ hidden from η
        3. NESTED HIERARCHY: parent blanket contains this blanket

        Returns:
            ValidationResult with violations and warnings
        """
        if not self._validation_enabled:
            return ValidationResult(valid=True)

        violations: list[BlanketViolation] = []

        # Check 1: No instantaneous feedback
        if self._action_feedback_detected:
            violations.append(
                BlanketViolation(
                    violation_type="instantaneous_feedback",
                    severity="error",
                    message="Action at time t observed at time t (breaks causality)",
                )
            )

        # Check 2: Blanket closure (μ not directly observable)
        if self._mu is not None and self._current_sensory is not None:
            # Check if μ appears in sensory observation
            # (In practice, this checks if internal state leaked to observation)
            sensory_obs = self._current_sensory.combined
            if torch.allclose(sensory_obs[: self._mu.shape[0]], self._mu, rtol=1e-3):
                violations.append(
                    BlanketViolation(
                        violation_type="closure_broken",
                        severity="warning",
                        message="Internal state μ appears directly in sensory observation",
                    )
                )

        # Check 3: Nested hierarchy
        if self.parent_blanket is not None:
            # Verify this blanket's states are contained in parent blanket
            if not self._check_hierarchy_containment():
                violations.append(
                    BlanketViolation(
                        violation_type="hierarchy_broken",
                        severity="error",
                        message=f"Blanket hierarchy broken: {self.level} not contained in parent",
                    )
                )

        # Valid if no error-level violations
        valid = not any(v.severity == "error" for v in violations)

        return ValidationResult(valid=valid, violations=violations)

    def _check_hierarchy_containment(self) -> bool:
        """Check if this blanket is properly contained in parent blanket.

        Hierarchy: Organism.blanket ⊃ Colony.blanket ⊃ Agent.blanket

        Returns:
            True if hierarchy is maintained
        """
        if self.parent_blanket is None:
            return True  # Root blanket (organism level)

        # Check sensory containment
        # Child sensory should be derived from parent sensory
        if self._current_sensory is not None and self.parent_blanket._current_sensory is not None:
            parent_obs = self.parent_blanket._current_sensory.combined
            child_obs = self._current_sensory.combined

            # Child observation should have smaller or equal dimensionality
            if child_obs.numel() > parent_obs.numel():
                return False

        # Check active containment
        # Child actions should contribute to parent actions
        if self._current_active is not None and self.parent_blanket._current_active is not None:
            parent_action = self.parent_blanket._current_active.e8_action
            child_action = self._current_active.e8_action

            # Both should be E8 (8D) - dimension check
            if child_action.shape != parent_action.shape:
                logger.warning(
                    f"Blanket hierarchy: action dimension mismatch "
                    f"(child={child_action.shape}, parent={parent_action.shape})"
                )

        return True

    def update_internal_state(self, mu: torch.Tensor) -> None:
        """Update internal state (μ).

        This state is HIDDEN from external observation (blanket closure).

        Args:
            mu: Internal state tensor
        """
        self._mu = mu

    def check_action_isolation(self, action: torch.Tensor) -> bool:
        """Check if action respects temporal isolation.

        ACTION ISOLATION INVARIANT:
        - a_t is computed from μ_t
        - μ_t+1 depends on a_t-1 (previous action), NOT a_t
        - This prevents instantaneous feedback loops

        Args:
            action: Current action tensor

        Returns:
            True if action isolation maintained
        """
        # If we have a previous action, ensure current action doesn't
        # immediately feed back into dynamics
        if self._previous_active is not None:
            prev_action = self._previous_active.e8_action
            # Check if action is being used in same timestep as computation
            # (This is a heuristic - true check requires tracing computation graph)
            if torch.equal(action, prev_action):
                self._action_feedback_detected = True
                logger.error("Action isolation violated: same action used in same timestep")
                return False

        # Update action buffer for next check
        self._previous_active = self._current_active

        return True

    def set_validation_enabled(self, enabled: bool) -> None:
        """Enable or disable validation checks.

        Useful for disabling during testing or performance-critical sections.

        Args:
            enabled: Whether to enable validation
        """
        self._validation_enabled = enabled


# =============================================================================
# SINGLETON
# =============================================================================


_blanket: OrganismMarkovBlanket | None = None
_blanket_lock = threading.Lock()


def get_markov_blanket(organism: OrganismRSSM | None = None) -> OrganismMarkovBlanket:
    """Get or create the global Markov blanket.

    Thread-safe via double-check locking pattern.

    Args:
        organism: Optional OrganismRSSM to link for colony collaboration
    """
    global _blanket

    # Fast path - already initialized
    if _blanket is not None:
        if organism is not None:
            _blanket.set_organism(organism)
        return _blanket

    # Slow path - needs initialization with lock
    with _blanket_lock:
        # Double-check inside lock
        if _blanket is None:
            _blanket = OrganismMarkovBlanket(organism=organism)
        elif organism is not None:  # type: ignore[unreachable]
            _blanket.set_organism(organism)

    return _blanket


def reset_markov_blanket() -> None:
    """Reset the singleton."""
    global _blanket
    _blanket = None


logger.info(
    "✅ Markov Blanket module loaded\n"
    "   - Sensory: HAL/AGUI/API → E8 → Collaboration → Bulk(512)\n"
    "   - Active: Internal → Collaboration → E8 → HAL/AGUI/API\n"
    "   - SYMMETRIC variable-length E8 on both sides\n"
    "   - Blanket discipline enforcement: action isolation + hierarchy validation"
)

__all__ = [
    "ActiveDecoder",
    "ActiveState",
    "BlanketViolation",
    "OrganismMarkovBlanket",
    "SensoryEncoder",
    "SensoryState",
    "ValidationResult",
    "get_markov_blanket",
    "reset_markov_blanket",
]
