"""Test CockroachDB JSON codec patches.

Dec 21, 2025 (Crystal): Verifies that the JSON codec patches are correctly
applied to handle CockroachDB's different pg_catalog.json type behavior.

The patches must:
1. Be applied to PGDialect_asyncpg (not PGDialect)
2. Gracefully handle ValueError for pg_catalog.json
3. Allow connections to proceed without JSON codec if unavailable
"""

from __future__ import annotations
import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.timeout(5),
]


class TestCockroachJSONPatches:
    """Test CockroachDB JSON codec compatibility patches."""

    def test_patches_are_applied_to_correct_class(self) -> None:
        """Patches must target PGDialect_asyncpg, not PGDialect.

        SQLAlchemy 2.x has setup_asyncpg_json_codec on PGDialect_asyncpg,
        not on the base PGDialect class.
        """
        # Import triggers patches
        from kagami.core.database import cockroach
        from sqlalchemy.dialects.postgresql import asyncpg as sqla_asyncpg

        # Verify the method exists and is patched
        json_method = sqla_asyncpg.PGDialect_asyncpg.setup_asyncpg_json_codec
        jsonb_method = sqla_asyncpg.PGDialect_asyncpg.setup_asyncpg_jsonb_codec

        # Check they're our safe wrappers
        assert (
            json_method.__name__ == "_safe_json_codec"
        ), f"JSON codec patch not applied. Got {json_method.__name__}"
        assert (
            jsonb_method.__name__ == "_safe_jsonb_codec"
        ), f"JSONB codec patch not applied. Got {jsonb_method.__name__}"

    def test_asyncpg_set_type_codec_patched(self) -> None:
        """asyncpg.connection.Connection.set_type_codec must be patched."""
        from kagami.core.database import cockroach
        import asyncpg.connection

        method = asyncpg.connection.Connection.set_type_codec
        assert (
            method.__name__ == "_safe_set_type_codec"
        ), f"set_type_codec patch not applied. Got {method.__name__}"

    def test_cockroach_module_imports_cleanly(self) -> None:
        """cockroach module must import without errors.

        Dec 21, 2025 FIX: The module previously failed to import because
        it tried to import 'settings' from kagami.core.config, which
        doesn't exist. Now uses config_root.config instead.
        """
        try:
            from kagami.core.database import cockroach

            assert cockroach is not None
        except ImportError as e:
            pytest.fail(f"cockroach module failed to import: {e}")

    @pytest.mark.asyncio
    async def test_safe_set_type_codec_handles_pg_catalog_error(self) -> None:
        """_safe_set_type_codec should gracefully handle pg_catalog.json errors.

        When CockroachDB doesn't support pg_catalog.json type introspection,
        the patched set_type_codec should return None without error.
        """
        from kagami.core.database import cockroach

        # Store original for restoration
        import asyncpg.connection

        original_method = cockroach._orig_set_type_codec

        # Create a connection-like object
        class MockConnection:
            """Mock that simulates asyncpg Connection for codec patching."""

            pass

        # Simulate what happens when the original method raises
        async def failing_set_type_codec(self, typename, *args, **kwargs) -> None:
            raise ValueError("unknown type: pg_catalog.json")

        # Temporarily replace original to simulate error
        cockroach._orig_set_type_codec = failing_set_type_codec

        try:
            mock_conn = MockConnection()
            # The patched method should handle this gracefully
            result = await cockroach._safe_set_type_codec(mock_conn, "json")
            # Should return None, not raise
            assert result is None, "Expected None return on pg_catalog.json error"
        finally:
            # Restore
            cockroach._orig_set_type_codec = original_method


# Mark all tests with timeout
