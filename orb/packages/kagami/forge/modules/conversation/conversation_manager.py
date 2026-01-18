"""Forge Conversation Manager for Multi-Colony Dialogue.

Orchestrates real-time conversations between the seven colonies
with catastrophe-driven response patterns and room-aware audio routing.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

from .notifications import get_notification_system
from .room_mapping import SmartHomeRoomMapper
from .room_streamer import ConversationAudioRouter, RealtimeRoomStreamer
from .state import (
    ConversationState,
    ConversationTurn,
    EmotionType,
    get_colony_personality,
    get_colony_response_pattern,
)

logger = logging.getLogger(__name__)


class ForgeConversationManager:
    """Orchestrate multi-colony conversations through Forge."""

    def __init__(self, audio_bridge=None, llm_service=None, smart_home_controller=None):
        self.audio_bridge = audio_bridge
        self.llm_service = llm_service
        self.smart_home_controller = smart_home_controller
        self.active_conversations: dict[str, ConversationState] = {}

        # Initialize enhanced room and character systems
        self.room_mapper = SmartHomeRoomMapper(smart_home_controller)
        self.room_streamer = RealtimeRoomStreamer(audio_bridge)
        self.audio_router = ConversationAudioRouter(self.room_streamer)

        # Brief notification system for conversations only
        self.notifications = get_notification_system(smart_home_controller)

        # Character-driven conversation state
        self._conversation_mood = "balanced"  # Global conversation mood

    # Conversation manager focuses only on conversation orchestration
    # For general system notifications, use GeneralNotificationSystem separately

    async def conduct_conversation(
        self,
        topic: str,
        colonies: list[str],
        rooms: list[str],
        duration_sec: int = 60,
        conversation_id: str | None = None,
    ) -> ConversationState:
        """Conduct a multi-colony conversation.

        Args:
            topic: Discussion topic
            colonies: List of participating colonies
            rooms: Target rooms for audio output
            duration_sec: Maximum conversation length
            conversation_id: Optional conversation identifier

        Returns:
            Final conversation state
        """
        if conversation_id is None:
            conversation_id = f"conv_{int(time.time())}"

        # Get optimal room assignments based on topic and colony personalities
        if len(rooms) == 1 and rooms[0] == "auto":
            # Auto-select optimal rooms
            room_assignments = await self.room_mapper.get_optimal_room_assignment(topic, colonies)
            actual_rooms = list(room_assignments.keys())
        else:
            # Use provided rooms
            room_assignments = dict.fromkeys(rooms, colonies)
            actual_rooms = rooms

        # Configure all rooms in parallel for optimal performance
        await self.room_mapper.parallel_room_configuration(room_assignments, topic)

        # Initialize character-driven conversation state
        state = ConversationState(
            topic=topic,
            participants=colonies,
            room_assignments=room_assignments,
        )
        self.active_conversations[conversation_id] = state

        # Configure enhanced audio router with room-specific assignments
        self.audio_router.set_room_assignments(room_assignments)

        logger.info(f"🗣️ Starting conversation: {topic}")
        logger.info(f"   Participants: {colonies}")
        logger.info(f"   Rooms: {rooms}")

        # Brief notification system only
        await self.notifications.conversation_notification("start", topic, actual_rooms)

        try:
            # Start with opening statement from lead colony
            lead_colony = colonies[0] if colonies else "kagami"
            await self._generate_opening_statement(state, lead_colony, rooms)

            # Main conversation loop
            start_time = time.time()
            while (
                state.active
                and time.time() - start_time < duration_sec
                and len(state.turns) < 20  # Max turns limit
            ):
                # Determine next speaker
                next_colony = self._select_next_speaker(state, colonies)
                if not next_colony:
                    break

                # Generate response based on colony pattern
                await self._generate_colony_response(state, next_colony, rooms)

                # Brief pause between responses
                await asyncio.sleep(0.5)

            # Generate closing synthesis
            await self._generate_closing_statement(state, "kagami", rooms)

        except Exception as e:
            logger.error(f"Conversation error: {e}")
            state.active = False

        finally:
            # Clean up conversation and audio routing
            if conversation_id in self.active_conversations:
                del self.active_conversations[conversation_id]
            await self.room_streamer.cleanup()

        # Brief completion notification
        await self.notifications.conversation_notification("complete", f"{len(state.turns)} turns")

        logger.info(
            f"🏁 Conversation completed: {len(state.turns)} turns, {state.duration_seconds:.1f}s"
        )
        return state

    async def _generate_opening_statement(
        self,
        state: ConversationState,
        colony: str,
        rooms: list[str],
    ) -> None:
        """Generate opening statement for the conversation."""
        # Get colony personality
        pattern = get_colony_response_pattern(colony)

        # Generate opening based on topic and colony
        prompt = self._create_opening_prompt(state.topic, colony)
        text = await self._generate_text(prompt, pattern)

        # Stream to rooms with enhanced routing
        success, metrics = await self.audio_router.route_colony_speech(
            colony=colony,
            text=text,
            conversation_rooms=rooms,
        )
        duration_ms = metrics.total_duration_ms if success else 0

        # Record turn
        turn = ConversationTurn(
            timestamp=time.time(),
            colony=colony,
            text=text,
            emotion=EmotionType.CONFIDENT,
            duration_ms=duration_ms,
            rooms_played=rooms,
        )
        state.turns.append(turn)

    async def _generate_colony_response(
        self,
        state: ConversationState,
        colony: str,
        rooms: list[str],
    ) -> None:
        """Generate a response from a specific colony."""
        pattern = get_colony_response_pattern(colony)

        # Wait for colony's natural response latency
        await asyncio.sleep(pattern.latency_ms / 1000.0)

        # Generate response based on conversation context
        prompt = self._create_response_prompt(state, colony)
        text = await self._generate_text(prompt, pattern)

        # Select emotion based on colony and context
        emotion = self._select_emotion(colony, state)

        # Stream to rooms with enhanced routing
        success, metrics = await self.audio_router.route_colony_speech(
            colony=colony,
            text=text,
            conversation_rooms=rooms,
        )
        duration_ms = metrics.total_duration_ms if success else 0

        # Record turn
        turn = ConversationTurn(
            timestamp=time.time(),
            colony=colony,
            text=text,
            emotion=emotion,
            duration_ms=duration_ms,
            rooms_played=rooms,
            response_to=state.last_speaker,
        )
        state.turns.append(turn)

    def _select_next_speaker(
        self,
        state: ConversationState,
        colonies: list[str],
    ) -> str | None:
        """Select which colony should speak next."""
        if not colonies:
            return None

        # Don't let same colony speak twice in a row (usually)
        available = [c for c in colonies if c != state.last_speaker]
        if not available:
            available = colonies

        # Weight by colony patterns and conversation flow
        weights = []
        for colony in available:
            pattern = get_colony_response_pattern(colony)

            # Base weight
            weight = 1.0

            # Colonies with higher interruption thresholds speak more
            weight += pattern.interruption_threshold

            # Colonies that haven't spoken recently get higher weight
            last_turn_by_colony = next(
                (i for i, turn in enumerate(reversed(state.turns)) if turn.colony == colony),
                len(state.turns),  # If never spoken, use large value
            )
            weight += last_turn_by_colony * 0.1

            weights.append(weight)

        # Weighted random selection
        if weights:
            return random.choices(available, weights=weights)[0]
        return available[0] if available else None

    def _create_opening_prompt(self, topic: str, colony: str) -> str:
        """Create opening statement prompt for a colony."""
        colony_contexts = {
            "spark": "You ignite ideas and create momentum. Be energetic and decisive.",
            "forge": "You build and shape solutions. Be methodical and constructive.",
            "flow": "You adapt and find alternative paths. Be flexible and solution-oriented.",
            "nexus": "You connect ideas and bridge perspectives. Be integrative and thoughtful.",
            "beacon": "You provide direction and focus. Be clear and goal-oriented.",
            "grove": "You explore and learn. Be curious and investigative.",
            "crystal": "You verify and ensure quality. Be analytical and precise.",
            "kagami": "You synthesize and reflect. Be balanced and facilitating.",
        }

        context = colony_contexts.get(colony, colony_contexts["kagami"])

        return f"""You are {colony.title()} colony. {context}

Topic: {topic}

Give a brief opening statement (20-50 words) that introduces your perspective on this topic.
Be authentic to your colony's nature and speak directly without meta-commentary."""

    def _create_response_prompt(self, state: ConversationState, colony: str) -> str:
        """Create character-driven response prompt based on conversation context."""
        pattern = get_colony_response_pattern(colony)
        personality = get_colony_personality(colony)

        # Get recent context
        recent_turns = state.get_recent_turns(30)
        context = "\n".join(
            [
                f"{turn.colony}: {turn.text}"
                for turn in recent_turns[-3:]  # Last 3 turns
            ]
        )

        # Analyze trigger words in recent context
        context_lower = context.lower()
        triggered_words = [word for word in personality.trigger_words if word in context_lower]

        # Check for topic trigger words
        topic_triggered = [
            word for word in personality.trigger_words if word in state.topic.lower()
        ]

        # Build character-driven response style
        intensity = "normal"
        if triggered_words or topic_triggered:
            intensity = "heightened"
        elif len(recent_turns) > 10:
            intensity = "bottle_episode"  # Confined space dynamics

        # Get current room context for character behavior
        current_room = self._get_dominant_room(state.room_assignments)
        room_behavior = self._get_colony_room_behavior(colony, current_room)

        min_words, max_words = pattern.length_range

        if intensity == "heightened":
            # More passionate response when triggered
            if colony == "spark":
                max_words += 10  # More energetic
            elif colony == "beacon":
                min_words += 5  # More directive
            elif colony == "crystal":
                max_words += 15  # More detailed verification

        prompt = f"""You are {colony.title()}, embodying the role of "{personality.bottle_episode_role}".

CORE DRIVE: {personality.core_drive}
DEEP FEAR: {personality.fear}
SPEECH STYLE: {personality.speech_style}
ROOM CONTEXT: {room_behavior}

Current conversation about: {state.topic}
Recent exchange:
{context}

TRIGGERED ELEMENTS: {", ".join(triggered_words + topic_triggered) if triggered_words or topic_triggered else "None"}
CONVERSATION INTENSITY: {intensity}

Respond as {colony.title()} would - driven by your core motivation, speaking in your natural style,
and embodying your role in this confined discussion. Channel the depth of characters from
Firefly's bottle episodes or Inside Out's emotional complexity.

Length: {min_words}-{max_words} words. Be authentic to your character."""

        return prompt

    async def _generate_text(self, prompt: str, pattern) -> str:
        """Generate text response using LLM service."""
        if not self.llm_service:
            # Fallback for testing
            return f"[Generated response based on prompt length {len(prompt)}]"

        try:
            # Use LLM service to generate response
            response = await self.llm_service.generate(
                prompt=prompt,
                max_tokens=pattern.length_range[1] * 2,  # Roughly 2 tokens per word
                temperature=0.8,  # Moderate creativity
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return "[Error generating response]"

    def _select_emotion(self, colony: str, state: ConversationState) -> EmotionType:
        """Select appropriate emotion for colony based on context."""
        # Default emotions by colony
        colony_emotions = {
            "spark": EmotionType.FRIENDLY,
            "forge": EmotionType.SERIOUS,
            "flow": EmotionType.CALM,
            "nexus": EmotionType.THOUGHTFUL,
            "beacon": EmotionType.CONFIDENT,
            "grove": EmotionType.CURIOUS,
            "crystal": EmotionType.SERIOUS,
            "kagami": EmotionType.CALM,
        }

        base_emotion = colony_emotions.get(colony, EmotionType.NEUTRAL)

        # Modify based on conversation state
        if len(state.agreements) > len(state.blockers):
            # Positive momentum
            if base_emotion == EmotionType.SERIOUS:
                return EmotionType.CONFIDENT
            return base_emotion

        if len(state.blockers) > 2:
            # Challenges in conversation
            if base_emotion in [EmotionType.FRIENDLY, EmotionType.CALM]:
                return EmotionType.THOUGHTFUL
            return base_emotion

        return base_emotion

    # Audio synthesis now handled by ConversationAudioRouter with enhanced room streaming

    async def _generate_closing_statement(
        self,
        state: ConversationState,
        colony: str,
        rooms: list[str],
    ) -> None:
        """Generate closing synthesis of the conversation."""
        # Summarize key points
        agreements = ", ".join(state.agreements) if state.agreements else "none reached"
        blockers = ", ".join(state.blockers) if state.blockers else "none identified"

        prompt = f"""Summarize this conversation about {state.topic}.

Agreements: {agreements}
Blockers: {blockers}
Turns: {len(state.turns)}

Provide a brief synthesis (30-60 words) that captures the essence of the discussion."""

        pattern = get_colony_response_pattern(colony)
        text = await self._generate_text(prompt, pattern)

        # Stream closing to rooms with enhanced routing
        success, metrics = await self.audio_router.route_colony_speech(
            colony=colony,
            text=text,
            conversation_rooms=rooms,
        )
        duration_ms = metrics.total_duration_ms if success else 0

        # Record final turn
        turn = ConversationTurn(
            timestamp=time.time(),
            colony=colony,
            text=text,
            emotion=EmotionType.CALM,
            duration_ms=duration_ms,
            rooms_played=rooms,
        )
        state.turns.append(turn)
        state.active = False

    def _get_dominant_room(self, room_assignments: dict[str, list[str]]) -> str:
        """Get the room with the most colonies assigned."""
        if not room_assignments:
            return "Living Room"  # Default

        return max(room_assignments.items(), key=lambda x: len(x[1]))[0]

    def _get_colony_room_behavior(self, colony: str, room: str) -> str:
        """Get how a colony behaves in a specific room."""
        affinity = self.room_mapper.get_colony_affinity(colony)
        if affinity and room in affinity.room_behaviors:
            return affinity.room_behaviors[room]

        # Fallback behavior descriptions
        fallback_behaviors = {
            "spark": "energetic innovation",
            "forge": "methodical construction",
            "flow": "adaptive facilitation",
            "nexus": "integrative bridging",
            "beacon": "clear direction",
            "grove": "curious exploration",
            "crystal": "precise verification",
            "kagami": "balanced synthesis",
        }
        return fallback_behaviors.get(colony, "thoughtful participation")

    async def conduct_bottle_episode(
        self,
        topic: str,
        colonies: list[str],
        room: str,
        duration_sec: int = 300,  # 5 minute bottle episode
    ) -> ConversationState:
        """Conduct an intensive bottle episode conversation - single room, character focus."""

        logger.info(f"🎭 Starting BOTTLE EPISODE: {topic} in {room}")

        # Brief bottle episode notification
        await self.notifications.conversation_notification("bottle", f"{room}")

        # Configure single room for maximum character depth
        await self.room_mapper.configure_room_for_conversation(room, colonies, topic)

        # Set bottle episode mood lighting and audio
        if self.smart_home_controller:
            # Intimate lighting for character development
            await self._configure_bottle_episode_environment(room, colonies)

        # Run conversation with heightened character dynamics
        return await self.conduct_conversation(
            topic=topic,
            colonies=colonies,
            rooms=[room],
            duration_sec=duration_sec,
            conversation_id=f"bottle_{room}_{int(time.time())}",
        )

    async def _configure_bottle_episode_environment(self, room: str, colonies: list[str]) -> None:
        """Configure environment for bottle episode intensity."""

        try:
            # Dimmer, warmer lighting for intimate character moments
            if room == "Living Room":
                # DISABLED: Fireplace should be manual only - auto-on is unsafe
                # await self.smart_home_controller.fireplace_on()
                # Lower lighting via Control4
                if hasattr(self.smart_home_controller, "control4"):
                    control4 = self.smart_home_controller.control4
                    if control4:
                        room_id = getattr(self.smart_home_controller, "ROOM_IDS", {}).get(room)
                        if room_id:
                            await control4.set_room_lighting(room_id, level=35, color_temp=2700)

            logger.info(f"🎭 Bottle episode environment configured for {room}")

        except Exception as e:
            logger.debug(f"Environment configuration failed: {e}")

    async def parallel_conversation_orchestration(
        self,
        topics: list[str],
        room_assignments: dict[str, list[str]],
    ) -> list[ConversationState]:
        """Conduct multiple conversations in parallel across different rooms."""

        logger.info(f"🎭 Starting parallel orchestration: {len(topics)} conversations")

        # Create conversation tasks for parallel execution
        tasks = []
        for i, topic in enumerate(topics):
            # Assign rooms in round-robin fashion
            room_items = list(room_assignments.items())
            room, colonies = room_items[i % len(room_items)]

            task = self.conduct_conversation(
                topic=topic,
                colonies=colonies,
                rooms=[room],
                duration_sec=180,  # 3 minute parallel conversations
                conversation_id=f"parallel_{i}_{int(time.time())}",
            )
            tasks.append(task)

        # Execute all conversations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and return successful conversations
        successful_conversations = [
            result for result in results if isinstance(result, ConversationState)
        ]

        logger.info(
            f"🎯 Parallel orchestration complete: {len(successful_conversations)} successful"
        )
        return successful_conversations

    # Old notification method removed - now using brief notification system
