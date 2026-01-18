"""
Base components for K os.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class IntentType(str, Enum):
    COMMAND = "command"
    QUERY = "query"
    VOICE = "voice"
    ANALYSIS = "analysis"


@dataclass
class Intent:
    type: IntentType
    content: str
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    timestamp: datetime | None = None


@dataclass
class Response:
    content: Any
    mascot_message: str
    emotion: str
    suggested_actions: list[dict[str, Any]] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
