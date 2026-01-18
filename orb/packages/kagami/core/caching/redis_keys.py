"""Centralized Redis key namespace management.

Provides consistent key namespacing across the codebase with the kagami: prefix.
All Redis keys should be generated through this class to maintain uniformity.
"""

from __future__ import annotations


class RedisKeys:
    """Redis key builder with consistent kagami: prefix.

    All methods are static and return properly namespaced Redis keys.
    This ensures consistency and makes key migrations/refactoring easier.
    """

    BASE = "kagami"

    @staticmethod
    def receipt(correlation_id: str, phase: str = "") -> str:
        """Build receipt key.

        Args:
            correlation_id: Unique correlation identifier
            phase: Optional phase (PLAN/EXECUTE/VERIFY)

        Returns:
            Key format: kagami:receipts:{correlation}:{phase} or kagami:receipts:{correlation}

        Examples:
            >>> RedisKeys.receipt("abc123", "EXECUTE")
            'kagami:receipts:abc123:EXECUTE'
            >>> RedisKeys.receipt("abc123")
            'kagami:receipts:abc123'
        """
        if phase:
            return f"{RedisKeys.BASE}:receipts:{correlation_id}:{phase}"
        return f"{RedisKeys.BASE}:receipts:{correlation_id}"

    @staticmethod
    def receipt_with_instance(instance_id: str, correlation_id: str) -> str:
        """Build receipt key with instance ID.

        Used for distributed instance tracking.

        Args:
            instance_id: Instance/worker identifier
            correlation_id: Unique correlation identifier

        Returns:
            Key format: kagami:receipts:{instance_id}:{correlation_id}

        Examples:
            >>> RedisKeys.receipt_with_instance("worker-1", "abc123")
            'kagami:receipts:worker-1:abc123'
        """
        return f"{RedisKeys.BASE}:receipts:{instance_id}:{correlation_id}"

    @staticmethod
    def receipt_prefix() -> str:
        """Get receipt key prefix for scanning/filtering.

        Returns:
            Prefix: kagami:receipts:

        Examples:
            >>> RedisKeys.receipt_prefix()
            'kagami:receipts:'
        """
        return f"{RedisKeys.BASE}:receipts:"

    @staticmethod
    def rate_limit(namespace: str, client_id: str, window: int = 0) -> str:
        """Build rate limit key.

        Args:
            namespace: Rate limit namespace (e.g., 'api', 'agent')
            client_id: Client identifier
            window: Optional time window identifier

        Returns:
            Key format: kagami:rl:{namespace}:{client}:{window} or kagami:rl:{namespace}:{client}

        Examples:
            >>> RedisKeys.rate_limit("api", "user1", 123)
            'kagami:rl:api:user1:123'
            >>> RedisKeys.rate_limit("api", "user1")
            'kagami:rl:api:user1'
        """
        if window:
            return f"{RedisKeys.BASE}:rl:{namespace}:{client_id}:{window}"
        return f"{RedisKeys.BASE}:rl:{namespace}:{client_id}"

    @staticmethod
    def cache(key: str) -> str:
        """Build cache key.

        Args:
            key: Cache item identifier

        Returns:
            Key format: kagami:cache:{key}

        Examples:
            >>> RedisKeys.cache("model_weights_v1")
            'kagami:cache:model_weights_v1'
        """
        return f"{RedisKeys.BASE}:cache:{key}"

    @staticmethod
    def dlq() -> str:
        """Get Dead Letter Queue key.

        Returns:
            Key: kagami:receipts:dlq

        Examples:
            >>> RedisKeys.dlq()
            'kagami:receipts:dlq'
        """
        return f"{RedisKeys.BASE}:receipts:dlq"

    @staticmethod
    def session(session_id: str) -> str:
        """Build session key.

        Args:
            session_id: Session identifier

        Returns:
            Key format: kagami:sessions:{session_id}

        Examples:
            >>> RedisKeys.session("sess_abc123")
            'kagami:sessions:sess_abc123'
        """
        return f"{RedisKeys.BASE}:sessions:{session_id}"

    @staticmethod
    def flush_lock() -> str:
        """Get receipt flush lock key.

        Used for coordinating memory-to-Redis flushes across instances.

        Returns:
            Key: kagami:receipts:flush_lock

        Examples:
            >>> RedisKeys.flush_lock()
            'kagami:receipts:flush_lock'
        """
        return f"{RedisKeys.BASE}:receipts:flush_lock"

    @staticmethod
    def stream(stream_name: str) -> str:
        """Build stream key.

        Args:
            stream_name: Stream identifier

        Returns:
            Key format: kagami:receipts:stream or kagami:stream:{name}

        Examples:
            >>> RedisKeys.stream("receipts")
            'kagami:receipts:stream'
            >>> RedisKeys.stream("events")
            'kagami:stream:events'
        """
        if stream_name == "receipts":
            return f"{RedisKeys.BASE}:receipts:stream"
        return f"{RedisKeys.BASE}:stream:{stream_name}"

    @staticmethod
    def queue(queue_name: str) -> str:
        """Build queue key.

        Args:
            queue_name: Queue identifier (e.g., 'fallback_queue', 'overflow')

        Returns:
            Key format: kagami:receipts:{queue_name}

        Examples:
            >>> RedisKeys.queue("fallback_queue")
            'kagami:receipts:fallback_queue'
            >>> RedisKeys.queue("overflow")
            'kagami:receipts:overflow'
        """
        return f"{RedisKeys.BASE}:receipts:{queue_name}"

    @staticmethod
    def receipt_ids() -> str:
        """Get receipt IDs set[Any] key.

        Used for deduplication tracking.

        Returns:
            Key: kagami:receipts:ids

        Examples:
            >>> RedisKeys.receipt_ids()
            'kagami:receipts:ids'
        """
        return f"{RedisKeys.BASE}:receipts:ids"

    @staticmethod
    def receipt_list() -> str:
        """Get receipt list[Any] key.

        Used for maintaining a time-ordered list[Any] of all receipts.

        Returns:
            Key: kagami:receipts:all

        Examples:
            >>> RedisKeys.receipt_list()
            'kagami:receipts:all'
        """
        return f"{RedisKeys.BASE}:receipts:all"


__all__ = ["RedisKeys"]
