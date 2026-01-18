"""Client factory registry for LLM service.

Extracts client creation logic from service.py to reduce cyclomatic complexity.
Each factory handles a single provider with CC < 10.

PROVIDERS (Dec 2024):
- local/transformers: HuggingFace transformers (Qwen2.5 series)
- api: OpenAI-compatible (vLLM, SGLang, LMDeploy)
- deepseek: DeepSeek Cloud API (api.deepseek.com)
- anthropic: Anthropic Claude API (api.anthropic.com)
- gemini: Google Gemini API
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

# DeepSeek API configuration
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-chat"  # V3 is served as deepseek-chat
DEEPSEEK_CODER_MODEL = "deepseek-coder"

# Anthropic Claude API configuration
ANTHROPIC_API_BASE = "https://api.anthropic.com"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"  # Claude Sonnet 4
ANTHROPIC_OPUS_MODEL = "claude-opus-4-20250514"  # Claude Opus 4


class ClientFactory(ABC):
    """Base factory for creating LLM clients."""

    @abstractmethod
    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create and initialize a client.

        Args:
            model: Model name/identifier
            structured: Whether to use structured output
            base_url: Optional base URL for API clients

        Returns:
            Initialized client instance

        Raises:
            RuntimeError: If client creation fails
        """
        ...


class OpenAICompatibleFactory(ClientFactory):
    """Factory for OpenAI-compatible API clients."""

    def _get_base_url(self, base_url: str | None, structured: bool) -> str | None:
        """Get API base URL from parameters or environment."""
        result = (
            base_url
            or os.getenv("KAGAMI_LLM_API_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("OPENAI_API_BASE_URL")
        )
        if not structured and not result:
            result = "https://api.openai.com/v1"
        return result

    def _get_model(self, model: str | None) -> str:
        """Get model name from parameters or environment."""
        return (
            model
            or os.getenv("KAGAMI_LLM_API_MODEL")
            or os.getenv("OPENAI_MODEL")
            or "deepseek-ai/DeepSeek-V3"  # Updated: V3 is the Dec 2024 release
        )

    def _get_api_key(self) -> str | None:
        """Get API key from environment."""
        key = os.getenv("KAGAMI_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        return key.strip() if isinstance(key, str) else None

    def _get_timeout(self) -> float:
        """Get timeout from environment."""
        return float(os.getenv("KAGAMI_LLM_API_TIMEOUT_S", "60"))

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create OpenAI-compatible client."""
        from kagami.core.services.llm.openai_compatible_client import (
            OpenAICompatibleClient,
            OpenAICompatibleConfig,
        )

        api_base = self._get_base_url(base_url, structured)
        if structured and not api_base:
            raise RuntimeError("Structured API client requires base_url")

        client = OpenAICompatibleClient(
            OpenAICompatibleConfig(
                base_url=api_base,  # type: ignore[arg-type]
                model=self._get_model(model),
                api_key=self._get_api_key(),
                timeout_s=self._get_timeout(),
            )
        )
        await client.initialize()
        return client


class DeepSeekFactory(ClientFactory):
    """Factory for DeepSeek Cloud API clients.

    DeepSeek V3 (Dec 26, 2024):
    - 671B parameters (37B active via MoE)
    - MIT Licensed, open weights
    - API: api.deepseek.com (OpenAI-compatible)
    - Models: deepseek-chat (V3), deepseek-coder
    - 128K context, $0.14/$0.28 per 1M tokens (very cheap)
    """

    def _get_base_url(self) -> str:
        """Get DeepSeek API base URL."""
        return os.getenv("DEEPSEEK_API_BASE", DEEPSEEK_API_BASE)

    def _get_model(self, model: str | None) -> str:
        """Get DeepSeek model name."""
        if model:
            return model
        # Default to deepseek-chat (V3) for general, coder for code tasks
        return os.getenv("DEEPSEEK_MODEL", DEEPSEEK_DEFAULT_MODEL)

    def _get_api_key(self) -> str | None:
        """Get DeepSeek API key."""
        key = os.getenv("DEEPSEEK_API_KEY")
        return key.strip() if isinstance(key, str) else None

    def _get_timeout(self) -> float:
        """Get timeout for DeepSeek API."""
        return float(os.getenv("DEEPSEEK_TIMEOUT_S", "120"))  # Higher for reasoning

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create DeepSeek API client (uses OpenAI-compatible interface)."""
        from kagami.core.services.llm.openai_compatible_client import (
            OpenAICompatibleClient,
            OpenAICompatibleConfig,
        )

        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError(
                "DeepSeek API key not configured. Set DEEPSEEK_API_KEY environment variable. "
                "Get key at: https://platform.deepseek.com/"
            )

        client = OpenAICompatibleClient(
            OpenAICompatibleConfig(
                base_url=base_url or self._get_base_url(),
                model=self._get_model(model),
                api_key=api_key,
                timeout_s=self._get_timeout(),
            )
        )
        await client.initialize()
        logger.info(f"✅ DeepSeek client initialized (model: {self._get_model(model)})")
        return client


class AnthropicFactory(ClientFactory):
    """Factory for Anthropic Claude API clients.

    Claude Models (Dec 2024):
    - claude-sonnet-4-20250514: Best balance of speed/quality ($3/$15 per 1M)
    - claude-opus-4-20250514: Highest quality ($15/$75 per 1M)
    - claude-3-5-haiku-20241022: Fast/cheap ($0.25/$1.25 per 1M)

    200K context window, excellent for complex reasoning.
    """

    def _get_api_key(self) -> str | None:
        """Get Anthropic API key."""
        key = os.getenv("ANTHROPIC_API_KEY")
        return key.strip() if isinstance(key, str) else None

    def _get_model(self, model: str | None) -> str:
        """Get Claude model name."""
        if model:
            return model
        return os.getenv("ANTHROPIC_MODEL", ANTHROPIC_DEFAULT_MODEL)

    def _get_timeout(self) -> float:
        """Get timeout for Anthropic API."""
        return float(os.getenv("ANTHROPIC_TIMEOUT_S", "120"))

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create Anthropic client."""
        try:
            import anthropic

            del anthropic  # Only checking availability
        except ImportError as err:
            raise RuntimeError(
                "Anthropic client not installed. Run: pip install anthropic"
            ) from err

        api_key = self._get_api_key()
        if not api_key:
            raise RuntimeError(
                "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable. "
                "Get key at: https://console.anthropic.com/settings/keys"
            )

        # Create Anthropic client wrapper
        from kagami.core.services.llm.anthropic_client import AnthropicClient

        client = AnthropicClient(
            api_key=api_key,
            model=self._get_model(model),
            timeout=self._get_timeout(),
        )
        await client.initialize()
        logger.info(f"✅ Anthropic client initialized (model: {self._get_model(model)})")
        return client


class StructuredOutputFactory(ClientFactory):
    """Factory for local structured output clients."""

    # Optimized model map - M3 Ultra 512GB (Dec 2024)
    # Maps Ollama model names to HuggingFace equivalents
    MODEL_MAP = {
        # Qwen series (primary)
        "qwen3:14b": "Qwen/Qwen2.5-14B-Instruct",
        "qwen3:72b": "Qwen/Qwen2.5-72B-Instruct",
        "qwen3-coder:32b": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "qwen3-coder:30b": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "qwen3:1.7b": "Qwen/Qwen2.5-1.5B-Instruct",
        "qwen3:7b": "Qwen/Qwen2.5-7B-Instruct",
        "qwen3-coder:14b": "Qwen/Qwen2.5-Coder-14B-Instruct",
        "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
        "qwen2.5:14b": "Qwen/Qwen2.5-14B-Instruct",
        "qwen2.5:32b": "Qwen/Qwen2.5-32B-Instruct",
        "qwen2.5:72b": "Qwen/Qwen2.5-72B-Instruct",
        # DeepSeek series (reasoning)
        "deepseek-r1:70b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-70B",
        "deepseek-r1:32b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
        "deepseek-r1:14b": "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        "deepseek-v3": "deepseek-ai/DeepSeek-V3",
        # Llama series
        "llama3.3:70b": "meta-llama/Llama-3.3-70B-Instruct",
        "llava:34b": "liuhaotian/llava-v1.6-34b",
        # Legacy (kept for compatibility)
        "qwen2:0.5b": "Qwen/Qwen2-0.5B-Instruct",
    }

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create structured output client."""
        from kagami.core.services.llm.structured_client import get_structured_client

        model_key = model.lower() if model else ""
        hf_model = self.MODEL_MAP.get(
            model_key,
            model or os.getenv("KAGAMI_BASE_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
        )
        logger.info(f"Using StructuredOutputClient with {hf_model}")

        client = get_structured_client(model_name=hf_model, device="auto")

        # Only fully initialize if not in fast startup mode
        if os.getenv("KAGAMI_FAST_STARTUP", "0") != "1":
            await client.initialize()

        return client


class GeminiFactory(ClientFactory):
    """Factory for Google Gemini clients."""

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create Gemini client."""
        from kagami.core.services.llm.gemini_client import GeminiClient

        model_name = model or "gemini-3-pro-preview"
        client = GeminiClient(model_name=model_name)
        await client.initialize()
        return client


class TransformersFactory(ClientFactory):
    """Factory for local transformers clients."""

    async def create(
        self,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """Create transformers client."""
        from kagami.core.services.llm.llm_providers import create_transformers_client

        # FIXED: Use consistent default model (Qwen2.5-14B works with stable transformers)
        model_name = (
            model
            or os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT")
            or os.getenv("KAGAMI_BASE_MODEL")
            or "Qwen/Qwen2.5-14B-Instruct"  # Changed from Qwen3-Coder which needs newer transformers
        )
        client = create_transformers_client(model_name)
        await client.initialize()
        return client


class ClientFactoryRegistry:
    """Registry for client factories.

    Supported providers (Dec 2024):
    - local/transformers/qwen: HuggingFace transformers (M3 Ultra optimized)
    - api: OpenAI-compatible (vLLM, SGLang, LMDeploy, etc.)
    - deepseek: DeepSeek Cloud API (api.deepseek.com) - V3 model
    - gemini: Google Gemini API
    - structured: Local structured output (Qwen2.5 series)
    """

    def __init__(self) -> None:
        self._factories: dict[str, ClientFactory] = {
            # Cloud providers
            "api": OpenAICompatibleFactory(),
            "anthropic": AnthropicFactory(),
            "claude": AnthropicFactory(),  # Alias
            "deepseek": DeepSeekFactory(),
            "gemini": GeminiFactory(),
            # Local providers (M3 Ultra 512GB optimized)
            "local": TransformersFactory(),
            "qwen": TransformersFactory(),
            "transformers": TransformersFactory(),
            "structured": StructuredOutputFactory(),
            # Aliases
            "openai": OpenAICompatibleFactory(),
            "openai_compat": OpenAICompatibleFactory(),
            "vllm": OpenAICompatibleFactory(),
            "sglang": OpenAICompatibleFactory(),
        }

    def get_factory(self, provider: str, structured: bool = False) -> ClientFactory:
        """Get factory for provider.

        Args:
            provider: Provider name (api, anthropic, gemini, local, etc.)
            structured: Whether structured output is requested

        Returns:
            ClientFactory instance

        Raises:
            RuntimeError: If provider not supported
        """
        # Cloud providers with native structured output support (via instructor)
        # These use their own generate_structured method, not local models
        NATIVE_STRUCTURED_PROVIDERS = {"api", "anthropic", "claude", "gemini", "deepseek"}

        # Special case: structured output request uses StructuredOutputFactory
        # ONLY for providers without native structured output support
        if structured and provider not in NATIVE_STRUCTURED_PROVIDERS:
            if "structured" not in self._factories:
                raise RuntimeError("Structured output not available")
            return self._factories["structured"]

        if provider not in self._factories:
            raise RuntimeError(
                f"Unsupported LLM provider: {provider}. "
                f"Use 'anthropic', 'api', 'gemini', 'deepseek', or 'local'."
            )

        return self._factories[provider]

    def register(self, provider: str, factory: ClientFactory) -> None:
        """Register a custom factory.

        Args:
            provider: Provider name
            factory: Factory instance
        """
        self._factories[provider] = factory


# Global registry instance (lazy initialization)
_REGISTRY: ClientFactoryRegistry | None = None


def get_registry() -> ClientFactoryRegistry:
    """Get the global factory registry (lazy initialization)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ClientFactoryRegistry()
    return _REGISTRY
