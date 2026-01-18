"""Composio Service — External Tool Integration.

CONSOLIDATION (December 8, 2025):
================================
Merged: client.py, tools.py, actions.py, service.py
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import time
from collections import deque
from typing import Any

from kagami_integrations.resilience import call_with_resilience_async

from kagami.core.integrations.slack_rate_limiter import MessagePriority, get_slack_rate_limiter
from kagami.core.interfaces import IComposioService as IComposioServiceBase
from kagami.core.resilience.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


# =============================================================================
# CLIENT WRAPPER
# =============================================================================


class ComposioClientWrapper:
    """Wrapper around the official Composio SDK client."""

    def __init__(self) -> None:
        self.client = None
        self.provider_name = None
        self.user_id = None
        self.initialized = False
        self.is_v3 = False
        self.executor_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=int(os.getenv("COMPOSIO_POOL_SIZE", "10")), thread_name_prefix="composio-"
        )

    def initialize(self) -> bool:
        """Initialize the Composio client."""
        if os.getenv("KAGAMI_DISABLE_COMPOSIO", "0").lower() in ("1", "true", "yes"):
            logger.info("Composio integration disabled (KAGAMI_DISABLE_COMPOSIO=1)")
            return False

        api_key = os.getenv("COMPOSIO_API_KEY")
        if not api_key:
            logger.info("COMPOSIO_API_KEY not found. Composio integration disabled.")
            return False

        try:
            provider = self._resolve_provider()
            self.provider_name = getattr(provider, "name", "unknown")  # type: ignore[arg-type]

            # Composio V3 SDK import - try multiple paths for compatibility
            Composio = None
            try:
                from composio import Composio
            except ImportError:
                try:
                    from composio_core import Composio
                except ImportError:
                    # V3 SDK uses different import path
                    try:
                        from composio.client import Composio
                    except ImportError:
                        from composio.core.client import Composio

            if Composio is None:
                raise ImportError("Could not import Composio from any known path")

            self.client = Composio(provider=provider, api_key=api_key)
            self.user_id = os.getenv("COMPOSIO_USER_ID") or "default"  # type: ignore[assignment]

            self.initialized = True
            logger.info("✅ Composio initialized (provider=%s)", self.provider_name)
            return True
        except Exception as e:
            logger.warning(f"Composio initialization failed: {e}")
            return False

    def _resolve_provider(self) -> Any:
        """Resolve Composio provider."""
        provider_key = (os.getenv("COMPOSIO_PROVIDER") or "openai").strip().lower()
        override_class = os.getenv("COMPOSIO_PROVIDER_CLASS")
        if override_class:
            try:
                module_path, _, class_name = override_class.rpartition(".")
                module = __import__(module_path, fromlist=[class_name])
                return getattr(module, class_name)()
            except Exception as e:
                logger.warning(f"Failed to import custom provider: {e}")

        if provider_key in ("openai_agents", "agents"):
            provider = self._import_provider("OpenAIAgentsProvider")  # type: ignore[func-returns-value]
            if provider:
                return provider

        provider = self._import_provider("OpenAIProvider")  # type: ignore[func-returns-value]
        if provider:
            return provider

        from composio.core.provider.agentic import AgenticProvider

        return AgenticProvider()

    def _import_provider(self, class_name: str) -> None:
        for module_name in ("composio_openai", "composio_openai.provider"):
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name, None)
                if cls:
                    return cls()  # type: ignore[no-any-return]
            except ImportError:
                continue
        return None


# =============================================================================
# TOOL MANAGER
# =============================================================================


class ToolManager:
    """Manages tool discovery and caching."""

    def __init__(self, client_wrapper: ComposioClientWrapper):
        self.client_wrapper = client_wrapper
        self._actions_cache = {"timestamp": 0, "items": []}
        self._apps_cache = {}  # type: ignore[var-annotated]
        self._actions_ttl = int(os.getenv("COMPOSIO_ACTIONS_TTL", "300"))
        self._apps_ttl = int(os.getenv("COMPOSIO_APPS_TTL", "120"))

    async def list_tools(self) -> list[Any]:
        """List available tools."""
        if not self.client_wrapper.initialized:
            return []

        try:
            client = self.client_wrapper.client
            maybe = client.tools.list()  # type: ignore[attr-defined]
            if asyncio.iscoroutine(maybe):
                result = await maybe
            else:
                result = await asyncio.to_thread(client.tools.list[Any])  # type: ignore[attr-defined]

            try:
                if isinstance(result, dict):
                    items = result.get("items") or result.get("data")
                    if isinstance(items, list):
                        return items
                if isinstance(getattr(result, "items", None), list[Any]):
                    return result.items  # type: ignore[no-any-return]
                if isinstance(getattr(result, "data", None), list[Any]):
                    return result.data  # type: ignore[no-any-return]
            except Exception:
                pass

            try:
                return list(result)
            except Exception:
                return [result] if result else []
        except Exception:
            return []

    def serialize_tool(self, tool: Any) -> dict[str, Any]:
        return {
            "name": getattr(tool, "name", ""),
            "key": str(getattr(tool, "name", "")).lower(),
            "description": getattr(tool, "description", ""),
            "categories": [getattr(tool, "category", "general")],
            "logo": getattr(tool, "logo", None),
            "enabled": False,
            "auth_required": getattr(tool, "requires_auth", True),
            "actions_count": len(getattr(tool, "actions", []) or []),
        }

    def serialize_action(self, action: Any) -> dict[str, Any]:
        return {
            "name": getattr(action, "name", ""),
            "app": str(getattr(action, "app", "")),
            "description": getattr(action, "description", ""),
            "parameters": getattr(action, "parameters", {}),
            "tags": getattr(action, "tags", []),
        }


# =============================================================================
# ACTION EXECUTOR
# =============================================================================


class ActionExecutor:
    """Handles action execution with resilience.

    Updated December 29, 2025 for Composio V3 SDK compatibility.
    V3 uses client.tools.execute(slug, arguments, connected_account_id=...) instead of
    client.entity().execute().
    """

    def __init__(self, client_wrapper: ComposioClientWrapper):
        self.client_wrapper = client_wrapper
        self._cb_state: dict[str, Any] = {}
        self._qps_windows: dict[str, Any] = {}
        self._result_cache: dict[str, Any] = {}
        self._connected_accounts: dict[str, str] = {}  # toolkit -> account_id

        self._timeout_ms = int(os.getenv("COMPOSIO_TOOL_TIMEOUT_MS", "5000"))
        self._retry_attempts = int(os.getenv("COMPOSIO_RETRY_ATTEMPTS", "3"))
        self._cb_failure_threshold = int(os.getenv("COMPOSIO_CB_FAILURE_THRESHOLD", "5"))
        self._cb_reset_seconds = int(os.getenv("COMPOSIO_CB_RESET_SECONDS", "60"))
        self._qps_default = float(os.getenv("COMPOSIO_QPS_DEFAULT", "10"))
        self._qps_window_seconds = float(os.getenv("COMPOSIO_QPS_WINDOW_SECONDS", "1.0"))
        self._cache_ttl = int(os.getenv("COMPOSIO_CACHE_TTL", "30"))

    def _refresh_connected_accounts(self) -> None:
        """Refresh the connected accounts cache."""
        if not self.client_wrapper.initialized:
            return
        try:
            accounts = self.client_wrapper.client.connected_accounts.list()  # type: ignore[attr-defined]
            items = accounts.items if hasattr(accounts, "items") else accounts
            for acc in items:
                if getattr(acc, "status", "") == "ACTIVE":
                    toolkit = getattr(acc.toolkit, "slug", str(acc.toolkit))
                    self._connected_accounts[toolkit] = acc.id
            logger.debug(f"Composio connected accounts: {list(self._connected_accounts.keys())}")
        except Exception as e:
            logger.warning(f"Failed to refresh connected accounts: {e}")

    def _get_connected_account_for_action(self, action_name: str) -> str | None:
        """Get the connected account ID for an action based on its toolkit prefix."""
        if not self._connected_accounts:
            self._refresh_connected_accounts()

        # Extract toolkit from action name (e.g., GITHUB_CREATE_ISSUE -> github)
        action_upper = action_name.upper()
        for toolkit in self._connected_accounts:
            if action_upper.startswith(toolkit.upper() + "_"):
                return self._connected_accounts[toolkit]
        return None

    async def execute(
        self, action_name: str, parameters: dict[str, Any], user_id: str | None = None
    ) -> dict[str, Any]:
        if not self.client_wrapper.initialized:
            return {"error": "Composio not initialized", "success": False}

        if self._is_circuit_open(action_name):
            return {"success": False, "error": "circuit_open", "action": action_name}

        if not self._qps_allow(action_name):
            return {"success": False, "error": "rate_limited", "action": action_name}

        # Get connected account for this action's toolkit
        connected_account_id = self._get_connected_account_for_action(action_name)
        if not connected_account_id:
            # Try to refresh and retry once
            self._refresh_connected_accounts()
            connected_account_id = self._get_connected_account_for_action(action_name)

        cache_key = f"{connected_account_id}|{action_name}|{json.dumps(parameters, sort_keys=True)}"
        if self._should_cache(action_name):
            cached = self._result_cache.get(cache_key)
            if cached and (time.time() - cached["ts"]) < self._cache_ttl:
                return cached["val"]  # type: ignore[no-any-return]

        async def _invoke() -> Any:
            """Execute using V3 SDK tools.execute() API."""
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(
                    self.client_wrapper.executor_pool,
                    lambda: self.client_wrapper.client.tools.execute(  # type: ignore[attr-defined]
                        slug=action_name,
                        arguments=parameters,
                        connected_account_id=connected_account_id,
                        dangerously_skip_version_check=True,  # Required for V3 SDK
                    ),
                ),
                timeout=max(0.1, self._timeout_ms / 1000.0),
            )

        try:
            res = await call_with_resilience_async(
                integration="composio",
                operation=action_name,
                fn=_invoke,
                attempts=self._retry_attempts,
                breaker=CircuitBreaker(
                    name=f"composio:{action_name}",
                    failure_threshold=self._cb_failure_threshold,
                    timeout=self._cb_reset_seconds,
                ),
            )
            result_data = getattr(res, "data", res)
            payload = {"success": True, "result": result_data, "action": action_name}

            if self._should_cache(action_name):
                self._result_cache[cache_key] = {"ts": time.time(), "val": payload}

            return payload
        except Exception as e:
            self._record_failure(action_name)
            return {"success": False, "error": str(e), "action": action_name}

    def _is_circuit_open(self, action: str) -> bool:
        st = self._cb_state.get(action)
        if not st:
            return False
        return time.time() < st.get("opened_until", 0)  # type: ignore[no-any-return]

    def _record_failure(self, action: str) -> None:
        st = self._cb_state.setdefault(action, {"failures": 0, "opened_until": 0})
        st["failures"] += 1
        if st["failures"] >= self._cb_failure_threshold:
            st["opened_until"] = time.time() + self._cb_reset_seconds

    def _qps_allow(self, action: str) -> bool:
        now = time.time()
        window = self._qps_windows.setdefault(action, deque())
        while window and window[0] < (now - self._qps_window_seconds):
            window.popleft()
        if len(window) < self._qps_default:
            window.append(now)
            return True
        return False

    def _should_cache(self, action: str) -> bool:
        name = action.lower()
        return any(name.startswith(p) for p in ("get", "list", "search", "read"))


# =============================================================================
# MAIN SERVICE
# =============================================================================


class ComposioIntegrationService(IComposioServiceBase):
    """Service for integrating with Composio tools and actions.

    Updated December 29, 2025 for V3 SDK compatibility.
    """

    def __init__(self) -> None:
        self.client = ComposioClientWrapper()
        self.tools = ToolManager(self.client)
        self.executor = ActionExecutor(self.client)
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> bool:  # type: ignore[override]
        self._initialized = self.client.initialize()
        if self._initialized:
            # Pre-load connected accounts
            self.executor._refresh_connected_accounts()
            logger.info(
                f"✅ Composio ready with {len(self.executor._connected_accounts)} connected apps: "
                f"{list(self.executor._connected_accounts.keys())}"
            )
        return self._initialized

    async def shutdown(self) -> None:
        """Shutdown the service."""
        self._initialized = False
        if hasattr(self.client, "executor_pool"):
            self.client.executor_pool.shutdown(wait=False)

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._initialized

    async def execute_action(
        self, action_name: str, params: dict[str, Any], user_id: str | None = None
    ) -> dict[str, Any]:
        """Execute a Composio action.

        IMPORTANT: Slack send messages are intercepted and routed through
        the Kagami bot token, NOT Composio's user OAuth. This ensures
        messages appear from 'Kagami' bot, not the user's Slack account.

        RATE LIMITING: All Slack messages are rate-limited to 10/hour per
        channel to prevent saturation (audit finding: 100% saturation in
        3 channels).
        """
        # CRITICAL: Route ALL Slack send operations through bot token with rate limiting
        if action_name.startswith("SLACK_SEND") or "SLACK_SENDS" in action_name:
            return await self._send_slack_via_bot(params)

        return await self.executor.execute(action_name, params, user_id)

    async def _send_slack_via_bot(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send Slack message via bot token with rate limiting.

        This ensures messages appear from 'Kagami' bot, not the user's account.
        Using Composio's SLACK_SEND_MESSAGE would post AS the user, which is wrong.

        Rate limiting: 10 messages per hour per channel (1 per 6 minutes).
        """
        try:
            # Get Slack realtime integration (uses bot token)
            from kagami.core.integrations.slack_realtime import get_slack_realtime

            slack = await get_slack_realtime()
            channel = params.get("channel", "#all-awkronos")
            text = params.get("text", "")
            blocks = params.get("blocks")
            priority = params.get("priority", "NORMAL")

            # Send with rate limiting
            success = await slack.send(text, channel, blocks, priority)

            if success:
                logger.debug(f"Slack message sent via bot to {channel}")
                return {"successful": True, "data": {"channel": channel, "via": "bot_token"}}
            else:
                return {
                    "successful": False,
                    "error": "rate_limited",
                    "queued": True,
                }
        except Exception as e:
            logger.error(f"Slack bot send failed: {e}")
            return {"successful": False, "error": str(e)}

    async def get_connected_apps(self) -> list[dict[str, Any]]:
        """Get list of connected apps with their account IDs.

        Returns:
            List of connected apps with toolkit name, account_id, and status.
        """
        if not self._initialized:
            return []

        try:
            accounts = self.client.client.connected_accounts.list()  # type: ignore[attr-defined]
            items = accounts.items if hasattr(accounts, "items") else accounts
            result = []
            for acc in items:
                toolkit = getattr(acc.toolkit, "slug", str(acc.toolkit))
                result.append(
                    {
                        "toolkit": toolkit,
                        "account_id": acc.id,
                        "status": getattr(acc, "status", "unknown"),
                        "user_id": getattr(acc, "user_id", "default"),
                    }
                )
            return result
        except Exception as e:
            logger.warning(f"Failed to get connected apps: {e}")
            return []

    async def get_tools_for_app(self, toolkit: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get available tools/actions for a specific app.

        Args:
            toolkit: App name (e.g., 'github', 'gmail', 'linear')
            limit: Max number of tools to return

        Returns:
            List of tool definitions with slug, name, description.
        """
        if not self._initialized:
            return []

        try:
            tools = self.client.client.tools.get_raw_composio_tools(  # type: ignore[attr-defined]
                toolkits=[toolkit], limit=limit
            )
            result = []
            for tool in tools:
                result.append(
                    {
                        "slug": getattr(tool, "slug", "unknown"),
                        "name": getattr(tool, "name", ""),
                        "description": getattr(tool, "description", ""),
                        "input_parameters": getattr(tool, "input_parameters", {}),
                        "tags": getattr(tool, "tags", []),
                    }
                )
            return result
        except Exception as e:
            logger.warning(f"Failed to get tools for {toolkit}: {e}")
            return []

    async def get_available_apps(
        self, category: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        tools = await self.tools.list_tools()
        result = []
        for t in tools:
            data = self.tools.serialize_tool(t)
            if category is None or category.lower() in [c.lower() for c in data["categories"]]:
                result.append(data)
        return result[:limit] if limit else result

    async def find_actions_by_use_case(
        self, use_case: str, app_filter: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        _ = use_case
        tools = await self.tools.list_tools()
        actions = []
        for t in tools:
            for a in getattr(t, "actions", []) or []:
                if app_filter and getattr(t, "name", "") not in app_filter:
                    continue
                actions.append(self.tools.serialize_action(a))
        return actions[:limit]


# Singleton
_composio_service: ComposioIntegrationService | None = None


def get_composio_service() -> ComposioIntegrationService:
    global _composio_service
    if _composio_service is None:
        _composio_service = ComposioIntegrationService()
    return _composio_service


__all__ = [
    "ActionExecutor",
    "ComposioClientWrapper",
    "ComposioIntegrationService",
    "ToolManager",
    "get_composio_service",
]
