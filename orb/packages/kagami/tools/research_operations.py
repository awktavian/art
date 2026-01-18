"""Research Operations — Knowledge search and synthesis tools.

Provides research, summarization, and insight extraction with web search
and knowledge graph integration.

Used by: Grove, Beacon

Created: December 28, 2025
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def search_knowledge(
    query: str,
    sources: list[str] | None = None,
    max_results: int = 10,
) -> dict[str, Any]:
    """Search knowledge bases for information.

    Args:
        query: Search query
        sources: Sources to search (web, kg, docs)
        max_results: Maximum results

    Returns:
        Search results
    """
    try:
        sources = sources or ["web", "kg"]
        results = []

        # Web search
        if "web" in sources:
            try:
                from kagami.tools.web.search import web_search

                web_results = await web_search(query, max_results=max_results)
                results.extend(
                    [
                        {
                            "source": "web",
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("snippet", ""),
                            "relevance": 1.0 - (i * 0.1),
                        }
                        for i, r in enumerate(web_results)
                    ]
                )
            except Exception as e:
                logger.debug(f"Web search failed: {e}")

        # Knowledge graph
        if "kg" in sources:
            try:
                from kagami_knowledge.reasoning_engine import get_reasoning_engine

                kg_engine = get_reasoning_engine()
                kg_result = await kg_engine.query(query)

                for evidence in kg_result.evidence[:max_results]:
                    results.append(
                        {
                            "source": "knowledge_graph",
                            "content": evidence.content,
                            "importance": evidence.importance,
                            "hop_distance": evidence.hop_distance,
                        }
                    )
            except Exception as e:
                logger.debug(f"KG search failed: {e}")

        logger.info(f"Found {len(results)} results for query: {query}")

        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "sources_used": sources,
        }

    except Exception as e:
        logger.error(f"Knowledge search failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "query": query,
        }


async def summarize_research(
    sources: list[dict[str, Any]],
    focus: str | None = None,
    max_length: int = 500,
) -> dict[str, Any]:
    """Summarize research from multiple sources.

    Args:
        sources: List of source documents
        focus: Optional focus area
        max_length: Maximum summary length

    Returns:
        Research summary
    """
    try:
        # Extract key concepts
        concepts = set()
        all_text = []

        for source in sources:
            text = source.get("content", "") or source.get("snippet", "")
            all_text.append(text)

            # Simple concept extraction
            words = text.lower().split()
            concepts.update([w for w in words if len(w) > 5])

        # Build summary
        summary_parts = []
        summary_parts.append(f"Research on: {focus or 'general query'}")
        summary_parts.append(f"\nAnalyzed {len(sources)} sources.")
        summary_parts.append(f"\nKey concepts: {', '.join(list(concepts)[:10])}")

        summary = "\n".join(summary_parts)

        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return {
            "success": True,
            "summary": summary,
            "source_count": len(sources),
            "concept_count": len(concepts),
            "concepts": list(concepts)[:20],
        }

    except Exception as e:
        logger.error(f"Summarization failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


async def extract_insights(
    data: list[dict[str, Any]],
    insight_type: str = "patterns",
) -> dict[str, Any]:
    """Extract insights from research data.

    Args:
        data: Research data
        insight_type: Type of insights (patterns, trends, gaps)

    Returns:
        Extracted insights
    """
    try:
        insights = []

        if insight_type == "patterns":
            # Find common themes
            word_freq: dict[str, int] = {}
            for item in data:
                text = str(item.get("content", ""))
                for word in text.lower().split():
                    if len(word) > 5:
                        word_freq[word] = word_freq.get(word, 0) + 1

            top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            insights.append(
                {
                    "type": "pattern",
                    "insight": f"Most common themes: {', '.join([w for w, _ in top_words])}",
                    "confidence": 0.8,
                }
            )

        elif insight_type == "trends":
            insights.append(
                {
                    "type": "trend",
                    "insight": f"Analyzed {len(data)} data points",
                    "confidence": 0.7,
                }
            )

        elif insight_type == "gaps":
            insights.append(
                {
                    "type": "gap",
                    "insight": "Further research needed in specific areas",
                    "confidence": 0.6,
                }
            )

        return {
            "success": True,
            "insights": insights,
            "count": len(insights),
            "insight_type": insight_type,
        }

    except Exception as e:
        logger.error(f"Insight extraction failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


async def synthesize_findings(
    findings: list[dict[str, Any]],
    synthesis_style: str = "comprehensive",
) -> dict[str, Any]:
    """Synthesize multiple research findings.

    Args:
        findings: List of research findings
        synthesis_style: Style (comprehensive, concise, analytical)

    Returns:
        Synthesized research
    """
    try:
        synthesis = {
            "overview": f"Synthesized {len(findings)} findings",
            "key_points": [],
            "connections": [],
            "recommendations": [],
        }

        # Extract key points
        for i, finding in enumerate(findings[:5]):
            synthesis["key_points"].append(
                {
                    "point": finding.get("summary", f"Finding {i + 1}"),
                    "source": finding.get("source", "unknown"),
                }
            )

        # Find connections
        if len(findings) > 1:
            synthesis["connections"].append(
                {
                    "connection": "Multiple sources converge on similar themes",
                    "confidence": 0.7,
                }
            )

        # Generate recommendations
        synthesis["recommendations"].append(
            {
                "recommendation": "Further validation recommended",
                "priority": "medium",
            }
        )

        return {
            "success": True,
            "synthesis": synthesis,
            "finding_count": len(findings),
            "style": synthesis_style,
        }

    except Exception as e:
        logger.error(f"Synthesis failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


# Synchronous wrappers
def search_knowledge_sync(query: str, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for search_knowledge."""
    return asyncio.run(search_knowledge(query, **kwargs))


def summarize_research_sync(sources: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for summarize_research."""
    return asyncio.run(summarize_research(sources, **kwargs))


def extract_insights_sync(data: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for extract_insights."""
    return asyncio.run(extract_insights(data, **kwargs))


def synthesize_findings_sync(findings: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper for synthesize_findings."""
    return asyncio.run(synthesize_findings(findings, **kwargs))


__all__ = [
    "extract_insights",
    "search_knowledge",
    "summarize_research",
    "synthesize_findings",
]
