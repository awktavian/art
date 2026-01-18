"""Tests for centralized Redis key namespace management."""

from __future__ import annotations


import pytest
from kagami.core.caching.redis_keys import RedisKeys


class TestRedisKeys:
    """Test suite for RedisKeys namespace builder."""

    def test_receipt_with_phase(self) -> None:
        """Test receipt key with phase."""
        key = RedisKeys.receipt("abc123", "EXECUTE")
        assert key == "kagami:receipts:abc123:EXECUTE"

    def test_receipt_without_phase(self) -> None:
        """Test receipt key without phase."""
        key = RedisKeys.receipt("abc123")
        assert key == "kagami:receipts:abc123"

    def test_receipt_with_empty_phase(self) -> None:
        """Test receipt key with empty phase string."""
        key = RedisKeys.receipt("abc123", "")
        assert key == "kagami:receipts:abc123"

    def test_receipt_with_instance(self) -> None:
        """Test receipt key with instance ID."""
        key = RedisKeys.receipt_with_instance("worker-1", "abc123")
        assert key == "kagami:receipts:worker-1:abc123"

    def test_receipt_prefix(self) -> None:
        """Test receipt key prefix."""
        prefix = RedisKeys.receipt_prefix()
        assert prefix == "kagami:receipts:"

    def test_rate_limit_with_window(self) -> None:
        """Test rate limit key with time window."""
        key = RedisKeys.rate_limit("api", "user1", 123)
        assert key == "kagami:rl:api:user1:123"

    def test_rate_limit_without_window(self) -> None:
        """Test rate limit key without time window."""
        key = RedisKeys.rate_limit("api", "user1")
        assert key == "kagami:rl:api:user1"

    def test_rate_limit_zero_window(self) -> None:
        """Test rate limit key with zero window."""
        key = RedisKeys.rate_limit("api", "user1", 0)
        assert key == "kagami:rl:api:user1"

    def test_cache_key(self) -> None:
        """Test cache key."""
        key = RedisKeys.cache("model_weights_v1")
        assert key == "kagami:cache:model_weights_v1"

    def test_cache_key_with_special_chars(self) -> None:
        """Test cache key with special characters."""
        key = RedisKeys.cache("user:123:settings")
        assert key == "kagami:cache:user:123:settings"

    def test_dlq_key(self) -> None:
        """Test DLQ key."""
        key = RedisKeys.dlq()
        assert key == "kagami:receipts:dlq"

    def test_session_key(self) -> None:
        """Test session key."""
        key = RedisKeys.session("sess_abc123")
        assert key == "kagami:sessions:sess_abc123"

    def test_flush_lock_key(self) -> None:
        """Test flush lock key."""
        key = RedisKeys.flush_lock()
        assert key == "kagami:receipts:flush_lock"

    def test_stream_receipts(self) -> None:
        """Test stream key for receipts."""
        key = RedisKeys.stream("receipts")
        assert key == "kagami:receipts:stream"

    def test_stream_events(self) -> None:
        """Test stream key for events."""
        key = RedisKeys.stream("events")
        assert key == "kagami:stream:events"

    def test_stream_custom(self) -> None:
        """Test stream key for custom stream."""
        key = RedisKeys.stream("metrics")
        assert key == "kagami:stream:metrics"

    def test_queue_fallback(self) -> None:
        """Test queue key for fallback queue."""
        key = RedisKeys.queue("fallback_queue")
        assert key == "kagami:receipts:fallback_queue"

    def test_queue_overflow(self) -> None:
        """Test queue key for overflow."""
        key = RedisKeys.queue("overflow")
        assert key == "kagami:receipts:overflow"

    def test_receipt_ids(self) -> None:
        """Test receipt IDs set key."""
        key = RedisKeys.receipt_ids()
        assert key == "kagami:receipts:ids"

    def test_receipt_list(self) -> None:
        """Test receipt list key."""
        key = RedisKeys.receipt_list()
        assert key == "kagami:receipts:all"

    def test_all_keys_have_base_prefix(self) -> None:
        """Test that all keys start with the base prefix."""
        test_cases = [
            RedisKeys.receipt("test", "PLAN"),
            RedisKeys.receipt_with_instance("w1", "test"),
            RedisKeys.receipt_prefix(),
            RedisKeys.rate_limit("api", "user1", 123),
            RedisKeys.cache("test"),
            RedisKeys.dlq(),
            RedisKeys.session("test"),
            RedisKeys.flush_lock(),
            RedisKeys.stream("receipts"),
            RedisKeys.queue("test"),
            RedisKeys.receipt_ids(),
            RedisKeys.receipt_list(),
        ]

        for key in test_cases:
            assert key.startswith(f"{RedisKeys.BASE}:"), f"Key {key} missing base prefix"

    def test_no_double_colons(self) -> None:
        """Test that no keys have double colons."""
        test_cases = [
            RedisKeys.receipt("test", ""),
            RedisKeys.rate_limit("api", "user1", 0),
        ]

        for key in test_cases:
            assert "::" not in key, f"Key {key} contains double colons"

    def test_receipt_keys_are_unique(self) -> None:
        """Test that different receipt parameters produce unique keys."""
        keys = {
            RedisKeys.receipt("abc", "PLAN"),
            RedisKeys.receipt("abc", "EXECUTE"),
            RedisKeys.receipt("abc", "VERIFY"),
            RedisKeys.receipt("abc"),
            RedisKeys.receipt("xyz", "PLAN"),
        }

        assert len(keys) == 5, "Receipt keys are not unique"

    def test_rate_limit_keys_are_unique(self) -> None:
        """Test that different rate limit parameters produce unique keys."""
        keys = {
            RedisKeys.rate_limit("api", "user1"),
            RedisKeys.rate_limit("api", "user2"),
            RedisKeys.rate_limit("agent", "user1"),
            RedisKeys.rate_limit("api", "user1", 100),
            RedisKeys.rate_limit("api", "user1", 200),
        }

        assert len(keys) == 5, "Rate limit keys are not unique"

    def test_base_prefix_constant(self) -> None:
        """Test that BASE prefix is the expected value."""
        assert RedisKeys.BASE == "kagami"

    def test_key_compatibility(self) -> None:
        """Test that keys are compatible with Redis key patterns."""
        # Redis keys should not contain spaces or special chars that need escaping
        test_keys = [
            RedisKeys.receipt("test-123", "PLAN"),
            RedisKeys.rate_limit("api-v1", "user:123", 1000),
            RedisKeys.cache("model_v1.2.3"),
        ]

        for key in test_keys:
            # Should not contain spaces
            assert " " not in key
            # Should be ASCII-compatible
            assert key.encode("ascii")


class TestRedisKeysIntegration:
    """Integration tests for RedisKeys with actual usage patterns."""

    def test_receipt_lifecycle_keys(self) -> None:
        """Test key generation for receipt lifecycle."""
        correlation_id = "task-12345"

        # Phase-specific keys
        plan_key = RedisKeys.receipt(correlation_id, "PLAN")
        execute_key = RedisKeys.receipt(correlation_id, "EXECUTE")
        verify_key = RedisKeys.receipt(correlation_id, "VERIFY")

        # All should be different
        assert len({plan_key, execute_key, verify_key}) == 3

        # All should share prefix
        prefix = RedisKeys.receipt_prefix()
        assert all(key.startswith(prefix) for key in [plan_key, execute_key, verify_key])

    def test_distributed_receipt_keys(self) -> None:
        """Test key generation for distributed instances."""
        correlation_id = "task-67890"
        instances = ["worker-1", "worker-2", "worker-3"]

        keys = [RedisKeys.receipt_with_instance(inst, correlation_id) for inst in instances]

        # All should be unique
        assert len(set(keys)) == len(instances)

        # All should share base prefix
        prefix = RedisKeys.receipt_prefix()
        assert all(key.startswith(prefix) for key in keys)

    def test_rate_limiting_time_windows(self) -> None:
        """Test key generation for sliding time windows."""
        client_id = "api-user-123"
        namespace = "api"
        windows = [100, 101, 102, 103]  # Sliding time windows

        keys = [RedisKeys.rate_limit(namespace, client_id, window) for window in windows]

        # All should be unique
        assert len(set(keys)) == len(windows)

        # All should follow pattern
        expected_prefix = f"{RedisKeys.BASE}:rl:{namespace}:{client_id}:"
        assert all(key.startswith(expected_prefix) for key in keys)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
