"""Organism Deployment Adapter - RPC Bridge for Deployed Colonies.

This module enables UnifiedOrganism to seamlessly switch between in-process
execution (development) and deployed multi-process execution (production).

ARCHITECTURE:
=============
    ┌─────────────────────────────────────────────────────────┐
    │              UnifiedOrganism                             │
    │                                                          │
    │  execute_intent() ──────┐                               │
    │                         │                               │
    │                         ▼                               │
    │            OrganismDeploymentAdapter                    │
    │                         │                               │
    │         ┌───────────────┴──────────────┐               │
    │         │                               │               │
    │         ▼                               ▼               │
    │   RPC Execution                 Local Fallback         │
    │         │                               │               │
    └─────────┼───────────────────────────────┼───────────────┘
              │                               │
              ▼                               ▼
    HTTP POST to Colony             colony.execute()
    (Multi-process)                 (In-process)

DEPLOYMENT MODE DETECTION:
==========================
1. Check KAGAMI_COLONY_MANAGER environment variable
2. Ping health endpoints (http://localhost:9001-9007/health)
3. Fallback to in-process if unavailable

RPC EXECUTION FLOW:
===================
1. Serialize intent → JSON
2. POST to colony RPC endpoint (http://localhost:8001-8007/execute)
3. Receive TaskResult + E8 output
4. Deserialize → reconstruct TaskResult
5. Aggregate E8 outputs via E8ActionReducer

RECEIPT CORRELATION:
====================
Correlation IDs are chained across processes:
- Parent receipt_id → context["parent_receipt_id"]
- RPC response includes child receipt_id
- Shared storage (Redis/etcd) for receipt persistence

FAILURE HANDLING:
=================
- Exponential backoff on RPC failure (2^n seconds, max 16s)
- Circuit breaker after 5 consecutive failures (60s cooldown)
- Automatic fallback to in-process execution
- Health monitoring integration with ColonyManager

Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp
import torch

from kagami.core.unified_agents.e8_action_reducer import (
    create_e8_reducer,
)
from kagami.core.unified_agents.geometric_worker import TaskResult
from kagami.core.unified_agents.minimal_colony import COLONY_NAMES

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


class ExecutionMode(Enum):
    """Execution mode for organism deployment."""

    AUTO = "auto"  # Auto-detect (RPC if available, else local)
    RPC = "rpc"  # Force RPC execution
    LOCAL = "local"  # Force in-process execution
    HYBRID = "hybrid"  # Mix RPC and local based on health


@dataclass
class DeploymentConfig:
    """Configuration for deployment adapter."""

    mode: ExecutionMode = ExecutionMode.AUTO
    base_port: int = 8001  # Colony API ports (8001-8007)
    rpc_timeout: float = 30.0  # RPC request timeout (seconds)
    fallback_enabled: bool = True  # Allow fallback to local
    circuit_breaker_threshold: int = 5  # Failures before circuit opens
    circuit_breaker_timeout: float = 60.0  # Circuit cooldown (seconds)
    health_check_interval: float = 10.0  # Health check frequency
    retry_backoff_base: float = 2.0  # Exponential backoff base
    retry_max_delay: float = 16.0  # Max retry delay (seconds)
    max_retries: int = 3  # Max RPC retry attempts


# =============================================================================
# DEPLOYMENT ADAPTER
# =============================================================================


class OrganismDeploymentAdapter:
    """Adapter for deploying UnifiedOrganism across multiple processes.

    Bridges in-process colony execution with deployed colony RPC endpoints.
    Handles health monitoring, failure recovery, and seamless fallback.
    """

    def __init__(
        self,
        organism: Any,  # UnifiedOrganism (avoid circular import)
        colony_manager: Any | None = None,  # ColonyManager
        config: DeploymentConfig | None = None,
    ):
        """Initialize deployment adapter.

        Args:
            organism: UnifiedOrganism instance
            colony_manager: Colony process manager (optional, detect from env)
            config: Deployment configuration
        """
        self.organism = organism
        self.colony_manager = colony_manager
        self.config = config or DeploymentConfig()

        # HTTP session for RPC calls
        self._session: aiohttp.ClientSession | None = None

        # Circuit breaker state per colony
        self._circuit_breaker: dict[int, dict[str, Any]] = {
            i: {"failures": 0, "open_until": 0.0, "last_failure": 0.0} for i in range(7)
        }

        # E8 reducer for output aggregation
        self._reducer = create_e8_reducer(
            num_colonies=7,
            device=getattr(organism.config, "device", "cpu"),
        )

        # Deployment detection state
        self._is_deployed: bool | None = None
        self._last_health_check: float = 0.0
        self._colony_health: dict[int, bool] = dict[str, Any].fromkeys(range(7), False)

        logger.info(f"OrganismDeploymentAdapter initialized: mode={self.config.mode.value}")

    async def __aenter__(self) -> OrganismDeploymentAdapter:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Start adapter (create HTTP session)."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.config.rpc_timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.debug("HTTP session created for RPC calls")

        # Detect deployment on startup
        await self._detect_deployment()

    async def stop(self) -> None:
        """Stop adapter (close HTTP session)."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("HTTP session closed")

    # =========================================================================
    # DEPLOYMENT DETECTION
    # =========================================================================

    async def _detect_deployment(self) -> bool:
        """Detect if colonies are deployed.

        Returns:
            True if deployed colonies detected, False otherwise
        """
        # Check environment variable
        if os.environ.get("KAGAMI_COLONY_MANAGER") == "1":
            logger.info("Deployment detected via KAGAMI_COLONY_MANAGER env var")
            self._is_deployed = True
            await self._check_all_health()
            return True

        # Ping health endpoints
        healthy_count = 0
        for colony_idx in range(7):
            is_healthy = await self._check_colony_health(colony_idx)
            if is_healthy:
                healthy_count += 1
                self._colony_health[colony_idx] = True

        self._is_deployed = healthy_count > 0
        self._last_health_check = time.time()

        if self._is_deployed:
            logger.info(f"Deployment detected: {healthy_count}/7 colonies healthy")
        else:
            logger.debug("No deployed colonies detected, using local execution")

        return self._is_deployed

    async def _check_colony_health(self, colony_idx: int) -> bool:
        """Check if colony is healthy via HTTP ping.

        Args:
            colony_idx: Colony index (0-6)

        Returns:
            True if healthy, False otherwise
        """
        if not self._session:
            return False

        port = self.config.base_port + colony_idx
        health_url = f"http://localhost:{port}/health"

        try:
            async with self._session.get(health_url) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def _check_all_health(self) -> None:
        """Check health of all colonies (parallel)."""
        tasks = [self._check_colony_health(i) for i in range(7)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            self._colony_health[i] = result is True

    def is_deployed(self) -> bool:
        """Check if colonies are deployed and healthy.

        Returns:
            True if deployed, False otherwise
        """
        if self._is_deployed is None:
            # Not yet detected - assume local
            return False
        return self._is_deployed

    def get_healthy_colonies(self) -> list[int]:
        """Get list[Any] of healthy colony indices.

        Returns:
            List of colony indices that are healthy
        """
        return [i for i, healthy in self._colony_health.items() if healthy]

    # =========================================================================
    # INTENT EXECUTION
    # =========================================================================

    async def execute_intent(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
        mode: str = "auto",
    ) -> dict[str, Any]:
        """Execute intent via deployed colonies or in-process.

        Args:
            intent: Intent string (e.g., "research.web")
            params: Intent parameters
            context: Execution context
            mode: Execution mode ("auto", "rpc", "local")

        Returns:
            Execution result with mode, results, E8 action, receipt chain
        """
        context = context or {}

        # Refresh health check periodically
        if time.time() - self._last_health_check > self.config.health_check_interval:
            await self._check_all_health()
            self._last_health_check = time.time()

        # Determine execution mode
        if mode == "auto":
            if self.config.mode == ExecutionMode.RPC:
                exec_mode = "rpc"
            elif self.config.mode == ExecutionMode.LOCAL:
                exec_mode = "local"
            elif self.config.mode == ExecutionMode.AUTO:
                exec_mode = "rpc" if self.is_deployed() else "local"
            else:  # HYBRID
                exec_mode = "hybrid"
        else:
            exec_mode = mode

        # Execute based on mode
        if exec_mode == "local":
            return await self._execute_local(intent, params, context)
        elif exec_mode == "rpc":
            return await self._execute_rpc(intent, params, context)
        else:  # hybrid
            return await self._execute_hybrid(intent, params, context)

    async def _execute_local(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via in-process colonies.

        Args:
            intent: Intent string
            params: Intent parameters
            context: Execution context

        Returns:
            Result dictionary with mode="local"
        """
        # Delegate to organism's native execute_intent
        result = await self.organism.execute_intent(intent, params, context)
        result["mode"] = "local"
        return result  # type: ignore[no-any-return]

    async def _execute_rpc(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via RPC to deployed colonies.

        Args:
            intent: Intent string
            params: Intent parameters
            context: Execution context

        Returns:
            Result dictionary with mode="rpc"
        """
        # Route intent to determine which colonies to invoke
        routing = self.organism._router.route(intent, params, context=context)

        # Extract colony indices from routing
        colony_indices = [action.colony_idx for action in routing.actions]

        # Execute via RPC (parallel)
        tasks = []
        for colony_idx in colony_indices:
            # Check circuit breaker
            if self._is_circuit_open(colony_idx):
                logger.warning(
                    f"Circuit breaker open for colony {colony_idx}, falling back to local"
                )
                # Fallback to local for this colony
                colony = self.organism._get_or_create_colony(colony_idx)
                action = next(
                    (a.action for a in routing.actions if a.colony_idx == colony_idx), "execute"
                )
                tasks.append(colony.execute(action, params, context))
            else:
                # RPC call
                tasks.append(self._execute_via_rpc(colony_idx, intent, params, context))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle failures and reconstruct
        final_results = []
        colony_outputs = []

        for _i, (colony_idx, result) in enumerate(zip(colony_indices, results, strict=False)):
            if isinstance(result, Exception):
                logger.error(f"RPC execution failed for colony {colony_idx}: {result}")
                self._record_failure(colony_idx)

                # Fallback to local if enabled
                if self.config.fallback_enabled:
                    colony = self.organism._get_or_create_colony(colony_idx)
                    action = next(
                        (a.action for a in routing.actions if a.colony_idx == colony_idx), "execute"
                    )
                    result = await colony.execute(action, params, context)
                else:
                    # Create failure TaskResult
                    result = TaskResult(
                        task_id="rpc_failed",
                        success=False,
                        error=str(result),
                        latency=0.0,
                    )

            final_results.append(result)

            # Extract S7 output for E8 aggregation
            s7_output = self.organism._compute_s7_output(
                result,
                self.organism._get_or_create_colony(colony_idx),
                colony_idx,
            )
            colony_outputs.append(s7_output)

        # Aggregate E8 outputs
        output_tensor = torch.zeros(7, 8)
        for colony_idx, s7_output in zip(colony_indices, colony_outputs, strict=False):
            output_tensor[colony_idx] = s7_output

        e8_result = await self.organism._fuse_e8(output_tensor.unsqueeze(0))

        return {
            "success": all(r.success for r in final_results),  # type: ignore[union-attr]
            "mode": "rpc",
            "results": final_results,
            "e8_action": {
                "index": e8_result["index"],
                "code": e8_result["code"].tolist()
                if isinstance(e8_result["code"], torch.Tensor)
                else e8_result["code"],
                "weights": e8_result["weights"],
            },
            "correlation_chain": [r.correlation_id for r in final_results if r.correlation_id],  # type: ignore[union-attr]
        }

    async def _execute_hybrid(
        self,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute via mix of RPC and local based on health.

        Args:
            intent: Intent string
            params: Intent parameters
            context: Execution context

        Returns:
            Result dictionary with mode="hybrid"
        """
        # Route intent
        routing = self.organism._router.route(intent, params, context=context)
        colony_indices = [action.colony_idx for action in routing.actions]

        # Split by health
        healthy_colonies = self.get_healthy_colonies()
        rpc_colonies = [i for i in colony_indices if i in healthy_colonies]
        local_colonies = [i for i in colony_indices if i not in healthy_colonies]

        # Execute both in parallel
        tasks = []

        # RPC tasks
        for colony_idx in rpc_colonies:
            if not self._is_circuit_open(colony_idx):
                tasks.append(
                    ("rpc", colony_idx, self._execute_via_rpc(colony_idx, intent, params, context))
                )

        # Local tasks
        for colony_idx in local_colonies:
            colony = self.organism._get_or_create_colony(colony_idx)
            action = next(
                (a.action for a in routing.actions if a.colony_idx == colony_idx), "execute"
            )
            tasks.append(("local", colony_idx, colony.execute(action, params, context)))

        # Gather results
        task_modes = [(mode, idx) for mode, idx, _ in tasks]
        task_coros = [coro for _, _, coro in tasks]
        results = await asyncio.gather(*task_coros, return_exceptions=True)

        # Reconstruct
        final_results = []
        colony_outputs = []  # List of (colony_idx, s7_output) tuples

        for (mode, colony_idx), result in zip(task_modes, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"{mode.upper()} execution failed for colony {colony_idx}: {result}")
                if mode == "rpc":
                    self._record_failure(colony_idx)

                # Always fallback to local
                colony = self.organism._get_or_create_colony(colony_idx)
                action = next(
                    (a.action for a in routing.actions if a.colony_idx == colony_idx), "execute"
                )
                result = await colony.execute(action, params, context)

            final_results.append(result)

            # S7 output - track colony_idx with output to avoid order mismatch
            s7_output = self.organism._compute_s7_output(
                result,
                self.organism._get_or_create_colony(colony_idx),
                colony_idx,
            )
            colony_outputs.append((colony_idx, s7_output))

        # E8 aggregation - use tracked colony_idx, not colony_indices order
        output_tensor = torch.zeros(7, 8)
        for colony_idx, s7_output in colony_outputs:
            output_tensor[colony_idx] = s7_output

        e8_result = await self.organism._fuse_e8(output_tensor.unsqueeze(0))

        return {
            "success": all(r.success for r in final_results),  # type: ignore[union-attr]
            "mode": "hybrid",
            "results": final_results,
            "e8_action": {
                "index": e8_result["index"],
                "code": e8_result["code"].tolist()
                if isinstance(e8_result["code"], torch.Tensor)
                else e8_result["code"],
                "weights": e8_result["weights"],
            },
            "correlation_chain": [r.correlation_id for r in final_results if r.correlation_id],  # type: ignore[union-attr]
            "rpc_count": len(rpc_colonies),
            "local_count": len(local_colonies),
        }

    # =========================================================================
    # RPC EXECUTION
    # =========================================================================

    async def _execute_via_rpc(
        self,
        colony_idx: int,
        intent: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> TaskResult:
        """Execute single colony via RPC with retry logic.

        Args:
            colony_idx: Colony index (0-6)
            intent: Intent string
            params: Intent parameters
            context: Execution context

        Returns:
            TaskResult from RPC response
        """
        if not self._session:
            raise RuntimeError("HTTP session not initialized")

        colony_name = COLONY_NAMES[colony_idx]
        port = self.config.base_port + colony_idx
        url = f"http://localhost:{port}/execute"

        # Prepare payload
        payload = {
            "action": intent,
            "params": params,
            "context": context,
        }

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                async with self._session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Reconstruct TaskResult
                        result = TaskResult(  # type: ignore[call-arg]
                            task_id=data.get("task_id", "rpc_task"),
                            success=data.get("success", False),
                            output=data.get("output"),
                            error=data.get("error"),
                            latency=data.get("latency", 0.0),
                            correlation_id=data.get("correlation_id"),
                            phase=data.get("phase"),
                            parent_receipt_id=data.get("parent_receipt_id"),
                        )

                        # Record success
                        self._record_success(colony_idx)

                        logger.debug(
                            f"RPC execution succeeded: colony={colony_name}, "
                            f"latency={result.latency:.3f}s"
                        )

                        return result
                    else:
                        error_text = await resp.text()
                        last_error = Exception(f"HTTP {resp.status}: {error_text}")
                        logger.warning(f"RPC call failed (attempt {attempt + 1}): {last_error}")

            except TimeoutError as e:
                last_error = e
                logger.warning(f"RPC timeout (attempt {attempt + 1}): colony={colony_name}")

            except aiohttp.ClientError as e:
                last_error = e
                logger.warning(f"RPC client error (attempt {attempt + 1}): {e}")

            # Exponential backoff (2s, 4s, 8s, ...)
            if attempt < self.config.max_retries - 1:
                delay = min(
                    self.config.retry_backoff_base ** (attempt + 1),
                    self.config.retry_max_delay,
                )
                logger.debug(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        # All retries failed
        self._record_failure(colony_idx)
        raise Exception(
            f"RPC execution failed after {self.config.max_retries} attempts: {last_error}"
        )

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================

    def _is_circuit_open(self, colony_idx: int) -> bool:
        """Check if circuit breaker is open for colony.

        Args:
            colony_idx: Colony index (0-6)

        Returns:
            True if circuit is open (too many failures), False otherwise
        """
        state = self._circuit_breaker[colony_idx]

        # Check if circuit is open
        if state["open_until"] > time.time():
            return True

        return False

    def _record_failure(self, colony_idx: int) -> None:
        """Record RPC failure for circuit breaker.

        Args:
            colony_idx: Colony index (0-6)
        """
        state = self._circuit_breaker[colony_idx]
        state["failures"] += 1
        state["last_failure"] = time.time()

        # Open circuit if threshold exceeded
        if state["failures"] >= self.config.circuit_breaker_threshold:
            state["open_until"] = time.time() + self.config.circuit_breaker_timeout
            colony_name = COLONY_NAMES[colony_idx]
            logger.warning(
                f"Circuit breaker opened for colony {colony_idx} ({colony_name}): "
                f"{state['failures']} failures, cooldown={self.config.circuit_breaker_timeout}s"
            )

    def _record_success(self, colony_idx: int) -> None:
        """Record RPC success (reset circuit breaker).

        Args:
            colony_idx: Colony index (0-6)
        """
        state = self._circuit_breaker[colony_idx]

        # Reset failure count on success
        if state["failures"] > 0:
            logger.debug(
                f"Resetting circuit breaker for colony {colony_idx} "
                f"(previous failures: {state['failures']})"
            )
        state["failures"] = 0
        state["open_until"] = 0.0

    # =========================================================================
    # STATS & MONITORING
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get deployment adapter statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "is_deployed": self.is_deployed(),
            "mode": self.config.mode.value,
            "healthy_colonies": self.get_healthy_colonies(),
            "circuit_breakers": {
                COLONY_NAMES[i]: {
                    "failures": state["failures"],
                    "is_open": self._is_circuit_open(i),
                    "open_until": state["open_until"],
                }
                for i, state in self._circuit_breaker.items()
            },
            "last_health_check": self._last_health_check,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_deployment_adapter(
    organism: Any,
    colony_manager: Any | None = None,
    config: DeploymentConfig | None = None,
) -> OrganismDeploymentAdapter:
    """Create a deployment adapter.

    Args:
        organism: UnifiedOrganism instance
        colony_manager: Colony process manager (optional)
        config: Deployment configuration

    Returns:
        Configured OrganismDeploymentAdapter
    """
    return OrganismDeploymentAdapter(
        organism=organism,
        colony_manager=colony_manager,
        config=config,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DeploymentConfig",
    "ExecutionMode",
    "OrganismDeploymentAdapter",
    "create_deployment_adapter",
]
