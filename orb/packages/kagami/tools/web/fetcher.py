# SPDX-License-Identifier: MIT
"""Safe HTTP fetcher for web research (no robots.txt compliance per user directive)."""

import hashlib
import time
from dataclasses import dataclass

import requests

DEFAULT_UA = "K os-ResearchBot/1.0 (+https://github.com/awkronos/kagami)"
MAX_BYTES = 2_000_000  # 2MB cap
DEFAULT_TIMEOUT = 15.0


@dataclass
class FetchResult:
    """Result of a web fetch operation."""

    url: str
    status: int
    content_type: str
    text: str
    sha256: str
    fetch_time_ms: float


def _extract_text(content: str) -> str:
    """Extract readable text from HTML content."""
    trafilatura = None
    try:
        import trafilatura  # type: ignore[no-redef]

        extracted = trafilatura.extract(content)  # type: ignore[attr-defined]
        return extracted if extracted else content
    except ImportError:
        # Fallback: return raw content if trafilatura not installed
        trafilatura = None
        return content
    except Exception:
        return content


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT, ua: str = DEFAULT_UA) -> FetchResult:
    """
    Fetch a URL with safety limits.

    Args:
        url: Target URL
        timeout: Request timeout in seconds
        ua: User-Agent string

    Returns:
        FetchResult with extracted text and metadata

    Raises:
        requests.HTTPError: On HTTP errors
        requests.Timeout: On timeout
    """
    start_time = time.time()

    headers = {"User-Agent": ua}
    response = requests.get(
        url, timeout=timeout, headers=headers, stream=True, allow_redirects=True
    )
    response.raise_for_status()

    # Read up to MAX_BYTES
    content_bytes = response.raw.read(MAX_BYTES, decode_content=True)
    response.close()

    # Decode and extract text
    content_str = content_bytes.decode(errors="ignore")
    text = _extract_text(content_str)

    # Compute hash of original content
    content_hash = hashlib.sha256(content_bytes).hexdigest()

    fetch_time_ms = (time.time() - start_time) * 1000

    return FetchResult(
        url=response.url,  # Final URL after redirects
        status=response.status_code,
        content_type=response.headers.get("Content-Type", ""),
        text=text,
        sha256=content_hash,
        fetch_time_ms=fetch_time_ms,
    )
