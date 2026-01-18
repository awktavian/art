"""Comprehensive Tesla Integration Tests.

Tests for:
- TeslaIntegration class
- OAuth flow and token management
- API client operations
- Vehicle state management
- Geofencing/presence detection
- Vehicle commands
- Token refresh logic
- Error handling

Coverage target: Increase from 35/100 to 80+/100

Created: December 31, 2025
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami_smarthome.integrations.tesla import (
    API_BASE,
    ChargingState,
    TeslaIntegration,
    TeslaState,
    VehicleState,
)
from kagami_smarthome.types import SmartHomeConfig

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def tesla_config():
    """Create test config with Tesla credentials."""
    return SmartHomeConfig(
        tesla_access_token="test_access_token_12345",
        tesla_refresh_token="test_refresh_token_67890",
        tesla_client_id="test_client_id",
        tesla_client_secret="test_client_secret",
        home_latitude=47.6815,
        home_longitude=-122.3406,
    )


@pytest.fixture
def tesla_config_no_token():
    """Create test config without Tesla token."""
    return SmartHomeConfig(
        tesla_access_token=None,
        tesla_refresh_token=None,
    )


@pytest.fixture
def mock_vehicle_response():
    """Mock response for vehicles endpoint."""
    return {
        "response": [
            {
                "id": 12345678901234567,
                "vehicle_id": 1234567890,
                "vin": "5YJ3E1EA1NF123456",
                "display_name": "Test Model S",
                "state": "online",
            }
        ]
    }


@pytest.fixture
def mock_vehicle_data_response():
    """Mock response for vehicle_data endpoint."""
    return {
        "response": {
            "id": 12345678901234567,
            "state": "online",
            "drive_state": {
                "latitude": 47.6815,
                "longitude": -122.3406,
                "heading": 180,
                "speed": 0,
                "shift_state": "P",
            },
            "charge_state": {
                "battery_level": 75,
                "charging_state": "Disconnected",
                "charge_limit_soc": 80,
            },
            "climate_state": {
                "inside_temp": 22.0,
                "outside_temp": 15.0,
                "is_climate_on": False,
            },
            "vehicle_state": {
                "locked": True,
                "odometer": 12345.6,
            },
        }
    }


@pytest.fixture
def mock_token_response():
    """Mock response for token refresh."""
    return {
        "access_token": "new_access_token_abc123",
        "refresh_token": "new_refresh_token_xyz789",
        "expires_in": 28800,
    }


@pytest.fixture
def mock_aiohttp_session():
    """Create a properly mocked aiohttp session."""
    session = MagicMock()
    session.get = AsyncMock()
    session.post = AsyncMock()
    session.close = AsyncMock()
    return session


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestTeslaInitialization:
    """Test TeslaIntegration initialization."""

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_init_with_config_tokens(self, mock_keychain, tesla_config):
        """Test initialization with tokens in config."""
        integration = TeslaIntegration(tesla_config)

        assert integration._access_token == "test_access_token_12345"
        assert integration._refresh_token == "test_refresh_token_67890"
        assert not integration.is_connected
        assert integration._home_lat == 47.6815
        assert integration._home_lon == -122.3406

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_init_without_tokens(self, mock_keychain, tesla_config_no_token):
        """Test initialization without tokens."""
        integration = TeslaIntegration(tesla_config_no_token)

        assert integration._access_token is None
        assert integration._refresh_token is None
        assert not integration.is_connected

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_init_default_home_location(self, mock_keychain):
        """Test default home location is Green Lake."""
        config = SmartHomeConfig()
        integration = TeslaIntegration(config)

        # Default Green Lake coordinates
        assert integration._home_lat == 47.6815
        assert integration._home_lon == -122.3406

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_can_sign_commands_without_key(self, mock_keychain, tesla_config):
        """Test can_sign_commands is False without private key."""
        integration = TeslaIntegration(tesla_config)
        assert not integration.can_sign_commands


# =============================================================================
# CONNECTION TESTS
# =============================================================================


class TestTeslaConnection:
    """Test TeslaIntegration connection."""

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_connect_without_token_returns_false(self, mock_keychain, tesla_config_no_token):
        """Test connect fails without access token."""
        integration = TeslaIntegration(tesla_config_no_token)
        result = await integration.connect()
        assert result is False

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("aiohttp.ClientSession")
    async def test_connect_success(
        self,
        mock_session_class,
        mock_keychain,
        tesla_config,
        mock_vehicle_response,
        mock_vehicle_data_response,
    ):
        """Test successful connection."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock GET responses
        async def mock_get(url, **kwargs):
            response = MagicMock()
            if "/vehicles" in url and "vehicle_data" not in url:
                response.status = 200
                response.json = AsyncMock(return_value=mock_vehicle_response)
            elif "vehicle_data" in url:
                response.status = 200
                response.json = AsyncMock(return_value=mock_vehicle_data_response)
            else:
                response.status = 404
            return response

        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=mock_get))

        # Create context manager for get
        async def get_context(*args, **kwargs):
            return await mock_get(*args, **kwargs)

        mock_session.get = MagicMock()
        mock_session.get.return_value.__aenter__ = AsyncMock(side_effect=get_context)
        mock_session.get.return_value.__aexit__ = AsyncMock()

        integration = TeslaIntegration(tesla_config)

        # Manually set session and mock _api_get
        integration._session = mock_session
        integration._api_get = AsyncMock(
            side_effect=[mock_vehicle_response, mock_vehicle_data_response]
        )

        result = await integration.connect()

        assert result is True
        assert integration._vehicle_id == "12345678901234567"
        assert integration._vehicle_vin == "5YJ3E1EA1NF123456"
        assert integration.is_connected

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_connect_no_vehicles(self, mock_keychain, tesla_config):
        """Test connect fails when no vehicles found."""
        integration = TeslaIntegration(tesla_config)
        integration._session = MagicMock()
        integration._api_get = AsyncMock(return_value={"response": []})

        result = await integration.connect()

        assert result is False
        assert not integration.is_connected

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_disconnect(self, mock_keychain, tesla_config):
        """Test disconnect cleans up properly."""
        integration = TeslaIntegration(tesla_config)
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        integration._session = mock_session
        integration._initialized = True

        await integration.disconnect()

        assert not integration._initialized
        assert integration._session is None
        mock_session.close.assert_called_once()


# =============================================================================
# API REQUEST TESTS
# =============================================================================


class TestTeslaApiRequests:
    """Test Tesla API request methods."""

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_api_get_success(self, mock_keychain, tesla_config, mock_vehicle_response):
        """Test successful GET request."""
        integration = TeslaIntegration(tesla_config)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_vehicle_response)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock())
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        integration._session = mock_session

        result = await integration._api_get("/api/1/vehicles")

        assert result == mock_vehicle_response
        mock_session.get.assert_called_once()
        call_url = mock_session.get.call_args[0][0]
        assert API_BASE in call_url

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._refresh_access_token")
    async def test_api_get_401_triggers_refresh(self, mock_refresh, mock_keychain, tesla_config):
        """Test 401 response triggers token refresh."""
        mock_refresh.return_value = False  # Refresh fails

        integration = TeslaIntegration(tesla_config)

        mock_response = MagicMock()
        mock_response.status = 401

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=MagicMock())
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock()
        integration._session = mock_session

        result = await integration._api_get("/api/1/vehicles")

        assert result is None
        mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_api_get_no_session(self, mock_keychain, tesla_config):
        """Test GET returns None without session."""
        integration = TeslaIntegration(tesla_config)
        integration._session = None

        result = await integration._api_get("/api/1/vehicles")

        assert result is None

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_api_post_success(self, mock_keychain, tesla_config):
        """Test successful POST request (non-command)."""
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        mock_response = MagicMock()
        mock_response.status = 200

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock()
        integration._session = mock_session

        result = await integration._api_post("/api/1/vehicles/12345/wake_up")

        assert result is True


# =============================================================================
# TOKEN REFRESH TESTS
# =============================================================================


class TestTeslaTokenRefresh:
    """Test OAuth token refresh functionality."""

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._save_tokens_to_keychain")
    async def test_refresh_token_success(
        self, mock_save, mock_load, tesla_config, mock_token_response
    ):
        """Test successful token refresh."""
        integration = TeslaIntegration(tesla_config)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_token_response)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock()
        integration._session = mock_session

        result = await integration._refresh_access_token()

        assert result is True
        assert integration._access_token == "new_access_token_abc123"
        assert integration._refresh_token == "new_refresh_token_xyz789"
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_refresh_token_no_session(self, mock_keychain, tesla_config):
        """Test refresh fails without session."""
        integration = TeslaIntegration(tesla_config)
        integration._session = None

        result = await integration._refresh_access_token()

        assert result is False

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_refresh_token_no_refresh_token(self, mock_keychain, tesla_config):
        """Test refresh fails without refresh token."""
        integration = TeslaIntegration(tesla_config)
        integration._refresh_token = None
        integration._session = MagicMock()

        result = await integration._refresh_access_token()

        assert result is False

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_refresh_token_no_client_id(self, mock_keychain):
        """Test refresh fails without client_id."""
        config = SmartHomeConfig(
            tesla_access_token="test",
            tesla_refresh_token="test",
            tesla_client_id=None,
        )
        integration = TeslaIntegration(config)
        integration._session = MagicMock()

        result = await integration._refresh_access_token()

        assert result is False

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_refresh_token_api_failure(self, mock_keychain, tesla_config):
        """Test refresh handles API failure."""
        integration = TeslaIntegration(tesla_config)

        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=MagicMock())
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.post.return_value.__aexit__ = AsyncMock()
        integration._session = mock_session

        result = await integration._refresh_access_token()

        assert result is False


# =============================================================================
# GEOFENCING TESTS
# =============================================================================


class TestTeslaGeofencing:
    """Test geofencing and presence detection."""

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_is_home_when_at_home(self, mock_keychain, tesla_config):
        """Test is_home returns True when at home location."""
        integration = TeslaIntegration(tesla_config)
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,  # Home lat
            longitude=-122.3406,  # Home lon
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )

        assert integration.is_home() is True
        assert integration.is_away() is False

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_is_home_when_away(self, mock_keychain, tesla_config):
        """Test is_home returns False when away from home."""
        integration = TeslaIntegration(tesla_config)
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6100,  # Different location
            longitude=-122.3500,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )

        assert integration.is_home() is False
        assert integration.is_away() is True

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_is_home_no_state(self, mock_keychain, tesla_config):
        """Test is_home returns False when no state available."""
        integration = TeslaIntegration(tesla_config)
        integration._state = None

        assert integration.is_home() is False

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_is_home_no_location(self, mock_keychain, tesla_config):
        """Test is_home returns False when location not available."""
        integration = TeslaIntegration(tesla_config)
        integration._state = TeslaState(
            state=VehicleState.ASLEEP,
            latitude=None,
            longitude=None,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=None,
            outside_temp=None,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=None,
        )

        assert integration.is_home() is False

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_get_location(self, mock_keychain, tesla_config):
        """Test get_location returns coordinates."""
        integration = TeslaIntegration(tesla_config)
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,
            longitude=-122.3406,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )

        location = integration.get_location()
        assert location == (47.6815, -122.3406)

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_get_location_no_state(self, mock_keychain, tesla_config):
        """Test get_location returns None when no state."""
        integration = TeslaIntegration(tesla_config)
        integration._state = None

        assert integration.get_location() is None


# =============================================================================
# VEHICLE COMMAND TESTS
# =============================================================================


class TestTeslaVehicleCommands:
    """Test vehicle control commands."""

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_command_without_vehicle_id(self, mock_keychain, tesla_config):
        """Test commands fail without vehicle_id."""
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = None

        assert await integration.start_climate() is False
        assert await integration.stop_climate() is False
        assert await integration.lock() is False
        assert await integration.unlock() is False
        assert await integration.honk() is False
        assert await integration.flash_lights() is False

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_start_climate(self, mock_post, mock_keychain, tesla_config):
        """Test start_climate command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.start_climate()

        assert result is True
        mock_post.assert_called_once()
        call_path = mock_post.call_args[0][0]
        assert "auto_conditioning_start" in call_path

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_stop_climate(self, mock_post, mock_keychain, tesla_config):
        """Test stop_climate command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.stop_climate()

        assert result is True
        mock_post.assert_called_once()
        call_path = mock_post.call_args[0][0]
        assert "auto_conditioning_stop" in call_path

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_set_temperature(self, mock_post, mock_keychain, tesla_config):
        """Test set_temperature command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.set_temperature(21.0)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "set_temps" in call_args[0][0]
        assert call_args[0][1]["driver_temp"] == 21.0
        assert call_args[0][1]["passenger_temp"] == 21.0

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_set_seat_heater(self, mock_post, mock_keychain, tesla_config):
        """Test set_seat_heater command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.set_seat_heater(0, 3)  # Driver seat, max heat

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "remote_seat_heater_request" in call_args[0][0]
        assert call_args[0][1]["heater"] == 0
        assert call_args[0][1]["level"] == 3

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_start_charging(self, mock_post, mock_keychain, tesla_config):
        """Test start_charging command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.start_charging()

        assert result is True
        call_path = mock_post.call_args[0][0]
        assert "charge_start" in call_path

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_set_charge_limit(self, mock_post, mock_keychain, tesla_config):
        """Test set_charge_limit command with bounds."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        # Normal value
        await integration.set_charge_limit(80)
        assert mock_post.call_args[0][1]["percent"] == 80

        # Below minimum
        await integration.set_charge_limit(40)
        assert mock_post.call_args[0][1]["percent"] == 50

        # Above maximum
        await integration.set_charge_limit(110)
        assert mock_post.call_args[0][1]["percent"] == 100

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_lock_unlock(self, mock_post, mock_keychain, tesla_config):
        """Test lock and unlock commands."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        await integration.lock()
        assert "door_lock" in mock_post.call_args[0][0]

        await integration.unlock()
        assert "door_unlock" in mock_post.call_args[0][0]

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_open_trunk_frunk(self, mock_post, mock_keychain, tesla_config):
        """Test open_trunk and open_frunk commands."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        await integration.open_trunk()
        assert mock_post.call_args[0][1]["which_trunk"] == "rear"

        await integration.open_frunk()
        assert mock_post.call_args[0][1]["which_trunk"] == "front"

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_post")
    async def test_wake_up(self, mock_post, mock_keychain, tesla_config):
        """Test wake_up command."""
        mock_post.return_value = True
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        result = await integration.wake_up()

        assert result is True
        call_path = mock_post.call_args[0][0]
        assert "wake_up" in call_path


# =============================================================================
# STATE MANAGEMENT TESTS
# =============================================================================


class TestTeslaStateManagement:
    """Test vehicle state management."""

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_get_state(self, mock_keychain, tesla_config):
        """Test get_state returns current state."""
        integration = TeslaIntegration(tesla_config)
        state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,
            longitude=-122.3406,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )
        integration._state = state

        assert integration.get_state() == state

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_get_battery_level(self, mock_keychain, tesla_config):
        """Test get_battery_level returns correct value."""
        integration = TeslaIntegration(tesla_config)
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,
            longitude=-122.3406,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )

        assert integration.get_battery_level() == 75

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_get_battery_level_no_state(self, mock_keychain, tesla_config):
        """Test get_battery_level returns 0 when no state."""
        integration = TeslaIntegration(tesla_config)
        integration._state = None

        assert integration.get_battery_level() == 0

    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    def test_is_charging(self, mock_keychain, tesla_config):
        """Test is_charging returns correct value."""
        integration = TeslaIntegration(tesla_config)

        # Not charging
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,
            longitude=-122.3406,
            battery_level=75,
            charging_state=ChargingState.DISCONNECTED,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )
        assert integration.is_charging() is False

        # Charging
        integration._state = TeslaState(
            state=VehicleState.ONLINE,
            latitude=47.6815,
            longitude=-122.3406,
            battery_level=75,
            charging_state=ChargingState.CHARGING,
            charge_limit=80,
            inside_temp=22.0,
            outside_temp=15.0,
            climate_on=False,
            locked=True,
            odometer=12345.6,
            last_seen=datetime.now(),
        )
        assert integration.is_charging() is True

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._api_get")
    async def test_update_state(
        self, mock_get, mock_keychain, tesla_config, mock_vehicle_data_response
    ):
        """Test _update_state parses response correctly."""
        mock_get.return_value = mock_vehicle_data_response
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"

        await integration._update_state()

        state = integration._state
        assert state is not None
        assert state.state == VehicleState.ONLINE
        assert state.latitude == 47.6815
        assert state.longitude == -122.3406
        assert state.battery_level == 75
        assert state.charging_state == ChargingState.DISCONNECTED
        assert state.charge_limit == 80
        assert state.inside_temp == 22.0
        assert state.outside_temp == 15.0
        assert state.climate_on is False
        assert state.locked is True
        assert state.odometer == 12345.6


# =============================================================================
# VEHICLE STATE ENUM TESTS
# =============================================================================


class TestVehicleStateEnums:
    """Test vehicle state enums."""

    def test_vehicle_state_values(self):
        """Test VehicleState enum values."""
        assert VehicleState.ONLINE.value == "online"
        assert VehicleState.ASLEEP.value == "asleep"
        assert VehicleState.OFFLINE.value == "offline"
        assert VehicleState.UNKNOWN.value == "unknown"

    def test_charging_state_values(self):
        """Test ChargingState enum values."""
        assert ChargingState.DISCONNECTED.value == "Disconnected"
        assert ChargingState.CHARGING.value == "Charging"
        assert ChargingState.STOPPED.value == "Stopped"
        assert ChargingState.COMPLETE.value == "Complete"
        assert ChargingState.NO_POWER.value == "NoPower"
        assert ChargingState.UNKNOWN.value == "unknown"


# =============================================================================
# COMMAND PROXY TESTS
# =============================================================================


class TestTeslaCommandProxy:
    """Test Vehicle Command Protocol proxy routing."""

    @pytest.mark.asyncio
    @patch("kagami_smarthome.integrations.tesla.TeslaIntegration._load_tokens_from_keychain")
    async def test_command_via_proxy_connection_error(self, mock_keychain, tesla_config):
        """Test command proxy handles connection errors gracefully."""
        integration = TeslaIntegration(tesla_config)
        integration._vehicle_id = "12345"
        integration._vehicle_vin = "5YJ3E1EA1NF123456"
        integration._session = MagicMock()

        # The proxy connection will fail since it's not running
        result = await integration._command_via_proxy(
            "/api/1/vehicles/12345/command/flash_lights",
            None,
            {"Authorization": "Bearer test_token"},
        )

        # Should return False on proxy connection error
        assert result is False
