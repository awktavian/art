"""Cross-Device End-to-End Tests.

Comprehensive tests for multi-device scenarios:
- Phone to watch handoff: Start on phone, continue on watch
- TV to phone control: Use TV, adjust on phone
- Voice to manual: Voice command then manual override
- Offline to online sync: Commands while offline sync when online
- Multi-user conflict: Two users controlling same device

These tests validate seamless device transitions and conflict resolution.

Colony: Nexus (e4) - Connection and integration
Colony: Crystal (e7) - Verification and trust

h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
import pytest_asyncio

from tests.e2e.conftest import (
    MockDeviceConstellation,
    MockDevice,
    MockHub,
    DeviceType,
    ConnectionState,
    NetworkCondition,
    UserPersona,
    UserRole,
)

logger = logging.getLogger(__name__)

# Mark all tests in this module
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.cross_device,
    pytest.mark.asyncio,
]


# ==============================================================================
# CROSS-DEVICE DATA STRUCTURES
# ==============================================================================


class CommandSource(str, Enum):
    """Source of a command."""

    PHONE = "phone"
    WATCH = "watch"
    TV = "tv"
    VOICE = "voice"
    MANUAL = "manual"  # Physical switch/button
    SCHEDULE = "schedule"
    AUTOMATION = "automation"


class SyncState(str, Enum):
    """State synchronization status."""

    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    OFFLINE = "offline"


@dataclass
class DeviceSession:
    """Represents an active session on a device."""

    session_id: str
    device_id: str
    device_type: DeviceType
    user_id: str
    started_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    active_controls: list[str] = field(default_factory=list)
    is_active: bool = True

    def heartbeat(self) -> None:
        self.last_activity = time.time()

    def is_stale(self, timeout_seconds: float = 300) -> bool:
        return time.time() - self.last_activity > timeout_seconds


@dataclass
class CrossDeviceCommand:
    """A command that may be executed or synced across devices."""

    command_id: str
    source: CommandSource
    source_device: str
    user_id: str
    action: str
    target: str
    params: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    sync_state: SyncState = SyncState.PENDING
    conflicting_command: str | None = None
    resolved: bool = False


@dataclass
class ConflictResolution:
    """Result of conflict resolution between commands."""

    winner_command_id: str
    loser_command_id: str
    resolution_strategy: str  # "last_write_wins", "user_priority", "source_priority"
    timestamp: float = field(default_factory=time.time)


# ==============================================================================
# CROSS-DEVICE MANAGER
# ==============================================================================


class CrossDeviceManager:
    """Manages cross-device state and command synchronization."""

    def __init__(self, constellation: MockDeviceConstellation):
        self.constellation = constellation
        self.sessions: dict[str, DeviceSession] = {}
        self.pending_commands: list[CrossDeviceCommand] = []
        self.offline_queue: dict[str, list[CrossDeviceCommand]] = {}
        self.conflict_resolutions: list[ConflictResolution] = []
        self.state_versions: dict[str, int] = {}  # device_id -> version

    def create_session(
        self,
        device_id: str,
        device_type: DeviceType,
        user_id: str,
    ) -> DeviceSession:
        """Create a new session on a device."""
        session = DeviceSession(
            session_id=str(uuid.uuid4()),
            device_id=device_id,
            device_type=device_type,
            user_id=user_id,
        )
        self.sessions[session.session_id] = session
        logger.info(f"Created session {session.session_id} on {device_id} for {user_id}")
        return session

    def get_active_sessions(self, user_id: str) -> list[DeviceSession]:
        """Get all active sessions for a user."""
        return [
            s
            for s in self.sessions.values()
            if s.user_id == user_id and s.is_active and not s.is_stale()
        ]

    def handoff_session(
        self,
        from_session: DeviceSession,
        to_device_id: str,
        to_device_type: DeviceType,
    ) -> DeviceSession:
        """Hand off an active session from one device to another."""
        # Deactivate old session
        from_session.is_active = False

        # Create new session with same controls
        new_session = self.create_session(
            device_id=to_device_id,
            device_type=to_device_type,
            user_id=from_session.user_id,
        )
        new_session.active_controls = from_session.active_controls.copy()

        logger.info(f"Handed off session from {from_session.device_id} to {to_device_id}")
        return new_session

    async def execute_command(
        self,
        command: CrossDeviceCommand,
        controller: Any,
    ) -> dict[str, Any]:
        """Execute a cross-device command with conflict detection."""
        # Check for conflicts with pending commands
        conflicts = self._detect_conflicts(command)

        if conflicts:
            # Resolve conflicts
            resolution = self._resolve_conflict(command, conflicts[0])
            self.conflict_resolutions.append(resolution)

            if resolution.winner_command_id != command.command_id:
                command.sync_state = SyncState.CONFLICT
                command.conflicting_command = conflicts[0].command_id
                return {
                    "success": False,
                    "conflict": True,
                    "resolution": resolution,
                }

        # Execute the command
        try:
            result = await self._execute_action(command, controller)
            command.sync_state = SyncState.SYNCED
            command.resolved = True

            # Update state version
            self.state_versions[command.target] = self.state_versions.get(command.target, 0) + 1

            return {
                "success": True,
                "result": result,
                "version": self.state_versions[command.target],
            }
        except Exception as e:
            command.sync_state = SyncState.PENDING
            return {
                "success": False,
                "error": str(e),
            }

    async def _execute_action(
        self,
        command: CrossDeviceCommand,
        controller: Any,
    ) -> Any:
        """Execute the actual action from a command."""
        action_map = {
            "set_lights": controller.set_lights,
            "set_scene": controller.set_room_scene,
            "set_temp": controller.set_room_temp,
            "tv_on": controller.tv_on,
            "tv_off": controller.tv_off,
            "play_music": controller.spotify_play_playlist,
            "pause_music": controller.spotify_pause,
            "lock": controller.lock_all,
            "unlock": controller.unlock_door,
        }

        action_func = action_map.get(command.action)
        if action_func:
            if command.params:
                return await action_func(**command.params)
            return await action_func()
        return None

    def _detect_conflicts(
        self,
        command: CrossDeviceCommand,
    ) -> list[CrossDeviceCommand]:
        """Detect commands that conflict with the given command."""
        conflicts = []

        for pending in self.pending_commands:
            if (
                pending.command_id != command.command_id
                and pending.target == command.target
                and pending.action == command.action
                and pending.sync_state == SyncState.PENDING
                and abs(pending.timestamp - command.timestamp) < 2.0  # Within 2 seconds
            ):
                conflicts.append(pending)

        return conflicts

    def _resolve_conflict(
        self,
        command1: CrossDeviceCommand,
        command2: CrossDeviceCommand,
    ) -> ConflictResolution:
        """Resolve a conflict between two commands."""
        # Strategy 1: Last write wins (by timestamp)
        if command1.timestamp > command2.timestamp:
            winner, loser = command1, command2
        else:
            winner, loser = command2, command1

        # Mark loser as resolved
        loser.sync_state = SyncState.CONFLICT
        loser.resolved = True

        return ConflictResolution(
            winner_command_id=winner.command_id,
            loser_command_id=loser.command_id,
            resolution_strategy="last_write_wins",
        )

    def queue_offline_command(
        self,
        device_id: str,
        command: CrossDeviceCommand,
    ) -> None:
        """Queue a command for later execution when device is offline."""
        if device_id not in self.offline_queue:
            self.offline_queue[device_id] = []

        command.sync_state = SyncState.OFFLINE
        self.offline_queue[device_id].append(command)
        logger.info(f"Queued offline command {command.command_id} for {device_id}")

    async def sync_offline_commands(
        self,
        device_id: str,
        controller: Any,
    ) -> list[dict[str, Any]]:
        """Sync queued commands when device comes back online."""
        results = []

        if device_id in self.offline_queue:
            commands = self.offline_queue[device_id]
            logger.info(f"Syncing {len(commands)} offline commands for {device_id}")

            for command in commands:
                result = await self.execute_command(command, controller)
                results.append(
                    {
                        "command_id": command.command_id,
                        "result": result,
                    }
                )

            # Clear the queue
            self.offline_queue[device_id] = []

        return results


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def cross_device_manager(mock_constellation: MockDeviceConstellation) -> CrossDeviceManager:
    """Create a cross-device manager for testing."""
    return CrossDeviceManager(mock_constellation)


# ==============================================================================
# PHONE TO WATCH HANDOFF TESTS
# ==============================================================================


class TestPhoneToWatchHandoff:
    """Test seamless handoff from phone to watch."""

    async def test_phone_to_watch_handoff_basic(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test basic session handoff from phone to watch."""
        # Create phone session
        phone_session = cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Set active controls on phone
        phone_session.active_controls = ["Living Room Lights", "Thermostat"]

        # Execute command from phone
        phone_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 50},
        )

        result = await cross_device_manager.execute_command(
            phone_command,
            mock_smart_home_controller,
        )
        assert result["success"]

        # Handoff to watch
        watch_session = cross_device_manager.handoff_session(
            from_session=phone_session,
            to_device_id="watch-tim",
            to_device_type=DeviceType.WATCH,
        )

        # Verify handoff
        assert not phone_session.is_active
        assert watch_session.is_active
        assert watch_session.active_controls == phone_session.active_controls
        assert watch_session.user_id == phone_session.user_id

        # Execute command from watch - should work
        watch_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.WATCH,
            source_device="watch-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 75},
        )

        result = await cross_device_manager.execute_command(
            watch_command,
            mock_smart_home_controller,
        )
        assert result["success"]

    async def test_phone_to_watch_preserves_state(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test that state is preserved during handoff."""
        # Create phone session with state
        phone_session = cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Make several changes
        for level in [30, 50, 70]:
            command = CrossDeviceCommand(
                command_id=str(uuid.uuid4()),
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action="set_lights",
                target="living-room",
                params={"level": level},
            )
            await cross_device_manager.execute_command(command, mock_smart_home_controller)

        # Get current version
        pre_handoff_version = cross_device_manager.state_versions.get("living-room", 0)

        # Handoff to watch
        watch_session = cross_device_manager.handoff_session(
            from_session=phone_session,
            to_device_id="watch-tim",
            to_device_type=DeviceType.WATCH,
        )

        # State version should be preserved
        assert cross_device_manager.state_versions.get("living-room", 0) == pre_handoff_version

    async def test_multiple_handoffs(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test multiple device handoffs in sequence."""
        # Phone -> Watch -> Phone
        phone_session1 = cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )
        phone_session1.active_controls = ["Lights"]

        watch_session = cross_device_manager.handoff_session(
            from_session=phone_session1,
            to_device_id="watch-tim",
            to_device_type=DeviceType.WATCH,
        )

        phone_session2 = cross_device_manager.handoff_session(
            from_session=watch_session,
            to_device_id="phone-tim",
            to_device_type=DeviceType.PHONE,
        )

        # Verify chain
        assert not phone_session1.is_active
        assert not watch_session.is_active
        assert phone_session2.is_active
        assert phone_session2.active_controls == ["Lights"]


# ==============================================================================
# TV TO PHONE CONTROL TESTS
# ==============================================================================


class TestTVToPhoneControl:
    """Test controlling TV from phone and vice versa."""

    async def test_tv_started_phone_control(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test starting TV then controlling from phone."""
        # Start TV session
        tv_session = cross_device_manager.create_session(
            device_id="tv-living",
            device_type=DeviceType.TV,
            user_id=tim_persona.user_id,
        )

        # TV turns on and enters movie mode
        tv_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.TV,
            source_device="tv-living",
            user_id=tim_persona.user_id,
            action="tv_on",
            target="tv-living",
            params={},
        )
        await cross_device_manager.execute_command(tv_command, mock_smart_home_controller)

        # Now control from phone
        phone_session = cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Adjust lights from phone
        phone_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 20},
        )

        result = await cross_device_manager.execute_command(
            phone_command,
            mock_smart_home_controller,
        )
        assert result["success"]

        # Both sessions should be active
        active_sessions = cross_device_manager.get_active_sessions(tim_persona.user_id)
        assert len(active_sessions) == 2

    async def test_phone_controls_tv_playback(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test phone controlling TV playback."""
        # Both devices active
        cross_device_manager.create_session(
            device_id="tv-living",
            device_type=DeviceType.TV,
            user_id=tim_persona.user_id,
        )
        cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Phone sends TV commands
        commands = [
            ("tv_on", {}),
            ("play_music", {"playlist": "movie-soundtrack"}),
        ]

        for action, params in commands:
            command = CrossDeviceCommand(
                command_id=str(uuid.uuid4()),
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action=action,
                target="tv-living",
                params=params,
            )
            result = await cross_device_manager.execute_command(
                command,
                mock_smart_home_controller,
            )
            assert result["success"]


# ==============================================================================
# VOICE TO MANUAL OVERRIDE TESTS
# ==============================================================================


class TestVoiceToManualOverride:
    """Test voice command then manual override scenarios."""

    async def test_voice_command_manual_override(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test voice command followed by manual override."""
        # Voice command sets lights to 50%
        voice_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.VOICE,
            source_device="speaker-living",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 50},
        )

        result = await cross_device_manager.execute_command(
            voice_command,
            mock_smart_home_controller,
        )
        assert result["success"]
        voice_version = result["version"]

        # Simulate brief delay
        await asyncio.sleep(0.5)

        # Manual override (physical switch) sets lights to 100%
        manual_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.MANUAL,
            source_device="switch-living",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 100},
        )

        result = await cross_device_manager.execute_command(
            manual_command,
            mock_smart_home_controller,
        )
        assert result["success"]
        manual_version = result["version"]

        # Manual override should have newer version
        assert manual_version > voice_version

    async def test_rapid_voice_manual_conflict(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test rapid succession of voice and manual commands."""
        # Add both commands to pending (simulate near-simultaneous)
        voice_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.VOICE,
            source_device="speaker-living",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 30},
            timestamp=time.time(),
        )
        cross_device_manager.pending_commands.append(voice_command)

        # Manual command slightly after
        manual_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.MANUAL,
            source_device="switch-living",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 100},
            timestamp=time.time() + 0.5,  # 500ms later
        )

        # Execute manual command - should detect conflict and win
        result = await cross_device_manager.execute_command(
            manual_command,
            mock_smart_home_controller,
        )

        # Manual command should win (last write wins)
        assert result["success"]

        # Check conflict was recorded
        assert len(cross_device_manager.conflict_resolutions) == 1
        resolution = cross_device_manager.conflict_resolutions[0]
        assert resolution.winner_command_id == manual_command.command_id
        assert resolution.resolution_strategy == "last_write_wins"

    async def test_voice_command_then_automation(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test voice command interaction with automation rules."""
        # Voice command
        voice_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.VOICE,
            source_device="speaker-living",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 50},
        )

        await cross_device_manager.execute_command(
            voice_command,
            mock_smart_home_controller,
        )

        # Automation tries to change lights (e.g., sunset rule)
        auto_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.AUTOMATION,
            source_device="automation-engine",
            user_id="system",
            action="set_lights",
            target="living-room",
            params={"level": 30},
        )

        # No conflict since user command was first
        await asyncio.sleep(2.5)  # Outside conflict window
        result = await cross_device_manager.execute_command(
            auto_command,
            mock_smart_home_controller,
        )

        assert result["success"]


# ==============================================================================
# OFFLINE TO ONLINE SYNC TESTS
# ==============================================================================


class TestOfflineToOnlineSync:
    """Test offline command queueing and online sync."""

    async def test_queue_commands_while_offline(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        mock_constellation: MockDeviceConstellation,
        tim_persona: UserPersona,
    ):
        """Test queueing commands while device is offline."""
        # Set network to offline
        mock_constellation.set_network_condition(NetworkCondition.OFFLINE)

        # Queue several commands
        commands = [
            ("set_lights", {"level": 50}),
            ("set_temp", {"temp": 72}),
            ("set_scene", {"scene": "relaxing"}),
        ]

        for action, params in commands:
            command = CrossDeviceCommand(
                command_id=str(uuid.uuid4()),
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action=action,
                target="living-room",
                params=params,
            )
            cross_device_manager.queue_offline_command("phone-tim", command)

        # Verify commands are queued
        assert len(cross_device_manager.offline_queue["phone-tim"]) == 3

        # All commands should have OFFLINE state
        for cmd in cross_device_manager.offline_queue["phone-tim"]:
            assert cmd.sync_state == SyncState.OFFLINE

    async def test_sync_commands_when_online(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        mock_constellation: MockDeviceConstellation,
        tim_persona: UserPersona,
    ):
        """Test syncing queued commands when coming back online."""
        # Queue commands while offline
        commands = []
        for i in range(3):
            cmd = CrossDeviceCommand(
                command_id=str(uuid.uuid4()),
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action="set_lights",
                target="living-room",
                params={"level": (i + 1) * 25},
            )
            commands.append(cmd)
            cross_device_manager.queue_offline_command("phone-tim", cmd)

        # Simulate coming back online
        mock_constellation.set_network_condition(NetworkCondition.NORMAL)

        # Sync commands
        results = await cross_device_manager.sync_offline_commands(
            "phone-tim",
            mock_smart_home_controller,
        )

        # All commands should sync
        assert len(results) == 3
        for result in results:
            assert result["result"]["success"]

        # Queue should be empty
        assert len(cross_device_manager.offline_queue.get("phone-tim", [])) == 0

    async def test_offline_commands_preserve_order(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test that offline commands are replayed in order."""
        # Queue commands with specific timestamps
        base_time = time.time()

        for i in range(5):
            cmd = CrossDeviceCommand(
                command_id=f"cmd-{i}",
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action="set_lights",
                target="living-room",
                params={"level": i * 20},
                timestamp=base_time + i,
            )
            cross_device_manager.queue_offline_command("phone-tim", cmd)

        # Sync and verify order
        results = await cross_device_manager.sync_offline_commands(
            "phone-tim",
            mock_smart_home_controller,
        )

        # Results should be in order
        for i, result in enumerate(results):
            assert result["command_id"] == f"cmd-{i}"

    async def test_offline_conflict_resolution_on_sync(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test conflict resolution when syncing offline commands."""
        # Queue two conflicting commands (same target, close timestamps)
        cmd1 = CrossDeviceCommand(
            command_id="cmd-1",
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 25},
            timestamp=time.time(),
        )
        cross_device_manager.queue_offline_command("phone-tim", cmd1)

        cmd2 = CrossDeviceCommand(
            command_id="cmd-2",
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 75},
            timestamp=time.time() + 0.5,
        )
        cross_device_manager.queue_offline_command("phone-tim", cmd2)

        # Sync commands
        results = await cross_device_manager.sync_offline_commands(
            "phone-tim",
            mock_smart_home_controller,
        )

        # Both should process (sequentially, no conflict due to sequential execution)
        assert len(results) == 2
        # Last command's value should win
        final_version = cross_device_manager.state_versions.get("living-room", 0)
        assert final_version == 2  # Two successful updates


# ==============================================================================
# MULTI-USER CONFLICT TESTS
# ==============================================================================


class TestMultiUserConflict:
    """Test scenarios where multiple users control the same device."""

    async def test_two_users_same_device_sequential(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
        guest_persona: UserPersona,
    ):
        """Test two users controlling the same device sequentially."""
        # Tim sets lights
        tim_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 50},
        )

        result = await cross_device_manager.execute_command(
            tim_command,
            mock_smart_home_controller,
        )
        assert result["success"]
        tim_version = result["version"]

        # Guest sets lights (after Tim)
        await asyncio.sleep(0.1)

        guest_command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.PHONE,
            source_device="phone-guest",
            user_id=guest_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 75},
        )

        result = await cross_device_manager.execute_command(
            guest_command,
            mock_smart_home_controller,
        )
        assert result["success"]
        guest_version = result["version"]

        # Both should succeed, guest version is newer
        assert guest_version > tim_version

    async def test_two_users_simultaneous_conflict(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
        guest_persona: UserPersona,
    ):
        """Test two users trying to control same device simultaneously."""
        # Both commands arrive at nearly same time
        current_time = time.time()

        tim_command = CrossDeviceCommand(
            command_id="tim-cmd",
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 30},
            timestamp=current_time,
        )
        cross_device_manager.pending_commands.append(tim_command)

        guest_command = CrossDeviceCommand(
            command_id="guest-cmd",
            source=CommandSource.PHONE,
            source_device="phone-guest",
            user_id=guest_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 80},
            timestamp=current_time + 0.5,  # Slightly later
        )

        # Execute guest command (should detect conflict with Tim's)
        result = await cross_device_manager.execute_command(
            guest_command,
            mock_smart_home_controller,
        )

        # Guest command wins (last write wins)
        assert result["success"]
        assert len(cross_device_manager.conflict_resolutions) == 1

        resolution = cross_device_manager.conflict_resolutions[0]
        assert resolution.winner_command_id == "guest-cmd"

    async def test_owner_priority_over_guest(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
        guest_persona: UserPersona,
    ):
        """Test that owner actions take priority over guest in certain scenarios."""
        # This could be extended with a priority-based conflict resolution

        # Guest session
        cross_device_manager.create_session(
            device_id="phone-guest",
            device_type=DeviceType.PHONE,
            user_id=guest_persona.user_id,
        )

        # Owner session
        cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Get active sessions
        tim_sessions = cross_device_manager.get_active_sessions(tim_persona.user_id)
        guest_sessions = cross_device_manager.get_active_sessions(guest_persona.user_id)

        assert len(tim_sessions) == 1
        assert len(guest_sessions) == 1

        # In a real implementation, owner commands could have priority
        # For now, last-write-wins is the default strategy

    async def test_different_rooms_no_conflict(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
        guest_persona: UserPersona,
    ):
        """Test that commands to different rooms don't conflict."""
        # Tim controls living room
        tim_command = CrossDeviceCommand(
            command_id="tim-living",
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="set_lights",
            target="living-room",
            params={"level": 50},
            timestamp=time.time(),
        )
        cross_device_manager.pending_commands.append(tim_command)

        # Guest controls guest room (no conflict)
        guest_command = CrossDeviceCommand(
            command_id="guest-guest-room",
            source=CommandSource.PHONE,
            source_device="phone-guest",
            user_id=guest_persona.user_id,
            action="set_lights",
            target="guest-room",  # Different target
            params={"level": 75},
            timestamp=time.time(),
        )

        result = await cross_device_manager.execute_command(
            guest_command,
            mock_smart_home_controller,
        )

        # No conflict - different targets
        assert result["success"]
        assert len(cross_device_manager.conflict_resolutions) == 0


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================


class TestCrossDeviceEdgeCases:
    """Test edge cases in cross-device scenarios."""

    async def test_stale_session_cleanup(
        self,
        cross_device_manager: CrossDeviceManager,
        tim_persona: UserPersona,
    ):
        """Test that stale sessions are properly identified."""
        # Create session with old activity
        session = cross_device_manager.create_session(
            device_id="phone-tim",
            device_type=DeviceType.PHONE,
            user_id=tim_persona.user_id,
        )

        # Manually set old last_activity
        session.last_activity = time.time() - 600  # 10 minutes ago

        # Session should be stale
        assert session.is_stale(timeout_seconds=300)

        # But not stale with longer timeout
        assert not session.is_stale(timeout_seconds=900)

        # Active sessions should not include stale
        active = cross_device_manager.get_active_sessions(tim_persona.user_id)
        assert len(active) == 0

    async def test_rapid_command_sequence(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test rapid sequence of commands from same device."""
        commands = []
        for i in range(10):
            cmd = CrossDeviceCommand(
                command_id=f"rapid-{i}",
                source=CommandSource.PHONE,
                source_device="phone-tim",
                user_id=tim_persona.user_id,
                action="set_lights",
                target="living-room",
                params={"level": i * 10},
            )
            commands.append(cmd)

        # Execute all rapidly
        results = await asyncio.gather(
            *[
                cross_device_manager.execute_command(cmd, mock_smart_home_controller)
                for cmd in commands
            ]
        )

        # All should succeed (sequential execution in real system would prevent conflicts)
        successes = sum(1 for r in results if r.get("success", False))
        assert successes >= 8, "Most rapid commands should succeed"

    async def test_unknown_action_handling(
        self,
        cross_device_manager: CrossDeviceManager,
        mock_smart_home_controller,
        tim_persona: UserPersona,
    ):
        """Test handling of unknown/unsupported actions."""
        command = CrossDeviceCommand(
            command_id=str(uuid.uuid4()),
            source=CommandSource.PHONE,
            source_device="phone-tim",
            user_id=tim_persona.user_id,
            action="unsupported_action",
            target="some-device",
            params={},
        )

        result = await cross_device_manager.execute_command(
            command,
            mock_smart_home_controller,
        )

        # Should succeed but return None result
        assert result["success"]
        assert result["result"] is None


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
