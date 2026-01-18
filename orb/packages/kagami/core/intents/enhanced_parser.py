"""Enhanced Intent Parser - LLM-Powered Natural Language Intent Parsing.

Provides natural language intent parsing using LLM for complex,
ambiguous, or context-dependent intents.

Referenced by: kagami/core/schemas/schemas/intent_lang.py

Created: December 26, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ParsedIntent:
    """Result of parsing a natural language intent."""

    action: str  # The verb/action extracted
    target: str  # The target of the action
    parameters: dict[str, Any] = field(default_factory=dict[str, Any])
    confidence: float = 0.0
    ambiguities: list[str] = field(default_factory=list[Any])
    virtual_action_plan: list[str] = field(default_factory=list[Any])
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "target": self.target,
            "parameters": self.parameters,
            "confidence": self.confidence,
            "ambiguities": self.ambiguities,
            "virtual_action_plan": self.virtual_action_plan,
        }


class EnhancedIntentParser:
    """LLM-powered intent parser for natural language.

    Uses structured output from LLM to parse complex intents
    that can't be handled by regex-based parsing.
    """

    def __init__(self) -> None:
        self._llm = None
        self._initialized = False
        logger.info("EnhancedIntentParser created")

    async def initialize(self) -> bool:
        """Initialize the parser with LLM connection."""
        try:
            from kagami.core.services.llm.service import get_llm_service

            self._llm = get_llm_service()  # type: ignore[assignment]

            self._initialized = self._llm.is_initialized  # type: ignore[attr-defined]
            return self._initialized
        except Exception as e:
            logger.warning(f"Failed to initialize LLM for intent parsing: {e}")
            return False

    async def parse(
        self,
        text: str,
        context: dict[str, Any] | None = None,
    ) -> ParsedIntent:
        """Parse natural language text into structured intent.

        Args:
            text: Natural language intent text
            context: Optional context for disambiguation

        Returns:
            ParsedIntent with extracted action, target, and parameters
        """
        context = context or {}

        # Try LLM-based parsing if available
        if self._llm is not None and self._llm.is_initialized:  # type: ignore[unreachable]
            try:  # type: ignore[unreachable]
                return await self._parse_with_llm(text, context)
            except Exception as e:
                logger.warning(f"LLM parsing failed, using fallback: {e}")

        # Fallback to simple heuristic parsing
        return self._parse_heuristic(text, context)

    async def _parse_with_llm(
        self,
        text: str,
        context: dict[str, Any],
    ) -> ParsedIntent:
        """Parse using LLM structured output."""
        from pydantic import BaseModel, Field

        class IntentOutput(BaseModel):
            action: str = Field(description="The verb/action (e.g., create, delete, search)")
            target: str = Field(description="The target of the action")
            parameters: dict[str, Any] = Field(default_factory=dict[str, Any])
            confidence: float = Field(ge=0.0, le=1.0, default=0.8)
            ambiguities: list[str] = Field(default_factory=list[Any])

        prompt = f"""Parse this intent into structured form:
Text: {text}
Context: {context}

Extract the action verb, target, and any parameters."""

        result = await self._llm.generate(  # type: ignore[attr-defined]
            prompt,
            app_name="intent_parser",
            max_tokens=200,
            temperature=0.1,
            structured_output=IntentOutput,
        )

        if isinstance(result, IntentOutput):
            return ParsedIntent(
                action=result.action,
                target=result.target,
                parameters=result.parameters,
                confidence=result.confidence,
                ambiguities=result.ambiguities,
                raw_text=text,
            )

        # Fallback
        return self._parse_heuristic(text, context)

    def _parse_heuristic(
        self,
        text: str,
        context: dict[str, Any],
    ) -> ParsedIntent:
        """Simple heuristic-based parsing as fallback."""
        words = text.lower().split()

        # Common action verbs
        actions = [
            "create",
            "delete",
            "update",
            "search",
            "find",
            "get",
            "set[Any]",
            "run",
            "execute",
        ]
        action = "unknown"
        target = text

        for word in words:
            if word in actions:
                action = word
                # Target is everything after the action
                idx = text.lower().find(word)
                target = text[idx + len(word) :].strip()
                break

        return ParsedIntent(
            action=action,
            target=target,
            parameters={},
            confidence=0.5,  # Low confidence for heuristic
            ambiguities=["Parsed using heuristic fallback"],
            raw_text=text,
        )


# Singleton
_ENHANCED_PARSER: EnhancedIntentParser | None = None


def get_enhanced_parser() -> EnhancedIntentParser:
    """Get the global enhanced intent parser."""
    global _ENHANCED_PARSER
    if _ENHANCED_PARSER is None:
        _ENHANCED_PARSER = EnhancedIntentParser()
    return _ENHANCED_PARSER


__all__ = [
    "EnhancedIntentParser",
    "ParsedIntent",
    "get_enhanced_parser",
]
