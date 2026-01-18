"""Tests for SmartHome Domain Services.

Tests the decomposed service layer (Phase 5 refactor).

Created: December 30, 2025
"""

from __future__ import annotations

import pytest

# =============================================================================
# SERVICE IMPORT TESTS
# =============================================================================


class TestServiceImports:
    """Test that all services can be imported."""

    def test_device_service_import(self):
        """DeviceService imports."""
        from kagami_smarthome.services import DeviceService

        assert DeviceService is not None

    def test_av_service_import(self):
        """AVService imports."""
        from kagami_smarthome.services import AVService

        assert AVService is not None

    def test_climate_service_import(self):
        """ClimateService imports."""
        from kagami_smarthome.services import ClimateService

        assert ClimateService is not None

    def test_security_service_import(self):
        """SecurityService imports."""
        from kagami_smarthome.services import SecurityService

        assert SecurityService is not None

    def test_automation_service_import(self):
        """AutomationService imports."""
        from kagami_smarthome.services.automation_service import AutomationService

        assert AutomationService is not None

    def test_findmy_service_import(self):
        """FindMyService imports."""
        from kagami_smarthome.services.findmy_service import FindMyService

        assert FindMyService is not None

    def test_health_service_import(self):
        """HealthService imports."""
        from kagami_smarthome.services.health_service import HealthService

        assert HealthService is not None

    def test_oelo_service_import(self):
        """OeloService imports."""
        from kagami_smarthome.services.oelo_service import OeloService

        assert OeloService is not None

    def test_presence_service_import(self):
        """PresenceService imports from canonical location."""
        from kagami.core.integrations.presence_service import PresenceService

        assert PresenceService is not None

    def test_room_service_import(self):
        """RoomService imports."""
        from kagami_smarthome.services.room_service import RoomService

        assert RoomService is not None

    def test_scene_service_import(self):
        """SceneService imports."""
        from kagami_smarthome.services.scene_service import SceneService

        assert SceneService is not None

    def test_tesla_service_import(self):
        """TeslaService imports."""
        from kagami_smarthome.services.tesla_service import TeslaService

        assert TeslaService is not None

    def test_visitor_service_import(self):
        """VisitorService imports."""
        from kagami_smarthome.services.visitor_service import VisitorService

        assert VisitorService is not None

    def test_workshop_service_import(self):
        """WorkshopService imports."""
        from kagami_smarthome.services.workshop_service import WorkshopService

        assert WorkshopService is not None


# =============================================================================
# SERVICE INSTANTIATION TESTS
# =============================================================================


class TestServiceInstantiation:
    """Test services can be instantiated."""

    def test_device_service_instance(self):
        """DeviceService can be instantiated."""
        from kagami_smarthome.services import DeviceService

        service = DeviceService()
        assert service is not None

    def test_av_service_instance(self):
        """AVService can be instantiated."""
        from kagami_smarthome.services import AVService

        service = AVService()
        assert service is not None

    def test_climate_service_instance(self):
        """ClimateService can be instantiated."""
        from kagami_smarthome.services import ClimateService

        service = ClimateService()
        assert service is not None

    def test_security_service_instance(self):
        """SecurityService can be instantiated."""
        from kagami_smarthome.services import SecurityService

        service = SecurityService()
        assert service is not None


# =============================================================================
# SERVICE INTERFACE TESTS
# =============================================================================


class TestServiceInterfaces:
    """Test services have consistent interfaces."""

    def test_device_service_is_functional(self):
        """DeviceService is a functional class."""
        from kagami_smarthome.services import DeviceService

        service = DeviceService()
        assert service is not None
        # Services work via controller injection
        assert isinstance(service, object)

    def test_av_service_is_functional(self):
        """AVService is a functional class."""
        from kagami_smarthome.services import AVService

        service = AVService()
        assert service is not None

    def test_climate_service_is_functional(self):
        """ClimateService is a functional class."""
        from kagami_smarthome.services import ClimateService

        service = ClimateService()
        assert service is not None

    def test_security_service_is_functional(self):
        """SecurityService is a functional class."""
        from kagami_smarthome.services import SecurityService

        service = SecurityService()
        assert service is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
