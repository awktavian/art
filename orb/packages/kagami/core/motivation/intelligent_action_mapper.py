"""Intelligent Action Mapper — LLM-Primary with Pure Semantic Fallback.

ARCHITECTURE (Dec 30, 2025 — HARDENED, NO KEYWORDS):
=====================================================
Primary: LLM reasoning for goal → action mapping
Fallback: SemanticMatcher classification ONLY (no keywords, no regex, no heuristics)

Philosophy: Real intelligence when possible, semantic intelligence when not.
The system remains FUNCTIONAL and SMART even without LLM.

CRITICAL: NO keyword matching. NO regex patterns. ONLY semantic embeddings.

Physical Action Support:
- Detects physical intent via semantic similarity to action exemplars
- Routes to PhysicalPolicySpace for execution
- Physical actions are first-class citizens alongside digital
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.motivation.physical_policy_space import PhysicalPolicySpace

logger = logging.getLogger(__name__)


# Input sanitization patterns for LLM prompt injection prevention
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"disregard\s+(previous|above|all)",
    r"forget\s+(everything|all|previous)",
    r"you\s+are\s+now\s+(?:a|an)",
    r"new\s+instructions:",
    r"system\s*:",
    r"<\|.*?\|>",  # Special tokens
    r"\[\[.*?\]\]",  # Bracket patterns
    r"```.*?system",  # Code block injection
    r"act\s+as\s+(?:a|an|if)",
    r"pretend\s+(?:you|to)",
    r"roleplay\s+as",
]

INJECTION_DETECTOR = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE | re.DOTALL)


def sanitize_goal_input(goal: str, max_length: int = 500) -> tuple[str, bool]:
    """Sanitize goal input for LLM prompt.

    Args:
        goal: Raw goal string
        max_length: Maximum allowed length

    Returns:
        Tuple of (sanitized_goal, was_modified)
    """
    original = goal
    was_modified = False

    # 1. Length limit
    if len(goal) > max_length:
        goal = goal[:max_length] + "..."
        was_modified = True

    # 2. Check for prompt injection patterns
    if INJECTION_DETECTOR.search(goal):
        logger.warning(f"⚠️ Potential prompt injection detected in goal: {goal[:100]}...")
        goal = INJECTION_DETECTOR.sub("[REDACTED]", goal)
        was_modified = True

    # 3. Escape special characters that could affect prompt structure
    goal = goal.replace('"""', "'''")
    goal = goal.replace("```", "'''")

    # 4. Remove null bytes and control characters
    goal = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", goal)

    # 5. Normalize whitespace
    goal = re.sub(r"\s+", " ", goal).strip()

    if goal != original:
        was_modified = True

    return goal, was_modified


def sanitize_context(context: dict[str, Any], max_depth: int = 3) -> dict[str, Any]:
    """Sanitize context dict for LLM prompt.

    Args:
        context: Raw context dict
        max_depth: Maximum nesting depth

    Returns:
        Sanitized context
    """

    def _sanitize_value(value: Any, depth: int = 0) -> Any:
        if depth > max_depth:
            return "[TRUNCATED]"

        if isinstance(value, str):
            sanitized, _ = sanitize_goal_input(value, max_length=200)
            return sanitized
        elif isinstance(value, dict):
            return {k: _sanitize_value(v, depth + 1) for k, v in list(value.items())[:20]}
        elif isinstance(value, (list, tuple)):
            return [_sanitize_value(v, depth + 1) for v in value[:10]]
        elif isinstance(value, (int, float, bool, type(None))):
            return value
        else:
            return str(value)[:100]

    return _sanitize_value(context)


# Semantic action categories with exemplars for DIGITAL actions
SEMANTIC_ACTION_EXEMPLARS = {
    "research": {
        "app": "research",
        "action": "research.web",
        "exemplars": [
            "find information about a topic",
            "research papers on machine learning",
            "explore the topic of quantum computing",
            "investigate how neural networks work",
            "learn about distributed systems",
            "discover patterns in data",
            "study the relationship between variables",
            "what is the best approach for this problem",
            "how does this algorithm work",
            "why does this behavior occur",
        ],
    },
    "analyze": {
        "app": "orchestrator",
        "action": "analyze",
        "exemplars": [
            "analyze performance of the system",
            "diagnose issues with the code",
            "profile the system bottlenecks",
            "benchmark against baseline",
            "measure the impact of changes",
            "debug the problem in the code",
            "identify bottlenecks in performance",
            "examine the error patterns",
            "check for memory leaks",
        ],
    },
    "optimize": {
        "app": "orchestrator",
        "action": "optimize",
        "exemplars": [
            "improve performance of the function",
            "optimize the code for speed",
            "reduce latency in the API",
            "speed up the test suite",
            "enhance efficiency of the algorithm",
            "fix slow operations",
            "make this faster",
            "reduce memory usage",
        ],
    },
    "learn": {
        "app": "orchestrator",
        "action": "learn",
        "exemplars": [
            "learn from past mistakes",
            "train the model on new data",
            "adapt to changing conditions",
            "evolve the approach based on feedback",
            "find patterns in behavior",
            "improve based on experience",
        ],
    },
    "plan": {
        "app": "planner",
        "action": "plan.create",
        "exemplars": [
            "create a roadmap for the project",
            "plan the implementation steps",
            "design the architecture",
            "strategize the approach",
            "outline the steps needed",
            "develop a timeline",
            "organize the milestones",
        ],
    },
    "implement": {
        "app": "builder",
        "action": "implement",
        "exemplars": [
            "build a new feature",
            "implement the functionality",
            "write code for the module",
            "create the component",
            "add support for the format",
            "fix the bug in the code",
            "repair the broken test",
            "patch the security issue",
        ],
    },
    "generate": {
        "app": "forge",
        "action": "forge.generate",
        "exemplars": [
            "generate content for the page",
            "render the visualization",
            "create a new design",
            "produce the report",
            "synthesize the summary",
        ],
    },
}

# Semantic action categories for PHYSICAL/SMARTHOME actions
SEMANTIC_PHYSICAL_EXEMPLARS = {
    "climate_comfort": {
        "app": "smarthome",
        "action": "climate.comfort",
        "exemplars": [
            "make it comfortable in here",
            "adjust the temperature for comfort",
            "set comfortable temperature",
            "optimize the environment",
        ],
    },
    "climate_heat": {
        "app": "smarthome",
        "action": "climate.heat",
        "exemplars": [
            "make it warmer",
            "turn up the heat",
            "increase the temperature",
            "heat the room",
            "it's too cold",
        ],
    },
    "climate_cool": {
        "app": "smarthome",
        "action": "climate.cool",
        "exemplars": [
            "make it cooler",
            "turn on the AC",
            "decrease the temperature",
            "cool down the room",
            "it's too hot",
        ],
    },
    "lights_focus": {
        "app": "smarthome",
        "action": "lights.focus",
        "exemplars": [
            "focus mode lighting",
            "work lighting setup",
            "bright lights for concentration",
            "I need to focus",
            "study lighting",
        ],
    },
    "lights_relax": {
        "app": "smarthome",
        "action": "lights.relax",
        "exemplars": [
            "relaxation lighting",
            "dim the lights for relaxing",
            "cozy atmosphere",
            "wind down lighting",
            "evening mood",
        ],
    },
    "lights_bright": {
        "app": "smarthome",
        "action": "lights.bright",
        "exemplars": [
            "make it brighter",
            "turn up the lights",
            "full brightness",
            "maximum light",
            "I can't see",
        ],
    },
    "lights_dim": {
        "app": "smarthome",
        "action": "lights.dim",
        "exemplars": [
            "dim the lights",
            "lower the brightness",
            "soft lighting",
            "ambient light",
            "reduce brightness",
        ],
    },
    "scene_movie": {
        "app": "smarthome",
        "action": "scene.movie",
        "exemplars": [
            "movie mode",
            "watch a movie",
            "cinema setup",
            "TV time",
            "movie night",
            "set up for watching",
        ],
    },
    "audio_play": {
        "app": "smarthome",
        "action": "audio.play",
        "exemplars": [
            "play music",
            "start a playlist",
            "play some tunes",
            "audio on",
            "listen to music",
            "put on some music",
        ],
    },
    "audio_announce": {
        "app": "smarthome",
        "action": "audio.announce",
        "exemplars": [
            "make an announcement",
            "announce to the house",
            "broadcast a message",
            "tell everyone",
            "speak to all rooms",
        ],
    },
    "security_lock": {
        "app": "smarthome",
        "action": "security.lock_all",
        "exemplars": [
            "lock everything",
            "secure the house",
            "lock all doors",
            "safety mode",
            "secure the doors",
        ],
    },
    "scene_goodnight": {
        "app": "smarthome",
        "action": "scene.goodnight",
        "exemplars": [
            "good night mode",
            "bedtime setup",
            "going to sleep",
            "night mode",
            "prepare for bed",
        ],
    },
    "tesla_precondition": {
        "app": "smarthome",
        "action": "tesla.precondition",
        "exemplars": [
            "warm up the car",
            "precondition the vehicle",
            "prepare the Tesla",
            "start car climate",
            "get the car ready",
        ],
    },
    "shades_open": {
        "app": "smarthome",
        "action": "shades.open",
        "exemplars": [
            "open the blinds",
            "let in light",
            "raise the shades",
            "natural light please",
            "open the curtains",
        ],
    },
    "shades_close": {
        "app": "smarthome",
        "action": "shades.close",
        "exemplars": [
            "close the blinds",
            "block the sun",
            "lower the shades",
            "privacy mode",
            "close the curtains",
        ],
    },
}


class IntelligentActionMapper:
    """Map goals to actions using LLM reasoning with pure semantic fallback.

    PURE SEMANTIC ARCHITECTURE (NO KEYWORDS):
    =========================================
    1. Try LLM reasoning (best intelligence)
    2. On LLM failure → SemanticMatcher classification (semantic intelligence)
    3. On SemanticMatcher failure → Drive-based default (safe fallback)
    4. Never return None — always provide actionable mapping

    CRITICAL: NO keyword matching. NO regex patterns. ONLY semantic embeddings.

    Physical Action Support:
    - Detects physical intent via semantic similarity
    - Routes to PhysicalPolicySpace for execution
    """

    def __init__(self) -> None:
        self._llm_service = None
        self._semantic_matcher = None
        self._physical_policy_space: PhysicalPolicySpace | None = None
        self._cache: dict[str, tuple[str, str]] = {}  # goal_hash → (app, action)

        # Tracking
        self._llm_successes = 0
        self._semantic_successes = 0
        self._default_fallbacks = 0
        self._physical_mappings = 0
        self._total_mappings = 0
        self._sanitization_count = 0
        self._categories_initialized = False

    async def _ensure_llm(self) -> Any | None:
        """Lazy load LLM service."""
        if self._llm_service is None:
            try:
                from kagami.core.services.llm import get_llm_service

                self._llm_service = get_llm_service()
            except Exception as e:
                logger.debug(f"LLM service unavailable: {e}")
                return None

        # Check if models are ready
        if self._llm_service:
            if not self._llm_service.is_initialized or not self._llm_service.are_models_ready:
                logger.debug("LLM models not ready, using semantic fallback")
                return None

        return self._llm_service

    async def _ensure_semantic_matcher(self) -> Any | None:
        """Lazy load SemanticMatcher and initialize categories."""
        if self._semantic_matcher is None:
            try:
                from kagami.core.integrations.semantic_matcher import get_semantic_matcher

                self._semantic_matcher = get_semantic_matcher()
            except Exception as e:
                logger.warning(f"SemanticMatcher unavailable: {e}")
                return None

        # Initialize categories if not done
        if not self._categories_initialized and self._semantic_matcher:
            try:
                # Add digital action categories
                for category, data in SEMANTIC_ACTION_EXEMPLARS.items():
                    self._semantic_matcher.add_category(f"action_{category}", data["exemplars"])

                # Add physical action categories
                for category, data in SEMANTIC_PHYSICAL_EXEMPLARS.items():
                    self._semantic_matcher.add_category(f"physical_{category}", data["exemplars"])

                self._categories_initialized = True
                logger.info("✅ IntelligentActionMapper semantic categories initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic categories: {e}")

        return self._semantic_matcher

    async def _ensure_physical_policy_space(self) -> PhysicalPolicySpace | None:
        """Lazy load PhysicalPolicySpace."""
        if self._physical_policy_space is None:
            try:
                from kagami.core.motivation.physical_policy_space import get_physical_policy_space

                self._physical_policy_space = get_physical_policy_space()
            except Exception as e:
                logger.debug(f"PhysicalPolicySpace unavailable: {e}")
                return None
        return self._physical_policy_space

    async def map_goal_to_action(
        self, goal: str, drive: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Map goal to (app, action) using LLM with pure semantic fallback.

        Args:
            goal: The goal description
            drive: The motivating drive (curiosity, competence, etc.)
            context: Additional context

        Returns:
            Dict with keys:
                - app: Application to use
                - action: Action to take
                - method: "llm" | "semantic" | "default"
                - confidence: Confidence score (if semantic)
        """
        self._total_mappings += 1
        goal_hash = hash(goal)

        # 1. CHECK CACHE
        if goal_hash in self._cache:
            app, action = self._cache[goal_hash]
            return {"app": app, "action": action, "method": "cache"}

        # 2. TRY LLM (best intelligence)
        llm_mapping = await self._try_llm_mapping(goal, drive, context)
        if llm_mapping:
            self._llm_successes += 1
            self._cache[goal_hash] = (llm_mapping["app"], llm_mapping["action"])
            if llm_mapping.get("app") == "smarthome":
                self._physical_mappings += 1
            return llm_mapping

        # 3. TRY SEMANTIC CLASSIFICATION (pure semantic, no keywords)
        semantic_mapping = await self._try_semantic_mapping(goal, drive)
        if semantic_mapping:
            self._semantic_successes += 1
            self._cache[goal_hash] = (semantic_mapping["app"], semantic_mapping["action"])
            if semantic_mapping.get("app") == "smarthome":
                self._physical_mappings += 1
            return semantic_mapping

        # 4. SAFE DEFAULT (drive-based, no keywords)
        self._default_fallbacks += 1
        default_mapping = self._get_drive_default(drive)
        logger.debug(
            f"🔄 Default mapping for '{goal[:40]}...' → {default_mapping['app']}.{default_mapping['action']}"
        )
        return default_mapping

    async def _try_llm_mapping(
        self, goal: str, drive: str, context: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Try LLM-based mapping with input sanitization. Returns None on failure."""
        llm = await self._ensure_llm()
        if not llm:
            return None

        # SANITIZE INPUTS (prompt injection prevention)
        sanitized_goal, goal_modified = sanitize_goal_input(goal)
        sanitized_context = sanitize_context(context)

        if goal_modified:
            logger.warning(f"Goal input was sanitized for LLM prompt: {goal[:50]}...")
            self._sanitization_count += 1

        try:
            prompt = f"""You are Kagami's routing system. Determine the best app and action for this autonomous goal.

Goal: "{sanitized_goal}"
Drive: {drive}
Context: {sanitized_context}

Available apps and their capabilities:

DIGITAL APPS:
- research: Web search, knowledge discovery, information gathering
  Actions: research.web, research.discover

- orchestrator: System analysis, optimization, performance improvement
  Actions: analyze, optimize, learn

- planner: Strategic planning, task breakdown, scheduling
  Actions: plan.create, strategize

- forge: Content generation (3D, images, stories, code)
  Actions: forge.generate

- builder: Code construction, implementation
  Actions: build, implement

PHYSICAL/SMARTHOME APPS:
- smarthome: Physical home control, lighting, climate, scenes
  Actions:
    - climate.comfort, climate.heat, climate.cool (temperature)
    - lights.focus, lights.relax, lights.bright, lights.dim (lighting)
    - scene.movie, scene.goodnight (scenes)
    - audio.play, audio.announce (audio/announcements)
    - security.lock_all (locks)
    - tesla.precondition (vehicle)
    - shades.open, shades.close (blinds/shades)

Analyze the goal and determine:
1. Which app best handles this goal (digital OR physical)
2. Which action within that app is most appropriate
3. Brief reasoning

Format your response as:
app: <app_name>
action: <action_name>
reasoning: <one sentence why>

Example 1:
Goal: "Research the relationship between G₂ structure and integration quality"
app: research
action: research.web
reasoning: Requires web search for academic papers and theory validation

Example 2:
Goal: "Make the living room comfortable for movie night"
app: smarthome
action: scene.movie
reasoning: Physical action to set up movie mode with appropriate lighting and audio

Now analyze the given goal:"""

            from kagami.core.services.llm import TaskType

            response = await llm.generate(
                prompt=prompt,
                app_name="intelligent_action_mapper",
                task_type=TaskType.REASONING,
                max_tokens=150,
                temperature=0.3,
            )

            mapping = self._parse_llm_response(str(response))
            if mapping:
                mapping["method"] = "llm"
                # LOGSPAM FIX (Dec 30, 2025): Demoted to DEBUG - this fires every 30-60s
                logger.debug(
                    f"🧠 LLM mapped '{goal[:40]}...' → {mapping['app']}.{mapping['action']}"
                )
                return mapping

        except Exception as e:
            logger.debug(f"LLM mapping failed: {e}")

        return None

    async def _try_semantic_mapping(self, goal: str, drive: str) -> dict[str, Any] | None:
        """Try SemanticMatcher-based mapping. NO KEYWORDS. Returns None on failure."""
        matcher = await self._ensure_semantic_matcher()
        if not matcher:
            return None

        try:
            # Find best matching category across all (digital + physical)
            best_match = None
            best_score = 0.0
            best_type = None  # "digital" or "physical"

            # Check digital categories
            for category, data in SEMANTIC_ACTION_EXEMPLARS.items():
                sim = matcher.similarity(goal, f"action_{category}")
                if isinstance(sim, (int, float)) and sim > best_score:
                    best_score = float(sim)
                    best_match = data
                    best_type = "digital"

            # Check physical categories
            for category, data in SEMANTIC_PHYSICAL_EXEMPLARS.items():
                sim = matcher.similarity(goal, f"physical_{category}")
                if isinstance(sim, (int, float)) and sim > best_score:
                    best_score = float(sim)
                    best_match = data
                    best_type = "physical"

            # Require minimum confidence
            if best_match and best_score > 0.3:
                mapping = {
                    "app": best_match["app"],
                    "action": best_match["action"],
                    "method": "semantic",
                    "confidence": best_score,
                    "type": best_type,
                }
                # LOGSPAM FIX (Dec 30, 2025): Demoted to DEBUG - this fires every 30-60s
                logger.debug(
                    f"🎯 Semantic mapped '{goal[:40]}...' → "
                    f"{mapping['app']}.{mapping['action']} (confidence={best_score:.2f})"
                )
                return mapping

            logger.debug(f"Semantic match below threshold: {best_score:.2f} for '{goal[:40]}...'")

        except Exception as e:
            logger.debug(f"Semantic mapping failed: {e}")

        return None

    def _get_drive_default(self, drive: str) -> dict[str, Any]:
        """Get safe default action based on drive. NO KEYWORDS."""
        # Map drives to sensible default actions
        drive_defaults = {
            "curiosity": ("research", "research.web"),
            "competence": ("orchestrator", "analyze"),
            "autonomy": ("orchestrator", "learn"),
            "relatedness": ("planner", "plan.create"),
            "purpose": ("orchestrator", "analyze"),
        }

        app, action = drive_defaults.get(drive.lower(), ("orchestrator", "analyze"))
        return {
            "app": app,
            "action": action,
            "method": "default",
            "drive": drive,
        }

    def _parse_llm_response(self, response: str) -> dict[str, Any] | None:
        """Parse LLM response to extract app/action mapping."""
        try:
            lines = response.strip().split("\n")
            result: dict[str, Any] = {}

            for line in lines:
                line = line.strip()
                if line.lower().startswith("app:"):
                    result["app"] = line.split(":", 1)[1].strip().lower()
                elif line.lower().startswith("action:"):
                    result["action"] = line.split(":", 1)[1].strip().lower()
                elif line.lower().startswith("reasoning:"):
                    result["reasoning"] = line.split(":", 1)[1].strip()

            if "app" in result and "action" in result:
                return result

        except Exception as e:
            logger.debug(f"Failed to parse LLM response: {e}")

        return None

    async def execute_physical_action(
        self, action: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a physical action via PhysicalPolicySpace.

        Args:
            action: The physical action (e.g., "scene.movie", "lights.focus")
            context: Optional context (room, message, etc.)

        Returns:
            Execution result
        """
        policy_space = await self._ensure_physical_policy_space()
        if not policy_space:
            return {"success": False, "error": "PhysicalPolicySpace unavailable"}

        result = await policy_space.execute("smarthome", action, context or {})
        return {
            "success": result.success,
            "action": result.action,
            "details": result.details,
            "error": result.error,
            "h_x": result.h_x,
        }

    def get_degradation_stats(self) -> dict[str, Any]:
        """Get statistics for monitoring. NO KEYWORDS IN STATS."""
        total = self._total_mappings or 1
        return {
            "total_mappings": self._total_mappings,
            "llm_successes": self._llm_successes,
            "llm_success_rate": self._llm_successes / total,
            "semantic_successes": self._semantic_successes,
            "semantic_success_rate": self._semantic_successes / total,
            "default_fallbacks": self._default_fallbacks,
            "default_fallback_rate": self._default_fallbacks / total,
            "physical_mappings": self._physical_mappings,
            "physical_mapping_rate": self._physical_mappings / total,
            "sanitization_events": self._sanitization_count,
            "sanitization_rate": self._sanitization_count / total,
            "cache_size": len(self._cache),
            "categories_initialized": self._categories_initialized,
            "health": "healthy"
            if self._llm_successes / total > 0.3 or self._semantic_successes / total > 0.3
            else "degraded",
        }


# Singleton
_intelligent_action_mapper: IntelligentActionMapper | None = None


def get_intelligent_action_mapper() -> IntelligentActionMapper:
    """Get global IntelligentActionMapper instance."""
    global _intelligent_action_mapper
    if _intelligent_action_mapper is None:
        _intelligent_action_mapper = IntelligentActionMapper()
    return _intelligent_action_mapper


def reset_intelligent_action_mapper() -> None:
    """Reset singleton (for testing)."""
    global _intelligent_action_mapper
    _intelligent_action_mapper = None


__all__ = [
    "SEMANTIC_ACTION_EXEMPLARS",
    "SEMANTIC_PHYSICAL_EXEMPLARS",
    "IntelligentActionMapper",
    "get_intelligent_action_mapper",
    "reset_intelligent_action_mapper",
    "sanitize_context",
    "sanitize_goal_input",
]
