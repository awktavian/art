"""Anthropic Claude API client wrapper.

Provides a consistent interface matching other LLM clients in Kagami.

Claude Pricing (Dec 2024):
- Sonnet 4: $3/1M input, $15/1M output (best value)
- Opus 4: $15/1M input, $75/1M output (highest quality)
- Haiku 3.5: $0.25/1M input, $1.25/1M output (fast/cheap)
"""

import logging
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class AnthropicConfig:
    """Configuration for Anthropic client."""

    api_key: str
    model: str = "claude-sonnet-4-20250514"
    timeout: float = 120.0
    max_tokens: int = 4096


class AnthropicClient:
    """Anthropic Claude API client.

    Wraps the official anthropic library with Kagami's interface.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
        max_tokens: int = 4096,
    ):
        self.config = AnthropicConfig(
            api_key=api_key,
            model=model,
            timeout=timeout,
            max_tokens=max_tokens,
        )
        self._client: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Anthropic client."""
        if self._initialized:
            return

        try:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
            self._initialized = True
            logger.debug(f"Anthropic client initialized with model: {self.config.model}")
        except ImportError as err:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from err

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> str:
        """Generate a completion from Claude.

        Args:
            prompt: The user message/prompt
            system: Optional system message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            stop_sequences: Optional stop sequences

        Returns:
            Generated text response
        """
        if not self._initialized:
            await self.initialize()

        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": messages,
            "temperature": temperature,
        }

        if system:
            kwargs["system"] = system

        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        try:
            response = self._client.messages.create(**kwargs)
            return response.content[0].text  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def generate_stream(  # type: ignore[no-untyped-def]
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ):
        """Generate a streaming completion from Claude.

        Args:
            prompt: The user message/prompt
            system: Optional system message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)

        Yields:
            Text chunks as they're generated
        """
        if not self._initialized:
            await self.initialize()

        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": messages,
            "temperature": temperature,
        }

        if system:
            kwargs["system"] = system

        try:
            with self._client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Multi-turn chat with Claude.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system: Optional system message
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated response
        """
        if not self._initialized:
            await self.initialize()

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": messages,
            "temperature": temperature,
        }

        if system:
            kwargs["system"] = system

        try:
            response = self._client.messages.create(**kwargs)
            return response.content[0].text  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            raise

    @property
    def model_name(self) -> str:
        """Get the model name."""
        return self.config.model

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> T:
        """Generate structured output using instructor with Claude.

        Uses the instructor library for reliable structured output via
        Anthropic's tool use / function calling.

        Args:
            prompt: The user message/prompt
            response_model: Pydantic model class for output structure
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system: Optional system message

        Returns:
            Instance of response_model with parsed output
        """
        if not self._initialized:
            await self.initialize()

        try:
            import instructor
        except ImportError as err:
            raise RuntimeError(
                "instructor package not installed. Run: pip install instructor"
            ) from err

        # Create instructor-patched client
        import anthropic

        client = instructor.from_anthropic(
            anthropic.Anthropic(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
        )

        messages = [{"role": "user", "content": prompt}]

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "messages": messages,
            "temperature": temperature,
            "response_model": response_model,
        }

        if system:
            # Anthropic uses system as a separate kwarg, not in messages
            kwargs["system"] = system

        try:
            result = client.messages.create(**kwargs)
            return result  # type: ignore[return-value]
        except Exception as e:
            logger.error(f"Anthropic structured generation error: {e}")
            raise

    async def close(self) -> None:
        """Close the client (no-op for Anthropic)."""
        self._initialized = False
        self._client = None
