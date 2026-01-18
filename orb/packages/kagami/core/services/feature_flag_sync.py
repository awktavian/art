"""Feature Flag Synchronization Service.

Watches etcd for dynamic feature flag updates. Lives in services layer
because it coordinates with consensus infrastructure (etcd).

Moved from config layer (December 2025) to fix layer violation:
config (L0) should not import from consensus (L4).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FeatureFlagWatcher:
    """Watches etcd for dynamic feature flag updates."""

    def __init__(self) -> None:
        self._running = False
        self._etcd_client: Any = None
        self._watch_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return

        try:
            logger.info("FeatureFlagWatcher: getting etcd client...")
            from kagami.core.consensus import get_etcd_client

            # Run blocking etcd client creation in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            self._etcd_client = await asyncio.wait_for(
                loop.run_in_executor(None, get_etcd_client),
                timeout=10.0,
            )
            logger.info(f"FeatureFlagWatcher: etcd client = {self._etcd_client}")
            if self._etcd_client is None:
                logger.info("Feature flag watcher: no etcd client available")
                return

            self._running = True
            self._watch_task = asyncio.create_task(self._watch_loop(), name="feature_flag_watch")
            logger.info("FeatureFlagWatcher: loading initial state...")
            await self._load_initial_state()
            logger.info("FeatureFlagWatcher: start complete")

        except TimeoutError:
            logger.warning("FeatureFlagWatcher: etcd client creation timed out")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Feature flag watcher start failed: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        self._watch_task = None

    async def _load_initial_state(self) -> None:
        if not self._etcd_client:
            return

        try:
            prefix = "kagami:config:flags:"
            loop = asyncio.get_running_loop()

            def get_prefix() -> list[Any]:
                return list(self._etcd_client.get_prefix(prefix))

            # Add timeout to prevent blocking
            entries = await asyncio.wait_for(
                loop.run_in_executor(None, get_prefix),
                timeout=5.0,
            )

            overrides: dict[str, dict[str, Any]] = {}

            for value, metadata in entries:
                key = metadata.key.decode()
                parts = key.split(":")
                if len(parts) >= 5:
                    category = parts[3]
                    flag = parts[4]
                    try:
                        val = json.loads(value.decode())
                        if category not in overrides:
                            overrides[category] = {}
                        overrides[category][flag] = val
                    except json.JSONDecodeError:
                        pass

            if overrides:
                from kagami.core.config.feature_flags import get_feature_flags

                flags = get_feature_flags()
                flags.apply_overrides(overrides)

        except TimeoutError:
            logger.warning("Feature flags initial load timed out (continuing with defaults)")
        except Exception:
            pass

    async def _watch_loop(self) -> None:
        prefix = "kagami:config:flags:"

        while self._running:
            try:
                if self._etcd_client is None:
                    await asyncio.sleep(30)
                    continue

                queue: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_running_loop()
                etcd_client = self._etcd_client

                def producer() -> None:
                    try:
                        events_iterator, cancel = etcd_client.watch_prefix(prefix)
                        for event in events_iterator:
                            if not self._running:
                                cancel()
                                break
                            loop.call_soon_threadsafe(queue.put_nowait, event)
                    except Exception as e:
                        loop.call_soon_threadsafe(queue.put_nowait, e)

                thread = threading.Thread(
                    target=producer, daemon=True, name="feature_flag_watch_producer"
                )
                thread.start()

                while self._running:
                    item = await queue.get()
                    if isinstance(item, Exception):
                        break

                    await self._handle_event(item)

            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(5)

    async def _handle_event(self, event: Any) -> None:
        try:
            key = event.key.decode()
            parts = key.split(":")
            if len(parts) < 5:
                return

            category = parts[3]
            flag = parts[4]

            from kagami.core.config.feature_flags import FeatureFlags, get_feature_flags

            flags = get_feature_flags()

            is_delete = False
            try:
                import etcd3.events

                if isinstance(etcd3.events.DeleteEvent, type) and isinstance(
                    event, etcd3.events.DeleteEvent
                ):
                    is_delete = True
            except (ImportError, AttributeError, TypeError):
                pass

            if is_delete or not getattr(event, "value", None):
                defaults = FeatureFlags.from_env()
                if hasattr(defaults, category):
                    cat_obj = getattr(defaults, category)
                    if hasattr(cat_obj, flag):
                        default_val = getattr(cat_obj, flag)
                        flags.apply_overrides({category: {flag: default_val}})
                return

            try:
                val = json.loads(event.value.decode())
                flags.apply_overrides({category: {flag: val}})
            except json.JSONDecodeError:
                pass

        except Exception:
            pass


_feature_flag_watcher: FeatureFlagWatcher | None = None


def get_feature_flag_watcher() -> FeatureFlagWatcher:
    global _feature_flag_watcher
    if _feature_flag_watcher is None:
        _feature_flag_watcher = FeatureFlagWatcher()
    return _feature_flag_watcher


__all__ = [
    "FeatureFlagWatcher",
    "get_feature_flag_watcher",
]
