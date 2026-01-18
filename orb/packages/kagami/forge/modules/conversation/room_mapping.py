"""Smart Home Room Mapping for Colony Conversations.

Maps each colony to specific rooms, integrations, and devices based on their
personality traits and functional requirements. Creates optimal parallel
workflows for multi-room conversations.

Inspired by bottle episodes and character-driven narratives.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RoomProfile:
    """Profile of a smart home room with colony affinities."""

    room_name: str
    primary_colony: str  # Which colony "owns" this room
    secondary_colonies: list[str]  # Which colonies visit/collaborate here
    audio_zones: list[str]  # Audio output zones
    lighting_zones: list[str]  # Controllable lights
    climate_zone: str | None  # HVAC zone
    integrations: list[str]  # Available smart home integrations
    conversation_role: str  # Role in multi-colony discussions
    mood_lighting: dict[str, dict]  # Colony-specific lighting scenes


@dataclass
class ColonyRoomAffinity:
    """How each colony relates to different rooms."""

    primary_rooms: list[str]  # Rooms where this colony is strongest
    secondary_rooms: list[str]  # Rooms where colony has influence
    avoid_rooms: list[str]  # Rooms where colony rarely speaks
    room_behaviors: dict[str, str]  # How colony behaves in each room


class SmartHomeRoomMapper:
    """Maps colonies to smart home rooms with parallel workflow optimization."""

    def __init__(self, smart_home_controller=None):
        self.controller = smart_home_controller
        self.room_profiles: dict[str, RoomProfile] = {}
        self.colony_affinities: dict[str, ColonyRoomAffinity] = {}
        self._initialize_room_profiles()
        self._initialize_colony_affinities()

    def _initialize_room_profiles(self) -> None:
        """Initialize comprehensive room profiles for 7331 W Green Lake Dr N."""

        self.room_profiles = {
            # FIRST FLOOR - Social & Gathering Spaces
            "Living Room": RoomProfile(
                room_name="Living Room",
                primary_colony="kagami",  # Central synthesis space
                secondary_colonies=["nexus", "beacon", "crystal"],
                audio_zones=["living_room_kef", "living_room_atmos"],
                lighting_zones=["living_room_main", "living_room_accent", "fireplace"],
                climate_zone="living_room",
                integrations=["denon", "lg_tv", "control4", "lutron", "fireplace"],
                conversation_role="primary assembly - all colonies gather here",
                mood_lighting={
                    "conversation": {"brightness": 70, "warmth": 3000, "color": "soft_white"},
                    "focus": {"brightness": 90, "warmth": 4000, "color": "daylight"},
                    "reflection": {"brightness": 40, "warmth": 2700, "color": "warm_amber"},
                },
            ),
            "Kitchen": RoomProfile(
                room_name="Kitchen",
                primary_colony="spark",  # Innovation & experimentation
                secondary_colonies=["flow", "grove"],
                audio_zones=["kitchen_ceiling", "kitchen_island"],
                lighting_zones=["kitchen_main", "kitchen_under_cabinet", "kitchen_island"],
                climate_zone="kitchen",
                integrations=["sub_zero", "wolf", "electrolux", "control4"],
                conversation_role="creative laboratory - rapid prototyping discussions",
                mood_lighting={
                    "creative": {"brightness": 85, "warmth": 4000, "color": "energetic_white"},
                    "cooking": {"brightness": 100, "warmth": 5000, "color": "task_bright"},
                    "gathering": {"brightness": 65, "warmth": 3000, "color": "social_warm"},
                },
            ),
            "Dining Room": RoomProfile(
                room_name="Dining Room",
                primary_colony="nexus",  # Connection & integration
                secondary_colonies=["beacon", "grove", "kagami"],
                audio_zones=["dining_room_ceiling"],
                lighting_zones=["dining_room_chandelier", "dining_room_accent"],
                climate_zone="dining_room",
                integrations=["control4", "lutron"],
                conversation_role="formal deliberation - structured discussions",
                mood_lighting={
                    "formal": {"brightness": 80, "warmth": 3000, "color": "elegant_white"},
                    "intimate": {"brightness": 45, "warmth": 2700, "color": "candlelight"},
                    "meeting": {"brightness": 90, "warmth": 4000, "color": "clear_white"},
                },
            ),
            # SECOND FLOOR - Work & Personal Spaces
            "Office": RoomProfile(
                room_name="Office",
                primary_colony="beacon",  # Command & control center
                secondary_colonies=["crystal", "forge"],
                audio_zones=["office_desk", "office_ceiling"],
                lighting_zones=["office_main", "office_desk", "office_accent"],
                climate_zone="office",
                integrations=["control4", "lutron", "apple_findmy"],
                conversation_role="command center - decision making and planning",
                mood_lighting={
                    "command": {"brightness": 95, "warmth": 5000, "color": "executive_bright"},
                    "focus": {"brightness": 85, "warmth": 4500, "color": "concentration_blue"},
                    "strategy": {"brightness": 75, "warmth": 3500, "color": "thinking_neutral"},
                },
            ),
            "Primary Suite": RoomProfile(
                room_name="Primary Suite",
                primary_colony="kagami",  # Personal reflection space
                secondary_colonies=["flow", "grove"],
                audio_zones=["bedroom_ceiling", "bedroom_nightstand"],
                lighting_zones=["bedroom_main", "bedroom_accent", "bedroom_reading"],
                climate_zone="bedroom",
                integrations=["eight_sleep", "control4", "lutron"],
                conversation_role="private reflection - deep personal conversations",
                mood_lighting={
                    "reflection": {"brightness": 30, "warmth": 2500, "color": "meditation_amber"},
                    "morning": {"brightness": 70, "warmth": 4000, "color": "sunrise_white"},
                    "evening": {"brightness": 20, "warmth": 2200, "color": "sunset_red"},
                },
            ),
            # BASEMENT - Activity & Technical Spaces
            "Game Room": RoomProfile(
                room_name="Game Room",
                primary_colony="spark",  # Play & creativity
                secondary_colonies=["flow", "grove"],
                audio_zones=["game_room_surround", "game_room_ceiling"],
                lighting_zones=["game_room_main", "game_room_accent", "game_room_gaming"],
                climate_zone="basement",
                integrations=["samsung_tv", "control4", "oelo"],
                conversation_role="creative playground - experimental conversations",
                mood_lighting={
                    "gaming": {"brightness": 60, "warmth": 6500, "color": "gaming_rgb"},
                    "social": {"brightness": 75, "warmth": 3500, "color": "party_dynamic"},
                    "creative": {"brightness": 80, "warmth": 4000, "color": "inspiration_cool"},
                },
            ),
            "Gym": RoomProfile(
                room_name="Gym",
                primary_colony="flow",  # Movement & adaptation
                secondary_colonies=["spark", "beacon"],
                audio_zones=["gym_ceiling", "gym_motivation"],
                lighting_zones=["gym_main", "gym_mirror"],
                climate_zone="basement",
                integrations=["control4", "oelo"],
                conversation_role="dynamic movement - active problem-solving",
                mood_lighting={
                    "energy": {"brightness": 100, "warmth": 6000, "color": "motivation_blue"},
                    "flow": {"brightness": 85, "warmth": 4500, "color": "movement_green"},
                    "recovery": {"brightness": 50, "warmth": 3000, "color": "calm_purple"},
                },
            ),
            "Rack Room": RoomProfile(
                room_name="Rack Room",
                primary_colony="forge",  # Technical infrastructure
                secondary_colonies=["crystal", "beacon"],
                audio_zones=["rack_room_ceiling"],
                lighting_zones=["rack_room_main", "rack_room_equipment"],
                climate_zone="basement",
                integrations=["unifi", "control4", "environmental"],
                conversation_role="technical forge - system architecture discussions",
                mood_lighting={
                    "technical": {"brightness": 90, "warmth": 5000, "color": "server_white"},
                    "maintenance": {"brightness": 100, "warmth": 6500, "color": "diagnostic_blue"},
                    "monitoring": {"brightness": 40, "warmth": 2700, "color": "status_green"},
                },
            ),
            # SPECIALTY SPACES
            "Library": RoomProfile(
                room_name="Library",
                primary_colony="grove",  # Knowledge & exploration
                secondary_colonies=["nexus", "crystal"],
                audio_zones=["library_quiet", "library_reading"],
                lighting_zones=["library_main", "library_reading", "library_shelves"],
                climate_zone="library",
                integrations=["control4", "lutron"],
                conversation_role="wisdom sanctuary - deep knowledge exploration",
                mood_lighting={
                    "study": {"brightness": 85, "warmth": 4000, "color": "scholarly_white"},
                    "reading": {"brightness": 60, "warmth": 3000, "color": "book_amber"},
                    "contemplation": {"brightness": 40, "warmth": 2500, "color": "wisdom_gold"},
                },
            ),
            "Workshop": RoomProfile(
                room_name="Workshop",
                primary_colony="forge",  # Creation & building
                secondary_colonies=["spark", "crystal"],
                audio_zones=["workshop_ceiling"],
                lighting_zones=["workshop_main", "workshop_task", "workshop_safety"],
                climate_zone="workshop",
                integrations=["control4", "safety_systems"],
                conversation_role="creation space - hands-on problem solving",
                mood_lighting={
                    "building": {"brightness": 100, "warmth": 5500, "color": "work_bright"},
                    "precision": {"brightness": 95, "warmth": 6000, "color": "detail_cool"},
                    "safety": {"brightness": 85, "warmth": 4000, "color": "alert_yellow"},
                },
            ),
        }

    def _initialize_colony_affinities(self) -> None:
        """Define how each colony relates to different rooms."""

        self.colony_affinities = {
            "spark": ColonyRoomAffinity(
                primary_rooms=["Kitchen", "Game Room"],
                secondary_rooms=["Living Room", "Workshop", "Gym"],
                avoid_rooms=["Library", "Rack Room"],
                room_behaviors={
                    "Kitchen": "rapid-fire cooking innovation",
                    "Game Room": "experimental play strategies",
                    "Living Room": "energetic social catalyst",
                    "Workshop": "creative building bursts",
                    "Gym": "high-energy motivation",
                },
            ),
            "forge": ColonyRoomAffinity(
                primary_rooms=["Workshop", "Rack Room", "Office"],
                secondary_rooms=["Kitchen", "Living Room"],
                avoid_rooms=["Game Room"],
                room_behaviors={
                    "Workshop": "methodical construction planning",
                    "Rack Room": "systematic infrastructure design",
                    "Office": "detailed project management",
                    "Kitchen": "precise cooking engineering",
                    "Living Room": "structural conversation building",
                },
            ),
            "flow": ColonyRoomAffinity(
                primary_rooms=["Gym", "Primary Suite"],
                secondary_rooms=["Kitchen", "Living Room", "Game Room"],
                avoid_rooms=["Rack Room"],
                room_behaviors={
                    "Gym": "adaptive movement philosophy",
                    "Primary Suite": "gentle personal guidance",
                    "Kitchen": "flexible cooking adaptation",
                    "Living Room": "smooth social transitions",
                    "Game Room": "fluid creative expression",
                },
            ),
            "nexus": ColonyRoomAffinity(
                primary_rooms=["Dining Room", "Living Room"],
                secondary_rooms=["Library", "Office", "Primary Suite"],
                avoid_rooms=["Rack Room", "Workshop"],
                room_behaviors={
                    "Dining Room": "formal connection facilitation",
                    "Living Room": "central social integration",
                    "Library": "knowledge connection weaving",
                    "Office": "strategic relationship building",
                    "Primary Suite": "intimate understanding bridge",
                },
            ),
            "beacon": ColonyRoomAffinity(
                primary_rooms=["Office", "Living Room"],
                secondary_rooms=["Dining Room", "Gym", "Kitchen"],
                avoid_rooms=["Game Room"],
                room_behaviors={
                    "Office": "executive command decisions",
                    "Living Room": "group leadership direction",
                    "Dining Room": "formal meeting guidance",
                    "Gym": "fitness goal setting",
                    "Kitchen": "meal planning efficiency",
                },
            ),
            "grove": ColonyRoomAffinity(
                primary_rooms=["Library", "Primary Suite"],
                secondary_rooms=["Living Room", "Kitchen", "Game Room"],
                avoid_rooms=["Rack Room"],
                room_behaviors={
                    "Library": "deep knowledge exploration",
                    "Primary Suite": "personal growth inquiry",
                    "Living Room": "philosophical questioning",
                    "Kitchen": "culinary science wonder",
                    "Game Room": "creative learning experiments",
                },
            ),
            "crystal": ColonyRoomAffinity(
                primary_rooms=["Office", "Rack Room"],
                secondary_rooms=["Library", "Workshop", "Living Room"],
                avoid_rooms=["Game Room"],
                room_behaviors={
                    "Office": "quality assurance checking",
                    "Rack Room": "system verification protocols",
                    "Library": "fact checking and validation",
                    "Workshop": "precision quality control",
                    "Living Room": "conversation accuracy monitoring",
                },
            ),
            "kagami": ColonyRoomAffinity(
                primary_rooms=["Living Room", "Primary Suite"],
                secondary_rooms=["Dining Room", "Office"],
                avoid_rooms=[],
                room_behaviors={
                    "Living Room": "central synthesis facilitation",
                    "Primary Suite": "personal reflection mirroring",
                    "Dining Room": "balanced perspective integration",
                    "Office": "unified decision reflection",
                },
            ),
        }

    async def get_optimal_room_assignment(
        self,
        topic: str,
        colonies: list[str],
        user_preference: str | None = None,
    ) -> dict[str, list[str]]:
        """Get optimal room assignments for a conversation topic."""

        # If user specified a room, prioritize that
        if user_preference and user_preference in self.room_profiles:
            return {user_preference: colonies}

        # Analyze topic to determine best rooms
        topic_keywords = topic.lower().split()
        room_scores = {}

        for room_name, profile in self.room_profiles.items():
            score = 0

            # Score based on colony affinities
            for colony in colonies:
                affinity = self.colony_affinities.get(colony)
                if affinity:
                    if room_name in affinity.primary_rooms:
                        score += 3
                    elif room_name in affinity.secondary_rooms:
                        score += 1
                    elif room_name in affinity.avoid_rooms:
                        score -= 2

            # Score based on conversation role relevance
            role_keywords = profile.conversation_role.lower().split()
            for keyword in topic_keywords:
                if keyword in role_keywords:
                    score += 2

            room_scores[room_name] = score

        # Select top rooms for multi-room conversations
        sorted_rooms = sorted(room_scores.items(), key=lambda x: x[1], reverse=True)

        if len(colonies) <= 3:
            # Small conversations - single room
            best_room = sorted_rooms[0][0]
            return {best_room: colonies}
        else:
            # Large conversations - multi-room with primary/secondary
            primary_room = sorted_rooms[0][0]
            secondary_room = sorted_rooms[1][0] if len(sorted_rooms) > 1 else primary_room

            # Split colonies between rooms based on affinity
            primary_colonies = []
            secondary_colonies = []

            for colony in colonies:
                affinity = self.colony_affinities.get(colony)
                if affinity and primary_room in affinity.primary_rooms:
                    primary_colonies.append(colony)
                else:
                    secondary_colonies.append(colony)

            # Ensure at least one colony per room
            if not primary_colonies:
                primary_colonies = [colonies[0]]
                secondary_colonies = colonies[1:]
            if not secondary_colonies and len(colonies) > 1:
                secondary_colonies = [primary_colonies.pop()]

            result = {primary_room: primary_colonies}
            if secondary_colonies:
                result[secondary_room] = secondary_colonies

            return result

    async def configure_room_for_conversation(
        self,
        room_name: str,
        colonies: list[str],
        topic: str,
    ) -> dict[str, Any]:
        """Configure a room's environment for optimal conversation."""

        if room_name not in self.room_profiles:
            logger.warning(f"Unknown room: {room_name}")
            return {}

        profile = self.room_profiles[room_name]

        # Determine primary colony for this conversation
        primary_colony = profile.primary_colony
        for colony in colonies:
            affinity = self.colony_affinities.get(colony)
            if affinity and room_name in affinity.primary_rooms:
                primary_colony = colony
                break

        # Configure lighting for the conversation
        lighting_config = await self._configure_room_lighting(profile, primary_colony, topic)

        # Configure audio zones
        audio_config = await self._configure_room_audio(profile, colonies, topic)

        # Configure climate if needed
        climate_config = await self._configure_room_climate(profile, colonies, topic)

        return {
            "room": room_name,
            "primary_colony": primary_colony,
            "participating_colonies": colonies,
            "lighting": lighting_config,
            "audio": audio_config,
            "climate": climate_config,
            "conversation_role": profile.conversation_role,
        }

    async def _configure_room_lighting(
        self,
        profile: RoomProfile,
        primary_colony: str,
        topic: str,
    ) -> dict[str, Any]:
        """Configure lighting based on colony and topic."""

        # Determine mood based on topic and colony
        if "creative" in topic.lower() or "innovation" in topic.lower():
            mood = "creative"
        elif "focus" in topic.lower() or "analysis" in topic.lower():
            mood = "focus"
        elif "reflection" in topic.lower() or "personal" in topic.lower():
            mood = "reflection"
        else:
            mood = "conversation"  # Default

        # Get lighting settings for this mood
        if mood in profile.mood_lighting:
            lighting_settings = profile.mood_lighting[mood]
        else:
            lighting_settings = profile.mood_lighting.get(
                "conversation", {"brightness": 70, "warmth": 3000, "color": "soft_white"}
            )

        # Apply colony-specific modifications
        colony_lighting_mods = {
            "spark": {"brightness": +15, "warmth": +500},  # Brighter, cooler
            "forge": {"brightness": +10, "warmth": +200},  # Slightly brighter
            "flow": {"brightness": -5, "warmth": -200},  # Softer, warmer
            "nexus": {"brightness": 0, "warmth": 0},  # Balanced
            "beacon": {"brightness": +20, "warmth": +300},  # Bright and clear
            "grove": {"brightness": -10, "warmth": -300},  # Dimmer, warmer
            "crystal": {"brightness": +5, "warmth": +100},  # Clear and precise
            "kagami": {"brightness": 0, "warmth": 0},  # Perfect balance
        }

        mods = colony_lighting_mods.get(primary_colony, {"brightness": 0, "warmth": 0})

        final_brightness = max(10, min(100, lighting_settings["brightness"] + mods["brightness"]))
        final_warmth = max(2200, min(6500, lighting_settings["warmth"] + mods["warmth"]))

        return {
            "zones": profile.lighting_zones,
            "brightness": final_brightness,
            "color_temperature": final_warmth,
            "color": lighting_settings["color"],
            "mood": mood,
            "primary_colony": primary_colony,
        }

    async def _configure_room_audio(
        self,
        profile: RoomProfile,
        colonies: list[str],
        topic: str,
    ) -> dict[str, Any]:
        """Configure audio zones for conversation."""

        return {
            "zones": profile.audio_zones,
            "volume": 65,  # Base volume
            "participating_colonies": colonies,
            "spatial_audio": len(colonies) > 3,  # Enable spatial for larger groups
        }

    async def _configure_room_climate(
        self,
        profile: RoomProfile,
        colonies: list[str],
        topic: str,
    ) -> dict[str, Any]:
        """Configure climate for conversation comfort."""

        # Adjust temperature based on conversation intensity
        base_temp = 72  # Comfortable default

        if len(colonies) > 5:
            base_temp -= 1  # Cooler for large groups

        if "creative" in topic.lower() or "brainstorm" in topic.lower():
            base_temp += 1  # Slightly warmer for creativity

        return {
            "zone": profile.climate_zone,
            "temperature": base_temp,
            "humidity": 45,  # Comfortable humidity
        }

    def get_room_profile(self, room_name: str) -> RoomProfile | None:
        """Get detailed profile for a specific room."""
        return self.room_profiles.get(room_name)

    def get_colony_affinity(self, colony: str) -> ColonyRoomAffinity | None:
        """Get room affinity data for a specific colony."""
        return self.colony_affinities.get(colony)

    def get_available_rooms(self) -> list[str]:
        """Get list of all available rooms."""
        return list(self.room_profiles.keys())

    async def parallel_room_configuration(
        self,
        room_assignments: dict[str, list[str]],
        topic: str,
    ) -> dict[str, dict[str, Any]]:
        """Configure multiple rooms in parallel for optimal performance."""

        tasks = []
        for room_name, colonies in room_assignments.items():
            task = self.configure_room_for_conversation(room_name, colonies, topic)
            tasks.append(task)

        # Execute all room configurations in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        room_configs = {}
        for i, (room_name, colonies) in enumerate(room_assignments.items()):
            if i < len(results) and not isinstance(results[i], Exception):
                room_configs[room_name] = results[i]
            else:
                logger.error(
                    f"Failed to configure room {room_name}: {results[i] if i < len(results) else 'Unknown error'}"
                )
                room_configs[room_name] = {"error": "Configuration failed"}

        return room_configs
