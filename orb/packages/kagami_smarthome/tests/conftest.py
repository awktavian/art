"""Pytest configuration for smarthome tests.

CRITICAL: All tests must run without making real network connections.

This conftest ensures:
1. No real API calls to UniFi, Control4, etc.
2. Environment variables are set for test mode
3. Mocks are available for all integrations

Created: December 30, 2025
h(x) >= 0 always.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# ENVIRONMENT SETUP - Runs before any imports
# =============================================================================

# Set test environment to prevent real connections
os.environ["KAGAMI_ENV"] = "test"
os.environ["KAGAMI_TEST_MODE"] = "1"


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def mock_keychain():
    """Mock the secrets/keychain to prevent credential lookups.

    This prevents tests from:
    - Triggering 2FA requests (e.g., UniFi Cloud)
    - Accessing real credentials
    """
    with patch("kagami_smarthome.secrets.secrets") as mock_secrets:
        # Return None for all credential lookups
        mock_secrets.get.return_value = None
        yield mock_secrets


@pytest.fixture
def mock_unifi():
    """Mock UniFi integration."""
    mock = MagicMock()
    mock.connect = AsyncMock(return_value=False)
    mock.disconnect = AsyncMock()
    mock.get_clients = AsyncMock(return_value=[])
    mock.is_healthy = False
    return mock


@pytest.fixture
def mock_control4():
    """Mock Control4 integration."""
    mock = MagicMock()
    mock.connect = AsyncMock(return_value=False)
    mock.disconnect = AsyncMock()
    mock.set_room_lights = AsyncMock(return_value=True)
    mock.get_lights = MagicMock(return_value={})
    mock.is_healthy = False
    return mock


@pytest.fixture
def mock_denon():
    """Mock Denon integration."""
    mock = MagicMock()
    mock.connect = AsyncMock(return_value=False)
    mock.disconnect = AsyncMock()
    mock.power_on = AsyncMock(return_value=True)
    mock.power_off = AsyncMock(return_value=True)
    mock.set_volume = AsyncMock(return_value=True)
    mock.is_healthy = False
    return mock


@pytest.fixture
def test_config():
    """Create a test config with no real hosts."""
    from kagami_smarthome.types import SmartHomeConfig

    return SmartHomeConfig(
        # All hosts set to None = no real connections
        unifi_host=None,
        control4_host=None,
        denon_host=None,
        lg_tv_host=None,
        samsung_tv_host=None,
        mitsubishi_host=None,
        tesla_email=None,
        eight_sleep_email=None,
        august_email=None,
        # Test mode settings
        known_devices=[],
        away_timeout_minutes=30,
    )


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession to prevent any HTTP requests."""
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session.get = AsyncMock()
        mock_session.post = AsyncMock()
        mock_session.close = AsyncMock()
        mock_session_class.return_value = mock_session
        yield mock_session


# =============================================================================
# MARKERS
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (may need real connections)",
    )
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow running",
    )


# =============================================================================
# HOOKS
# =============================================================================


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly requested."""
    skip_integration = pytest.mark.skip(reason="Integration tests disabled by default")

    for item in items:
        if "integration" in item.keywords:
            # Skip integration tests unless --run-integration flag passed
            if not config.getoption("--run-integration", default=False):
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that may require real connections",
    )
