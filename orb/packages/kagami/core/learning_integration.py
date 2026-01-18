"""
K os Learning Integration
"""

import logging
import time
from typing import Any

from kagami_observability import metrics as observability_metrics

logger = logging.getLogger(__name__)


class LearningIntegration:
    """
    Integrates learning capabilities into K os apps.
    """

    def __init__(self) -> None:
        self.config = {
            "learning_enabled": True,
            "observation_batch_size": 100,
            "insight_update_interval": 300,
        }
        self.observations: list[dict[str, Any]] = []
        self.patterns: list[dict[str, Any]] = []
        self.insights: list[dict[str, Any]] = []
        self.app_status: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Initializes the learning integration."""
        logger.info("Learning Integration Initialized")

    def observe(
        self,
        app_name: str,
        event_type: str,
        data: dict[str, Any],
        context: dict[str, Any],
        outcomes: dict[str, Any] | None = None,
    ) -> None:
        """Observe an event for learning."""
        observation = {
            "app_name": app_name,
            "event_type": event_type,
            "data": data,
            "context": context,
            "outcomes": outcomes or {},
            "timestamp": time.time(),
        }
        self.observations.append(observation)

        app_key = app_name or "global"
        app_state = self.app_status.setdefault(
            app_key,
            {
                "observations": 0,
                "insights": 0,
                "patterns": 0,
                "event_counts": {},
            },
        )
        app_state["observations"] = int(app_state.get("observations", 0)) + 1
        event_counts = app_state.setdefault("event_counts", {})
        event_key = event_type or "unknown"
        event_counts[event_key] = int(event_counts.get(event_key, 0)) + 1

        try:
            observability_metrics.record_learning_observation(
                app_key,
                event_type,
                backlog_size=len(self.observations),
            )
        except Exception:
            logger.debug("learning observation metrics update failed", exc_info=True)

    def get_learning_status(self) -> dict[str, Any]:
        """Get the status of the learning system."""
        status = {
            "learning_enabled": self.config["learning_enabled"],
            "total_observations": len(self.observations),
            "total_patterns": len(self.patterns),
            "total_insights": len(self.insights),
            "registered_apps": list(self.app_status.keys()),
            "app_details": self.app_status,
        }
        try:
            observability_metrics.update_learning_status_gauges(status)

        except Exception:
            logger.debug("learning status gauge update failed", exc_info=True)
        return status

    def get_global_insights(self) -> list[dict[str, Any]]:
        """Get global insights across all apps."""
        return list(self.insights)

    def get_app_insights(self, app_name: str) -> list[dict[str, Any]]:
        """Get insights for a specific app."""
        return [insight for insight in self.insights if insight.get("app_name") == app_name]

    async def start_learning(self) -> None:
        """Start the learning process."""
        logger.info("Learning process started.")

    async def stop_learning(self) -> None:
        """Stop the learning process."""
        logger.info("Learning process stopped.")


# Singleton via centralized registry
from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_learning_integration = _singleton_registry.register_sync(
    "learning_integration", LearningIntegration
)
