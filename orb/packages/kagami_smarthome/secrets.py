"""Secure Secrets Management via Kagami Security API.

Uses the centralized Kagami security API for credential storage.
No plaintext passwords in config files or environment variables.

Usage:
    from kagami_smarthome.secrets import secrets
    secrets.set("unifi_password", "your_password")

    # Retrieve:
    password = secrets.get("unifi_password")

Created: December 29, 2025
Updated: December 31, 2025 - Use unified security API
"""

from __future__ import annotations

import sys
from typing import Any

# Use the unified security API from Kagami core
from kagami.core.security import get_secret, set_secret
from kagami.core.security.backends.keychain_backend import HalKeychain


class SmartHomeSecrets:
    """Smart home secrets wrapper using Kagami security API."""

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a secret value."""
        return get_secret(key, default)

    def set(self, key: str, value: str) -> bool:
        """Set a secret value."""
        return set_secret(key, value)

    def has(self, key: str) -> bool:
        """Check if a secret exists."""
        return get_secret(key) is not None


# Global instance for easy access
secrets = SmartHomeSecrets()
KeychainSecrets = HalKeychain


# Known credential keys for smart home
CREDENTIAL_KEYS = [
    # UniFi (Network + Protect)
    "unifi_host",
    "unifi_username",
    "unifi_password",
    "unifi_local_username",  # Local account (no cloud)
    "unifi_local_password",
    # Control4
    "control4_host",
    "control4_username",
    "control4_password",
    "control4_bearer_token",
    "control4_controller_name",
    # Eight Sleep
    "eight_sleep_email",
    "eight_sleep_password",
    # August Smart Locks (direct yalexs API)
    "august_email",
    "august_password",
    "august_install_id",  # Generated UUID for this installation
    "august_access_token",
    "august_access_token_expires",
    "august_blacklisted_houses",  # Comma-separated house IDs to ignore
    # DSC Security (Envisalink direct)
    "dsc_host",  # Envisalink IP if not using Control4
    "dsc_port",  # Envisalink port (default 4025)
    "dsc_password",  # Envisalink password (default "user")
    "dsc_code",  # Arm/disarm code
    "dsc_zone_labels",  # JSON: {"1": "Front Door", "2": "Back Door", ...}
    "dsc_zone_types",  # JSON: {"1": "door_window", "3": "motion", "5": "smoke"}
    "dsc_enable_temperature",  # "true"/"false" for EMS-100 temperature monitoring
    # Apple iCloud / Find My
    "apple_id",  # Apple ID email
    "apple_password",  # Apple ID password (same as icloud_password)
    "icloud_password",  # Alias for apple_password
    # LG TV
    "lg_tv_host",
    "lg_tv_client_key",
    # Samsung TV
    "samsung_tv_host",
    "samsung_tv_token",
    # Tesla
    "tesla_access_token",
    "tesla_refresh_token",
    "tesla_client_id",
    "tesla_client_secret",
    # Denon
    "denon_host",
    # Oelo
    "oelo_host",
    # Mitsubishi (Kumo Cloud)
    "kumo_username",
    "kumo_password",
    # LG ThinQ
    "lg_thinq_access_token",
    # SmartThings
    "smartthings_token",
    # Electrolux
    "electrolux_email",
    "electrolux_password",
    # Sub-Zero/Wolf
    "subzero_wolf_email",
    "subzero_wolf_password",
    # Formlabs (Form 4 3D Printer)
    "formlabs_host",  # PreFormServer host (default: localhost)
    "formlabs_port",  # PreFormServer port (default: 44388)
    # Glowforge (Laser Cutter)
    "glowforge_ip",  # Glowforge static IP
    # Presence Detection
    "user_device_patterns",  # Comma-separated regex patterns for your devices
    "home_latitude",
    "home_longitude",
    # Weather
    "openweathermap_api_key",  # OpenWeatherMap API key (free tier: 1000/day)
    # Maps / Location
    "google_maps_api_key",  # Google Maps Distance Matrix API key
    # Spotify (Web API for playlist/control, librespot for streaming)
    "spotify_client_id",  # Spotify Web API client ID
    "spotify_client_secret",  # Spotify Web API client secret
    "spotify_refresh_token",  # OAuth refresh token for Web API
    # Note: librespot streaming credentials stored in ~/.kagami/spotify_credentials.json
]


def setup_interactive() -> None:
    """Interactive setup wizard for credentials."""
    import getpass

    print("=" * 60)
    print("KAGAMI SMART HOME - SECURE CREDENTIALS SETUP")
    print("=" * 60)
    print("\nCredentials will be stored in macOS Keychain.")
    print("Press Enter to skip any credential.\n")

    credentials = [
        # UniFi
        ("unifi_host", "UniFi Host (IP or unifi.ui.com)", False),
        ("unifi_username", "UniFi Username (email)", False),
        ("unifi_password", "UniFi Password", True),
        # Control4
        ("control4_host", "Control4 Director IP (e.g., 192.168.1.2)", False),
        ("control4_username", "Control4 Username (email)", False),
        ("control4_password", "Control4 Password", True),
        # Eight Sleep
        ("eight_sleep_email", "Eight Sleep Email", False),
        ("eight_sleep_password", "Eight Sleep Password", True),
        # August
        ("august_email", "August Email", False),
        ("august_password", "August Password", True),
        # DSC Security
        ("dsc_code", "DSC Arm/Disarm Code", True),
        # Note: Spotify uses OAuth (browser auth), credentials stored in ~/.kagami/spotify_credentials.json
    ]

    for key, prompt, is_password in credentials:
        current = secrets.get(key)
        status = "✓ stored" if current else "not set"

        if is_password:
            value = getpass.getpass(f"{prompt} [{status}]: ")
        else:
            value = input(f"{prompt} [{status}]: ")

        if value:
            if secrets.set(key, value):
                print(f"   ✅ Saved {key}")
            else:
                print(f"   ❌ Failed to save {key}")
        elif current:
            print(f"   ⏭️  Keeping existing {key}")

    print("\n" + "=" * 60)
    print("STORED CREDENTIALS:")
    print("=" * 60)
    for key in secrets.list_keys():
        print(f"  ✅ {key}")

    # Check core credentials
    core_keys = [
        "unifi_username",
        "unifi_password",
        "control4_username",
        "control4_password",
        "eight_sleep_email",
        "eight_sleep_password",
    ]
    missing = [k for k in core_keys if not secrets.has(k)]
    if missing:
        print(f"\n  ⚠️  Missing: {', '.join(missing)}")

    print("\nDone! Credentials are now stored in Keychain.")


def get_config_from_keychain() -> dict[str, Any]:
    """Get all stored credentials as a config dict."""
    return {key: secrets.get(key) for key in CREDENTIAL_KEYS}


def load_integration_credentials(
    integration: str,
    config: Any,
    keys: list[tuple[str, str]],
) -> None:
    """Load credentials from keychain into a config object.

    This is the canonical way for integrations to load credentials.
    Removes duplicate keychain loading code across integrations.

    Args:
        integration: Name of integration for logging
        config: Config object with attributes to set
        keys: List of (keychain_key, config_attr) tuples

    Example:
        load_integration_credentials("eight_sleep", config, [
            ("eight_sleep_email", "eight_sleep_email"),
            ("eight_sleep_password", "eight_sleep_password"),
        ])
    """
    import logging

    logger = logging.getLogger(__name__)

    for keychain_key, config_attr in keys:
        # Only load if not already set in config
        current = getattr(config, config_attr, None)
        if not current:
            value = secrets.get(keychain_key)
            if value:
                setattr(config, config_attr, value)
                logger.debug(f"{integration}: Loaded {config_attr} from Keychain")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_interactive()
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        print("Stored credentials:")
        if hasattr(secrets, "list"):
            stored_keys = secrets.list()
        else:
            stored_keys = [k for k in CREDENTIAL_KEYS if secrets.has(k)]
        for key in stored_keys:
            print(f"  ✅ {key}")
    elif len(sys.argv) > 2 and sys.argv[1] == "get":
        key = sys.argv[2]
        value = secrets.get(key)
        if value:
            print(value)
        else:
            print(f"Not found: {key}", file=sys.stderr)
            sys.exit(1)
    elif len(sys.argv) > 3 and sys.argv[1] == "set":
        key, value = sys.argv[2], sys.argv[3]
        if secrets.set(key, value):
            print(f"✅ Stored {key}")
        else:
            sys.exit(1)
    else:
        print("Usage:")
        print("  python -m kagami_smarthome.secrets setup  # Interactive setup")
        print("  python -m kagami_smarthome.secrets list   # List stored keys")
        print("  python -m kagami_smarthome.secrets get <key>")
        print("  python -m kagami_smarthome.secrets set <key> <value>")
