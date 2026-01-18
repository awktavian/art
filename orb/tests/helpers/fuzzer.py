"""Input Fuzzing for Testing.

Generates random inputs to test edge cases.
"""

from __future__ import annotations

import logging
import random
import string
from typing import Any

logger = logging.getLogger(__name__)


class InputFuzzer:
    """Generates fuzzed inputs for testing."""

    def __init__(self, seed: int | None = None) -> None:
        """Initialize fuzzer.

        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)

    def fuzz_dict(self, template: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generate fuzzed dictionary.

        Args:
            template: Optional template to base fuzzing on

        Returns:
            Fuzzed dictionary
        """
        if template:
            fuzzed = {}
            for key, value in template.items():
                if random.random() > 0.3:  # 70% chance to include
                    fuzzed[key] = self._fuzz_value(value)
                # Add random keys
                if random.random() > 0.8:
                    fuzzed[self._random_string(10)] = self._random_value()
            return fuzzed
        else:
            # Generate random dict
            return {
                self._random_string(random.randint(1, 20)): self._random_value()
                for _ in range(random.randint(0, 10))
            }

    def fuzz_string(self, template: str | None = None) -> str:
        """Generate fuzzed string."""
        mutations = [
            "",  # Empty
            " ",  # Whitespace
            "\n\t\r",  # Special chars
            "x" * random.randint(1, 1000),  # Long string
            self._random_string(random.randint(1, 100)),  # Random
            "../../etc/passwd",  # Path traversal
            "<script>alert('xss')</script>",  # XSS
            "'; DROP TABLE users; --",  # SQL injection
            "\x00" * 10,  # Null bytes
            "🔥" * 50,  # Unicode
        ]

        return random.choice(mutations)

    def fuzz_number(self) -> int | float:
        """Generate fuzzed number."""
        mutations = [
            0,
            -1,
            1,
            random.randint(-1000000, 1000000),
            float("inf"),
            float("-inf"),
            float("nan"),
            2**63 - 1,
            -(2**63),
            1e-100,
            1e100,
            random.random(),
        ]

        return random.choice(mutations)

    def _fuzz_value(self, value: Any) -> Any:
        """Fuzz a value based on its type."""
        if isinstance(value, dict):
            return self.fuzz_dict(value)
        elif isinstance(value, str):
            return self.fuzz_string(value)
        elif isinstance(value, (int, float)):
            return self.fuzz_number()
        elif isinstance(value, list):
            return [self._fuzz_value(random.choice(value)) for _ in range(random.randint(0, 5))]
        elif value is None:
            return random.choice([None, "", 0, []])
        else:
            return self._random_value()

    def _random_string(self, length: int) -> str:
        """Generate random string."""
        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    def _random_value(self) -> Any:
        """Generate random value."""
        return random.choice(
            [
                None,
                True,
                False,
                random.randint(-100, 100),
                random.random(),
                self._random_string(random.randint(1, 50)),
                [],
                {},
            ]
        )
