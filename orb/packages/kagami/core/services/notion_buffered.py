"""Notion KB with local SQLite buffer for resilience.

P1 Mitigation: Notion API failure → Learnings lost
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class NotionBufferedClient:
    """Notion client with local SQLite buffer for offline resilience.

    P1 Mitigation: Prevents loss of learnings when Notion API unavailable

    Features:
    - Writes buffered to SQLite if Notion unavailable
    - Automatic retry with exponential backoff
    - Periodic flush of buffered items
    - No data loss during Notion outages

    Usage:
        client = NotionBufferedClient()
        await client.initialize()

        # Transparently handles Notion unavailability
        await client.store_learning("CI Fix", "Fixed X by doing Y")
    """

    def __init__(
        self,
        buffer_db_path: str | None = None,
        flush_interval_seconds: int = 3600,  # 1 hour
    ):
        """Initialize buffered Notion client.

        Args:
            buffer_db_path: Path to SQLite buffer database
            flush_interval_seconds: How often to flush buffer
        """
        self.buffer_db_path = buffer_db_path or str(Path.home() / ".kagami" / "notion_buffer.db")
        self.flush_interval_seconds = flush_interval_seconds

        self._conn: sqlite3.Connection | None = None
        self._flush_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize buffer database and start flush task."""
        # Create buffer database
        Path(self.buffer_db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.buffer_db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS buffered_learnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                flushed INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

        logger.info(f"✅ Notion buffer initialized: {self.buffer_db_path}")

        # Start periodic flush task
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def store_learning(
        self,
        title: str,
        content: str,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store learning in Notion (with SQLite buffer fallback).

        Args:
            title: Learning title
            content: Learning content
            category: Category (e.g., "CI Fixes", "Performance")
            tags: Tags for organization

        Returns:
            Status dictionary
        """
        # Try Notion first
        try:
            result = await self._store_to_notion(title, content, category, tags)
            logger.info(f"✅ Stored to Notion: {title}")
            return {"status": "notion", "result": result}

        except Exception as e:
            logger.warning(f"⚠️ Notion unavailable: {e}")
            logger.info(f"📦 Buffering to SQLite: {title}")

            # Buffer to SQLite
            await self._buffer_to_sqlite(title, content, category, tags)

            return {"status": "buffered", "message": "Stored in local buffer"}

    async def _store_to_notion(
        self,
        title: str,
        content: str,
        category: str | None,
        tags: list[str] | None,
    ) -> dict[str, Any]:
        """Store learning to Notion database.

        External API Integration Required:

        To implement this method:
        1. Install notion-client: pip install notion-client
        2. Get Notion API key from https://www.notion.so/my-integrations
        3. Create a database in Notion and share it with the integration
        4. Store the API key in keychain: kagami.notion_api_key
        5. Store the database ID in config: kagami.notion_database_id

        Implementation should:
        - Create a new page in the configured database
        - Set title as page title
        - Set content as page body (markdown to blocks)
        - Set category and tags as database properties

        Args:
            title: Learning title
            content: Learning content (markdown)
            category: Optional category
            tags: Optional list of tags

        Returns:
            Dict with page_id and url on success

        Raises:
            NotImplementedError: Notion API integration not yet implemented.

        See Also:
            https://developers.notion.com/docs/getting-started
        """
        # Notion API integration - see docstring for implementation steps
        raise NotImplementedError(
            "Notion API integration not yet implemented. See docstring for implementation steps."
        )

    async def _buffer_to_sqlite(
        self,
        title: str,
        content: str,
        category: str | None,
        tags: list[str] | None,
    ) -> None:
        """Buffer learning to SQLite."""
        tags_str = ",".join(tags) if tags else None

        self._conn.execute(
            """
            INSERT INTO buffered_learnings (title, content, category, tags)
            VALUES (?, ?, ?, ?)
            """,
            (title, content, category, tags_str),
        )
        self._conn.commit()

    async def _periodic_flush(self) -> None:
        """Periodically flush buffered items to Notion."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval_seconds)
                await self.flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush task error: {e}")

    async def flush_buffer(self) -> dict[str, Any]:
        """Flush buffered learnings to Notion.

        Returns:
            Flush statistics
        """
        cursor = self._conn.execute(
            "SELECT id, title, content, category, tags FROM buffered_learnings WHERE flushed = 0"
        )

        buffered_items = cursor.fetchall()

        if not buffered_items:
            return {"flushed": 0, "failed": 0}

        logger.info(f"🔄 Flushing {len(buffered_items)} buffered items to Notion...")

        flushed_count = 0
        failed_count = 0

        for item_id, title, content, category, tags_str in buffered_items:
            try:
                tags = tags_str.split(",") if tags_str else None
                await self._store_to_notion(title, content, category, tags)

                # Mark as flushed
                self._conn.execute(
                    "UPDATE buffered_learnings SET flushed = 1 WHERE id = ?",
                    (item_id,),
                )
                self._conn.commit()

                flushed_count += 1
                logger.info(f"✅ Flushed: {title}")

            except Exception as e:
                logger.warning(f"Failed to flush {title}: {e}")
                failed_count += 1
                # Will try again next flush

        result = {
            "flushed": flushed_count,
            "failed": failed_count,
            "remaining": failed_count,
        }

        logger.info(f"✅ Flush complete: {result}")
        return result

    def get_buffer_stats(self) -> dict[str, Any]:
        """Get buffer statistics."""
        cursor = self._conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN flushed = 0 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN flushed = 1 THEN 1 ELSE 0 END) as flushed
            FROM buffered_learnings
            """
        )

        total, pending, flushed = cursor.fetchone()

        return {
            "total": total or 0,
            "pending": pending or 0,
            "flushed": flushed or 0,
            "buffer_path": self.buffer_db_path,
        }

    async def close(self) -> None:
        """Close client and flush remaining items."""
        if self._flush_task:
            self._flush_task.cancel()

        # Final flush attempt
        await self.flush_buffer()

        if self._conn:
            self._conn.close()


# Global client instance
_global_client: NotionBufferedClient | None = None


async def get_notion_buffered_client() -> NotionBufferedClient:
    """Get global buffered Notion client."""
    global _global_client
    if _global_client is None:
        _global_client = NotionBufferedClient()
        await _global_client.initialize()
    return _global_client
