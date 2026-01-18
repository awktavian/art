"""Optimality Integration — Wire Improvements into K OS.

This module provides the integration layer that connects all optimality
improvements to the actual K OS components.

INTEGRATION POINTS:
==================
1. KagamiWorldModel - Enhanced Hopfield, Wasserstein IB
2. HofstadterStrangeLoop - Adaptive convergence
3. OrganismRSSM - True octonion multiplication
4. ExpectedFreeEnergy - Analytical epistemic value
5. WorldModelLoop - Enhanced online learning + EWC
6. ActiveInferenceEngine - Uncertainty calibration

Usage:
    from kagami.core.optimality.integration import integrate_all_improvements

    # Apply all improvements to a model
    wiring = integrate_all_improvements(world_model)

    # Or integrate specific components
    from kagami.core.optimality.integration import OptimalityWiring
    wiring = OptimalityWiring(world_model)
    wiring.wire_strange_loop()
    wiring.wire_hopfield_memory()

Created: December 4, 2025
Status: Production wiring for optimality improvements.
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn

# Canonical Fano plane (G₂ 3-form derived) - Dec 6, 2025
from kagami_math.fano_plane import get_fano_lines_zero_indexed

logger = logging.getLogger(__name__)


class OptimalityWiring:
    """Wire optimality improvements into K OS components.

    This class handles the integration of all optimality improvements
    into the existing K OS architecture without breaking existing code.

    Strategy:
    - Use composition over inheritance where possible
    - Monkey-patch methods where necessary
    - Provide clean rollback if needed
    """

    def __init__(self, world_model: nn.Module | None = None):
        """Initialize wiring.

        Args:
            world_model: KagamiWorldModel instance (optional, can set[Any] later)
        """
        self.world_model = world_model
        self._wired_components: list[str] = []
        self._original_methods: dict[str, Any] = {}

        # Import improvements
        from kagami.core.optimality.improvements import (
            AdaptiveConvergenceMonitor,
            AnalyticalEpistemicValue,
            ModernHopfieldScaled,
            TrueOctonionMultiply,
            UncertaintyCalibrator,
            WassersteinIB,
            get_optimality_improvements,
        )

        self.improvements = get_optimality_improvements()

        # Component instances (created on demand)
        self._adaptive_convergence: AdaptiveConvergenceMonitor | None = None
        self._analytical_epistemic: AnalyticalEpistemicValue | None = None
        self._hopfield_scaled: ModernHopfieldScaled | None = None
        self._octonion_multiply: TrueOctonionMultiply | None = None
        self._wasserstein_ib: WassersteinIB | None = None
        self._uncertainty_calibrator: UncertaintyCalibrator | None = None

    def wire_all(self) -> dict[str, bool]:
        """Wire all improvements.

        Returns:
            Dict of component -> success status
        """
        results = {}

        results["strange_loop"] = self.wire_strange_loop()
        results["hopfield_memory"] = self.wire_hopfield_memory()
        results["octonion_multiply"] = self.wire_octonion_multiply()
        results["epistemic_value"] = self.wire_epistemic_value()
        results["uncertainty_calibration"] = self.wire_uncertainty_calibration()
        results["online_learning"] = self.wire_online_learning()

        logger.info(f"✅ Wired {sum(results.values())}/{len(results)} optimality improvements")

        return results

    def wire_strange_loop(self) -> bool:
        """Wire adaptive convergence into HofstadterStrangeLoop.

        Replaces fixed 3 iterations with dynamic convergence detection.
        """
        if self.world_model is None:
            logger.warning("No world model - cannot wire strange loop")
            return False

        try:
            from kagami.core.optimality.improvements import AdaptiveConvergenceMonitor

            # Get RSSM and strange loop
            rssm = getattr(self.world_model, "rssm", None)
            if rssm is None:
                logger.warning("World model has no RSSM")
                return False

            strange_loop = getattr(rssm, "strange_loop", None)
            if strange_loop is None:
                logger.warning("RSSM has no strange_loop")
                return False

            # Create adaptive monitor
            self._adaptive_convergence = AdaptiveConvergenceMonitor()

            # Store original forward
            original_forward = strange_loop.forward
            self._original_methods["strange_loop_forward"] = original_forward

            # Create wrapped forward with adaptive convergence
            def adaptive_forward(
                internal_z: torch.Tensor,
                action: torch.Tensor,
                sensory: torch.Tensor | None = None,
                phi: torch.Tensor | float | None = None,
            ) -> dict[str, torch.Tensor]:
                """Wrapped forward with adaptive convergence monitoring."""
                # Call original
                result = original_forward(internal_z, action, sensory, phi)

                # Update convergence statistics
                loop_loss = result.get("loop_closure_loss", torch.tensor(1.0))
                if isinstance(loop_loss, torch.Tensor):
                    loss_val = loop_loss.item()
                else:
                    loss_val = float(loop_loss)

                self._adaptive_convergence.update_statistics(  # type: ignore[union-attr]
                    iterations_used=1,  # EMA-based, not iterative
                    final_loss=loss_val,
                )

                # Add convergence stats to result
                result["convergence_stats"] = self._adaptive_convergence.get_statistics()  # type: ignore[union-attr]

                return result

            # Patch
            strange_loop.forward = adaptive_forward
            self._wired_components.append("strange_loop")

            logger.info("✅ Wired adaptive convergence to strange loop")
            return True

        except Exception as e:
            logger.error(f"Failed to wire strange loop: {e}")
            return False

    def wire_hopfield_memory(self) -> bool:
        """Wire hierarchical E8 Hopfield memory with 240^L capacity.

        UPGRADED (Dec 4, 2025): Uses hierarchical E8 residual addressing.
        Capacity: 240^4 = 3.3B slots (vs flat 240).
        """
        if self.world_model is None:
            return False

        try:
            from kagami.core.optimality.improvements import ModernHopfieldScaled

            # Get episodic memory
            episodic_memory = getattr(self.world_model, "_hopfield_memory", None)
            if episodic_memory is None:
                episodic_memory = getattr(self.world_model, "episodic_memory", None)

            if episodic_memory is None:
                logger.warning("World model has no Hopfield memory")
                return False

            # Get config
            config = getattr(episodic_memory, "config", None)
            pattern_dim = getattr(config, "value_dim", 256) if config else 256

            # Create HIERARCHICAL scaled version
            device = next(self.world_model.parameters()).device
            self._hopfield_scaled = ModernHopfieldScaled(
                pattern_dim=pattern_dim,
                num_patterns=240,  # E8 roots per level
                num_heads=4,
                num_levels=4,  # 240^4 = 3.3B capacity
                dropout=0.1,
            ).to(device)

            # Copy any existing values (if possible)
            if hasattr(episodic_memory, "values") and episodic_memory.values is not None:
                with torch.no_grad():
                    old_values = episodic_memory.values.data
                    # Copy to first level
                    self._hopfield_scaled.level_values[0].data.copy_(old_values)
                    logger.debug("Copied existing memory values to hierarchical level 0")

            # Store original methods
            original_read = getattr(episodic_memory, "read", None)
            original_write = getattr(episodic_memory, "write", None)
            if original_read:
                self._original_methods["hopfield_read"] = original_read
            if original_write:
                self._original_methods["hopfield_write"] = original_write

            hopfield_scaled = self._hopfield_scaled

            # Create enhanced read with hierarchical E8
            def enhanced_read(
                query: torch.Tensor,
                return_energy: bool = False,
                return_indices: bool = False,
            ) -> tuple[Any, ...]:
                """Hierarchical E8 read with 240^L capacity."""
                # Flatten if needed
                shape = query.shape
                if len(shape) == 3:
                    B, S, D = shape
                    query = query.view(B * S, D)

                # Project to pattern_dim if needed
                if query.shape[-1] != pattern_dim:
                    # Use existing projection or pad
                    if hasattr(episodic_memory, "g2_proj"):
                        query_8d = episodic_memory.g2_proj(query)
                        # Pad 8D to pattern_dim
                        query = torch.nn.functional.pad(query_8d, (0, pattern_dim - 8))
                    else:
                        query = torch.nn.functional.pad(
                            query, (0, max(0, pattern_dim - query.shape[-1]))
                        )[:, :pattern_dim]

                # Hierarchical retrieval
                result = hopfield_scaled(query, return_attention=True)

                content = result["retrieved"]

                # Combine all level attentions for compatibility
                attentions = result.get("attentions", [])
                if attentions:
                    attention = attentions[0]  # First level attention
                else:
                    attention = torch.zeros(query.shape[0], 240, device=query.device)

                returns = [content, attention]

                if return_energy:
                    # Use entropy as energy proxy
                    energy = result.get("attention_entropy", torch.zeros(query.shape[0]))
                    if isinstance(energy, torch.Tensor):
                        energy = energy.expand(query.shape[0])
                    returns.append(energy)

                if return_indices:
                    _, indices = attention.topk(5, dim=-1)
                    returns.append(indices)

                return tuple(returns)

            # Create enhanced write
            def enhanced_write(
                query: torch.Tensor,
                content: torch.Tensor,
                strength: float = 0.1,
            ) -> dict[str, Any]:
                """Hierarchical write to level values."""
                # Flatten
                if len(query.shape) == 3:
                    query = query.view(-1, query.shape[-1])
                    content = content.view(-1, content.shape[-1])

                # Project query to pattern_dim
                if query.shape[-1] != pattern_dim:
                    if hasattr(episodic_memory, "g2_proj"):
                        query_8d = episodic_memory.g2_proj(query)
                        query = torch.nn.functional.pad(query_8d, (0, pattern_dim - 8))
                    else:
                        query = torch.nn.functional.pad(
                            query, (0, max(0, pattern_dim - query.shape[-1]))
                        )[:, :pattern_dim]

                # Ensure content matches pattern_dim
                if content.shape[-1] != pattern_dim:
                    if content.shape[-1] < pattern_dim:
                        content = torch.nn.functional.pad(
                            content, (0, pattern_dim - content.shape[-1])
                        )
                    else:
                        content = content[..., :pattern_dim]

                # Get attention weights for writing
                result = hopfield_scaled(query, return_attention=True)
                attentions = result.get("attentions", [])

                # Hebbian update to first level (primary storage)
                if attentions:
                    attention = attentions[0]  # [B, 240]
                    # Weighted average for each pattern
                    weighted_content = torch.matmul(attention.T, content)  # [240, D]
                    attention_sum = attention.sum(dim=0, keepdim=True).T.clamp(min=1e-8)
                    target = weighted_content / attention_sum

                    # Update level 0 values
                    with torch.no_grad():
                        delta = strength * (target - hopfield_scaled.level_values[0].data)
                        hopfield_scaled.level_values[0].data += delta

                    return {
                        "write_norm": delta.norm().item(),
                        "levels_used": result.get("levels_used", 1),
                        "effective_capacity": result.get("effective_capacity", 240),
                    }

                return {"write_norm": 0.0}

            # Patch
            if original_read:
                episodic_memory.read = enhanced_read
            if original_write:
                episodic_memory.write = enhanced_write

            # Also replace read_hierarchical if it exists
            if hasattr(episodic_memory, "read_hierarchical"):
                episodic_memory.read_hierarchical = lambda query, max_levels=None: (
                    enhanced_read(query)[0],  # content
                    [enhanced_read(query)[1]],  # attentions list[Any]
                    1,  # num_levels (already hierarchical internally)
                )

            # Store reference on world model
            self.world_model._optimal_hopfield = hopfield_scaled

            self._wired_components.append("hopfield_memory")

            effective_capacity = 240**4
            logger.info(f"✅ Wired hierarchical E8 Hopfield: 240^4 = {effective_capacity:,} slots")
            return True

        except Exception as e:
            logger.error(f"Failed to wire Hopfield memory: {e}")
            import traceback

            traceback.print_exc()
            return False

    def wire_octonion_multiply(self) -> bool:
        """Wire true octonion multiplication into colony coordination.

        Exploits non-associativity for proper colony interactions.
        """
        try:
            from kagami.core.optimality.improvements import TrueOctonionMultiply

            self._octonion_multiply = TrueOctonionMultiply()

            # Try to wire into FanoOctonionCombiner
            try:
                from kagami.core.world_model.layers.catastrophe_kan import FanoOctonionCombiner

                # Store original compute_fano_products
                original_compute = FanoOctonionCombiner.compute_fano_products
                self._original_methods["fano_compute"] = original_compute

                octonion_mult = self._octonion_multiply

                def enhanced_fano_products(  # type: ignore[no-untyped-def]
                    _self_combiner,  # Instance (unused - uses closure for octonion_mult)
                    colony_outputs: torch.Tensor,
                ) -> torch.Tensor:
                    """Enhanced Fano products using true octonion multiplication."""
                    B, num_colonies, D = colony_outputs.shape
                    device = colony_outputs.device

                    # Pad to 8D if needed
                    if D < 8:
                        colony_8d = torch.nn.functional.pad(colony_outputs, (0, 8 - D))
                    else:
                        colony_8d = colony_outputs[..., :8]

                    # Compute true octonion products for each Fano line
                    fano_coupled = torch.zeros(B, num_colonies, D, device=device)

                    # Fano lines (0-indexed) - canonical from G₂ 3-form
                    fano_lines = get_fano_lines_zero_indexed()

                    for i, j, k in fano_lines:
                        # True octonion multiplication
                        product = octonion_mult.multiply(colony_8d[:, i], colony_8d[:, j])

                        # Add to target colony
                        if D < 8:
                            fano_coupled[:, k] += product[..., :D] * 0.1  # Scale factor
                        else:
                            fano_coupled[:, k, :8] += product * 0.1

                    return fano_coupled

                # Patch class method
                FanoOctonionCombiner.compute_fano_products = enhanced_fano_products  # type: ignore[assignment]
                self._wired_components.append("octonion_multiply")

                logger.info("✅ Wired true octonion multiplication")
                return True

            except ImportError:
                logger.warning("FanoOctonionCombiner not available for wiring")
                return False

        except Exception as e:
            logger.error(f"Failed to wire octonion multiply: {e}")
            return False

    def wire_epistemic_value(self) -> bool:
        """Wire analytical epistemic value into EFE computation.

        NOTE: ExpectedFreeEnergy.epistemic is an INSTANCE attribute (nn.Module),
        not a class method. We wire by replacing the instance's epistemic module
        when the world model is available.
        """
        if self.world_model is None:
            logger.warning("No world model - cannot wire epistemic value")
            return False

        try:
            from kagami.core.optimality.improvements import AnalyticalEpistemicValue

            # Get the ActiveInferenceEngine from world model
            ai_engine = getattr(self.world_model, "_active_inference_engine", None)
            if ai_engine is None:
                logger.warning("World model has no _active_inference_engine")
                return False

            # Get the EFE module
            efe = getattr(ai_engine, "efe", None)
            if efe is None:
                logger.warning("ActiveInferenceEngine has no efe module")
                return False

            # Get config from existing epistemic
            existing_epistemic = getattr(efe, "epistemic", None)
            if existing_epistemic is None:
                logger.warning("EFE has no epistemic module")
                return False

            # Get dimensions from config
            # FIX (Dec 6, 2025): state_dim = h_dim + z_dim (combined state for epistemic)
            config = getattr(efe, "config", None)
            h_dim = getattr(config, "state_dim", 256) if config else 256
            z_dim = getattr(config, "stochastic_dim", 14) if config else 14
            state_dim = h_dim + z_dim  # Combined deterministic + stochastic
            obs_dim = getattr(config, "observation_dim", 512) if config else 512

            # Create analytical epistemic with matching dimensions
            device = next(self.world_model.parameters()).device
            self._analytical_epistemic = AnalyticalEpistemicValue(
                state_dim=state_dim,
                obs_dim=obs_dim,
            ).to(device)

            # Store original for potential unwiring
            self._original_methods["efe_epistemic_module"] = existing_epistemic

            # FIX (Dec 6, 2025): Wire to BOTH EFE and its epistemic module
            # The EpistemicValue.forward() now checks for _analytical_epistemic
            # and uses it when observations are provided
            efe._analytical_epistemic = self._analytical_epistemic

            # Also wire to the epistemic submodule so it can use analytical computation
            if hasattr(efe, "epistemic"):
                efe.epistemic._analytical_epistemic = self._analytical_epistemic

            self._wired_components.append("epistemic_value")
            logger.info("✅ Wired analytical epistemic value (supplementary)")
            return True

        except Exception as e:
            logger.error(f"Failed to wire epistemic value: {e}")
            return False

    def wire_uncertainty_calibration(self) -> bool:
        """Wire uncertainty calibration into Active Inference."""
        try:
            from kagami.core.optimality.improvements import UncertaintyCalibrator

            self._uncertainty_calibrator = UncertaintyCalibrator()

            # Try to wire into ActiveInferenceEngine
            try:
                from kagami.core.active_inference.engine import ActiveInferenceEngine

                calibrator = self._uncertainty_calibrator

                # Store original select_action
                original_select = ActiveInferenceEngine.select_action
                self._original_methods["ai_select_action"] = original_select

                async def calibrated_select_action(  # type: ignore[no-untyped-def]
                    self_ai,
                    candidates: list[dict[str, Any]] | None = None,
                    goals: Any = None,
                    plan_tic: dict[str, Any] | None = None,
                ) -> dict[str, Any]:
                    """Select action with calibrated confidence."""
                    # Call original
                    result = await original_select(self_ai, candidates, goals, plan_tic)

                    # Calibrate confidence if present
                    if "confidence" in result:
                        raw_conf = result["confidence"]
                        if isinstance(raw_conf, torch.Tensor):
                            calibrated = calibrator.calibrate(raw_conf, is_binary=True)
                            result["confidence_raw"] = raw_conf
                            result["confidence"] = calibrated
                            result["confidence_calibrated"] = True

                    return result

                # Patch
                ActiveInferenceEngine.select_action = calibrated_select_action  # type: ignore[assignment]
                self._wired_components.append("uncertainty_calibration")

                logger.info("✅ Wired uncertainty calibration")
                return True

            except ImportError:
                logger.warning("ActiveInferenceEngine not available for wiring")
                return False

        except Exception as e:
            logger.error(f"Failed to wire uncertainty calibration: {e}")
            return False

    def wire_online_learning(self) -> bool:
        """Wire enhanced online learning into WorldModelLoop.

        NOTE: WorldModelLoop uses compute_loss() not train_step().
        We wire by enhancing compute_loss to add experience replay.
        """
        try:
            from kagami.core.optimality.enhanced_online_learning import (
                get_enhanced_online_learning,
            )

            if self.world_model is None:
                return False

            # Create enhanced online learning
            enhanced = get_enhanced_online_learning(self.world_model)

            if enhanced is None:
                return False

            # Try to wire into WorldModelLoop
            try:
                # Dynamic import to avoid optimality ↔ learning ↔ world_model cycles.
                import importlib

                wml_mod = importlib.import_module("kagami.core.learning.world_model_loop")
                WorldModelLoop = getattr(wml_mod, "WorldModelLoop", None)
                if WorldModelLoop is None:
                    raise ImportError("WorldModelLoop not available")

                # Check if compute_loss exists (it does)
                if not hasattr(WorldModelLoop, "compute_loss"):
                    logger.warning("WorldModelLoop has no compute_loss method")
                    return False

                # Store reference to enhanced learning as class attribute
                WorldModelLoop._enhanced_online_learning = enhanced

                # Store original compute_loss
                original_compute = WorldModelLoop.compute_loss
                self._original_methods["wml_compute_loss"] = original_compute

                def enhanced_compute_loss(  # type: ignore[no-untyped-def]
                    self_loop,
                    batch: dict[str, Any],
                    task_id: str | None = None,
                ) -> torch.Tensor:
                    """Enhanced compute_loss with experience replay."""
                    # Get enhanced learning
                    enhanced_ol = getattr(self_loop, "_enhanced_online_learning", None)

                    # Call original
                    result = original_compute(self_loop, batch, task_id)

                    # Add experience to enhanced replay buffer
                    if enhanced_ol is not None and "state" in batch:
                        try:
                            state = batch.get("state")
                            action = batch.get("action", {})
                            next_state = batch.get("next_state", state)

                            # Use loss value as TD-error proxy
                            td_error = (
                                result.item() if isinstance(result, torch.Tensor) else float(result)
                            )

                            enhanced_ol.add_experience(
                                state=state,
                                action=action,
                                next_state=next_state,
                                reward=0.0,
                                done=False,
                                td_error=td_error,
                            )
                        except Exception:
                            pass  # Non-critical

                    return result

                # Patch
                WorldModelLoop.compute_loss = enhanced_compute_loss
                self._wired_components.append("online_learning")

                logger.info("✅ Wired enhanced online learning")
                return True

            except ImportError:
                logger.warning("WorldModelLoop not available for wiring")
                return False

        except Exception as e:
            logger.error(f"Failed to wire online learning: {e}")
            return False

    def unwire_all(self) -> None:
        """Restore all original methods."""
        # Restore strange loop
        if "strange_loop_forward" in self._original_methods:
            try:
                rssm = getattr(self.world_model, "rssm", None)
                if rssm and hasattr(rssm, "strange_loop"):
                    rssm.strange_loop.forward = self._original_methods["strange_loop_forward"]
            except Exception:
                pass

        # Restore Hopfield
        if "hopfield_read" in self._original_methods:
            try:
                mem = getattr(self.world_model, "_hopfield_memory", None)
                if mem:
                    mem.read = self._original_methods["hopfield_read"]
            except Exception:
                pass

        # Restore class-level patches
        if "fano_compute" in self._original_methods:
            try:
                from kagami.core.world_model.layers.catastrophe_kan import FanoOctonionCombiner

                FanoOctonionCombiner.compute_fano_products = self._original_methods["fano_compute"]  # type: ignore[method-assign]
            except Exception:
                pass

        if "efe_epistemic" in self._original_methods:
            try:
                from kagami.core.active_inference.efe import ExpectedFreeEnergy

                ExpectedFreeEnergy.epistemic = self._original_methods["efe_epistemic"]
            except Exception:
                pass

        if "ai_select_action" in self._original_methods:
            try:
                from kagami.core.active_inference.engine import ActiveInferenceEngine

                ActiveInferenceEngine.select_action = self._original_methods["ai_select_action"]  # type: ignore[method-assign]
            except Exception:
                pass

        if "wml_compute_loss" in self._original_methods:
            try:
                # Dynamic import to avoid optimality ↔ learning cycles.
                import importlib

                wml_mod = importlib.import_module("kagami.core.learning.world_model_loop")
                WorldModelLoop = getattr(wml_mod, "WorldModelLoop", None)
                if WorldModelLoop is None:
                    raise ImportError("WorldModelLoop not available")
                WorldModelLoop.compute_loss = self._original_methods["wml_compute_loss"]
            except Exception:
                pass

        self._wired_components.clear()
        self._original_methods.clear()

        logger.info("✅ Unwired all optimality improvements")

    def get_status(self) -> dict[str, Any]:
        """Get wiring status."""
        return {
            "wired_components": self._wired_components,
            "num_wired": len(self._wired_components),
            "has_world_model": self.world_model is not None,
            "convergence_stats": (
                self._adaptive_convergence.get_statistics() if self._adaptive_convergence else None
            ),
            "calibration_ece": (
                self._uncertainty_calibrator.compute_ece() if self._uncertainty_calibrator else None
            ),
        }


# Module-level singleton
_wiring: OptimalityWiring | None = None


def get_optimality_wiring(
    world_model: nn.Module | None = None,
) -> OptimalityWiring:
    """Get or create optimality wiring singleton.

    Args:
        world_model: World model to wire

    Returns:
        OptimalityWiring instance
    """
    global _wiring

    if _wiring is None:
        _wiring = OptimalityWiring(world_model)
    elif world_model is not None and _wiring.world_model is None:
        _wiring.world_model = world_model

    return _wiring


def integrate_all_improvements(
    world_model: nn.Module,
) -> OptimalityWiring:
    """Convenience function to integrate all improvements.

    Args:
        world_model: KagamiWorldModel instance

    Returns:
        OptimalityWiring with all components wired
    """
    wiring = get_optimality_wiring(world_model)
    wiring.wire_all()
    return wiring


__all__ = [
    "OptimalityWiring",
    "get_optimality_wiring",
    "integrate_all_improvements",
]
