"""Tests for Kagami Login SDK (JavaScript).

Validates SDK structure and exported functionality.
These tests verify the SDK file exists and has proper structure.

Colony: Crystal (e7) — Verification
Created: January 7, 2026
鏡
"""

import re
from pathlib import Path

import pytest


# Get workspace root (kagami directory)
WORKSPACE_ROOT = Path(__file__).parent
for _ in range(6):  # Navigate up from tests/kagami_api/routes/user/
    if (WORKSPACE_ROOT / "apps").exists():
        break
    WORKSPACE_ROOT = WORKSPACE_ROOT.parent

SDK_PATH = WORKSPACE_ROOT / "apps/agents/_sdk/kagami-login.js"


class TestSDKStructure:
    """Tests for SDK file structure."""

    def test_sdk_file_exists(self):
        """SDK file exists at expected location."""
        assert SDK_PATH.exists(), f"SDK not found at {SDK_PATH}"

    def test_sdk_is_readable(self):
        """SDK file is readable."""
        content = SDK_PATH.read_text()
        assert len(content) > 1000, "SDK seems too small"

    def test_sdk_has_version(self):
        """SDK has version number."""
        content = SDK_PATH.read_text()
        assert "version:" in content or "@version" in content

    def test_sdk_exports_kagami_auth(self):
        """SDK exports KagamiAuth global."""
        content = SDK_PATH.read_text()
        assert "KagamiAuth" in content
        assert "global.KagamiAuth" in content or "window.KagamiAuth" in content


class TestSDKFeatures:
    """Tests for SDK feature presence."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_init_function(self, sdk_content):
        """SDK has init function."""
        assert "function init(" in sdk_content or "init," in sdk_content

    def test_has_login_function(self, sdk_content):
        """SDK has login function."""
        assert "function login(" in sdk_content or "async function login(" in sdk_content

    def test_has_logout_function(self, sdk_content):
        """SDK has logout function."""
        assert "function logout(" in sdk_content or "async function logout(" in sdk_content

    def test_has_callback_handler(self, sdk_content):
        """SDK has callback handler."""
        assert "handleCallback" in sdk_content

    def test_has_token_refresh(self, sdk_content):
        """SDK has token refresh."""
        assert "refreshToken" in sdk_content

    def test_has_pkce_support(self, sdk_content):
        """SDK has PKCE support."""
        assert "generateCodeVerifier" in sdk_content or "code_verifier" in sdk_content
        assert "code_challenge" in sdk_content

    def test_has_button_creation(self, sdk_content):
        """SDK has button creation."""
        assert "createButton" in sdk_content

    def test_has_authenticated_fetch(self, sdk_content):
        """SDK has authenticated fetch wrapper."""
        assert "authenticatedFetch" in sdk_content

    def test_has_user_info(self, sdk_content):
        """SDK has user info retrieval."""
        assert "getUserInfo" in sdk_content or "getUser" in sdk_content


class TestSDKAudioFeatures:
    """Tests for SDK audio features."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_audio_context(self, sdk_content):
        """SDK has Web Audio support."""
        assert "AudioContext" in sdk_content

    def test_has_success_sound(self, sdk_content):
        """SDK has success sound."""
        assert "playSuccessSound" in sdk_content or "playSuccess" in sdk_content

    def test_has_error_sound(self, sdk_content):
        """SDK has error sound."""
        assert "playErrorSound" in sdk_content or "playError" in sdk_content

    def test_has_click_sound(self, sdk_content):
        """SDK has click sound."""
        assert "playClickSound" in sdk_content or "playClick" in sdk_content

    def test_has_audio_config(self, sdk_content):
        """SDK has audio configuration."""
        assert "enableAudio" in sdk_content
        assert "audioVolume" in sdk_content


class TestSDKHapticFeatures:
    """Tests for SDK haptic features."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_haptic_feedback(self, sdk_content):
        """SDK has haptic feedback."""
        assert "hapticFeedback" in sdk_content or "haptics" in sdk_content

    def test_has_vibrate_api(self, sdk_content):
        """SDK uses vibrate API."""
        assert "navigator.vibrate" in sdk_content

    def test_has_haptic_config(self, sdk_content):
        """SDK has haptic configuration."""
        assert "enableHaptics" in sdk_content


class TestSDKMicrointeractions:
    """Tests for SDK microinteraction features."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_ripple_effect(self, sdk_content):
        """SDK has ripple effect."""
        assert "ripple" in sdk_content.lower()

    def test_has_hover_effects(self, sdk_content):
        """SDK has hover effects."""
        assert "mouseenter" in sdk_content
        assert "mouseleave" in sdk_content

    def test_has_transitions(self, sdk_content):
        """SDK has CSS transitions."""
        assert "transition" in sdk_content

    def test_has_animation(self, sdk_content):
        """SDK has animations."""
        assert "animation" in sdk_content


class TestSDKAccessibility:
    """Tests for SDK accessibility features."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_aria_labels(self, sdk_content):
        """SDK sets aria-label."""
        assert "aria-label" in sdk_content

    def test_has_keyboard_support(self, sdk_content):
        """SDK has keyboard support."""
        assert "keydown" in sdk_content
        # Enter/Space key handling
        assert "Enter" in sdk_content or "keyCode" in sdk_content

    def test_has_focus_handling(self, sdk_content):
        """SDK handles focus states."""
        assert "focus" in sdk_content


class TestSDKSecurity:
    """Tests for SDK security features."""

    @pytest.fixture
    def sdk_content(self):
        """Load SDK content."""
        return SDK_PATH.read_text()

    def test_has_state_validation(self, sdk_content):
        """SDK validates state parameter."""
        assert "state" in sdk_content
        # State comparison for CSRF protection
        assert "storedState" in sdk_content or "oauth_state" in sdk_content

    def test_has_nonce_validation(self, sdk_content):
        """SDK validates nonce."""
        assert "nonce" in sdk_content

    def test_uses_crypto_random(self, sdk_content):
        """SDK uses crypto for randomness."""
        assert "crypto.getRandomValues" in sdk_content or "crypto.subtle" in sdk_content

    def test_has_secure_storage(self, sdk_content):
        """SDK supports secure storage options."""
        assert "localStorage" in sdk_content
        assert "sessionStorage" in sdk_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
