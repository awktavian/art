"""Tests for secret rotation."""

import pytest
from datetime import datetime, timedelta

from kagami.core.security.rotation import (
    RotationPolicy,
    RotationStatus,
    SecretRotator,
    create_default_policies,
)
from kagami.core.security.secrets_manager import SecretsManager
from kagami.core.security.backends.local_backend import LocalEncryptedBackend


@pytest.fixture
def local_backend(tmp_path):
    """Create local encrypted backend for testing."""
    config = {
        "storage_path": str(tmp_path / "secrets.enc"),
        "master_key_path": str(tmp_path / "master.key"),
        "auto_generate_key": True,
    }
    return LocalEncryptedBackend(config)


@pytest.fixture
def secrets_manager(local_backend):
    """Create secrets manager for testing."""
    return SecretsManager(
        backend=local_backend,
        enable_cache=True,
        enable_rate_limiting=False,  # Disable for testing
    )


@pytest.fixture
def rotator(secrets_manager):
    """Create rotator for testing."""
    policies = [
        RotationPolicy(
            secret_name="test_secret",
            rotation_days=30,
            auto_generate=True,
            generation_length=32,
        )
    ]
    return SecretRotator(secrets_manager=secrets_manager, policies=policies)


class TestSecretRotator:
    """Test secret rotator."""

    @pytest.mark.asyncio
    async def test_rotate_secret(self, rotator, secrets_manager):
        """Test rotating a secret."""
        # Create initial secret
        await secrets_manager.set_secret(
            name="test_secret",
            value="original_value_123456",
            user="test",
        )

        # Rotate secret
        event = await rotator.rotate_secret(
            secret_name="test_secret",
            new_value="rotated_value_789012",
            user="test",
        )

        assert event.status == RotationStatus.SUCCESS
        assert event.secret_name == "test_secret"
        assert event.new_version is not None

        # Verify new value
        new_value = await secrets_manager.get_secret("test_secret", user="test")
        assert new_value == "rotated_value_789012"

    @pytest.mark.asyncio
    async def test_auto_generate_rotation(self, rotator, secrets_manager):
        """Test rotation with auto-generated value."""
        # Create initial secret
        await secrets_manager.set_secret(
            name="test_secret",
            value="original_value_123456",
            user="test",
        )

        # Rotate without providing new value
        event = await rotator.rotate_secret(
            secret_name="test_secret",
            user="test",
        )

        assert event.status == RotationStatus.SUCCESS

        # Verify new value was generated
        new_value = await secrets_manager.get_secret("test_secret", user="test")
        assert new_value != "original_value_123456"
        assert len(new_value) >= 32

    @pytest.mark.asyncio
    async def test_rotation_history(self, rotator, secrets_manager):
        """Test rotation history tracking."""
        # Create and rotate secret
        await secrets_manager.set_secret(
            name="test_secret",
            value="value_1_123456789",
            user="test",
        )

        await rotator.rotate_secret("test_secret", user="test")

        # Check history
        history = rotator.get_rotation_history(secret_name="test_secret")

        assert len(history) >= 1
        assert history[0].secret_name == "test_secret"
        assert history[0].status == RotationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_rotation_policy(self, rotator):
        """Test rotation policy management."""
        # Add policy
        policy = RotationPolicy(
            secret_name="new_secret",
            rotation_days=60,
            auto_generate=True,
        )
        rotator.add_policy(policy)

        assert "new_secret" in rotator.policies

        # Remove policy
        rotator.remove_policy("new_secret")

        assert "new_secret" not in rotator.policies

    @pytest.mark.asyncio
    async def test_rotation_notification(self, rotator, secrets_manager):
        """Test rotation notifications."""
        notifications = []

        def notification_callback(event):
            notifications.append(event)

        rotator.add_notification_callback(notification_callback)

        # Create and rotate secret
        await secrets_manager.set_secret(
            name="test_secret",
            value="value_123456789",
            user="test",
        )

        await rotator.rotate_secret("test_secret", user="test")

        # Should have received notification
        assert len(notifications) == 1
        assert notifications[0].secret_name == "test_secret"

    @pytest.mark.asyncio
    async def test_rotation_summary(self, rotator, secrets_manager):
        """Test rotation summary."""
        # Create and rotate multiple secrets
        for i in range(3):
            name = f"secret_{i}"
            await secrets_manager.set_secret(
                name=name,
                value=f"value_{i}_1234567890",
                user="test",
            )

            rotator.add_policy(
                RotationPolicy(
                    secret_name=name,
                    rotation_days=30,
                    auto_generate=True,
                )
            )

            await rotator.rotate_secret(name, user="test")

        # Get summary
        summary = rotator.get_rotation_summary()

        assert summary["total_rotations"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0
        assert summary["success_rate"] == 1.0


class TestRotationPolicy:
    """Test rotation policies."""

    def test_default_policies(self):
        """Test creating default policies."""
        policies = create_default_policies()

        assert len(policies) > 0

        # Check for common secrets
        policy_names = [p.secret_name for p in policies]
        assert "JWT_SECRET" in policy_names
        assert "KAGAMI_API_KEY" in policy_names

    def test_policy_attributes(self):
        """Test policy attributes."""
        policy = RotationPolicy(
            secret_name="test_secret",
            rotation_days=90,
            grace_period_seconds=600,
            auto_generate=True,
            generation_length=64,
        )

        assert policy.secret_name == "test_secret"
        assert policy.rotation_days == 90
        assert policy.grace_period_seconds == 600
        assert policy.auto_generate is True
        assert policy.generation_length == 64
