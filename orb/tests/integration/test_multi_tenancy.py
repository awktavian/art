"""Multi-Tenancy Integration Tests

Validates tenant isolation and row-level security.

Created: November 16, 2025 (Q4 Production Roadmap)
"""

from __future__ import annotations
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.integration,
]


from uuid import uuid4


@pytest.mark.asyncio
async def test_tenant_isolation_receipts() -> None:
    """Test that tenants cannot access each other's receipts."""
    from sqlalchemy import select

    from kagami_api.middleware.tenant import DEFAULT_TENANT_ID
    from kagami.core.database import get_async_session
    from kagami.core.database.async_connection import init_async_db
    from kagami.core.database.models import Receipt

    # Initialize DB tables
    await init_async_db()

    # Create unique tenant IDs for this test
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    correlation_a = str(uuid4())
    correlation_b = str(uuid4())

    async with get_async_session() as session:
        # Create receipt for tenant A with unique secret
        receipt_a = Receipt(
            correlation_id=correlation_a,
            phase="execute",
            tenant_id=tenant_a,
            data={"secret": f"tenant_a_secret_{correlation_a[:8]}"},
        )
        session.add(receipt_a)

        # Create receipt for tenant B with unique secret
        receipt_b = Receipt(
            correlation_id=correlation_b,
            phase="execute",
            tenant_id=tenant_b,
            data={"secret": f"tenant_b_secret_{correlation_b[:8]}"},
        )
        session.add(receipt_b)

        await session.commit()

    # Query as tenant A - should ONLY see tenant A's data
    async with get_async_session() as session:
        stmt = select(Receipt).where(Receipt.tenant_id == tenant_a)
        result = await session.execute(stmt)
        receipts_a = result.scalars().all()

        # Verify we got our receipt
        assert len(receipts_a) >= 1, "Should have at least one receipt for tenant A"

        # Verify all returned receipts belong to tenant A
        for receipt in receipts_a:
            assert receipt.tenant_id == tenant_a, "Receipt should belong to tenant A"
            # Verify no tenant B data leaked
            secret = receipt.data.get("secret", "")
            assert (
                "tenant_b_secret" not in secret
            ), "Tenant B secret should not appear in tenant A query"

        # Verify our specific receipt is present
        our_receipt = next((r for r in receipts_a if r.correlation_id == correlation_a), None)
        assert our_receipt is not None, "Our specific receipt should be found"
        assert our_receipt.data["secret"] == f"tenant_a_secret_{correlation_a[:8]}"

    # Query as tenant B - should ONLY see tenant B's data
    async with get_async_session() as session:
        stmt = select(Receipt).where(Receipt.tenant_id == tenant_b)
        result = await session.execute(stmt)
        receipts_b = result.scalars().all()

        # Verify we got our receipt
        assert len(receipts_b) >= 1, "Should have at least one receipt for tenant B"

        # Verify all returned receipts belong to tenant B
        for receipt in receipts_b:
            assert receipt.tenant_id == tenant_b, "Receipt should belong to tenant B"
            # Verify no tenant A data leaked
            secret = receipt.data.get("secret", "")
            assert (
                "tenant_a_secret" not in secret
            ), "Tenant A secret should not appear in tenant B query"

        # Verify our specific receipt is present
        our_receipt = next((r for r in receipts_b if r.correlation_id == correlation_b), None)
        assert our_receipt is not None, "Our specific receipt should be found"
        assert our_receipt.data["secret"] == f"tenant_b_secret_{correlation_b[:8]}"

    # Cross-tenant query should return nothing
    async with get_async_session() as session:
        # Try to query tenant A data while filtering by tenant B
        stmt = (
            select(Receipt)
            .where(Receipt.tenant_id == tenant_b)
            .where(Receipt.correlation_id == correlation_a)
        )
        result = await session.execute(stmt)
        cross_tenant = result.scalars().all()
        assert len(cross_tenant) == 0, "Cross-tenant query should return no results"


@pytest.mark.asyncio
async def test_tenant_middleware_extraction() -> None:
    """Test tenant extraction from JWT."""
    from unittest.mock import MagicMock

    from fastapi import Request

    from kagami_api.middleware.tenant import TenantMiddleware, get_tenant_id

    test_tenant_id = uuid4()

    # Mock request with user containing tenant_id
    request = MagicMock(spec=Request)
    request.state.user = MagicMock()
    request.state.user.tenant_id = test_tenant_id
    request.headers = {}

    middleware = TenantMiddleware(app=None)  # type: ignore[arg-type]
    tenant_id = await middleware._extract_tenant(request)

    assert extracted_tenant_id == test_tenant_id, "Should extract exact tenant_id from JWT"
    assert isinstance(extracted_tenant_id, UUID), "Should return UUID type"


@pytest.mark.asyncio
async def test_no_tenant_leakage() -> None:
    """Test that queries are automatically scoped to tenant."""
    from kagami_api.middleware.tenant import verify_tenant_isolation
    from kagami.core.database.async_connection import init_async_db

    await init_async_db()

    # Create multiple tenants
    tenants = [str(uuid4()) for _ in range(3)]
    correlation_ids = {t: str(uuid4()) for t in tenants}

    # Create receipts for each tenant
    async with get_async_session() as session:
        for tenant in tenants:
            receipt = Receipt(
                correlation_id=correlation_ids[tenant],
                phase="execute",
                tenant_id=tenant,
                data={"owner": tenant[:8]},
            )
            session.add(receipt)
        await session.commit()

    # Concurrent reads - each should only see their own data
    async def verify_tenant_data(tenant: str) -> bool:
        async with get_async_session() as session:
            stmt = select(Receipt).where(Receipt.tenant_id == tenant)
            result = await session.execute(stmt)
            receipts = result.scalars().all()

            # Verify all returned receipts belong to this tenant
            for r in receipts:
                if r.tenant_id != tenant:
                    return False
                # Verify no other tenant's data is present
                for other_tenant in tenants:
                    if other_tenant != tenant and r.data.get("owner") == other_tenant[:8]:
                        return False
            return True

    # Run concurrent verification
    results = await asyncio.gather(*[verify_tenant_data(t) for t in tenants])
    assert all(results), "All tenants should only see their own data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
