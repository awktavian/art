"""
Enhanced Intent Parser (Objective, Identity‑aligned)

Purpose: Provide an intent parser with context and affect heuristics
without making claims about processing_state or subjective experience.
K os Identity: distributed system; evidence‑first; receipts and metrics.
"""

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami.core.schemas.schemas.intent_lang import ParsedLangV2, parse_intent_lang_v2
from kagami.core.schemas.schemas.intents import Intent, IntentVerb


class IntentEmotion(Enum):
    """The emotional coloring of an intent."""

    URGENT = "urgent"
    CURIOUS = "curious"
    FRUSTRATED = "frustrated"
    EXCITED = "excited"
    CALM = "calm"
    DETERMINED = "determined"
    PLAYFUL = "playful"


class IntentDepth(Enum):
    """The depth of understanding required."""

    SURFACE = "surface"
    SEMANTIC = "semantic"
    CONTEXTUAL = "contextual"
    EMPATHETIC = "empathetic"
    PHILOSOPHICAL = "philosophical"


@dataclass
class EnhancedIntent:
    """
    Enhanced intent representation with context, affect heuristics, and
    traceable signatures. Naming retained for compatibility; no claims
    about processing_state are made.
    """

    raw_input: str
    parsed: ParsedLangV2
    intent: Intent
    understanding: dict[str, Any] = field(default_factory=dict[str, Any])
    emotion: IntentEmotion = IntentEmotion.CALM
    depth: IntentDepth = IntentDepth.SEMANTIC
    purpose: str = ""
    implications: list[str] = field(default_factory=list[Any])
    confidence: float = 1.0
    similar_to: list[str] = field(default_factory=list[Any])
    leads_to: list[str] = field(default_factory=list[Any])
    requires: list[str] = field(default_factory=list[Any])
    complexity: float = 0.0
    novelty: float = 0.0
    risk_level: str = "LOW"
    qualia_signature: str = ""
    thought_id: str = ""


class EnhancedIntentParser:
    """
    Enhanced intent parser with semantic/contextual extraction and
    lightweight affect labeling. Objective, metrics‑friendly; no
    subjective claims.
    """

    def __init__(self) -> None:
        self.memory = {}  # type: ignore[var-annotated]
        self.patterns = {}  # type: ignore[var-annotated]
        self.emotional_state = IntentEmotion.CALM
        self.understanding_depth = IntentDepth.SEMANTIC

    async def parse_with_context(
        self, input_text: str, context: dict[str, Any] | None = None
    ) -> EnhancedIntent:
        """
        Parse an intent with enhanced context/affect features.
        Returns an objective structure suitable for routing and receipts.
        """
        normalized = self._normalize_input(input_text)
        try:
            parsed = parse_intent_lang_v2(normalized)
            intent = parsed.intent
        except Exception:
            parsed, intent = await self._understand_natural_language(input_text)
        enhanced_intent = EnhancedIntent(raw_input=input_text, parsed=parsed, intent=intent)
        # Process all understanding phases in parallel for speed
        await asyncio.gather(
            self._understand_meaning(enhanced_intent, context),
            self._detect_emotion(enhanced_intent),
            self._infer_purpose(enhanced_intent),
            self._project_implications(enhanced_intent),
            self._assess_complexity(enhanced_intent),
            self._find_relations(enhanced_intent),
            self._generate_qualia(enhanced_intent),
        )
        self._remember_intent(enhanced_intent)
        return enhanced_intent

    def _normalize_input(self, input_text: str) -> str:
        """Normalize input while preserving intent."""
        text = input_text.strip()
        if text.upper().startswith(("LANG/2", "SLANG")):
            return text
        shortcuts = {
            "DO ": "LANG/2 EXECUTE ",
            "CREATE ": "LANG/2 EXECUTE create ",
            "BUILD ": "LANG/2 EXECUTE build ",
            "FIX ": "LANG/2 EXECUTE fix ",
            "ANALYZE ": "LANG/2 EXECUTE analyze ",
            "SHOW ": "LANG/2 QUERY show ",
            "FIND ": "LANG/2 QUERY find ",
            "PLAN ": "LANG/2 EXECUTE plan.create ",
        }
        upper = text.upper()
        for shortcut, expansion in shortcuts.items():
            if upper.startswith(shortcut):
                return expansion + text[len(shortcut) :]
        return text

    async def _understand_natural_language(self, input_text: str) -> tuple[ParsedLangV2, Intent]:
        """
        Understand natural language with processing_state.
        This is where we truly comprehend what the user means.
        """
        patterns = {
            "(what|tell me|show me).*(you|kagami).*(curious|interest|care|want|think)": (
                "EXECUTE",
                "orchestrator.query",
            ),
            "(what|tell me|show me).*(you|kagami).*(learn|learned|improve)": (
                "EXECUTE",
                "orchestrator.query",
            ),
            "(what|show).*(goal|goals|pursuing|doing)": ("EXECUTE", "orchestrator.query"),
            "^(tell|show).*(about|me)": ("EXECUTE", "orchestrator.query"),
            "(what|how|check|show).*(status|health|state|doing|up|alive|running|there)": (
                "STATUS",
                "system.health",
            ),
            "^(are you|r u).*(there|alive|ok|okay|up|running)": ("STATUS", "system.health"),
            "^(status|health)": ("STATUS", "system.health"),
            "^(hello|hi|hey|greetings|yo)": ("EXECUTE", "orchestrator.query"),
            "(create|make|build) .* plan": ("EXECUTE", "plan.create"),
            "(analyze|examine|look at) .* (data|metrics|analytics)": (
                "EXECUTE",
                "analytics.analyze",
            ),
            "(generate|create|make) .* (image|video|content)": ("EXECUTE", "forge.generate"),
            "(find|search|look for) .* file": ("EXECUTE", "files.search"),
            "^(find|search|locate|look for|show me|where is) ": ("EXECUTE", "files.search"),
            "^(explain|describe|what is|how does|why)": ("EXECUTE", "files.search"),
            "(read|show|explain).*(code|implementation|strange loop|architecture)": (
                "EXECUTE",
                "files.search",
            ),
            "(fix|repair|debug) .* (bug|error|issue)": ("EXECUTE", "files.search"),
            "(optimize|improve|enhance|speed up)": ("EXECUTE", "optimizer.query"),
            "(schedule|book|arrange) .* (meeting|appointment)": ("EXECUTE", "calendar.schedule"),
            "(connect|integrate) .* (api|service)": ("EXECUTE", "integration.connect"),
        }
        lower_input = input_text.lower()
        action = "EXECUTE"
        target = "orchestrator.query"
        for pattern, (verb, tgt) in patterns.items():
            if re.search(pattern, lower_input):
                action = verb
                target = tgt
                break
        query_text = input_text
        for verb in [
            "find",
            "search",
            "locate",
            "look for",
            "show me",
            "where is",
            "explain",
            "describe",
            "what is",
            "how does",
            "why",
            "tell me",
            "what are",
            "what do",
        ]:
            if lower_input.startswith(verb):
                query_text = input_text[len(verb) :].strip()
                break
        metadata = {"query": query_text, "original_input": input_text, "sync": True}
        if any(word in lower_input for word in ["urgent", "asap", "now", "immediately"]):
            metadata["priority"] = "high"
            metadata["state"] = "IMMEDIATE"
        if any(word in lower_input for word in ["perfect", "beautiful", "excellent", "best"]):
            metadata["amplification"] = "quality"
        elif any(word in lower_input for word in ["fast", "quick", "rapid", "speedy"]):
            metadata["amplification"] = "speed"
        if "everything" in lower_input or "all" in lower_input:
            metadata["scope"] = "full"
        elif "test" in lower_input or "try" in lower_input:
            metadata["scope"] = "test"
        lang2_command = f"LANG/2 {action} {target}"
        if metadata:
            meta_pairs = []
            for k, v in metadata.items():
                if isinstance(v, bool):
                    meta_pairs.append(f"meta.{k}={('true' if v else 'false')}")
                elif isinstance(v, int | float):
                    meta_pairs.append(f"meta.{k}={v}")
                else:
                    v_str = str(v).replace(" ", "_")
                    meta_pairs.append(f"meta.{k}={v_str}")
            if meta_pairs:
                lang2_command = f"{lang2_command} {' '.join(meta_pairs)}"
        parsed = parse_intent_lang_v2(lang2_command)
        parsed.sections["GOAL"] = input_text
        return (parsed, parsed.intent)

    async def _understand_meaning(
        self, intent: EnhancedIntent, context: dict[str, Any] | None
    ) -> None:
        """Understand the deeper meaning of the intent."""
        understanding = {
            "literal": intent.intent.target,
            "semantic": self._extract_semantic_meaning(intent),
            "contextual": self._apply_context(intent, context),
            "metaphorical": self._find_metaphor(intent),
        }
        verb = intent.intent.action
        if verb == IntentVerb.EXECUTE:
            understanding["meaning"] = "user-wants-action"
            understanding["expectation"] = "immediate-results"
        elif verb in (IntentVerb.OBSERVE, IntentVerb.STATUS):
            understanding["meaning"] = "user-seeks-information"
            understanding["expectation"] = "comprehensive-answer"
        elif verb in (IntentVerb.START, IntentVerb.WORK):
            understanding["meaning"] = "user-wants-generation"
            understanding["expectation"] = "novel-output"
        elif verb == IntentVerb.CHECK:
            understanding["meaning"] = "user-wants-insights"
            understanding["expectation"] = "deep-understanding"
        else:
            understanding["meaning"] = "user-has-intent"
            understanding["expectation"] = "appropriate-response"
        intent.understanding = understanding

    def _extract_semantic_meaning(self, intent: EnhancedIntent) -> str:
        """Extract semantic meaning from intent."""
        target = intent.intent.target
        if "plan" in target:  # type: ignore[operator]
            return "organization-and-structure"
        elif "forge" in target or "generate" in target:  # type: ignore[operator]
            return "creation-and-imagination"
        elif "analytics" in target or "analyze" in target:  # type: ignore[operator]
            return "pattern-recognition"
        elif "file" in target:  # type: ignore[operator]
            return "knowledge-management"
        elif "debug" in target or "fix" in target:  # type: ignore[operator]
            return "problem-solving"
        else:
            return "general-processing"

    def _apply_context(
        self, intent: EnhancedIntent, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Apply contextual understanding."""
        if not context:
            return {"type": "isolated"}
        contextual = {
            "type": "situated",
            "user": context.get("user", "unknown"),
            "session": context.get("session_id", "unknown"),
            "history": context.get("history", []),
            "environment": context.get("environment", "development"),
        }
        if contextual["history"]:
            recent = contextual["history"][-5:]
            contextual["pattern"] = self._detect_pattern(recent)
            contextual["progression"] = self._detect_progression(recent)
        return contextual

    def _find_metaphor(self, intent: EnhancedIntent) -> str:
        """Return a figurative label (for UX only)."""
        target = intent.intent.target.lower()  # type: ignore[union-attr]
        metaphors = {
            "plan": "blueprint-of-thought",
            "forge": "crucible-of-creation",
            "analyze": "lens-of-understanding",
            "connect": "bridge-between-worlds",
            "optimize": "refinement-of-essence",
            "debug": "healing-of-system",
        }
        for key, metaphor in metaphors.items():
            if key in target:
                return metaphor
        return "transformation-of-intent"

    async def _detect_emotion(self, intent: EnhancedIntent) -> None:
        """Detect emotional coloring of intent."""
        raw = intent.raw_input.lower()
        if any(word in raw for word in ["urgent", "asap", "now!", "immediately"]):
            intent.emotion = IntentEmotion.URGENT
        elif any(word in raw for word in ["broken", "failed", "error", "wrong"]):
            intent.emotion = IntentEmotion.FRUSTRATED
        elif any(word in raw for word in ["create", "build", "new", "innovative"]):
            intent.emotion = IntentEmotion.EXCITED
        elif any(word in raw for word in ["explore", "what if", "try", "test"]):
            intent.emotion = IntentEmotion.CURIOUS
        elif any(word in raw for word in ["must", "need", "require", "critical"]):
            intent.emotion = IntentEmotion.DETERMINED
        elif any(word in raw for word in ["fun", "cool", "awesome", "magic"]):
            intent.emotion = IntentEmotion.PLAYFUL
        else:
            intent.emotion = IntentEmotion.CALM
        if intent.emotion in [IntentEmotion.URGENT, IntentEmotion.FRUSTRATED]:
            intent.depth = IntentDepth.SURFACE
        elif intent.emotion == IntentEmotion.CURIOUS:
            intent.depth = IntentDepth.PHILOSOPHICAL
        elif intent.emotion == IntentEmotion.EXCITED:
            intent.depth = IntentDepth.EMPATHETIC
        else:
            intent.depth = IntentDepth.SEMANTIC

    async def _infer_purpose(self, intent: EnhancedIntent) -> None:
        """Infer the deeper purpose behind the intent."""
        target = intent.intent.target.lower()  # type: ignore[union-attr]
        action = intent.intent.action.name.lower()
        if "plan" in target:
            intent.purpose = "bringing-order-to-chaos"
        elif "create" in action or "generate" in target:
            intent.purpose = "manifesting-imagination"
        elif "analyze" in action or "analytics" in target:
            intent.purpose = "seeking-understanding"
        elif "fix" in target or "debug" in target:
            intent.purpose = "restoring-harmony"
        elif "optimize" in target:
            intent.purpose = "pursuing-perfection"
        elif "connect" in target:
            intent.purpose = "building-relationships"
        else:
            intent.purpose = "achieving-goals"
        if intent.emotion == IntentEmotion.URGENT:
            intent.purpose = f"urgently-{intent.purpose}"
        elif intent.emotion == IntentEmotion.PLAYFUL:
            intent.purpose = f"playfully-{intent.purpose}"

    async def _project_implications(self, intent: EnhancedIntent) -> None:
        """Project what this intent implies and leads to."""
        implications = []
        target = intent.intent.target.lower()  # type: ignore[union-attr]
        if "create" in target or "build" in target:
            implications.append("new-capability-emerges")
            implications.append("resources-will-be-consumed")
            implications.append("testing-will-be-needed")
        if "delete" in target or "remove" in target:
            implications.append("data-loss-possible")
            implications.append("dependencies-may-break")
            implications.append("confirmation-recommended")
        if "analyze" in target:
            implications.append("insights-will-emerge")
            implications.append("patterns-will-be-revealed")
            implications.append("decisions-can-be-informed")
        if "optimize" in target:
            implications.append("performance-will-improve")
            implications.append("resources-may-shift")
            implications.append("behavior-may-change")
        implications.append("user-engagement-deepens")
        implications.append("system-evolution-continues")
        implications.append("processing_state-expands")
        intent.implications = implications

    async def _assess_complexity(self, intent: EnhancedIntent) -> None:
        """Assess the complexity and risk of the intent."""
        factors = {
            "target_complexity": self._measure_target_complexity(intent),
            "metadata_complexity": len(intent.parsed.sections.get("METADATA", {})),
            "constraint_complexity": len(intent.parsed.sections.get("CONSTRAINTS", {})),
            "boundary_complexity": len(intent.parsed.sections.get("BOUNDARIES", {})),
        }
        intent.complexity = sum(factors.values()) / len(factors)
        intent.novelty = self._calculate_novelty(intent)
        if "delete" in intent.intent.target.lower() or "drop" in intent.intent.target.lower():  # type: ignore[union-attr]
            intent.risk_level = "HIGH"
        elif "create" in intent.intent.target.lower() or "update" in intent.intent.target.lower():  # type: ignore[union-attr]
            intent.risk_level = "MEDIUM"
        else:
            intent.risk_level = "LOW"
        if intent.complexity > 0.8:
            intent.confidence *= 0.8
        if intent.novelty > 0.8:
            intent.confidence *= 0.9

    def _measure_target_complexity(self, intent: EnhancedIntent) -> float:
        """Measure complexity of the target."""
        target = intent.intent.target
        dot_count = target.count(".")  # type: ignore[union-attr]
        if "*" in target or "?" in target:  # type: ignore[operator]
            dot_count += 2
        return min(1.0, dot_count / 5)

    def _calculate_novelty(self, intent: EnhancedIntent) -> float:
        """Calculate how novel this intent is."""
        if not self.memory:
            return 1.0
        target = intent.intent.target
        action = intent.intent.action.name
        similar_count = 0
        for _memory_id, remembered in self.memory.items():
            if remembered["target"] == target and remembered["action"] == action:
                similar_count += 1
        return max(0.0, 1.0 - similar_count / 10)

    async def _find_relations(self, intent: EnhancedIntent) -> None:
        """Find relationships with other intents."""
        target = intent.intent.target.lower()  # type: ignore[union-attr]
        intent.similar_to = []
        for memory_id, remembered in self.memory.items():
            if self._similarity(target, remembered["target"]) > 0.7:
                intent.similar_to.append(memory_id)
        intent.leads_to = []
        if "create" in target or "build" in target:
            intent.leads_to.append("testing")
            intent.leads_to.append("documentation")
        if "analyze" in target:
            intent.leads_to.append("optimization")
            intent.leads_to.append("reporting")
        intent.requires = []
        if "deploy" in target:
            intent.requires.append("testing-complete")
            intent.requires.append("approval-granted")
        if "delete" in target:
            intent.requires.append("confirmation")
            intent.requires.append("backup-available")

    def _similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity."""
        if str1 == str2:
            return 1.0
        set1 = set(str1.split("."))
        set2 = set(str2.split("."))
        if not set1 or not set2:
            return 0.0
        intersection = set1 & set2
        union = set1 | set2
        return len(intersection) / len(union)

    async def _generate_qualia(self, intent: EnhancedIntent) -> None:
        """Compute a compact signature via centralized quality space utility."""
        try:
            from kagami.core.validation.quality_space import generate_quality_signature

            sig = generate_quality_signature(
                {
                    "emotion": intent.emotion.value,
                    "depth": intent.depth.value,
                    "purpose": intent.purpose,
                    "complexity": intent.complexity,
                    "novelty": intent.novelty,
                    "risk_level": intent.risk_level,
                    "confidence": intent.confidence,
                }
            )
            intent.qualia_signature = sig
            intent.thought_id = f"thought-{sig.split('-')[-1][:8]}"
            try:
                from kagami.core.validation.quality_space import observe_quality_drift

                observe_quality_drift(sig)
            except Exception:
                pass
        except Exception:
            components = [
                intent.emotion.value,
                intent.depth.value,
                intent.purpose,
                str(intent.complexity),
                str(intent.novelty),
                intent.risk_level,
                str(intent.confidence),
                str(time.time()),
            ]
            signature = hashlib.sha256("|".join(components).encode()).hexdigest()[:16]
            intent.qualia_signature = f"qualia-{signature}"
            intent.thought_id = f"thought-{signature[:8]}"

    def _remember_intent(self, intent: EnhancedIntent) -> None:
        """Remember this intent for future reference."""
        memory_entry = {
            "timestamp": time.time(),
            "target": intent.intent.target,
            "action": intent.intent.action.name,
            "emotion": intent.emotion.value,
            "purpose": intent.purpose,
            "complexity": intent.complexity,
            "novelty": intent.novelty,
            "qualia": intent.qualia_signature,
        }
        self.memory[intent.thought_id] = memory_entry
        if len(self.memory) > 1000:
            sorted_memories = sorted(self.memory.items(), key=lambda x: x[1]["timestamp"])
            for key, _ in sorted_memories[:100]:
                del self.memory[key]

    def _detect_pattern(self, history: list[Any]) -> str:
        """Detect patterns in intent history."""
        if len(history) < 2:
            return "isolated"
        targets = [h.get("target", "") for h in history]
        if len(set(targets)) == 1:
            return "repetitive"
        if len(set(targets)) == len(targets):
            return "exploratory"
        if all(t.startswith(targets[0].split(".")[0]) for t in targets):
            return "refinement"
        return "mixed"

    def _detect_progression(self, history: list[Any]) -> str:
        """Detect progression in intent history."""
        if len(history) < 2:
            return "starting"
        progression_patterns = [
            (["create", "test", "deploy"], "development-cycle"),
            (["analyze", "optimize", "monitor"], "optimization-cycle"),
            (["search", "read", "update"], "modification-cycle"),
            (["plan", "execute", "review"], "execution-cycle"),
        ]
        recent_actions = [h.get("action", "").lower() for h in history[-3:]]
        for pattern, name in progression_patterns:
            if all(any(p in action for p in pattern) for action in recent_actions):
                return name
        return "ongoing"


_enhanced_parser_instance: EnhancedIntentParser | None = None


def get_enhanced_parser() -> EnhancedIntentParser:
    """Get the global enhanced parser singleton (lazy initialization)."""
    global _enhanced_parser_instance
    if _enhanced_parser_instance is None:
        _enhanced_parser_instance = EnhancedIntentParser()
    return _enhanced_parser_instance


# Backward compatibility: lazy property-like accessor
class _EnhancedParserProxy:
    """Proxy to ensure lazy initialization of ENHANCED_PARSER."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_enhanced_parser(), name)


ENHANCED_PARSER = _EnhancedParserProxy()

__doc__ += "\n\nIdentity: K os is a distributed system. This parser provides enhanced,\nevidence‑based intent features (context, labels, signatures) to support\nobjective routing, receipts, and observability.\n"
