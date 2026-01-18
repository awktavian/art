"""Integration tests for the Apps 100/100 Transformation.

Tests the core infrastructure created in Phase 1:
- Multi-user authentication system
- Internationalization framework
- Offline cache layer
- Accessibility foundation

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 9
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


# =============================================================================
# TEST: MULTI-USER AUTHENTICATION
# =============================================================================


class TestMultiUserAuth:
    """Tests for the multi-user authentication system."""

    def test_household_model_structure(self):
        """Verify household SQLAlchemy model is correctly structured."""
        from kagami.core.database.models import Household, HouseholdMember, HouseholdInvitation

        # Check Household has required columns
        assert hasattr(Household, "id")
        assert hasattr(Household, "name")
        assert hasattr(Household, "owner_id")
        assert hasattr(Household, "timezone")
        assert hasattr(Household, "guest_access_enabled")

        # Check HouseholdMember has required columns
        assert hasattr(HouseholdMember, "household_id")
        assert hasattr(HouseholdMember, "user_id")
        assert hasattr(HouseholdMember, "role")
        assert hasattr(HouseholdMember, "expires_at")

        # Check HouseholdInvitation has required columns
        assert hasattr(HouseholdInvitation, "email")
        assert hasattr(HouseholdInvitation, "code")
        assert hasattr(HouseholdInvitation, "status")

    def test_oauth_connection_model(self):
        """Verify OAuth connection model is correctly structured."""
        from kagami.core.database.models import OAuthConnection

        assert hasattr(OAuthConnection, "user_id")
        assert hasattr(OAuthConnection, "provider")
        assert hasattr(OAuthConnection, "provider_user_id")
        assert hasattr(OAuthConnection, "access_token")
        assert hasattr(OAuthConnection, "refresh_token")

    def test_household_roles(self):
        """Verify all required household roles are supported."""
        expected_roles = ["owner", "admin", "member", "child", "elder", "caregiver", "guest"]

        # Roles are defined in the migration SQL CHECK constraint
        migration_path = (
            Path(__file__).parent.parent.parent
            / "migrations"
            / "versions"
            / "20260101_households_multiuser.sql"
        )
        if migration_path.exists():
            content = migration_path.read_text()
            for role in expected_roles:
                assert f"'{role}'" in content, f"Role '{role}' not found in migration"


# =============================================================================
# TEST: INTERNATIONALIZATION
# =============================================================================


class TestInternationalization:
    """Tests for the i18n framework."""

    def test_supported_locales(self):
        """Verify all 10 required languages are supported."""
        from kagami.core.i18n import SUPPORTED_LOCALES

        required = ["en", "es", "ar", "zh", "vi", "ja", "ko", "fr", "de", "pt"]
        for locale in required:
            assert locale in SUPPORTED_LOCALES, f"Locale '{locale}' not supported"

    def test_rtl_detection(self):
        """Verify Arabic is detected as RTL."""
        from kagami.core.i18n import is_rtl, RTL_LOCALES

        assert "ar" in RTL_LOCALES
        assert is_rtl("ar") is True
        assert is_rtl("en") is False
        assert is_rtl("zh") is False

    def test_translation_function(self):
        """Test basic translation function."""
        from kagami.core.i18n import t, set_locale

        set_locale("en")

        # Test basic translation
        assert t("common.ok") == "OK"
        assert t("common.cancel") == "Cancel"

        # Test fallback for missing key
        assert t("nonexistent.key") == "nonexistent.key"

    def test_pluralization_english(self):
        """Test English pluralization rules."""
        from kagami.core.i18n import _get_plural_category

        assert _get_plural_category(0, "en") == "other"
        assert _get_plural_category(1, "en") == "one"
        assert _get_plural_category(2, "en") == "other"
        assert _get_plural_category(10, "en") == "other"

    def test_pluralization_arabic(self):
        """Test Arabic pluralization rules (complex)."""
        from kagami.core.i18n import _get_plural_category

        assert _get_plural_category(0, "ar") == "zero"
        assert _get_plural_category(1, "ar") == "one"
        assert _get_plural_category(2, "ar") == "two"
        assert _get_plural_category(5, "ar") == "few"
        assert _get_plural_category(15, "ar") == "many"
        assert _get_plural_category(100, "ar") == "other"

    def test_pluralization_cjk(self):
        """Test CJK languages (no grammatical plural)."""
        from kagami.core.i18n import _get_plural_category

        for locale in ["zh", "ja", "ko", "vi"]:
            assert _get_plural_category(0, locale) == "other"
            assert _get_plural_category(1, locale) == "other"
            assert _get_plural_category(100, locale) == "other"

    def test_locale_files_exist(self):
        """Verify all locale JSON files exist."""
        locales_dir = (
            Path(__file__).parent.parent.parent
            / "packages"
            / "kagami"
            / "core"
            / "i18n"
            / "locales"
        )
        required = ["en", "es", "ar", "zh", "vi", "ja", "ko", "fr", "de", "pt"]

        for locale in required:
            locale_file = locales_dir / f"{locale}.json"
            assert locale_file.exists(), f"Missing locale file: {locale}.json"

    def test_locale_file_valid_json(self):
        """Verify all locale files are valid JSON."""
        locales_dir = (
            Path(__file__).parent.parent.parent
            / "packages"
            / "kagami"
            / "core"
            / "i18n"
            / "locales"
        )

        for locale_file in locales_dir.glob("*.json"):
            try:
                with open(locale_file, encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"Invalid JSON in {locale_file}: {e}")


# =============================================================================
# TEST: OFFLINE CACHE
# =============================================================================


class TestOfflineCache:
    """Tests for the offline cache layer."""

    @pytest.fixture
    def cache(self):
        """Create a temporary offline cache for testing."""
        from kagami.core.caching.offline import OfflineCache

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test-cache.db"
            cache = OfflineCache(user_id="test-user", db_path=db_path)
            yield cache

    @pytest.mark.asyncio
    async def test_cache_initialization(self, cache):
        """Test cache initializes correctly."""
        await cache.initialize()
        assert cache._initialized is True

    @pytest.mark.asyncio
    async def test_device_state_storage(self, cache):
        """Test storing and retrieving device state."""
        await cache.initialize()

        # Store state
        await cache.store_device_state("light-1", {"on": True, "brightness": 50})

        # Retrieve state
        state = await cache.get_device_state("light-1")
        assert state is not None
        assert state["on"] is True
        assert state["brightness"] == 50

    @pytest.mark.asyncio
    async def test_command_queue(self, cache):
        """Test command queue operations."""
        await cache.initialize()

        # Queue a command
        cmd_id = await cache.queue_command({"action": "set_lights", "params": {"brightness": 75}})

        assert cmd_id is not None

        # Get pending commands
        commands = await cache.get_pending_commands()
        assert len(commands) == 1
        assert commands[0].action == "set_lights"

    @pytest.mark.asyncio
    async def test_home_state_snapshot(self, cache):
        """Test home state snapshot storage."""
        await cache.initialize()

        # Store snapshot
        home_state = {"rooms": [{"id": "1", "name": "Living Room"}, {"id": "2", "name": "Kitchen"}]}
        await cache.store_home_state(home_state)

        # Retrieve snapshot
        retrieved = await cache.get_home_state()
        assert retrieved is not None
        assert len(retrieved["rooms"]) == 2

    @pytest.mark.asyncio
    async def test_preference_storage(self, cache):
        """Test user preference storage."""
        await cache.initialize()

        # Store preference
        await cache.store_preference("theme", "dark")

        # Retrieve preference
        theme = await cache.get_preference("theme")
        assert theme == "dark"

        # Default value for missing
        missing = await cache.get_preference("nonexistent", "default")
        assert missing == "default"


# =============================================================================
# TEST: ACCESSIBILITY
# =============================================================================


class TestAccessibility:
    """Tests for accessibility features."""

    def test_accessibility_manager_exists(self):
        """Verify accessibility manager exists."""
        from kagami.core.accessibility import AccessibilityManager

        manager = AccessibilityManager(user_id="test-user")
        assert manager is not None

    def test_simplified_mode_config(self):
        """Test simplified mode configuration."""
        from kagami.core.accessibility import SimplifiedModeConfig

        config = SimplifiedModeConfig()

        # Default values
        assert config.enabled is False
        assert config.larger_buttons is True
        assert config.text_scale_factor == 1.3
        assert config.reduce_motion is True
        assert config.emergency_button_visible is True

    def test_alert_severity_levels(self):
        """Verify alert severity levels exist."""
        from kagami.core.accessibility import AlertSeverity

        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_contrast_calculation(self):
        """Test WCAG contrast ratio calculation."""
        from kagami.core.accessibility.contrast import calculate_contrast_ratio, check_contrast

        # Black on white should have maximum contrast
        ratio = calculate_contrast_ratio("#ffffff", "#000000")
        assert ratio == pytest.approx(21.0, rel=0.01)

        # Check WCAG compliance
        assert check_contrast("#ffffff", "#000000", level="AAA") is True
        assert check_contrast("#ffffff", "#767676", level="AA") is True

    def test_motion_config(self):
        """Test reduced motion configuration."""
        from kagami.core.accessibility.motion import (
            MotionConfig,
            should_reduce_motion,
            set_reduce_motion,
        )

        config = MotionConfig()

        # Default values
        assert config.reduce_motion is False
        assert config.duration_normal == 250

        # Reduced motion values
        config.reduce_motion = True
        assert config.get_duration("normal") == 50

    def test_visual_alert_config(self):
        """Test visual alert configuration."""
        from kagami.core.accessibility.visual_alerts import (
            VisualAlertConfig,
            AlertPattern,
            AlertLocation,
        )

        config = VisualAlertConfig(
            message="Test alert",
            severity="warning",
            pattern=AlertPattern.FLASH,
            location=AlertLocation.BORDER,
        )

        assert config.color_value == "#f39c12"  # Warning color
        assert config.duration_ms == 2000


# =============================================================================
# TEST: LEGACY CODE REMOVAL
# =============================================================================


class TestLegacyCodeRemoval:
    """Tests to verify legacy code has been removed."""

    def test_no_demo_data_provider_ios(self):
        """Verify DemoDataProvider removed from iOS."""
        ios_app_file = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "ios"
            / "kagami-ios"
            / "KagamiIOS"
            / "KagamiIOSApp.swift"
        )
        if ios_app_file.exists():
            content = ios_app_file.read_text()
            assert "DemoDataProvider" not in content

    def test_no_colony_indicator_ios(self):
        """Verify ColonyIndicator removed from iOS."""
        colony_file = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "ios"
            / "kagami-ios"
            / "KagamiIOS"
            / "Views"
            / "ColonyIndicator.swift"
        )
        assert not colony_file.exists()

    def test_no_colony_badge_watch(self):
        """Verify ColonyBadge removed from Watch."""
        colony_file = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "watch"
            / "kagami-watch"
            / "KagamiWatch"
            / "Views"
            / "ColonyBadge.swift"
        )
        assert not colony_file.exists()

    def test_no_craft_css(self):
        """Verify craft pyramid CSS files removed."""
        css_dir = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "desktop"
            / "kagami-client"
            / "src"
            / "css"
        )
        if css_dir.exists():
            craft_files = list(css_dir.glob("craft-*.css"))
            prism_files = list(css_dir.glob("prism-*.css"))
            assert len(craft_files) == 0
            assert len(prism_files) == 0

    def test_no_hx_display_ios(self):
        """Verify h(x) display removed from iOS ContentView."""
        content_view = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "ios"
            / "kagami-ios"
            / "KagamiIOS"
            / "ContentView.swift"
        )
        if content_view.exists():
            content = content_view.read_text()
            # Should not have h(x) in UI (may have in comments)
            assert 'Text("h(x)"' not in content


# =============================================================================
# TEST: HUB WEB INTERFACE
# =============================================================================


class TestHubWebInterface:
    """Tests for the Hub web interface for deaf users."""

    def test_hub_web_interface_exists(self):
        """Verify Hub web interface was created."""
        hub_web = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "hub"
            / "kagami-hub"
            / "web"
            / "index.html"
        )
        assert hub_web.exists()

    def test_hub_web_interface_accessible(self):
        """Verify Hub web interface has accessibility features."""
        hub_web = (
            Path(__file__).parent.parent.parent
            / "apps"
            / "hub"
            / "kagami-hub"
            / "web"
            / "index.html"
        )
        if hub_web.exists():
            content = hub_web.read_text()

            # Check for ARIA attributes
            assert "aria-live" in content
            assert "aria-label" in content
            assert 'role="alert"' in content

            # Check for skip link
            assert "skip-link" in content

            # Check for reduced motion support
            assert "prefers-reduced-motion" in content

            # Check for high contrast support
            assert "prefers-contrast" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
