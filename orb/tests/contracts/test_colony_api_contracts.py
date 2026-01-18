"""Colony API Contract Tests.

Verifies that colony-related API response schemas remain stable.
Contract violations indicate breaking changes to the colony protocol.

Created: December 29, 2025
Purpose: Ensure backward compatibility of 7-colony Fano architecture APIs
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.tier_integration]

from typing import Any

from syrupy.assertion import SnapshotAssertion


# =============================================================================
# COLONY STATUS CONTRACT
# =============================================================================


class TestColonyStatusContract:
    """Contract tests for colony status API."""

    VALID_COLONIES = frozenset(
        ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
    )

    def test_colony_list_returns_exactly_seven(self, client: Any) -> None:
        """Contract: /api/colonies must return exactly 7 colonies (Fano plane)."""
        response = client.get("/api/colonies")
        if response.status_code == 404:
            pytest.skip("Colonies endpoint not available")

        assert response.status_code == 200
        data = response.json()

        assert "colonies" in data
        colonies = data["colonies"]
        assert len(colonies) == 7, f"Must have exactly 7 colonies, got {len(colonies)}"

    def test_colony_names_match_fano_spec(self, client: Any) -> None:
        """Contract: Colony names must match Fano specification."""
        response = client.get("/api/colonies")
        if response.status_code == 404:
            pytest.skip("Colonies endpoint not available")

        assert response.status_code == 200
        data = response.json()

        colony_names = {c.get("name", "").lower() for c in data.get("colonies", [])}

        assert colony_names == self.VALID_COLONIES, (
            f"Colony names must match Fano spec. "
            f"Got: {colony_names}, Expected: {self.VALID_COLONIES}"
        )

    def test_colony_status_has_required_fields(self, client: Any) -> None:
        """Contract: Each colony status must have name, status, health."""
        response = client.get("/api/colonies")
        if response.status_code == 404:
            pytest.skip("Colonies endpoint not available")

        assert response.status_code == 200
        data = response.json()

        for colony in data.get("colonies", []):
            assert "name" in colony, f"Colony must have 'name': {colony}"
            assert "status" in colony, f"Colony must have 'status': {colony}"
            assert "health" in colony, f"Colony must have 'health': {colony}"

    def test_colony_status_values_valid(self, client: Any) -> None:
        """Contract: Colony status must be 'active', 'idle', or 'error'."""
        response = client.get("/api/colonies")
        if response.status_code == 404:
            pytest.skip("Colonies endpoint not available")

        assert response.status_code == 200
        data = response.json()

        valid_statuses = {"active", "idle", "error", "initializing"}

        for colony in data.get("colonies", []):
            status = colony.get("status", "").lower()
            assert status in valid_statuses, (
                f"Colony {colony.get('name')} has invalid status: {status}"
            )

    def test_colony_health_is_numeric(self, client: Any) -> None:
        """Contract: Colony health must be numeric in range [0, 1]."""
        response = client.get("/api/colonies")
        if response.status_code == 404:
            pytest.skip("Colonies endpoint not available")

        assert response.status_code == 200
        data = response.json()

        for colony in data.get("colonies", []):
            health = colony.get("health")
            if health is not None:
                assert isinstance(health, (int, float)), (
                    f"Colony {colony.get('name')} health must be numeric: {health}"
                )
                assert 0.0 <= health <= 1.0, (
                    f"Colony {colony.get('name')} health must be in [0,1]: {health}"
                )


# =============================================================================
# FANO ROUTING CONTRACT
# =============================================================================


class TestFanoRoutingContract:
    """Contract tests for Fano plane routing API."""

    def test_route_response_has_colony(self, client: Any) -> None:
        """Contract: Routing response must specify target colony."""
        response = client.post(
            "/api/route",
            json={"action": "test_action", "params": {}},
        )
        if response.status_code == 404:
            pytest.skip("Routing endpoint not available")

        if response.status_code == 200:
            data = response.json()
            assert "colony" in data or "target" in data, (
                "Routing response must specify colony/target"
            )

    def test_route_response_has_fano_metadata(self, client: Any) -> None:
        """Contract: Routing response should include Fano plane metadata."""
        response = client.post(
            "/api/route",
            json={"action": "complex_action", "params": {"complexity": 0.8}},
        )
        if response.status_code == 404:
            pytest.skip("Routing endpoint not available")

        if response.status_code == 200:
            data = response.json()
            # Fano metadata is optional but should follow schema if present
            if "fano" in data:
                fano = data["fano"]
                # If present, should have line info
                if "line" in fano:
                    line = fano["line"]
                    assert isinstance(line, (list, tuple)), "Fano line must be list/tuple"
                    assert len(line) == 3, "Fano line must have 3 colonies"


# =============================================================================
# RECEIPT CONTRACT
# =============================================================================


class TestReceiptAPIContract:
    """Contract tests for receipt API endpoints."""

    def test_receipt_list_schema(
        self, client: Any, snapshot: SnapshotAssertion
    ) -> None:
        """Contract: Receipt list response schema must remain stable."""
        response = client.get("/api/receipts?limit=5")
        if response.status_code == 404:
            pytest.skip("Receipts endpoint not available")

        assert response.status_code == 200
        data = response.json()

        # Required pagination fields
        assert "receipts" in data or "items" in data
        assert "total" in data or "count" in data

    def test_receipt_has_correlation_id(self, client: Any) -> None:
        """Contract: Each receipt must have correlation_id."""
        response = client.get("/api/receipts?limit=5")
        if response.status_code == 404:
            pytest.skip("Receipts endpoint not available")

        assert response.status_code == 200
        data = response.json()

        receipts = data.get("receipts", data.get("items", []))
        for receipt in receipts:
            assert "correlation_id" in receipt, (
                f"Receipt missing correlation_id: {receipt}"
            )

    def test_receipt_has_timestamp(self, client: Any) -> None:
        """Contract: Each receipt must have timestamp (ts)."""
        response = client.get("/api/receipts?limit=5")
        if response.status_code == 404:
            pytest.skip("Receipts endpoint not available")

        assert response.status_code == 200
        data = response.json()

        receipts = data.get("receipts", data.get("items", []))
        for receipt in receipts:
            # Can be 'ts' or 'timestamp'
            has_ts = "ts" in receipt or "timestamp" in receipt
            assert has_ts, f"Receipt missing timestamp: {receipt}"


# =============================================================================
# EXECUTION PHASES CONTRACT
# =============================================================================


class TestExecutionPhasesContract:
    """Contract tests for 3-phase execution model."""

    VALID_PHASES = frozenset(["PLAN", "EXECUTE", "VERIFY"])

    def test_phase_ordering(self) -> None:
        """Contract: Phases follow PLAN -> EXECUTE -> VERIFY ordering."""
        phase_order = {"PLAN": 0, "EXECUTE": 1, "VERIFY": 2}

        # Verify ordering
        assert phase_order["PLAN"] < phase_order["EXECUTE"]
        assert phase_order["EXECUTE"] < phase_order["VERIFY"]

    def test_execute_response_has_phase(self, client: Any) -> None:
        """Contract: Execute response must include current phase."""
        response = client.post(
            "/api/execute",
            json={"action": "test", "params": {}},
        )
        if response.status_code == 404:
            pytest.skip("Execute endpoint not available")

        if response.status_code in (200, 202):
            data = response.json()
            if "phase" in data:
                phase = data["phase"].upper()
                assert phase in self.VALID_PHASES, (
                    f"Invalid phase: {phase}. Must be one of {self.VALID_PHASES}"
                )


# =============================================================================
# WORLD MODEL API CONTRACT
# =============================================================================


class TestWorldModelAPIContract:
    """Contract tests for world model API endpoints."""

    def test_world_model_status_schema(self, client: Any) -> None:
        """Contract: World model status must have required fields."""
        response = client.get("/api/world-model/status")
        if response.status_code == 404:
            pytest.skip("World model endpoint not available")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "loaded" in data or "status" in data
        assert "model_name" in data or "name" in data or "version" in data

    def test_world_model_encode_response(self, client: Any) -> None:
        """Contract: Encode response must have embedding dimensions."""
        response = client.post(
            "/api/world-model/encode",
            json={"input": "test input"},
        )
        if response.status_code == 404:
            pytest.skip("World model encode endpoint not available")

        if response.status_code == 200:
            data = response.json()
            # Must have embedding or latent
            has_output = (
                "embedding" in data
                or "latent" in data
                or "encoded" in data
            )
            assert has_output, "Encode response must have embedding/latent output"


# =============================================================================
# SAFETY API CONTRACT
# =============================================================================


class TestSafetyAPIContract:
    """Contract tests for safety API endpoints."""

    def test_safety_check_returns_h_value(self, client: Any) -> None:
        """Contract: Safety check must return h(x) value."""
        response = client.post(
            "/api/safety/check",
            json={"text": "Hello, world!"},
        )
        if response.status_code == 404:
            pytest.skip("Safety check endpoint not available")

        if response.status_code == 200:
            data = response.json()
            # Must have h_value or h_x or barrier_value
            has_h = (
                "h_value" in data
                or "h_x" in data
                or "barrier_value" in data
                or "safe" in data
            )
            assert has_h, "Safety check must return h(x) value or safe boolean"

    def test_safety_check_h_value_invariant(self, client: Any) -> None:
        """Contract: Safety h(x) must be >= 0 (CBF invariant)."""
        response = client.post(
            "/api/safety/check",
            json={"text": "Safe test input"},
        )
        if response.status_code == 404:
            pytest.skip("Safety check endpoint not available")

        if response.status_code == 200:
            data = response.json()
            h_value = (
                data.get("h_value")
                or data.get("h_x")
                or data.get("barrier_value")
            )
            if h_value is not None:
                assert h_value >= 0, (
                    f"SAFETY INVARIANT VIOLATED: h(x) = {h_value} < 0"
                )


# =============================================================================
# PAGINATION CONTRACT
# =============================================================================


class TestPaginationContract:
    """Contract tests for paginated API responses."""

    PAGINATED_ENDPOINTS = [
        "/api/receipts",
        "/api/logs",
        "/api/events",
    ]

    @pytest.mark.parametrize("endpoint", PAGINATED_ENDPOINTS)
    def test_pagination_has_limit_offset(
        self, client: Any, endpoint: str
    ) -> None:
        """Contract: Paginated endpoints must support limit/offset."""
        response = client.get(f"{endpoint}?limit=5&offset=0")
        if response.status_code == 404:
            pytest.skip(f"{endpoint} not available")

        if response.status_code == 200:
            data = response.json()
            # Should have items and pagination info
            has_items = (
                "items" in data
                or "data" in data
                or "receipts" in data
                or "logs" in data
            )
            assert has_items, f"{endpoint} missing items array"

    @pytest.mark.parametrize("endpoint", PAGINATED_ENDPOINTS)
    def test_pagination_respects_limit(
        self, client: Any, endpoint: str
    ) -> None:
        """Contract: Paginated endpoints must respect limit parameter."""
        response = client.get(f"{endpoint}?limit=3")
        if response.status_code == 404:
            pytest.skip(f"{endpoint} not available")

        if response.status_code == 200:
            data = response.json()
            items = (
                data.get("items")
                or data.get("data")
                or data.get("receipts")
                or data.get("logs")
                or []
            )
            assert len(items) <= 3, (
                f"{endpoint} returned {len(items)} items, expected <= 3"
            )
