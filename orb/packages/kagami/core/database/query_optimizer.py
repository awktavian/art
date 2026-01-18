"""Database Query Optimization and Profiling Tools.

Provides comprehensive tools for:
1. Query profiling and analysis
2. Automatic index recommendations
3. Query plan visualization
4. Connection pool optimization
5. Query result caching integration

Target: 50%+ improvement in database query performance.

Colony: Nexus (e₄) - Integration
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueryType(str, Enum):
    """Type of database query."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"
    UNKNOWN = "UNKNOWN"


@dataclass
class QueryStats:
    """Statistics for a single query."""

    query: str
    query_type: QueryType
    execution_time: float
    row_count: int = 0
    cache_hit: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query[:200],  # Truncate for display
            "query_type": self.query_type.value,
            "execution_time_ms": self.execution_time * 1000,
            "row_count": self.row_count,
            "cache_hit": self.cache_hit,
            "timestamp": self.timestamp,
        }


@dataclass
class QueryProfile:
    """Profile for query performance."""

    query_hash: str
    query_template: str
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    avg_time: float = 0.0
    total_rows: int = 0
    cache_hits: int = 0

    def update(self, stats: QueryStats) -> None:
        """Update profile with new stats."""
        self.call_count += 1
        self.total_time += stats.execution_time
        self.min_time = min(self.min_time, stats.execution_time)
        self.max_time = max(self.max_time, stats.execution_time)
        self.avg_time = self.total_time / self.call_count
        self.total_rows += stats.row_count
        if stats.cache_hit:
            self.cache_hits += 1

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        return self.cache_hits / self.call_count if self.call_count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query_template": self.query_template[:200],
            "call_count": self.call_count,
            "total_time_ms": self.total_time * 1000,
            "min_time_ms": self.min_time * 1000,
            "max_time_ms": self.max_time * 1000,
            "avg_time_ms": self.avg_time * 1000,
            "total_rows": self.total_rows,
            "cache_hit_rate": self.cache_hit_rate,
        }


@dataclass
class IndexRecommendation:
    """Recommendation for creating an index."""

    table_name: str
    columns: list[str]
    reason: str
    estimated_improvement: float  # Percentage
    query_examples: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "table_name": self.table_name,
            "columns": self.columns,
            "reason": self.reason,
            "estimated_improvement_pct": self.estimated_improvement,
            "query_examples": [q[:100] for q in self.query_examples],
        }


class QueryProfiler:
    """Profiles and analyzes database queries."""

    def __init__(self, enable_profiling: bool = True):
        """Initialize query profiler.

        Args:
            enable_profiling: Enable query profiling
        """
        self.enable_profiling = enable_profiling
        self._profiles: dict[str, QueryProfile] = {}
        self._recent_queries: list[QueryStats] = []
        self._max_recent_queries = 1000
        self._slow_query_threshold = 1.0  # 1 second
        self._lock = asyncio.Lock()

    def _extract_query_type(self, query: str) -> QueryType:
        """Extract query type from SQL."""
        query_upper = query.strip().upper()
        for qtype in QueryType:
            if qtype != QueryType.UNKNOWN and query_upper.startswith(qtype.value):
                return qtype
        return QueryType.UNKNOWN

    def _normalize_query(self, query: str) -> str:
        """Normalize query for profiling (remove parameters)."""
        # Replace numbers with ?
        normalized = re.sub(r"\b\d+\b", "?", query)
        # Replace quoted strings with ?
        normalized = re.sub(r"'[^']*'", "?", normalized)
        normalized = re.sub(r'"[^"]*"', "?", normalized)
        # Collapse whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _hash_query(self, query: str) -> str:
        """Generate hash for query."""
        import hashlib

        return hashlib.md5(query.encode()).hexdigest()[:16]

    async def record_query(
        self,
        query: str,
        execution_time: float,
        row_count: int = 0,
        cache_hit: bool = False,
    ) -> None:
        """Record query execution.

        Args:
            query: SQL query
            execution_time: Execution time in seconds
            row_count: Number of rows returned/affected
            cache_hit: Whether result was from cache
        """
        if not self.enable_profiling:
            return

        # Create stats
        stats = QueryStats(
            query=query,
            query_type=self._extract_query_type(query),
            execution_time=execution_time,
            row_count=row_count,
            cache_hit=cache_hit,
        )

        async with self._lock:
            # Add to recent queries
            self._recent_queries.append(stats)
            if len(self._recent_queries) > self._max_recent_queries:
                self._recent_queries.pop(0)

            # Update profile
            normalized = self._normalize_query(query)
            query_hash = self._hash_query(normalized)

            if query_hash not in self._profiles:
                self._profiles[query_hash] = QueryProfile(
                    query_hash=query_hash,
                    query_template=normalized,
                )

            self._profiles[query_hash].update(stats)

        # Log slow queries
        if execution_time > self._slow_query_threshold:
            logger.warning(f"Slow query detected ({execution_time:.2f}s): {query[:100]}")

    async def get_slow_queries(
        self, min_time: float = 1.0, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get slow queries.

        Args:
            min_time: Minimum execution time in seconds
            limit: Maximum number of results

        Returns:
            List of slow query profiles
        """
        async with self._lock:
            slow = [p for p in self._profiles.values() if p.avg_time >= min_time]
            slow.sort(key=lambda x: x.avg_time, reverse=True)
            return [p.to_dict() for p in slow[:limit]]

    async def get_most_frequent_queries(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most frequently executed queries.

        Args:
            limit: Maximum number of results

        Returns:
            List of query profiles sorted by call count
        """
        async with self._lock:
            frequent = sorted(
                self._profiles.values(),
                key=lambda x: x.call_count,
                reverse=True,
            )
            return [p.to_dict() for p in frequent[:limit]]

    async def get_total_query_time_by_type(self) -> dict[str, float]:
        """Get total query time broken down by query type.

        Returns:
            Dictionary mapping query type to total time
        """
        result: dict[str, float] = {}

        async with self._lock:
            for stats in self._recent_queries:
                qtype = stats.query_type.value
                result[qtype] = result.get(qtype, 0.0) + stats.execution_time

        return result

    async def get_recommendations(self) -> list[IndexRecommendation]:
        """Generate index recommendations based on query patterns.

        Returns:
            List of index recommendations
        """
        recommendations: list[IndexRecommendation] = []

        async with self._lock:
            # Analyze slow SELECT queries
            slow_selects = [
                p
                for p in self._profiles.values()
                if p.avg_time > 0.5 and "SELECT" in p.query_template.upper()
            ]

            for profile in slow_selects:
                # Extract table and WHERE clause columns
                tables = self._extract_tables(profile.query_template)
                where_columns = self._extract_where_columns(profile.query_template)

                if tables and where_columns:
                    # Recommend composite index
                    for table in tables:
                        recommendations.append(
                            IndexRecommendation(
                                table_name=table,
                                columns=where_columns[:3],  # Max 3 columns
                                reason=f"Slow query with {profile.call_count} executions, "
                                f"avg time {profile.avg_time:.2f}s",
                                estimated_improvement=min(70.0, profile.avg_time * 10),
                                query_examples=[profile.query_template],
                            )
                        )

        return recommendations

    def _extract_tables(self, query: str) -> list[str]:
        """Extract table names from query."""
        # Simple regex-based extraction
        from_match = re.search(r"FROM\s+(\w+)", query, re.IGNORECASE)
        join_matches = re.findall(r"JOIN\s+(\w+)", query, re.IGNORECASE)

        tables = []
        if from_match:
            tables.append(from_match.group(1))
        tables.extend(join_matches)

        return tables

    def _extract_where_columns(self, query: str) -> list[str]:
        """Extract columns from WHERE clause."""
        where_match = re.search(r"WHERE\s+(.*?)(?:GROUP|ORDER|LIMIT|$)", query, re.IGNORECASE)
        if not where_match:
            return []

        where_clause = where_match.group(1)
        # Extract column names (before =, <, >, etc.)
        columns = re.findall(r"(\w+)\s*(?:=|<|>|IN|LIKE)", where_clause, re.IGNORECASE)
        return list(dict[str, Any].fromkeys(columns))  # Remove duplicates, preserve order

    async def get_stats(self) -> dict[str, Any]:
        """Get overall profiler statistics.

        Returns:
            Dictionary with profiler stats
        """
        async with self._lock:
            total_queries = len(self._recent_queries)
            total_profiles = len(self._profiles)
            total_time = sum(q.execution_time for q in self._recent_queries)
            cache_hits = sum(1 for q in self._recent_queries if q.cache_hit)

            return {
                "total_queries": total_queries,
                "total_profiles": total_profiles,
                "total_time_ms": total_time * 1000,
                "avg_time_ms": (total_time / total_queries * 1000) if total_queries > 0 else 0,
                "cache_hit_rate": cache_hits / total_queries if total_queries > 0 else 0,
                "slow_queries": len(await self.get_slow_queries()),
            }

    async def reset(self) -> None:
        """Reset profiler statistics."""
        async with self._lock:
            self._profiles.clear()
            self._recent_queries.clear()


class ConnectionPoolOptimizer:
    """Optimizes database connection pool settings."""

    @staticmethod
    def calculate_pool_size(
        max_concurrent_requests: int = 100,
        avg_query_time_ms: float = 50,
        target_wait_time_ms: float = 10,
    ) -> dict[str, int]:
        """Calculate optimal connection pool size.

        Args:
            max_concurrent_requests: Maximum concurrent database requests
            avg_query_time_ms: Average query execution time
            target_wait_time_ms: Target wait time for connections

        Returns:
            Dictionary with pool_size and max_overflow
        """
        # Use Little's Law: L = λW
        # L = number of connections needed
        # λ = arrival rate (requests per second)
        # W = average service time (seconds)

        avg_query_time_s = avg_query_time_ms / 1000
        arrival_rate = max_concurrent_requests / avg_query_time_s

        # Calculate pool size with safety margin
        pool_size = int(arrival_rate * avg_query_time_s * 1.5)

        # Clamp to reasonable values
        pool_size = max(5, min(pool_size, 50))
        max_overflow = int(pool_size * 0.5)

        return {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_recycle": 3600,  # 1 hour
            "pool_pre_ping": True,
        }

    @staticmethod
    def create_optimized_engine(
        database_url: str,
        max_concurrent_requests: int = 100,
        **kwargs: Any,
    ) -> AsyncEngine:
        """Create optimized async database engine.

        Args:
            database_url: Database connection URL
            max_concurrent_requests: Expected max concurrent requests
            **kwargs: Additional engine parameters

        Returns:
            Configured async engine
        """
        pool_config = ConnectionPoolOptimizer.calculate_pool_size(max_concurrent_requests)

        engine = create_async_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_config["pool_size"],
            max_overflow=pool_config["max_overflow"],
            pool_recycle=pool_config["pool_recycle"],
            pool_pre_ping=pool_config["pool_pre_ping"],
            echo=kwargs.get("echo", False),
            **kwargs,
        )

        logger.info(
            f"Created optimized engine: pool_size={pool_config['pool_size']}, "
            f"max_overflow={pool_config['max_overflow']}"
        )

        return engine


class QueryOptimizer:
    """Automatically optimizes database queries."""

    def __init__(self, profiler: QueryProfiler):
        """Initialize query optimizer.

        Args:
            profiler: Query profiler instance
        """
        self.profiler = profiler

    async def optimize_query(self, query: str) -> str:
        """Suggest optimizations for a query.

        Args:
            query: SQL query to optimize

        Returns:
            Optimized query (or original if no optimizations found)
        """
        optimized = query

        # Add LIMIT if SELECT without LIMIT
        if "SELECT" in query.upper() and "LIMIT" not in query.upper() and "WHERE" in query.upper():
            optimized += " LIMIT 1000"
            logger.debug("Added LIMIT to unbounded SELECT")

        # Suggest using EXISTS instead of COUNT
        if re.search(r"COUNT\(\*\)\s*>\s*0", query, re.IGNORECASE):
            logger.info("Consider using EXISTS instead of COUNT(*) > 0 for better performance")

        # Suggest avoiding SELECT *
        if re.search(r"SELECT\s+\*", query, re.IGNORECASE):
            logger.info("Consider selecting only needed columns instead of SELECT *")

        return optimized


# Decorator for automatic query profiling


def profile_query(
    profiler: QueryProfiler,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to automatically profile database queries.

    Args:
        profiler: Query profiler instance

    Example:
        profiler = QueryProfiler()

        @profile_query(profiler)
        async def get_users(db: AsyncSession) -> list[User]:
            result = await db.execute(select(User))
            return result.scalars().all()
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Extract query from function
                query = func.__name__
                row_count = 0
                if hasattr(result, "__len__"):
                    try:
                        row_count = len(result)
                    except TypeError:
                        pass

                await profiler.record_query(
                    query=query,
                    execution_time=execution_time,
                    row_count=row_count,
                )

                return result

            except Exception:
                execution_time = time.time() - start_time
                await profiler.record_query(
                    query=func.__name__,
                    execution_time=execution_time,
                )
                raise

        return wrapper

    return decorator


# Global profiler instance
_global_profiler: QueryProfiler | None = None


def get_global_profiler() -> QueryProfiler:
    """Get or create global query profiler."""
    global _global_profiler

    if _global_profiler is None:
        _global_profiler = QueryProfiler()

    return _global_profiler
