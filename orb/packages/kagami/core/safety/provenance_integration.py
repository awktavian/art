"""Provenance Chain Integration with Receipt System.

Provides verification and CBF-aware safety checks using provenance data.
Note: Provenance recording is now integrated directly into UnifiedReceiptFacade
(see kagami/core/receipts/__init__.py).

Integration Points:
1. Receipt emission → Provenance record (automatic via URF)
2. etcd sync → Cross-instance verification
3. CBF filter → Provenance-aware safety

Usage:
    from kagami.core.safety.provenance_integration import (
        verify_action_provenance,
        start_cross_instance_verification,
    )

    # Verify provenance for a correlation_id
    is_valid, issues = await verify_action_provenance(correlation_id)

Created: December 5, 2025
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from kagami.core.safety.provenance_chain import (
    ProvenanceRecord,
    get_provenance_chain,
)

logger = logging.getLogger(__name__)


# NOTE: enable_provenance_tracking and disable_provenance_tracking have been
# moved to kagami.core.receipts.__init__ for direct integration with URF.
# Re-export them here for backward compatibility.
async def enable_provenance_tracking() -> bool:
    """Enable provenance tracking. Delegated to receipts module."""
    from kagami.core.receipts import enable_provenance_tracking as _enable

    return bool(await _enable())


async def disable_provenance_tracking() -> None:
    """Disable provenance tracking. Delegated to receipts module."""
    from kagami.core.receipts import disable_provenance_tracking as _disable

    await _disable()


# =============================================================================
# VERIFICATION API
# =============================================================================


async def verify_action_provenance(correlation_id: str) -> tuple[bool, list[str]]:
    """Verify provenance chain for a correlation_id.

    Args:
        correlation_id: Correlation ID linking related actions

    Returns:
        Tuple of (is_valid, list[Any] of issues)
    """
    chain = get_provenance_chain()
    if not chain._initialized:
        await chain.initialize()

    return await chain.verify_chain(correlation_id)


async def get_action_provenance(correlation_id: str) -> list[ProvenanceRecord]:
    """Get all provenance records for a correlation_id.

    Args:
        correlation_id: Correlation ID

    Returns:
        List of ProvenanceRecord (newest first)
    """
    chain = get_provenance_chain()
    if not chain._initialized:
        await chain.initialize()

    return await chain.get_chain(correlation_id)


async def record_manual_provenance(
    action: str,
    context: dict[str, Any],
    correlation_id: str | None = None,
    output_hash: str | None = None,
) -> ProvenanceRecord:
    """Manually record a provenance entry.

    Use this for actions that don't go through the receipt system.

    Args:
        action: Action type
        context: Action context
        correlation_id: Optional correlation ID
        output_hash: Optional hash of output

    Returns:
        Signed ProvenanceRecord
    """
    chain = get_provenance_chain()
    if not chain._initialized:
        await chain.initialize()

    return await chain.record_action(
        action=action,
        context=context,
        correlation_id=correlation_id,
        output_hash=output_hash,
    )


# =============================================================================
# CBF INTEGRATION
# =============================================================================


async def provenance_aware_safety_check(
    context: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Enhanced safety check that considers provenance history.

    Checks:
    1. Is the action chain valid (no tampering)?
    2. Are there suspicious patterns in history?
    3. Is this a known-good or known-bad pattern?

    Args:
        context: Current action context
        correlation_id: Optional correlation ID for history

    Returns:
        Safety assessment dict[str, Any]
    """
    provenance_valid: bool = True
    chain_length: int = 0
    issues: list[str] = []
    risk_modifier: float = 0.0  # Added to CBF threat score

    if not correlation_id:
        return {
            "provenance_valid": provenance_valid,
            "chain_length": chain_length,
            "issues": issues,
            "risk_modifier": risk_modifier,
        }

    try:
        chain = get_provenance_chain()
        if not chain._initialized:
            await chain.initialize()

        # Verify chain integrity
        is_valid, chain_issues = await chain.verify_chain(correlation_id)
        provenance_valid = is_valid
        issues.extend(chain_issues)

        # Get chain history
        records = await chain.get_chain(correlation_id)
        chain_length = len(records)

        # Check for suspicious patterns
        if not is_valid:
            # Tampered chain → high risk
            risk_modifier = max(risk_modifier, 0.5)
            logger.warning(f"Provenance chain invalid for {correlation_id}: {issues}")

        elif len(records) > 100:
            # Very long chain → possible runaway
            risk_modifier = max(risk_modifier, 0.2)
            logger.info(f"Long provenance chain ({len(records)}) for {correlation_id}")

        # Check for rapid action sequences (potential automation attack)
        if len(records) >= 2:
            time_deltas = [
                records[i].timestamp - records[i + 1].timestamp for i in range(len(records) - 1)
            ]
            avg_delta = sum(time_deltas) / len(time_deltas)
            if avg_delta < 0.1:  # < 100ms average
                risk_modifier = max(risk_modifier, 0.3)
                issues.append("Suspicious rapid action sequence")

    except Exception as e:
        logger.error(f"Provenance safety check failed: {e}")
        issues.append(f"Check failed: {e}")

    return {
        "provenance_valid": provenance_valid,
        "chain_length": chain_length,
        "issues": issues,
        "risk_modifier": risk_modifier,
    }


# =============================================================================
# ETCD WATCH FOR CROSS-INSTANCE VERIFICATION
# =============================================================================


class CrossInstanceVerifier:
    """Watches etcd for provenance records and verifies them.

    Provides distributed trust: any instance can verify any record.
    """

    def __init__(self) -> None:
        self._running = False
        self._watch_task: asyncio.Task | None = None
        self._verified_count = 0
        self._failed_count = 0

    async def start(self) -> None:
        """Start cross-instance verification."""
        if self._running:
            return

        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop(), name="cross_instance_verifier")
        logger.info("✅ Cross-instance provenance verifier started")

    async def stop(self) -> None:
        """Stop verifier."""
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info(
            f"Cross-instance verifier stopped "
            f"(verified: {self._verified_count}, failed: {self._failed_count})"
        )

    async def _watch_loop(self) -> None:
        """Watch etcd for new provenance records.

        IMPORTANT: etcd3's ``watch_prefix`` returns a *blocking* iterator backed by gRPC.
        Iterating it directly inside an async task will freeze the asyncio event loop
        (and can prevent FastAPI/uvicorn startup from completing).

        Solution: run the blocking iterator in a daemon thread and forward decoded
        events into the asyncio loop via an asyncio.Queue.
        """
        try:
            # Dynamic import to avoid safety ↔ consensus cycles.
            import importlib

            consensus_mod = importlib.import_module("kagami.core.consensus")
            get_etcd_client = getattr(consensus_mod, "get_etcd_client", None)
            client = get_etcd_client() if get_etcd_client is not None else None
            if not client:
                logger.warning("etcd unavailable for cross-instance verification")
                return

            prefix = "kagami:provenance:records:"
            events_iterator, cancel = client.watch_prefix(prefix)

            chain = get_provenance_chain()
            await chain.initialize()

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[dict[str, Any] | Exception] = asyncio.Queue(maxsize=1024)
            stop_event = threading.Event()

            def _producer() -> None:
                """Run the blocking etcd watch iterator in a thread."""
                import json

                try:
                    for event in events_iterator:
                        if stop_event.is_set() or not self._running:
                            break
                        try:
                            if not getattr(event, "value", None):
                                continue
                            record_data = json.loads(event.value.decode())
                            asyncio.run_coroutine_threadsafe(queue.put(record_data), loop)
                        except Exception as e:
                            asyncio.run_coroutine_threadsafe(queue.put(e), loop)
                except Exception as e:
                    asyncio.run_coroutine_threadsafe(queue.put(e), loop)
                finally:
                    try:
                        cancel()
                    except (AttributeError, RuntimeError, OSError) as e:
                        # AttributeError: cancel not defined
                        # RuntimeError: already cancelled or closed
                        # OSError: connection/socket error
                        logger.debug(f"Watch cancellation error (expected): {e}")

            thread = threading.Thread(
                target=_producer, daemon=True, name="provenance_watch_producer"
            )
            thread.start()

            try:
                while self._running:
                    item = await queue.get()
                    if isinstance(item, Exception):
                        logger.debug(f"Provenance watch producer error: {item}")
                        continue

                    record_data = item
                    record_hash = record_data.get("record_hash")
                    if not record_hash:
                        continue

                    # Skip our own records
                    if record_data.get("instance_id") == chain.instance_id:
                        continue

                    # Verify the record
                    is_valid, reason = await chain.verify_record(record_hash)

                    if is_valid:
                        self._verified_count += 1
                        # Optionally witness valid records
                        await chain.witness_record(record_hash)
                        logger.debug(f"Verified peer record: {record_hash[:16]}...")
                    else:
                        self._failed_count += 1
                        logger.warning(f"❌ Invalid peer record {record_hash[:16]}: {reason}")

                        # Emit metric for invalid records
                        try:
                            from kagami_observability.metrics import _counter

                            invalid_counter = _counter(
                                "kagami_provenance_invalid_records_total",
                                "Invalid provenance records detected",
                                ["reason"],
                            )
                            invalid_counter.labels(reason=reason[:50]).inc()
                        except (ImportError, AttributeError, TypeError, ValueError) as e:
                            # ImportError: metrics module not available
                            # AttributeError: _counter not defined
                            # TypeError: invalid arguments
                            # ValueError: invalid metric name or labels
                            logger.debug(f"Metrics emission failed: {e}")

            finally:
                stop_event.set()
                try:
                    cancel()
                except (AttributeError, RuntimeError, OSError) as e:
                    # AttributeError: cancel not defined
                    # RuntimeError: already cancelled or closed
                    # OSError: connection/socket error
                    logger.debug(f"Watch cleanup error (expected): {e}")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Cross-instance verifier error: {e}")


# Global verifier instance
_cross_verifier: CrossInstanceVerifier | None = None


async def start_cross_instance_verification() -> None:
    """Start cross-instance provenance verification."""
    global _cross_verifier

    if _cross_verifier is None:
        _cross_verifier = CrossInstanceVerifier()

    await _cross_verifier.start()


async def stop_cross_instance_verification() -> None:
    """Stop cross-instance verification."""
    if _cross_verifier:
        await _cross_verifier.stop()


__all__ = [
    "disable_provenance_tracking",
    # Enable/disable
    "enable_provenance_tracking",
    "get_action_provenance",
    # CBF integration
    "provenance_aware_safety_check",
    # Manual recording
    "record_manual_provenance",
    # Cross-instance
    "start_cross_instance_verification",
    "stop_cross_instance_verification",
    # Verification
    "verify_action_provenance",
]
