"""ElevenLabs Agent Manager — Sync prompts to cloud.

Manages the ElevenLabs Conversational AI agent configuration,
keeping it in sync with our local prompt definitions from prompts.py.

The prompts in prompts.py are derived from CLAUDE.md and .cursor/rules/kagami.mdc.
This module syncs them to the ElevenLabs cloud agent.

Created: January 8, 2026
鏡
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from kagami.core.security import get_secret

from .prompts import VoiceMode, get_first_message, get_system_prompt

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AgentManager:
    """Manages ElevenLabs agent configuration."""

    def __init__(self) -> None:
        self._api_key: str = ""
        self._agent_id: str = ""
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize with credentials from keychain."""
        try:
            self._api_key = get_secret("elevenlabs_api_key")
            self._agent_id = get_secret("elevenlabs_agent_id")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize AgentManager: {e}")
            return False

    @property
    def agent_id(self) -> str:
        """Get the agent ID."""
        return self._agent_id

    async def sync_prompts(self, mode: VoiceMode = VoiceMode.NORMAL) -> bool:
        """Sync prompts to ElevenLabs agent.

        Args:
            mode: The voice mode to sync (NORMAL or PRANK)

        Returns:
            True if sync succeeded
        """
        if not self._initialized:
            if not await self.initialize():
                return False

        system_prompt = get_system_prompt(mode)
        first_message = get_first_message(mode)

        logger.info(f"🔄 Syncing {mode.value} prompts to ElevenLabs agent...")

        async with httpx.AsyncClient() as client:
            patch_data = {
                "conversation_config": {
                    "agent": {
                        "first_message": first_message,
                        "prompt": {"prompt": system_prompt},
                    }
                }
            }

            try:
                resp = await client.patch(
                    f"https://api.elevenlabs.io/v1/convai/agents/{self._agent_id}",
                    headers={"xi-api-key": self._api_key},
                    json=patch_data,
                    timeout=30.0,
                )

                if resp.status_code == 200:
                    logger.info(f"✅ Agent synced to {mode.value} mode")
                    return True
                else:
                    logger.error(f"❌ Sync failed: {resp.status_code} - {resp.text[:200]}")
                    return False
            except Exception as e:
                logger.error(f"❌ Sync error: {e}")
                return False

    async def get_current_config(self) -> dict | None:
        """Get the current agent configuration from ElevenLabs."""
        if not self._initialized:
            if not await self.initialize():
                return None

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"https://api.elevenlabs.io/v1/convai/agents/{self._agent_id}",
                    headers={"xi-api-key": self._api_key},
                    timeout=30.0,
                )

                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.error(f"Failed to get config: {resp.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Error getting config: {e}")
                return None


# Singleton instance
_agent_manager: AgentManager | None = None


async def get_agent_manager() -> AgentManager:
    """Get or create the agent manager singleton."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
        await _agent_manager.initialize()
    return _agent_manager


async def sync_agent(mode: VoiceMode = VoiceMode.NORMAL) -> bool:
    """Sync agent prompts to ElevenLabs.

    Args:
        mode: Voice mode (NORMAL or PRANK)

    Returns:
        True if sync succeeded
    """
    manager = await get_agent_manager()
    return await manager.sync_prompts(mode)


async def prank_call(phone_number: str, webhook_url: str | None = None) -> str | None:
    """Make a prank call.

    Syncs PRANK mode to agent, makes the call, then restores NORMAL mode.

    Args:
        phone_number: Phone number to call
        webhook_url: Webhook URL for Twilio (uses ngrok if not provided)

    Returns:
        Call SID if successful, None if failed
    """
    from .realtime import call

    # Sync prank prompts
    manager = await get_agent_manager()
    if not await manager.sync_prompts(VoiceMode.PRANK):
        logger.error("Failed to sync prank prompts")
        return None

    logger.info("🎭 Prank mode activated!")

    # Make the call
    session = await call(
        phone_number=phone_number,
        bidirectional=True,
        webhook_url=webhook_url,
    )

    if session:
        return session.session_id
    return None


async def restore_normal_mode() -> bool:
    """Restore agent to normal mode after prank."""
    manager = await get_agent_manager()
    return await manager.sync_prompts(VoiceMode.NORMAL)


__all__ = [
    "AgentManager",
    "get_agent_manager",
    "prank_call",
    "restore_normal_mode",
    "sync_agent",
]
