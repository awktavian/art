"""Base Integration Framework for K os.

Provides abstract base class and utilities for building integrations
with external agent frameworks.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""

    name: str
    """Integration name (langchain, crewai, etc)"""

    kagami_url: str = "http://localhost:8001"
    """K os API base URL"""

    kagami_api_key: str | None = None
    """K os API key for authentication"""

    timeout_seconds: float = 30.0
    """Default timeout for API calls"""

    max_retries: int = 3
    """Maximum number of retries for failed requests"""

    enable_receipts: bool = True
    """Whether to track and return receipts"""

    enable_metrics: bool = True
    """Whether to collect integration metrics"""

    extra_config: dict[str, Any] | None = None
    """Framework-specific configuration"""


@dataclass
class IntegrationResult:
    """Result from an integration operation."""

    status: str
    """Status: accepted, completed, error, blocked, needs_confirmation"""

    response: Any
    """Operation response/result"""

    correlation_id: str | None = None
    """K os correlation ID for tracking"""

    receipt: dict[str, Any] | None = None
    """K os receipt (if enabled)"""

    metadata: dict[str, Any] | None = None
    """Additional metadata"""

    error: str | None = None
    """Error message if status is error"""


class BaseIntegration(ABC):
    """Abstract base class for K os integrations.

    Subclass this to create integrations with specific frameworks.
    Provides common functionality for API calls, error handling, etc.
    """

    def __init__(self, config: IntegrationConfig):
        """Initialize integration.

        Args:
            config: Integration configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{config.name}")
        self._initialized = False
        self._client: Any = None

    async def initialize(self) -> None:
        """Initialize the integration.

        Called once before first use. Override to set up connections,
        load models, etc.
        """
        if self._initialized:
            return

        self.logger.info(f"Initializing {self.config.name} integration")
        await self._initialize_impl()
        self._initialized = True
        self.logger.info(f"{self.config.name} integration ready")

    @abstractmethod
    async def _initialize_impl(self) -> None:
        """Implementation-specific initialization.

        Override this in subclasses to perform initialization.
        """

    async def execute_intent(
        self,
        command: str,
        confirm: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> IntegrationResult:
        """Execute a K os intent.

        Args:
            command: Natural language or LANG/2 command
            confirm: Whether to auto-confirm high-risk operations
            metadata: Additional metadata to pass

        Returns:
            Integration result with status and response
        """
        if not self._initialized:
            await self.initialize()

        try:
            import httpx

            headers = {}
            if self.config.kagami_api_key:
                headers["x-api-key"] = self.config.kagami_api_key

            body = {"lang": command, "confirm": confirm}
            if metadata:
                body["metadata"] = metadata

            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    f"{self.config.kagami_url}/api/command/execute",
                    json=body,
                    headers=headers,
                )

                if response.status_code == 429:
                    return IntegrationResult(
                        status="error",
                        response=None,
                        error="rate_limit_exceeded",
                    )

                response.raise_for_status()
                result = response.json()

                return IntegrationResult(
                    status=result.get("status", "unknown"),
                    response=result.get("response") or result.get("result"),
                    correlation_id=result.get("receipt", {}).get("correlation_id"),
                    receipt=result.get("receipt") if self.config.enable_receipts else None,
                    metadata=result.get("metadata"),
                    error=result.get("error"),
                )

        except Exception as e:
            self.logger.error(f"Failed to execute intent: {e}")
            return IntegrationResult(
                status="error",
                response=None,
                error=str(e),
            )

    @abstractmethod
    async def as_tool(self) -> Any:
        """Convert this integration to a framework-specific tool.

        Returns:
            Tool object for the target framework (LangChain Tool, CrewAI BaseTool, etc)
        """

    @abstractmethod
    async def from_tool(self, tool: Any) -> None:
        """Import a tool from the target framework into K os.

        Args:
            tool: Tool object from the target framework
        """

    async def get_available_actions(self) -> list[dict[str, Any]]:
        """Get available K os actions/apps.

        Returns:
            List of available actions with descriptions
        """
        try:
            import httpx

            headers = {}
            if self.config.kagami_api_key:
                headers["x-api-key"] = self.config.kagami_api_key

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.config.kagami_url}/api/apps",
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()  # type: ignore  # External lib
        except Exception as e:
            self.logger.warning(f"Failed to get available actions: {e}")
            return []

    async def shutdown(self) -> None:
        """Shutdown the integration and cleanup resources."""
        self.logger.info(f"Shutting down {self.config.name} integration")
        await self._shutdown_impl()
        self._initialized = False

    async def _shutdown_impl(self) -> None:
        """Implementation-specific shutdown.

        Override this in subclasses to cleanup resources.
        """
        # Best-effort cleanup for common patterns:
        # - integrations that keep an httpx.AsyncClient in self._client
        # - integrations that keep any closeable resource in self.client
        for attr in ("_client", "client"):
            obj = getattr(self, attr, None)
            if obj is None:
                continue
            close = getattr(obj, "aclose", None) or getattr(obj, "close", None)
            if close is None:
                continue
            try:
                res = close()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.logger.debug(f"Best-effort close failed for {attr}: {e}")

        self._client = None
        return
