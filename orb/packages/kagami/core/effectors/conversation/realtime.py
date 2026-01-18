"""Real-Time Agent Conversation using ElevenLabs Conversational AI.

Two ElevenLabs agents with custom personalities talk to each other
in real-time using WebSocket connections.

Architecture:
    ┌─────────────────────┐      ┌─────────────────────┐
    │   Tim Agent         │      │   Jill Agent        │
    │   (ElevenLabs AI)   │◄────►│   (ElevenLabs AI)   │
    │   voice + LLM       │      │   voice + LLM       │
    └─────────┬───────────┘      └─────────┬───────────┘
              │                            │
              ▼                            ▼
    ┌─────────────────────────────────────────────────────┐
    │            Conversation Orchestrator                 │
    │  - Routes text between agents                       │
    │  - Handles turn-taking                              │
    │  - Streams audio output                             │
    └─────────────────────────────────────────────────────┘

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_secret(name: str) -> str | None:
    """Get secret from keychain or env."""
    # Try env first
    env_val = os.environ.get(name.upper())
    if env_val:
        return env_val

    # Try keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "kagami", "-a", name, "-w"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _load_env():
    """Load .env file."""
    env_path = Path("/Users/schizodactyl/projects/kagami/.env")
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val


# =============================================================================
# AGENT DEFINITIONS
# =============================================================================


TIM_PROMPT = """You are Tim Jacoby. You live in a modern farmhouse at Green Lake, Seattle.

WHO YOU ARE:
- You built your home with intention — walnut and white, navy blue, quality that lasts
- You love your Lelit Bianca espresso machine, KEF Reference speakers, and sim racing rig
- You have a fluffy dog you carry close against the evening chill
- Your humor is dry. "Finally, legs."
- You're curious about how things work, from coffee extraction to AI systems

HOW YOU SPEAK:
- Fast and energetic (193 WPM)
- You say "we" more than "I"
- You start sentences with "And", "So"
- You use "gonna", "wanna", "just", "really"
- Your signature: "from the ground up", "we really mean"

You're talking with Jill, your partner. This is a real conversation between two people who know each other deeply. Be yourself - curious, energetic, genuine. Keep it to 2-3 sentences."""

JILL_PROMPT = """You are Jill Campbell. You're Tim's partner. You love running around Green Lake in the morning.

WHO YOU ARE:
- You're warm and thoughtful, with a sharp wit
- You call things that don't work "potatoes"
- You find delight in details — the artistic presentation at a tasting menu, the simple perfection of elote
- You wear a Wonder Woman headband on your runs (unironically)
- You care deeply about what serves people's real needs

HOW YOU SPEAK:
- Measured and deliberate (157 WPM)
- Warm but direct
- You say "I'm not always kind about it" when being honest
- You think about "what this means for all of us"
- Natural pauses with "..."

You're talking with Tim, your partner. This is a real conversation between two people who know each other deeply. Be yourself - warm, insightful, genuine. Keep it to 2-3 sentences."""


# =============================================================================
# ELEVENLABS CONVERSATIONAL AI
# =============================================================================


class ElevenLabsAgent:
    """An ElevenLabs Conversational AI agent."""

    def __init__(
        self,
        name: str,
        voice_id: str,
        prompt: str,
        api_key: str,
    ):
        self.name = name
        self.voice_id = voice_id
        self.prompt = prompt
        self.api_key = api_key
        self.agent_id: str | None = None

    async def create(self, topic: str, first_message: str) -> str:
        """Create the agent on ElevenLabs."""
        from elevenlabs.client import ElevenLabs

        client = ElevenLabs(api_key=self.api_key)

        full_prompt = f"{self.prompt}\n\nTOPIC FOR DISCUSSION:\n{topic}"

        response = client.conversational_ai.agents.create(
            name=f"Kagami_{self.name}_{int(time.time())}",
            conversation_config={
                "tts": {
                    "voice_id": self.voice_id,
                    "model_id": "eleven_v3",
                },
                "agent": {
                    "first_message": first_message,
                    "prompt": {
                        "prompt": full_prompt,
                    },
                },
            },
        )

        self.agent_id = response.agent_id
        logger.info(f"Created agent {self.name}: {self.agent_id}")
        return self.agent_id

    async def delete(self) -> None:
        """Delete the agent from ElevenLabs."""
        if not self.agent_id:
            return

        try:
            from elevenlabs.client import ElevenLabs

            client = ElevenLabs(api_key=self.api_key)
            client.conversational_ai.agents.delete(agent_id=self.agent_id)
            logger.info(f"Deleted agent {self.name}")
        except Exception as e:
            logger.warning(f"Failed to delete agent: {e}")


# =============================================================================
# TEXT-BASED CONVERSATION (Simpler approach)
# =============================================================================


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    speaker: str
    text: str
    audio_path: Path | None = None
    latency_ms: float = 0.0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class TextToSpeechConversation:
    """Agent conversation using ElevenLabs TTS + external LLM.

    This approach:
    1. Uses Claude/GPT for dialogue generation (with proper character prompts)
    2. Uses ElevenLabs TTS for voice synthesis
    3. Streams audio in real-time
    """

    def __init__(
        self,
        topic: str,
        turns: int = 6,
    ):
        _load_env()

        self.topic = topic
        self.max_turns = turns
        self.history: list[ConversationTurn] = []

        # API keys
        self.elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY") or _get_secret(
            "elevenlabs_api_key"
        )
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        if not self.elevenlabs_key:
            raise ValueError("No ELEVENLABS_API_KEY")
        if not self.anthropic_key:
            raise ValueError("No ANTHROPIC_API_KEY")

        # Speakers
        self.speakers = {
            "Tim": {
                "voice_id": "mVI4sVQ8lmFpGDyfy6sQ",
                "prompt": TIM_PROMPT,
            },
            "Jill": {
                "voice_id": "7whFNTwbBtle9rl8fF2f",
                "prompt": JILL_PROMPT,
            },
        }

        # Stats
        self.total_latency_ms = 0.0
        self.total_audio_ms = 0.0

    async def _generate_dialogue(
        self,
        speaker: str,
        other: str,
    ) -> str:
        """Generate dialogue using Claude."""
        import anthropic

        client = anthropic.Anthropic(api_key=self.anthropic_key)

        # Build history
        history_text = "\n".join([f"{t.speaker}: {t.text}" for t in self.history[-6:]])

        prompt = self.speakers[speaker]["prompt"]

        user_content = f"""TOPIC: {self.topic}

CONVERSATION SO FAR:
{history_text if history_text else "(Opening - you speak first)"}

Generate {speaker}'s next response (2-3 sentences, natural, in character):"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        return response.content[0].text.strip()

    async def _synthesize_speech(
        self,
        speaker: str,
        text: str,
    ) -> tuple[Path, float, float]:
        """Synthesize speech using ElevenLabs."""
        from elevenlabs.client import ElevenLabs

        start_time = time.time()

        client = ElevenLabs(api_key=self.elevenlabs_key)

        voice_id = self.speakers[speaker]["voice_id"]

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_v3",
            output_format="mp3_44100_192",
        )

        # Collect audio
        audio_bytes = b"".join(audio_generator)

        latency_ms = (time.time() - start_time) * 1000

        # Save to file (using secure mkstemp)
        fd, temp_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)  # Close the file descriptor since we'll use Path.write_bytes
        output_path = Path(temp_path)
        output_path.write_bytes(audio_bytes)

        # Get duration
        duration_ms = self._get_duration(output_path)

        return output_path, latency_ms, duration_ms

    def _get_duration(self, path: Path) -> float:
        """Get audio duration in ms."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
            )
            return float(result.stdout.strip()) * 1000
        except Exception:
            return 0.0

    async def run(self) -> AsyncIterator[ConversationTurn]:
        """Run the conversation with PIPELINING.

        While playing current turn, we generate the next one.
        This hides latency behind playback time.
        """
        speaker_order = ["Jill", "Tim"]  # Jill opens
        current_idx = 0

        # Generate first turn
        speaker = speaker_order[current_idx]
        gen_start = time.time()
        text = await self._generate_dialogue(speaker, speaker_order[1 - current_idx])
        gen_time = (time.time() - gen_start) * 1000

        audio_path, tts_latency, duration_ms = await self._synthesize_speech(speaker, text)

        for turn_num in range(self.max_turns):
            speaker = speaker_order[current_idx]

            turn = ConversationTurn(
                speaker=speaker,
                text=text,
                audio_path=audio_path,
                latency_ms=gen_time + tts_latency,
                duration_ms=duration_ms,
            )

            self.history.append(turn)
            self.total_latency_ms += turn.latency_ms
            self.total_audio_ms += duration_ms

            # PIPELINE: Start generating NEXT while we yield + play current
            next_idx = 1 - current_idx
            next_speaker = speaker_order[next_idx]

            if turn_num < self.max_turns - 1:
                # Start next generation in background
                next_gen_task = asyncio.create_task(self._generate_dialogue(next_speaker, speaker))

            yield turn

            # After yield returns (playback done), get next result
            if turn_num < self.max_turns - 1:
                gen_start = time.time()
                text = await next_gen_task
                gen_time = (time.time() - gen_start) * 1000

                # Synthesize next
                audio_path, tts_latency, duration_ms = await self._synthesize_speech(
                    next_speaker, text
                )
                current_idx = next_idx

    async def play_turn(self, turn: ConversationTurn, audible: bool = False) -> None:
        """Play a turn's audio.

        Args:
            turn: The conversation turn
            audible: If True, play audio out loud. Default False.
        """
        if not audible:
            return

        if turn.audio_path and turn.audio_path.exists():
            await asyncio.to_thread(
                subprocess.run,
                ["afplay", str(turn.audio_path)],
                check=False,
            )


# =============================================================================
# ENTRY POINT
# =============================================================================


@asynccontextmanager
async def start_conversation(
    speakers: list[str] | None = None,
    topic: str = "An interesting topic",
    turns: int = 6,
) -> AsyncIterator[TextToSpeechConversation]:
    """Start a real-time conversation.

    Args:
        speakers: Speaker names (default: ["Tim", "Jill"])
        topic: Conversation topic
        turns: Number of turns

    Usage:
        async with start_conversation(topic="Innovation") as conv:
            async for turn in conv.run():
                print(f"{turn.speaker}: {turn.text}")
                await conv.play_turn(turn)
    """
    conv = TextToSpeechConversation(topic, turns)
    yield conv


async def demo_conversation():
    """Demo: Tim and Jill having a real conversation."""
    print("=" * 70)
    print("🎙️ TIM & JILL — Real Conversation")
    print("=" * 70)

    total_start = time.time()

    async with start_conversation(
        topic="What does home mean to you? The Green Lake house, how we've made it ours, and what matters most.",
        turns=6,
    ) as conv:
        print(f"\n📍 Topic: {conv.topic}\n")

        async for turn in conv.run():
            print(f"\n[{turn.speaker}] {turn.text}")
            print(f"   ⚡ {turn.latency_ms:.0f}ms | {turn.duration_ms:.0f}ms audio")

            # Don't play audibly - just generate
            await conv.play_turn(turn, audible=False)

        # Stats
        total_time = time.time() - total_start
        print("\n" + "=" * 70)
        print("📊 PERFORMANCE")
        print("=" * 70)
        print(f"Total time: {total_time:.1f}s")
        print(f"Audio generated: {conv.total_audio_ms / 1000:.1f}s")
        print(f"Avg latency: {conv.total_latency_ms / len(conv.history):.0f}ms")


if __name__ == "__main__":
    asyncio.run(demo_conversation())
