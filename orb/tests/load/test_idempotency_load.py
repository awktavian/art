"""Load test: Idempotency prevents duplicates under concurrent load.

Tests that idempotency middleware correctly handles:
- 10,000 concurrent requests
- Duplicate idempotency keys
- High throughput scenarios
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_e2e



import asyncio
import time
from collections import defaultdict


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_idempotency_concurrent_10k():
    """Test: 10K concurrent requests with duplicate keys correctly rejected."""
    from unittest.mock import Mock

    from fastapi import HTTPException, Request

    from kagami_api.idempotency import ensure_idempotency

    # Stats
    accepted = 0
    rejected = 0
    errors = []

    async def make_request(idem_key: str, request_id: int):
        """Simulate single request with idempotency key."""
        nonlocal accepted, rejected

        # Mock request
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"Idempotency-Key": idem_key}
        request.url = Mock()
        request.url.path = f"/api/test/{request_id}"
        request.state = Mock()

        try:
            await ensure_idempotency(request, ttl_seconds=300)
            accepted += 1
        except HTTPException as e:
            if e.status_code == 409:
                rejected += 1
            else:
                errors.append(e)

    # Test scenario: 10K requests, 100 unique keys (100 requests per key)
    tasks = []
    num_unique_keys = 100
    requests_per_key = 100

    for key_id in range(num_unique_keys):
        idem_key = f"load-test-key-{key_id}"
        for req_id in range(requests_per_key):
            tasks.append(make_request(idem_key, key_id * requests_per_key + req_id))

    # Execute all concurrently
    start = time.time()
    await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start

    # Assertions
    total_requests = num_unique_keys * requests_per_key
    assert (
        accepted == num_unique_keys
    ), f"Expected {num_unique_keys} accepted (first per key), got {accepted}"
    assert (
        rejected == total_requests - num_unique_keys
    ), f"Expected {total_requests - num_unique_keys} rejected (duplicates), got {rejected}"
    assert len(errors) == 0, f"Unexpected errors: {errors}"

    # Performance
    throughput = total_requests / duration
    print("\n✅ Idempotency load test passed:")
    print(f"   Total requests: {total_requests}")
    print(f"   Accepted: {accepted} (unique keys)")
    print(f"   Rejected: {rejected} (duplicates)")
    print(f"   Duration: {duration:.2f}s")
    print(f"   Throughput: {throughput:.0f} req/s")

    # Should handle at least 1000 req/s
    assert throughput > 1000, f"Expected >1000 req/s, got {throughput:.0f}"


@pytest.mark.load
@pytest.mark.slow
@pytest.mark.asyncio
async def test_idempotency_prevents_double_execution():
    """Test: Duplicate keys don't cause double execution."""
    executions = defaultdict(int)

    async def tracked_operation(operation_id: str):
        """Operation that tracks executions."""
        executions[operation_id] += 1
        await asyncio.sleep(0.01)  # Simulate work
        return {"result": "success", "operation_id": operation_id}

    from unittest.mock import Mock

    from fastapi import Request

    from kagami_api.idempotency import ensure_idempotency

    async def request_with_idempotency(idem_key: str, op_id: str):
        """Make request with idempotency check."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"Idempotency-Key": idem_key}
        request.url = Mock()
        request.url.path = f"/api/op/{op_id}"
        request.state = Mock()

        try:
            await ensure_idempotency(request, ttl_seconds=300)
            # Only execute if not duplicate
            return await tracked_operation(op_id)
        except Exception:
            # Duplicate key - don't execute
            return {"result": "duplicate"}

    # Send same key 5 times concurrently
    idem_key = "test-duplicate-execution"
    op_id = "op-123"

    tasks = [request_with_idempotency(idem_key, op_id) for _ in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Only 1 execution should occur
    assert (
        executions[op_id] == 1
    ), f"Operation executed {executions[op_id]} times, expected 1 (idempotency violated!)"

    print("\n✅ Double execution prevented:")
    print("   5 requests → 1 execution (idempotency working)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
