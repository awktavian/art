"""Integration Registry for K os.

Central registry for managing integrations with external frameworks.
"""

from __future__ import annotations

import logging

from kagami_integrations.base import BaseIntegration, IntegrationConfig

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """Registry for K os integrations."""

    def __init__(self) -> None:
        self._integrations: dict[str, BaseIntegration] = {}
        self._configs: dict[str, IntegrationConfig] = {}
        self._classes: dict[str, type[BaseIntegration]] = {}

    def register(
        self,
        name: str,
        integration_class: type[BaseIntegration],
        config: IntegrationConfig | None = None,
    ) -> None:
        """Register an integration.

        Args:
            name: Integration name
            integration_class: Integration class
            config: Configuration (will create default if None)
        """
        if config is None:
            config = IntegrationConfig(name=name)

        self._configs[name] = config
        if integration_class is not None:
            self._classes[name] = integration_class

        # Lazy instantiation - create on first get()
        logger.info(f"Registered integration: {name}")

    def get(self, name: str) -> BaseIntegration | None:
        """Get an integration instance.

        Args:
            name: Integration name

        Returns:
            Integration instance or None if not registered
        """
        if name in self._integrations:
            return self._integrations[name]

        if name not in self._configs:
            logger.warning(f"Integration not registered: {name}")
            return None

        # Lazy load
        config = self._configs[name]
        try:
            integration_cls = self._classes.get(name)
            if integration_cls is not None:
                integration = integration_cls(config)
            elif name == "langchain":
                from kagami_integrations.langchain.integration import LangChainIntegration

                integration = LangChainIntegration(config)
            elif name == "crewai":
                from kagami_integrations.crewai.integration import CrewAIIntegration

                integration = CrewAIIntegration(config)

            elif name == "autogen":
                from kagami_integrations.autogen.integration import AutoGenIntegration

                integration = AutoGenIntegration(config)
            else:
                logger.error(f"Unknown integration: {name}")
                return None

            self._integrations[name] = integration
            return integration

        except ImportError as e:
            logger.warning(f"Integration '{name}' dependencies not installed: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to create integration '{name}': {e}")
            return None

    def list_available(self) -> list[str]:
        """List available integrations.

        Returns:
            List of registered integration names
        """
        return list(self._configs.keys())

    async def shutdown_all(self) -> None:
        """Shutdown all active integrations."""
        for name, integration in self._integrations.items():
            try:
                await integration.shutdown()
            except Exception as e:
                logger.error(f"Failed to shutdown integration '{name}': {e}")


# Global registry instance
_registry: IntegrationRegistry | None = None


def get_integration_registry() -> IntegrationRegistry:
    """Get the global integration registry.

    Returns:
        Integration registry singleton
    """
    global _registry
    if _registry is None:
        _registry = IntegrationRegistry()

        # Auto-register known integrations
        from kagami_integrations.base import IntegrationConfig

        # LangChain
        _registry.register(
            "langchain",
            None,  # type: ignore
            IntegrationConfig(name="langchain"),
        )

        # CrewAI
        _registry.register(
            "crewai",
            None,  # type: ignore
            IntegrationConfig(name="crewai"),
        )

        # AutoGen
        _registry.register(
            "autogen",
            None,  # type: ignore
            IntegrationConfig(name="autogen"),
        )

    return _registry
