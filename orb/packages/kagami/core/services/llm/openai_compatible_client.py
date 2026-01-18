"""OpenAI-compatible HTTP client for local/remote inference servers.

This client is intentionally lightweight and uses `httpx` directly to avoid
hard dependencies on the `openai` Python SDK while still speaking the common
OpenAI-compatible REST shape (vLLM, SGLang, LMDeploy, etc.).

Primary use-case for kagamiOS:
- Run DeepSeek-V3.2-Exp behind vLLM/SGLang and point Kagami at it.

Refs:
- DeepSeek-V3.2-Exp HF card: https://huggingface.co/deepseek-ai/DeepSeek-V3.2-Exp
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _chat_completions_url(base_url: str) -> str:
    """Return full URL for /v1/chat/completions given a base URL.

    Accepts either:
    - http://host:port
    - http://host:port/v1
    """

    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("base_url is required for OpenAI-compatible client") from None
    if b.endswith("/v1"):
        return f"{b}/chat/completions"
    return f"{b}/v1/chat/completions"


def _extract_json_snippet(text: str) -> str | None:
    """Best-effort extraction of a top-level JSON object/array from text."""

    if not isinstance(text, str) or not text:
        return None
    s = text.strip()
    # Prefer object, then array
    obj_start = s.find("{")
    obj_end = s.rfind("}")
    arr_start = s.find("[")
    arr_end = s.rfind("]")
    if obj_start != -1 and obj_end > obj_start:
        return s[obj_start : obj_end + 1]
    if arr_start != -1 and arr_end > arr_start:
        return s[arr_start : arr_end + 1]
    return None


@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout_s: float = 60.0


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client (chat completions)."""

    def __init__(self, config: OpenAICompatibleConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        self._client = httpx.AsyncClient(timeout=float(self.config.timeout_s), headers=headers)
        self._initialized = True

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
        self._client = None
        self._initialized = False

    async def generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str:
        if not self._initialized or self._client is None:
            await self.initialize()
        assert self._client is not None

        url = _chat_completions_url(self.config.base_url)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": str(prompt)}],
            "temperature": float(max(0.0, temperature)),
            "max_tokens": int(max(1, max_tokens)),
            "stream": False,
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        # OpenAI-compatible response shape
        try:
            choice0 = (data.get("choices") or [])[0]
            msg = choice0.get("message") if isinstance(choice0, dict) else None
            if isinstance(msg, dict) and msg.get("content") is not None:
                return str(msg.get("content") or "").strip()
            if isinstance(choice0, dict) and choice0.get("text") is not None:
                return str(choice0.get("text") or "").strip()
        except Exception:
            pass

        # Last resort: stringify whole payload
        return str(data).strip()

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        max_tokens: int,
        temperature: float,
    ) -> T:
        """Generate structured output by prompting for JSON and validating with Pydantic."""

        schema = {}
        try:
            schema = response_model.model_json_schema()
        except Exception:
            schema = {"type": "object"}

        system = (
            "Return ONLY valid JSON. Do not include markdown fences or extra text. "
            "The JSON MUST conform to this JSON Schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
        merged_prompt = f"{system}\n\n{prompt}"
        text = await self.generate_text(
            prompt=merged_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        snippet = _extract_json_snippet(text) or text
        try:
            data = json.loads(snippet)
        except Exception as e:
            # Try a second pass: remove leading/trailing junk if present
            snippet2 = _extract_json_snippet(text)
            if snippet2 and snippet2 != snippet:
                data = json.loads(snippet2)
            else:
                raise RuntimeError(f"Structured JSON parse failed: {e}") from e

        try:
            return response_model.model_validate(data)
        except Exception as e:
            raise RuntimeError(f"Structured validation failed: {e}") from e


__all__ = ["OpenAICompatibleClient", "OpenAICompatibleConfig"]
