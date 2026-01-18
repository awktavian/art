"""Language Interface Disambiguation

Detects ambiguous user inputs and requests clarification when confidence < 0.7.

Examples of ambiguous commands:
- "delete all deprecated" → Which deprecated items? Files? Functions? Variables?
- "update the config" → Which config? Application? Database? API?
- "fix the bug" → Which bug? In which module?

This module prevents wrong operations by asking for clarification when uncertain.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DisambiguationResult:
    """Result of disambiguation analysis."""

    is_ambiguous: bool
    confidence: float  # 0.0-1.0, where <0.7 triggers clarification
    ambiguity_type: str  # "target", "scope", "action", "parameter"
    clarification_prompt: str | None
    suggested_interpretations: list[dict[str, Any]] | None = None


class LanguageDisambiguator:
    """Detects and resolves ambiguous language in intents."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(__name__)

        # Ambiguous action patterns
        self.ambiguous_actions = {
            "delete all": "scope_unclear",  # All what?
            "remove": "target_unclear",  # Remove what from where?
            "update": "target_unclear",  # Update what?
            "fix": "target_unclear",  # Fix what?
            "configure": "target_unclear",  # Configure which component?
            "restart": "scope_unclear",  # Restart what? Everything?
            "clear": "scope_unclear",  # Clear what data?
        }

        # Scope quantifiers that need specificity
        self.vague_quantifiers = [
            "all",
            "everything",
            "any",
            "some",
            "the",  # "the config" without context
        ]

        # Actions requiring explicit targets
        self.high_risk_actions = [
            "delete",
            "drop",
            "destroy",
            "remove",
            "purge",
            "truncate",
        ]

    def analyze_intent(self, intent: dict[str, Any]) -> DisambiguationResult:
        """Analyze intent for ambiguity."""
        action = str(intent.get("action", "")).lower()
        params = intent.get("params", {})
        target = str(intent.get("target", "")).lower()

        # Check for ambiguous action patterns
        for pattern, ambiguity_type in self.ambiguous_actions.items():
            if pattern in action:
                # Check if params provide clarification
                if not self._has_sufficient_params(params, action):
                    confidence = 0.5  # Ambiguous
                    return DisambiguationResult(
                        is_ambiguous=confidence < self.confidence_threshold,
                        confidence=confidence,
                        ambiguity_type=ambiguity_type,
                        clarification_prompt=self._generate_clarification(action, ambiguity_type),
                        suggested_interpretations=self._suggest_interpretations(action, params),
                    )

        # Check for vague quantifiers with high-risk actions
        if any(risk_action in action for risk_action in self.high_risk_actions):
            if any(quant in action for quant in self.vague_quantifiers):
                if not self._has_explicit_scope(params):
                    confidence = 0.4  # Very ambiguous + high risk
                    return DisambiguationResult(
                        is_ambiguous=confidence < self.confidence_threshold,
                        confidence=confidence,
                        ambiguity_type="dangerous_ambiguity",
                        clarification_prompt=(
                            f"'{action}' is a destructive operation with unclear scope. "
                            "Please specify exactly what to delete (e.g., file paths, IDs, filters)."
                        ),
                    )

        # Check for missing critical parameters
        if action and not params and not target:
            confidence = 0.6  # Somewhat ambiguous
            return DisambiguationResult(
                is_ambiguous=confidence < self.confidence_threshold,
                confidence=confidence,
                ambiguity_type="missing_parameters",
                clarification_prompt=f"Action '{action}' requires parameters. What should it operate on?",
            )

        # Not ambiguous - high confidence
        confidence = 0.9
        return DisambiguationResult(
            is_ambiguous=False,
            confidence=confidence,
            ambiguity_type="clear",
            clarification_prompt=None,
        )

    def _has_sufficient_params(self, params: dict[str, Any], action: str) -> bool:
        """Check if params provide sufficient specificity."""
        if not params:
            return False

        # Check for explicit identifiers
        identifying_keys = ["id", "path", "name", "filter", "query", "target", "scope"]
        return any(key in params for key in identifying_keys)

    def _has_explicit_scope(self, params: dict[str, Any]) -> bool:
        """Check if params explicitly define scope."""
        scope_keys = ["ids", "paths", "names", "filter", "where", "limit"]
        return any(key in params for key in scope_keys)

    def _generate_clarification(self, action: str, ambiguity_type: str) -> str:
        """Generate clarification prompt for ambiguous action."""
        if ambiguity_type == "scope_unclear":
            return f"'{action}' - please specify the scope (what items? from where?)"
        elif ambiguity_type == "target_unclear":
            return f"'{action}' - please specify the target (which resource? what identifier?)"
        elif ambiguity_type == "action_unclear":
            return f"'{action}' - please clarify what you want to do"
        elif ambiguity_type == "parameter_unclear":
            return f"'{action}' - please provide required parameters"
        else:
            return f"Please clarify: '{action}'"

    def _suggest_interpretations(self, action: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Suggest possible interpretations of ambiguous command."""
        suggestions = []

        if "delete all" in action:
            suggestions.extend(
                [
                    {
                        "interpretation": "Delete all files in specific directory",
                        "needs": "directory_path",
                    },
                    {
                        "interpretation": "Delete all items matching filter",
                        "needs": "filter_criteria",
                    },
                    {
                        "interpretation": "Delete all soft-deleted items",
                        "needs": "confirmation",
                    },
                ]
            )

        elif "update" in action and "config" in action:
            suggestions.extend(
                [
                    {
                        "interpretation": "Update application config",
                        "needs": "app_name, config_key, value",
                    },
                    {
                        "interpretation": "Update database config",
                        "needs": "connection_string or specific_setting",
                    },
                    {
                        "interpretation": "Update API config",
                        "needs": "endpoint, setting, value",
                    },
                ]
            )

        elif "fix" in action:
            suggestions.extend(
                [
                    {
                        "interpretation": "Fix specific bug",
                        "needs": "bug_id or issue_number",
                    },
                    {"interpretation": "Fix lint errors in file", "needs": "file_path"},
                    {"interpretation": "Fix failing test", "needs": "test_name"},
                ]
            )

        return suggestions

    def require_clarification_if_needed(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        """Return clarification request if intent is ambiguous, None otherwise."""
        result = self.analyze_intent(intent)

        if result.is_ambiguous and result.confidence < self.confidence_threshold:
            self.logger.warning(
                f"Ambiguous intent detected: {intent.get('action')} "
                f"(confidence: {result.confidence:.2f}, threshold: {self.confidence_threshold})"
            )

            # Emit metric
            try:
                from kagami_observability.metrics import (
                    LANGUAGE_DISAMBIGUATION_TOTAL,
                )

                LANGUAGE_DISAMBIGUATION_TOTAL.labels(ambiguity_type=result.ambiguity_type).inc()
            except Exception:
                pass

            return {
                "status": "needs_clarification",
                "confidence": result.confidence,
                "ambiguity_type": result.ambiguity_type,
                "clarification_prompt": result.clarification_prompt,
                "suggested_interpretations": result.suggested_interpretations,
                "original_intent": intent,
            }

        return None  # Not ambiguous, proceed


# Singleton instance
_disambiguator: LanguageDisambiguator | None = None


def get_disambiguator(confidence_threshold: float = 0.7) -> LanguageDisambiguator:
    """Get global disambiguator instance."""
    global _disambiguator
    if _disambiguator is None:
        _disambiguator = LanguageDisambiguator(confidence_threshold=confidence_threshold)
    return _disambiguator


async def check_disambiguation(intent: dict[str, Any]) -> dict[str, Any] | None:
    """Check if intent needs clarification. Returns clarification request or None."""
    disambiguator = get_disambiguator()
    return disambiguator.require_clarification_if_needed(intent)
