# SPDX-License-Identifier: MIT
"""Pluggable web search client with uniform result schema and receipt/metrics support."""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SearchHit:
    """Uniform search result structure."""

    title: str
    url: str
    snippet: str
    source: str  # "serpapi"|"bing"|"duckduckgo"|"local"


async def _search_serpapi(client: httpx.AsyncClient, query: str, top_k: int) -> list[SearchHit]:
    """Search using SerpAPI."""
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        return []

    try:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={"q": query, "api_key": serpapi_key, "num": top_k},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        hits = []
        for item in (data.get("organic_results") or [])[:top_k]:
            hits.append(
                SearchHit(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="serpapi",
                )
            )
        return hits
    except Exception:
        return []


async def _search_bing(client: httpx.AsyncClient, query: str, top_k: int) -> list[SearchHit]:
    """Search using Bing."""
    bing_key = os.getenv("BING_SEARCH_KEY")
    if not bing_key:
        return []

    try:
        headers = {"Ocp-Apim-Subscription-Key": bing_key}
        response = await client.get(
            "https://api.bing.microsoft.com/v7.0/search",
            headers=headers,
            params={"q": query, "count": top_k},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        hits = []
        web_pages = data.get("webPages", {}).get("value", [])
        for item in web_pages[:top_k]:
            hits.append(
                SearchHit(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source="bing",
                )
            )
        return hits
    except Exception:
        return []


async def _search_duckduckgo(client: httpx.AsyncClient, query: str, top_k: int) -> list[SearchHit]:
    """Search using DuckDuckGo HTML (no API key needed)."""
    try:
        from bs4 import BeautifulSoup

        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}

        response = await client.post(url, data=params, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        hits = []

        for result in soup.select(".result")[:top_k]:
            title_elem = result.select_one(".result__title")
            url_elem = result.select_one(".result__url")
            snippet_elem = result.select_one(".result__snippet")

            if title_elem and url_elem:
                hits.append(
                    SearchHit(
                        title=title_elem.get_text(strip=True),
                        url=url_elem.get("href", ""),  # type: ignore[arg-type]
                        snippet=(snippet_elem.get_text(strip=True) if snippet_elem else ""),
                        source="duckduckgo",
                    )
                )
        return hits
    except Exception as e:
        logger.debug(f"DuckDuckGo search failed: {e}")
        return []


async def search_web(query: str, top_k: int = 5) -> list[SearchHit]:
    """
    Search the web using available providers.

    Tries providers in order: SERPAPI, Bing, DuckDuckGo, fallback to empty.

    Args:
        query: Search query string
        top_k: Maximum results to return

    Returns:
        List of SearchHit results (may be empty if no provider configured)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try SERPAPI first
        hits = await _search_serpapi(client, query, top_k)
        if hits:
            return hits

        # Try Bing search
        hits = await _search_bing(client, query, top_k)
        if hits:
            return hits

        # Fallback to DuckDuckGo
        hits = await _search_duckduckgo(client, query, top_k)
        return hits


async def web_search(
    query: str,
    max_results: int = 5,
    timeout: float = 10.0,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Perform web search (convenience function) with metrics and receipts.

    This is the main entry point for agents.

    Args:
        query: Search query
        max_results: Maximum number of results
        timeout: Request timeout
        correlation_id: Optional correlation ID to link receipts (Principle 2)

    Returns:
        List of search results (dicts)
    """
    # Emit metrics
    start_time = time.time()

    try:
        from kagami_observability.metrics import get_counter, get_histogram

        web_search_total = get_counter(
            "kagami_web_search_total", "Total web searches performed", ["status"]
        )
        web_search_duration = get_histogram(
            "kagami_web_search_duration_seconds",
            "Web search duration in seconds",
            ["status"],
        )
    except Exception:
        web_search_total = None
        web_search_duration = None

    # Emit PLAN receipt
    cid = correlation_id or f"web_search_{int(time.time() * 1000)}"

    try:
        from kagami.core.receipts import emit_receipt

        emit_receipt(
            correlation_id=cid,
            action="web.search",
            app="research",
            event_name="web.search.plan",
            event_data={"query": query, "max_results": max_results},
            status="planning",
            phase="plan",
        )
    except Exception as e:
        logger.warning(f"Receipt emission failed: {e}")

    # Execute search
    results: list[dict[str, Any]] = []
    error_msg = None

    try:
        # Directly await the async function
        hits = await search_web(query, max_results)

        results = [
            {"title": h.title, "url": h.url, "snippet": h.snippet, "source": h.source} for h in hits
        ]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Web search failed: {e}")

    # Emit metrics
    duration = time.time() - start_time
    status = "success" if results and not error_msg else "error" if error_msg else "no_results"

    if web_search_total:
        web_search_total.labels(status=status).inc()
    if web_search_duration:
        web_search_duration.labels(status=status).observe(duration)

    # Emit EXECUTE and VERIFY receipts
    try:
        emit_receipt(
            correlation_id=cid,
            action="web.search",
            app="research",
            event_name="web.search.execute",
            event_data={"query": query, "result_count": len(results), "error": error_msg},
            status=status,
            phase="execute",
        )

        emit_receipt(
            correlation_id=cid,
            action="web.search",
            app="research",
            event_name="web.search.verify",
            event_data={
                "query": query,
                "result_count": len(results),
                "duration_ms": duration * 1000,
                "verified": error_msg is None,
                "error": error_msg,
            },
            status=status,
            phase="verify",
        )
    except Exception as e:
        logger.error(f"Receipt emission failed: {e}")

    if error_msg:
        raise RuntimeError(f"Web search failed: {error_msg}")

    return results
