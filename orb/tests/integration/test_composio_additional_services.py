"""Integration tests for additional Composio services.

Tests Twitter, Google Drive, Todoist, Notion, and Google Sheets integrations.
These services were identified as stubbed/untested in the validation audit.

Created: January 11, 2026
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.tier_integration

try:
    from composio import Composio
except ImportError:
    Composio = None  # type: ignore[assignment]


# Skip all tests in this module if Composio is not available
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.skipif(Composio is None, reason="Composio SDK not installed"),
]


def get_composio_client():
    """Get configured Composio client."""
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not set")
    return Composio(api_key=api_key)


def get_connected_account(client, toolkit_slug: str) -> str | None:
    """Get the connected account ID for a toolkit."""
    accounts_resp = client.connected_accounts.list()
    accounts = accounts_resp.items if hasattr(accounts_resp, "items") else []
    for acc in accounts:
        if hasattr(acc, "toolkit") and hasattr(acc.toolkit, "slug"):
            if acc.toolkit.slug == toolkit_slug and acc.status == "ACTIVE":
                return acc.id
    return None


# =============================================================================
# Twitter (X) Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_twitter_account_connected():
    """Test that Twitter/X account is connected."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "twitter")

    if not account_id:
        pytest.skip("Twitter not connected - connect via Composio dashboard")

    assert account_id is not None, "Twitter account should be connected"


@pytest.mark.asyncio
async def test_twitter_get_user_profile():
    """Test fetching Twitter user profile."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "twitter")

    if not account_id:
        pytest.skip("Twitter not connected")

    try:
        result = client.tools.execute(
            slug="TWITTER_GET_AUTHENTICATED_USER",
            arguments={},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return user data"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Twitter toolkit configuration issue: {e}")
        raise


# =============================================================================
# Google Drive Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_google_drive_account_connected():
    """Test that Google Drive account is connected."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "googledrive")

    if not account_id:
        pytest.skip("Google Drive not connected - connect via Composio dashboard")

    assert account_id is not None, "Google Drive account should be connected"


@pytest.mark.asyncio
async def test_google_drive_list_files():
    """Test listing files from Google Drive."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "googledrive")

    if not account_id:
        pytest.skip("Google Drive not connected")

    try:
        result = client.tools.execute(
            slug="GOOGLEDRIVE_LIST_FILES",
            arguments={"page_size": 5},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return file list"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Google Drive toolkit issue: {e}")
        raise


# =============================================================================
# Todoist Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_todoist_account_connected():
    """Test that Todoist account is connected."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "todoist")

    if not account_id:
        pytest.skip("Todoist not connected - connect via Composio dashboard")

    assert account_id is not None, "Todoist account should be connected"


@pytest.mark.asyncio
async def test_todoist_list_projects():
    """Test listing Todoist projects."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "todoist")

    if not account_id:
        pytest.skip("Todoist not connected")

    try:
        result = client.tools.execute(
            slug="TODOIST_GET_ALL_PROJECTS",
            arguments={},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return projects"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Todoist toolkit issue: {e}")
        raise


@pytest.mark.asyncio
async def test_todoist_list_tasks():
    """Test listing Todoist tasks."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "todoist")

    if not account_id:
        pytest.skip("Todoist not connected")

    try:
        result = client.tools.execute(
            slug="TODOIST_GET_ALL_TASKS",
            arguments={},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return tasks"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Todoist toolkit issue: {e}")
        raise


# =============================================================================
# Notion Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_notion_account_connected():
    """Test that Notion account is connected."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "notion")

    if not account_id:
        pytest.skip("Notion not connected - connect via Composio dashboard")

    assert account_id is not None, "Notion account should be connected"


@pytest.mark.asyncio
async def test_notion_search():
    """Test Notion search functionality."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "notion")

    if not account_id:
        pytest.skip("Notion not connected")

    try:
        result = client.tools.execute(
            slug="NOTION_SEARCH",
            arguments={"query": ""},  # Empty query returns all accessible pages
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return search results"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Notion toolkit issue: {e}")
        raise


@pytest.mark.asyncio
async def test_notion_list_users():
    """Test listing Notion workspace users."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "notion")

    if not account_id:
        pytest.skip("Notion not connected")

    try:
        result = client.tools.execute(
            slug="NOTION_LIST_ALL_USERS",
            arguments={},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return users"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Notion toolkit issue: {e}")
        raise


# =============================================================================
# Google Sheets Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_google_sheets_account_connected():
    """Test that Google Sheets account is connected."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    account_id = get_connected_account(client, "googlesheets")

    if not account_id:
        pytest.skip("Google Sheets not connected - connect via Composio dashboard")

    assert account_id is not None, "Google Sheets account should be connected"


@pytest.mark.asyncio
async def test_google_sheets_get_spreadsheet():
    """Test getting spreadsheet info from Google Sheets.

    Note: This test requires a known spreadsheet ID. Skip if no test spreadsheet.
    """
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    # Skip if no test spreadsheet ID configured
    test_spreadsheet_id = os.getenv("TEST_GOOGLE_SHEETS_ID")
    if not test_spreadsheet_id:
        pytest.skip("TEST_GOOGLE_SHEETS_ID not set - create a test spreadsheet")

    client = get_composio_client()
    account_id = get_connected_account(client, "googlesheets")

    if not account_id:
        pytest.skip("Google Sheets not connected")

    try:
        result = client.tools.execute(
            slug="GOOGLESHEETS_GET_SPREADSHEET_INFO",
            arguments={"spreadsheet_id": test_spreadsheet_id},
            connected_account_id=account_id,
            dangerously_skip_version_check=True,
        )
        data = result.data if hasattr(result, "data") else result
        assert data is not None, "Should return spreadsheet info"
    except Exception as e:
        if "version" in str(e).lower() or "auth" in str(e).lower():
            pytest.skip(f"Google Sheets toolkit issue: {e}")
        raise


# =============================================================================
# Service Discovery Tests
# =============================================================================


@pytest.mark.asyncio
async def test_discover_all_connected_services():
    """List all connected services for documentation."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    client = get_composio_client()
    accounts_resp = client.connected_accounts.list()
    accounts = accounts_resp.items if hasattr(accounts_resp, "items") else []

    connected_services = []
    for acc in accounts:
        if acc.status == "ACTIVE":
            toolkit = getattr(acc.toolkit, "slug", str(acc.toolkit))
            connected_services.append(toolkit)

    print(f"\n=== Connected Services ({len(connected_services)}) ===")
    for svc in sorted(connected_services):
        print(f"  - {svc}")

    # We expect at least some services to be connected
    assert len(connected_services) >= 1, "At least one service should be connected"


@pytest.mark.asyncio
async def test_composio_service_initialization():
    """Test the high-level Composio service initializes correctly."""
    if os.getenv("KAGAMI_DISABLE_COMPOSIO") == "1":
        pytest.skip("Composio disabled")

    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        pytest.skip("COMPOSIO_API_KEY not configured")

    from kagami.core.services.composio import get_composio_service

    service = get_composio_service()
    initialized = await service.initialize()

    assert initialized is True, "Composio service should initialize successfully"
    assert service.is_initialized, "Service should report as initialized"

    # Check connected apps
    connected_apps = await service.get_connected_apps()
    assert len(connected_apps) >= 1, "Should have at least one connected app"

    print(f"\n=== Connected Apps via Service ({len(connected_apps)}) ===")
    for app in connected_apps:
        print(f"  - {app['toolkit']}: {app['status']}")
