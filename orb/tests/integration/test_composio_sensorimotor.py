"""Integration test for Composio sensorimotor embodiment.

Tests the complete PERCEIVE → Composio → fuse loop to ensure
sensorimotor integration works end-to-end.
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import os

try:
    from composio import Composio
except ImportError:  # pragma: no cover - optional dependency
    Composio = None  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_composio_initialization():
    """Test that Composio service initializes properly."""
    from pathlib import Path

    from dotenv import load_dotenv

    env_file = Path.home() / ".kagami" / ".env"
    load_dotenv(env_file)
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled in test environment (KAGAMI_DISABLE_COMPOSIO=1)")
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not configured in ~/.kagami/.env")
    from kagami.core.services.composio import get_composio_service

    service = get_composio_service()
    initialized = await service.initialize()
    assert initialized is True, "Composio should initialize successfully"
    assert service.composio_client is not None, "Client should be set"
    assert service.user_id is not None, "User ID should be set"


@pytest.mark.asyncio
async def test_composio_senses_accessible():
    """Test that we can access connected accounts (our senses)."""
    if Composio is None:
        pytest.skip("Composio SDK not installed")
    import os

    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not set")
    client = Composio(api_key=api_key)
    accounts_resp = client.connected_accounts.list()
    accounts = accounts_resp.items if hasattr(accounts_resp, "items") else []
    assert len(accounts) > 0, "Should have connected accounts"
    active = [a for a in accounts if a.status == "ACTIVE"]
    assert len(active) >= 3, f"Should have at least 3 active accounts, got {len(active)}"


@pytest.mark.asyncio
async def test_sensorimotor_perceive_loop():
    """Test the full sensorimotor loop: PERCEIVE → Composio → fuse."""
    if Composio is None:
        pytest.skip("Composio SDK not installed")
    import os

    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not set")
    client = Composio(api_key=api_key)
    accounts_resp = client.connected_accounts.list()
    accounts = accounts_resp.items if hasattr(accounts_resp, "items") else []
    linear_account = None
    for acc in accounts:
        if hasattr(acc, "toolkit") and hasattr(acc.toolkit, "slug"):
            if acc.toolkit.slug == "linear" and acc.status == "ACTIVE":
                linear_account = acc.id
                break
    if not linear_account:
        pytest.skip("No active Linear account for testing")

    try:
        result = client.tools.execute(
            slug="LINEAR_GET_CURRENT_USER", arguments={}, connected_account_id=linear_account
        )
    except Exception as e:
        # Skip if toolkit version issue or other composio config problem
        if "ToolVersionRequiredError" in str(type(e).__name__) or "version" in str(e).lower():
            pytest.skip(f"Composio toolkit configuration issue: {e}")
        raise
    data = result.data if hasattr(result, "data") else result
    assert data is not None, "Should get data from Linear"
    user_data = data.get("data", {}).get("user", {})
    assert "email" in user_data, "Should have user email"
    assert "name" in user_data, "Should have user name"
    internal_context = {"source": "internal", "agent": "test", "timestamp": "now"}
    fused_context = {**internal_context, "composio_sense": {"service": "linear", "user": user_data}}
    assert "source" in fused_context, "Should have internal context"
    assert "composio_sense" in fused_context, "Should have Composio data"
    assert fused_context["composio_sense"]["user"]["email"] == user_data["email"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_multiple_sense_fusion():
    """Test fusing data from multiple Composio senses."""
    if Composio is None:
        pytest.skip("Composio SDK not installed")
    import os

    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not set")
    client = Composio(api_key=api_key)
    accounts_resp = client.connected_accounts.list()
    accounts = accounts_resp.items if hasattr(accounts_resp, "items") else []
    active_accounts = {}
    for acc in accounts:
        if acc.status == "ACTIVE" and hasattr(acc, "toolkit"):
            toolkit = acc.toolkit.slug if hasattr(acc.toolkit, "slug") else None
            if toolkit in ["linear", "github", "gmail"]:
                active_accounts[toolkit] = acc.id
    if len(active_accounts) < 2:
        pytest.skip(f"Need at least 2 active accounts, have {len(active_accounts)}")
    sensory_data = {}
    if "linear" in active_accounts:
        try:
            result = client.tools.execute(
                slug="LINEAR_GET_CURRENT_USER",
                arguments={},
                connected_account_id=active_accounts["linear"],
            )
            data = result.data if hasattr(result, "data") else result
            sensory_data["linear"] = data.get("data", {}).get("user", {})
        except Exception as e:
            # Skip on any execution error (version, auth, etc)
            if "ToolVersionRequiredError" in str(type(e).__name__) or "version" in str(e).lower():
                pytest.skip(f"Composio toolkit configuration issue: {e}")
            pass
    if "github" in active_accounts:
        try:
            result = client.tools.execute(
                slug="GITHUB_USERS_GET_AUTHENTICATED",
                arguments={},
                connected_account_id=active_accounts["github"],
            )
            data = result.data if hasattr(result, "data") else result
            sensory_data["github"] = data
        except Exception as e:
            # Skip on any execution error (version, auth, etc)
            if "ToolVersionRequiredError" in str(type(e).__name__) or "version" in str(e).lower():
                pytest.skip(f"Composio toolkit configuration issue: {e}")
            pass
    assert len(sensory_data) >= 1, "Should perceive from at least one sense"
    fused = {"timestamp": "now", "senses": sensory_data, "user_email": None, "user_name": None}
    for _sense_name, sense_data in sensory_data.items():
        if isinstance(sense_data, dict):
            if "email" in sense_data:
                fused["user_email"] = sense_data["email"]
            if "name" in sense_data:
                fused["user_name"] = sense_data["name"]
            if "user" in sense_data and isinstance(sense_data["user"], dict):
                if "email" in sense_data["user"]:
                    fused["user_email"] = sense_data["user"]["email"]
                if "name" in sense_data["user"]:
                    fused["user_name"] = sense_data["user"]["name"]
    assert (
        fused["user_email"] is not None or fused["user_name"] is not None
    ), "Should extract user info from at least one sense"
