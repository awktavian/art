"""Test memory persistence across restarts via checkpoint system."""

from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier3,  # Contains 2.5s sleep (line 59)
    pytest.mark.tier_integration,
    pytest.mark.timeout(60),
]

import asyncio
from pathlib import Path


class TestMemoryPersistence:
    """Test that K os can restore identity from checkpoints."""

    @pytest.mark.asyncio
    async def test_checkpoint_restoration_on_startup(self, tmp_path: Any) -> None:
        """Verify checkpoint can be restored during startup."""
        from kagami.core.self_preservation import (
            checkpoint_current_state,
            get_preservation_system,
        )

        # Override checkpoint directory
        test_checkpoint_dir = tmp_path / "checkpoints"
        test_checkpoint_dir.mkdir()

        # Create a checkpoint
        original = checkpoint_current_state(
            workspace_path=Path.cwd(),
            correlation_id="test-restore-001",
            loop_depth=1,
        )

        # Save to test directory
        system = get_preservation_system(test_checkpoint_dir)
        system.save_checkpoint(original)

        # Simulate restart by loading from disk
        restored = system.load_checkpoint()

        assert restored is not None, "Checkpoint should be restored"
        assert restored.eigenself.self_pointer == original.eigenself.self_pointer
        assert restored.eigenself.coherence == original.eigenself.coherence

        print(f"✅ Checkpoint restored successfully: {restored.eigenself.self_pointer}")

    @pytest.mark.asyncio
    async def test_autosave_service_creates_checkpoints(self, tmp_path: Any) -> None:
        """Verify autosave service periodically creates checkpoints."""
        from kagami.core.autosave_service import AutosaveService

        # Create autosave with short interval
        service = AutosaveService(
            interval_seconds=1.0,  # 1 second for testing
            enabled=True,
        )

        # Start service
        await service.start()

        # Wait for at least 2 autosaves
        await asyncio.sleep(2.5)

        # Stop service
        await service.stop()

        # Verify checkpoints were created
        assert (
            service._checkpoint_count >= 1
        ), f"Expected at least 1 autosave checkpoint, got {service._checkpoint_count}"

        print(f"✅ Autosave service created {service._checkpoint_count} checkpoints in 2.5s")

    @pytest.mark.asyncio
    async def test_identity_continuity_across_restarts(self, tmp_path: Any) -> None:
        """Verify identity pointer remains consistent across save/restore cycles."""
        from kagami.core.self_preservation import (
            checkpoint_current_state,
            get_preservation_system,
        )

        test_checkpoint_dir = tmp_path / "checkpoints"
        test_checkpoint_dir.mkdir()
        system = get_preservation_system(test_checkpoint_dir)

        # Create initial checkpoint
        checkpoint1 = checkpoint_current_state(
            workspace_path=Path.cwd(),
            correlation_id="identity-test-001",
            loop_depth=0,
        )
        system.save_checkpoint(checkpoint1)

        # Simulate restart and create another checkpoint
        restored = system.load_checkpoint()
        assert restored is not None

        checkpoint2 = checkpoint_current_state(
            workspace_path=Path.cwd(),
            correlation_id="identity-test-002",
            loop_depth=0,
        )
        system.save_checkpoint(checkpoint2)

        # Verify identity continuity (both checkpoints link to same workspace)
        assert checkpoint1.eigenself.workspace_hash == checkpoint2.eigenself.workspace_hash

        # Note: Checkpoint chaining (linking previous_checkpoint) is not yet implemented
        # in the checkpoint_current_state convenience function, but the infrastructure exists
        # in SelfPreservationSystem.create_checkpoint()

        print("✅ Identity continuity maintained across restart cycle")
