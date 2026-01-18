"""Colony Display Formatter — Map Colonies to Elysia Display Types.

Each of Kagami's 7 colonies maps to an Elysia display type:

| Colony | Display Type | Catastrophe | Use Case |
|--------|-------------|-------------|----------|
| Spark | Generic | Fold (A₂) | Creative outputs, brainstorms |
| Forge | Table | Cusp (A₃) | Structured data, implementations |
| Flow | Conversation | Swallowtail (A₄) | Recovery dialogues, chat |
| Nexus | Document | Butterfly (A₅) | Long-form, integration |
| Beacon | E-commerce | Hyperbolic (D₄⁺) | Plans, products, cards |
| Grove | Ticket | Elliptic (D₄⁻) | Research items, issues |
| Crystal | Chart | Parabolic (D₅) | Analytics, verification |

Created: December 7, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DisplayType(Enum):
    """Elysia display types."""

    GENERIC = "generic"
    TABLE = "table"
    CONVERSATION = "conversation"
    DOCUMENT = "document"
    ECOMMERCE = "ecommerce"
    TICKET = "ticket"
    CHART = "chart"


# Colony → Display mapping
COLONY_DISPLAY_MAP = {
    "spark": DisplayType.GENERIC,
    "forge": DisplayType.TABLE,
    "flow": DisplayType.CONVERSATION,
    "nexus": DisplayType.DOCUMENT,
    "beacon": DisplayType.ECOMMERCE,
    "grove": DisplayType.TICKET,
    "crystal": DisplayType.CHART,
}

# Display → Colony reverse mapping
DISPLAY_COLONY_MAP = {v: k for k, v in COLONY_DISPLAY_MAP.items()}


@dataclass
class DisplayConfig:
    """Configuration for a display type."""

    display_type: DisplayType
    colony: str
    primary_fields: list[str]
    secondary_fields: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    style: dict[str, Any] = field(default_factory=dict)


# Default display configurations
DISPLAY_CONFIGS = {
    DisplayType.GENERIC: DisplayConfig(
        display_type=DisplayType.GENERIC,
        colony="spark",
        primary_fields=["content", "title"],
        secondary_fields=["metadata"],
        actions=["copy", "expand"],
        style={"layout": "card", "max_items": 10},
    ),
    DisplayType.TABLE: DisplayConfig(
        display_type=DisplayType.TABLE,
        colony="forge",
        primary_fields=["*"],  # All fields
        secondary_fields=[],
        actions=["sort", "filter", "export"],
        style={"layout": "table", "pagination": True, "page_size": 20},
    ),
    DisplayType.CONVERSATION: DisplayConfig(
        display_type=DisplayType.CONVERSATION,
        colony="flow",
        primary_fields=["message", "content", "text"],
        secondary_fields=["sender", "timestamp", "status"],
        actions=["reply", "thread", "react"],
        style={"layout": "timeline", "bubble": True},
    ),
    DisplayType.DOCUMENT: DisplayConfig(
        display_type=DisplayType.DOCUMENT,
        colony="nexus",
        primary_fields=["content", "body", "text"],
        secondary_fields=["title", "author", "date", "tags"],
        actions=["toc", "highlight", "annotate"],
        style={"layout": "prose", "max_length": 10000},
    ),
    DisplayType.ECOMMERCE: DisplayConfig(
        display_type=DisplayType.ECOMMERCE,
        colony="beacon",
        primary_fields=["name", "title", "description"],
        secondary_fields=["price", "image", "rating", "stock"],
        actions=["view", "compare", "add_to_cart"],
        style={"layout": "grid", "card_size": "medium"},
    ),
    DisplayType.TICKET: DisplayConfig(
        display_type=DisplayType.TICKET,
        colony="grove",
        primary_fields=["title", "description"],
        secondary_fields=["status", "priority", "assignee", "labels"],
        actions=["update_status", "assign", "comment"],
        style={"layout": "list", "group_by": "status"},
    ),
    DisplayType.CHART: DisplayConfig(
        display_type=DisplayType.CHART,
        colony="crystal",
        primary_fields=["data", "values", "series"],
        secondary_fields=["labels", "categories", "legend"],
        actions=["zoom", "export", "drill_down"],
        style={"layout": "chart", "chart_type": "auto"},
    ),
}


@dataclass
class FormattedDisplay:
    """Formatted output ready for Elysia frontend."""

    display_type: str
    colony: str
    items: list[dict[str, Any]]
    total_count: int
    config: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


class ColonyDisplayFormatter:
    """Format colony outputs using Elysia display types.

    Usage:
        formatter = ColonyDisplayFormatter()

        # Format based on colony
        display = formatter.format_for_colony(
            colony="grove",
            data=[{"title": "...", "content": "..."}],
            schema={"title": "text", "content": "text"},
        )

        # Auto-detect display type
        display = formatter.auto_format(data, schema)
    """

    def __init__(self, custom_configs: dict[DisplayType, DisplayConfig] | None = None):
        """Initialize formatter.

        Args:
            custom_configs: Optional custom display configurations
        """
        self.configs = DISPLAY_CONFIGS.copy()
        if custom_configs:
            self.configs.update(custom_configs)

    def format_for_colony(
        self,
        colony: str,
        data: list[dict[str, Any]],
        schema: dict[str, str] | None = None,
    ) -> FormattedDisplay:
        """Format data using colony's display type.

        Args:
            colony: Colony name (spark, forge, etc.)
            data: List of data items
            schema: Optional schema (field → type mapping)

        Returns:
            FormattedDisplay ready for frontend
        """
        display_type = COLONY_DISPLAY_MAP.get(colony, DisplayType.GENERIC)
        return self._format(display_type, colony, data, schema)

    def format_for_type(
        self,
        display_type: DisplayType | str,
        data: list[dict[str, Any]],
        schema: dict[str, str] | None = None,
    ) -> FormattedDisplay:
        """Format data using specified display type.

        Args:
            display_type: Display type (enum or string)
            data: List of data items
            schema: Optional schema

        Returns:
            FormattedDisplay ready for frontend
        """
        if isinstance(display_type, str):
            display_type = DisplayType(display_type)

        colony = DISPLAY_COLONY_MAP.get(display_type, "nexus")
        return self._format(display_type, colony, data, schema)

    def auto_format(
        self,
        data: list[dict[str, Any]],
        schema: dict[str, str] | None = None,
    ) -> FormattedDisplay:
        """Auto-detect best display type for data.

        Args:
            data: List of data items
            schema: Optional schema

        Returns:
            FormattedDisplay with auto-detected type
        """
        display_type = self._detect_display_type(data, schema)
        colony = DISPLAY_COLONY_MAP.get(display_type, "nexus")
        return self._format(display_type, colony, data, schema)

    def _format(
        self,
        display_type: DisplayType,
        colony: str,
        data: list[dict[str, Any]],
        schema: dict[str, str] | None,
    ) -> FormattedDisplay:
        """Internal formatting logic."""
        config = self.configs.get(display_type, DISPLAY_CONFIGS[DisplayType.GENERIC])

        # Extract primary and secondary fields
        formatted_items = []
        for item in data:
            formatted_item = self._format_item(item, config, schema)
            formatted_items.append(formatted_item)

        return FormattedDisplay(
            display_type=display_type.value,
            colony=colony,
            items=formatted_items,
            total_count=len(data),
            config={
                "primary_fields": config.primary_fields,
                "secondary_fields": config.secondary_fields,
                "actions": config.actions,
                "style": config.style,
            },
            metadata={
                "schema": schema or {},
                "auto_detected": schema is None,
            },
        )

    def _format_item(
        self,
        item: dict[str, Any],
        config: DisplayConfig,
        schema: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Format a single item based on config."""
        formatted = {"_raw": item}

        # Extract primary fields
        if "*" in config.primary_fields:
            # Include all fields
            formatted["primary"] = item
        else:
            formatted["primary"] = {k: item.get(k) for k in config.primary_fields if k in item}

        # Extract secondary fields
        formatted["secondary"] = {k: item.get(k) for k in config.secondary_fields if k in item}

        return formatted

    def _detect_display_type(
        self,
        data: list[dict[str, Any]],
        schema: dict[str, str] | None,
    ) -> DisplayType:
        """Auto-detect best display type with enhanced content analysis.

        Uses multi-signal detection:
        1. Key pattern matching (field names)
        2. Value type analysis (numeric arrays, long text, etc.)
        3. Data shape analysis (list length, field count)
        4. Content semantic hints (code, markdown, structured)
        """
        if not data:
            return DisplayType.GENERIC

        sample = data[0]
        keys = set(sample.keys())
        keys_lower = {k.lower() for k in keys}

        # Track detection scores for each type
        scores: dict[DisplayType, float] = dict.fromkeys(DisplayType, 0.0)

        # === Key pattern analysis (weighted) ===

        # Conversation patterns
        conversation_keys = {
            "message",
            "sender",
            "timestamp",
            "text",
            "role",
            "author",
            "reply",
            "thread",
        }
        conv_matches = len(keys_lower & conversation_keys)
        if conv_matches >= 2:
            scores[DisplayType.CONVERSATION] += 0.7 + (conv_matches - 2) * 0.1

        # Ticket/issue patterns
        ticket_keys = {
            "status",
            "priority",
            "assignee",
            "labels",
            "issue",
            "ticket",
            "severity",
            "resolution",
            "reporter",
        }
        ticket_matches = len(keys_lower & ticket_keys)
        if ticket_matches >= 2:
            scores[DisplayType.TICKET] += 0.7 + (ticket_matches - 2) * 0.1

        # E-commerce/card patterns
        ecommerce_keys = {
            "price",
            "image",
            "rating",
            "stock",
            "product",
            "sku",
            "quantity",
            "cart",
            "category",
            "brand",
        }
        ecom_matches = len(keys_lower & ecommerce_keys)
        if ecom_matches >= 2:
            scores[DisplayType.ECOMMERCE] += 0.7 + (ecom_matches - 2) * 0.1

        # Document patterns
        doc_keys = {
            "content",
            "body",
            "text",
            "title",
            "author",
            "date",
            "tags",
            "summary",
            "abstract",
        }
        doc_matches = len(keys_lower & doc_keys)
        if doc_matches >= 2:
            scores[DisplayType.DOCUMENT] += 0.5 + (doc_matches - 2) * 0.1

        # Chart/data patterns
        chart_keys = {
            "data",
            "values",
            "series",
            "labels",
            "x",
            "y",
            "metrics",
            "count",
            "sum",
            "avg",
        }
        chart_matches = len(keys_lower & chart_keys)
        if chart_matches >= 2:
            scores[DisplayType.CHART] += 0.6 + (chart_matches - 2) * 0.1

        # === Value type analysis ===

        numeric_array_count = 0
        long_text_count = 0
        code_text_count = 0
        url_count = 0

        for _key, value in sample.items():
            # Numeric arrays → Chart
            if isinstance(value, list) and value and isinstance(value[0], (int, float)):
                numeric_array_count += 1
                scores[DisplayType.CHART] += 0.4

            # Long text content → Document
            if isinstance(value, str):
                text_len = len(value)
                if text_len > 500:
                    long_text_count += 1
                    scores[DisplayType.DOCUMENT] += 0.3 + min(text_len / 5000, 0.4)

                # Code detection (indentation, brackets, keywords)
                if any(
                    marker in value
                    for marker in ["def ", "class ", "function ", "import ", "```", "    "]
                ):
                    code_text_count += 1
                    scores[DisplayType.DOCUMENT] += 0.3

                # Markdown detection
                if any(marker in value for marker in ["## ", "**", "- ", "1. ", "[", "]("]):
                    scores[DisplayType.DOCUMENT] += 0.2

                # URL detection → possibly E-commerce
                if value.startswith(("http://", "https://", "www.")):
                    url_count += 1

        # === Data shape analysis ===

        # Many items → Table or Chart
        if len(data) > 10:
            scores[DisplayType.TABLE] += 0.3
            if numeric_array_count > 0:
                scores[DisplayType.CHART] += 0.2

        # Many fields → Table
        if len(keys) > 5:
            scores[DisplayType.TABLE] += 0.4
        if len(keys) > 10:
            scores[DisplayType.TABLE] += 0.3

        # Few items with long content → Document
        if len(data) <= 3 and long_text_count > 0:
            scores[DisplayType.DOCUMENT] += 0.3

        # === Schema hints ===
        if schema:
            schema_types = set(schema.values())
            if "datetime" in schema_types or "timestamp" in schema_types:
                scores[DisplayType.CONVERSATION] += 0.2
            if "number" in schema_types or "float" in schema_types or "int" in schema_types:
                scores[DisplayType.CHART] += 0.2
                scores[DisplayType.TABLE] += 0.1

        # === Select best type ===
        best_type = max(scores, key=lambda t: scores[t])
        best_score = scores[best_type]

        # Require minimum confidence, else default to GENERIC
        if best_score < 0.3:
            return DisplayType.GENERIC

        return best_type


# Convenience function
def format_colony_output(
    colony: str,
    data: list[dict[str, Any]],
    schema: dict[str, str] | None = None,
) -> FormattedDisplay:
    """Format colony output using appropriate display type.

    Args:
        colony: Colony name
        data: Output data
        schema: Optional schema

    Returns:
        FormattedDisplay
    """
    formatter = ColonyDisplayFormatter()
    return formatter.format_for_colony(colony, data, schema)


__all__ = [
    "COLONY_DISPLAY_MAP",
    "DISPLAY_COLONY_MAP",
    "ColonyDisplayFormatter",
    "DisplayConfig",
    "DisplayType",
    "FormattedDisplay",
    "format_colony_output",
]
