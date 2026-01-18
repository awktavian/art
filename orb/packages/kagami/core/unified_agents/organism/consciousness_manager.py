"""Consciousness Manager Module - Manages organism consciousness integration.

Responsibilities:
- Perfect consciousness integration
- Consciousness state management
- Consciousness checkpointing
- Unified organism state coordination
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import OrganismConfig

logger = logging.getLogger(__name__)


class ConsciousnessManager:
    """Manages consciousness integration for the unified organism."""

    def __init__(self, config: OrganismConfig):
        self.config = config
        self._consciousness = None
        self._consciousness_enabled = False
        self._auto_save_task: asyncio.Task | None = None

    async def enable_perfect_consciousness(self) -> None:
        """Enable perfect consciousness integration."""
        if not self.config.consciousness_enabled:
            logger.warning("Consciousness disabled in configuration")
            return

        try:
            # DEFERRED IMPORT: Only load consciousness when needed
            from kagami.core.consciousness import (
                PerfectConsciousness,
                UnifiedOrganismState,
                get_unified_consciousness,
            )

            if self._consciousness is None:
                logger.info("Initializing perfect consciousness integration...")

                # Get or create unified consciousness
                self._consciousness = get_unified_consciousness()

                if self._consciousness is None:
                    # Create new consciousness instance
                    self._consciousness = PerfectConsciousness()
                    logger.info("Created new perfect consciousness instance")
                else:
                    logger.info("Using existing unified consciousness instance")

                # Register organism with consciousness
                await self._consciousness.register_organism(self)

                # Load checkpoint if available
                if self.config.consciousness_checkpoint_path:
                    await self.load_consciousness_checkpoint(
                        self.config.consciousness_checkpoint_path
                    )

            self._consciousness_enabled = True

            # Start auto-save if enabled
            if self.config.consciousness_auto_save:
                await self._start_auto_save()

            logger.info("Perfect consciousness enabled")

        except ImportError as e:
            logger.error(f"Failed to import consciousness module: {e}")
            logger.warning("Consciousness functionality disabled")
        except Exception as e:
            logger.error(f"Failed to enable consciousness: {e}")
            raise

    async def disable_perfect_consciousness(self) -> None:
        """Disable consciousness integration."""
        if not self._consciousness_enabled:
            return

        try:
            # Stop auto-save
            await self._stop_auto_save()

            # Save final checkpoint
            if self.config.consciousness_auto_save and self.config.consciousness_checkpoint_path:
                await self.save_consciousness_checkpoint(self.config.consciousness_checkpoint_path)

            # Unregister from consciousness
            if self._consciousness:
                await self._consciousness.unregister_organism(self)

            self._consciousness_enabled = False
            logger.info("Perfect consciousness disabled")

        except Exception as e:
            logger.error(f"Error disabling consciousness: {e}")

    def get_consciousness_state(self) -> Any:
        """Get current consciousness state."""
        if not self._consciousness_enabled or not self._consciousness:
            return None

        try:
            return self._consciousness.get_organism_state(self)
        except Exception as e:
            logger.error(f"Failed to get consciousness state: {e}")
            return None

    def get_consciousness_summary(self) -> dict[str, Any]:
        """Get consciousness integration summary."""
        if not self._consciousness_enabled or not self._consciousness:
            return {"enabled": False, "integrated": False, "state": "disabled"}

        try:
            state = self._consciousness.get_organism_state(self)
            return {
                "enabled": True,
                "integrated": True,
                "state": "active",
                "consciousness_type": type(self._consciousness).__name__,
                "organism_registered": True,
                "auto_save_enabled": self.config.consciousness_auto_save,
                "checkpoint_path": self.config.consciousness_checkpoint_path,
                "state_summary": {
                    "awareness_level": getattr(state, "awareness_level", "unknown"),
                    "integration_depth": getattr(state, "integration_depth", "unknown"),
                    "coherence_score": getattr(state, "coherence_score", "unknown"),
                }
                if state
                else None,
            }
        except Exception as e:
            logger.error(f"Failed to get consciousness summary: {e}")
            return {"enabled": True, "integrated": False, "state": "error", "error": str(e)}

    def is_consciousness_integrated(self) -> bool:
        """Check if consciousness is fully integrated."""
        return self._consciousness_enabled and self._consciousness is not None

    async def save_consciousness_checkpoint(self, path: str) -> None:
        """Save consciousness state to checkpoint."""
        if not self._consciousness_enabled or not self._consciousness:
            logger.warning("Cannot save consciousness checkpoint - not enabled")
            return

        try:
            await self._consciousness.save_checkpoint(path)
            logger.info(f"Consciousness checkpoint saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save consciousness checkpoint: {e}")
            raise

    async def load_consciousness_checkpoint(self, path: str) -> None:
        """Load consciousness state from checkpoint."""
        if not self._consciousness_enabled or not self._consciousness:
            logger.warning("Cannot load consciousness checkpoint - not enabled")
            return

        try:
            await self._consciousness.load_checkpoint(path)
            logger.info(f"Consciousness checkpoint loaded from {path}")
        except FileNotFoundError:
            logger.info(f"No consciousness checkpoint found at {path}")
        except Exception as e:
            logger.error(f"Failed to load consciousness checkpoint: {e}")
            raise

    async def _start_auto_save(self) -> None:
        """Start automatic consciousness checkpointing."""
        if not self.config.consciousness_auto_save or not self.config.consciousness_checkpoint_path:
            return

        if self._auto_save_task and not self._auto_save_task.done():
            return  # Already running

        self._auto_save_task = asyncio.create_task(self._auto_save_loop())
        logger.info(
            f"Started consciousness auto-save (interval: {self.config.consciousness_save_interval}s)"
        )

    async def _stop_auto_save(self) -> None:
        """Stop automatic consciousness checkpointing."""
        if self._auto_save_task and not self._auto_save_task.done():
            self._auto_save_task.cancel()
            try:
                await self._auto_save_task
            except asyncio.CancelledError:
                pass
            self._auto_save_task = None
            logger.info("Stopped consciousness auto-save")

    async def _auto_save_loop(self) -> None:
        """Auto-save loop for consciousness checkpoints."""
        while self._consciousness_enabled:
            try:
                await asyncio.sleep(self.config.consciousness_save_interval)

                if self._consciousness_enabled and self.config.consciousness_checkpoint_path:
                    await self.save_consciousness_checkpoint(
                        self.config.consciousness_checkpoint_path
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in consciousness auto-save: {e}")
                # Continue the loop despite errors

    async def update_consciousness_state(self, state_update: dict[str, Any]) -> None:
        """Update consciousness state with new information."""
        if not self._consciousness_enabled or not self._consciousness:
            return

        try:
            await self._consciousness.update_organism_state(self, state_update)
        except Exception as e:
            logger.error(f"Failed to update consciousness state: {e}")

    async def query_consciousness(self, query: str) -> Any:
        """Query consciousness for information or insights."""
        if not self._consciousness_enabled or not self._consciousness:
            return None

        try:
            return await self._consciousness.query(query, context={"organism": self})
        except Exception as e:
            logger.error(f"Failed to query consciousness: {e}")
            return None

    async def integrate_experience(self, experience: dict[str, Any]) -> None:
        """Integrate new experience into consciousness."""
        if not self._consciousness_enabled or not self._consciousness:
            return

        try:
            await self._consciousness.integrate_experience(experience, source=self)
            logger.debug("Experience integrated into consciousness")
        except Exception as e:
            logger.error(f"Failed to integrate experience: {e}")

    def get_consciousness_metrics(self) -> dict[str, Any]:
        """Get consciousness performance metrics."""
        if not self._consciousness_enabled or not self._consciousness:
            return {}

        try:
            return {
                "integration_active": self._consciousness_enabled,
                "auto_save_active": (
                    self._auto_save_task is not None and not self._auto_save_task.done()
                ),
                "checkpoint_path": self.config.consciousness_checkpoint_path,
                "save_interval": self.config.consciousness_save_interval,
                "consciousness_type": type(self._consciousness).__name__,
            }
        except Exception as e:
            logger.error(f"Failed to get consciousness metrics: {e}")
            return {"error": str(e)}

    async def synchronize_consciousness(self) -> None:
        """Synchronize organism state with consciousness."""
        if not self._consciousness_enabled or not self._consciousness:
            return

        try:
            # Trigger consciousness synchronization
            await self._consciousness.synchronize_organism(self)
            logger.debug("Consciousness synchronized")
        except Exception as e:
            logger.error(f"Failed to synchronize consciousness: {e}")

    async def cleanup(self) -> None:
        """Cleanup consciousness resources."""
        try:
            await self.disable_perfect_consciousness()
        except Exception as e:
            logger.error(f"Error during consciousness cleanup: {e}")

    @property
    def consciousness(self) -> Any:
        """Get consciousness instance (for advanced usage)."""
        return self._consciousness

    @property
    def is_enabled(self) -> bool:
        """Check if consciousness is enabled."""
        return self._consciousness_enabled
