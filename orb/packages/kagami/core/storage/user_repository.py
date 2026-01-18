"""User/auth repository with write-through caching.

Created: December 15, 2025
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kagami.core.database.models import APIKey, Session, User
from kagami.core.storage.base import BaseRepository, CacheStrategy

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for User/auth storage with write-through caching.

    Storage architecture:
    - Primary: CockroachDB (relational)
    - L2 Cache: Redis (fast auth checks)

    Cache strategy: WRITE_THROUGH
    - Frequent auth checks
    - Infrequent updates
    - Immediate consistency for auth
    """

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize user repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.WRITE_THROUGH,
            ttl=600,  # 10 minutes
            l1_max_size=500,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("UserRepository initialized")

    # ========== User Operations ==========

    async def get_by_id(self, user_id: UUID | str) -> User | None:
        """Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User or None
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        return await self.get(str(user_id))

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User or None
        """
        stmt = select(User).where(User.username == username)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: Email address

        Returns:
            User or None
        """
        stmt = select(User).where(User.email == email)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        """Create new user.

        Args:
            user: User to create

        Returns:
            Created user
        """
        await self.set(str(user.id), user)
        return user

    async def update_user(self, user: User) -> User:
        """Update existing user.

        Args:
            user: User to update

        Returns:
            Updated user
        """
        await self.set(str(user.id), user)
        return user

    async def delete_user(self, user_id: UUID | str) -> bool:
        """Delete user.

        Args:
            user_id: User UUID

        Returns:
            True if deleted
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        return await self.delete(str(user_id))

    async def list_active_users(
        self,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[User]:
        """List active users.

        Args:
            tenant_id: Optional tenant filter
            limit: Max results

        Returns:
            List of active users
        """
        stmt = select(User).where(User.is_active == True)  # noqa: E712

        if tenant_id is not None:
            stmt = stmt.where(User.tenant_id == tenant_id)

        stmt = stmt.limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    # ========== Storage Operations (L3) ==========

    async def _fetch_from_storage(self, key: str) -> User | None:
        """Fetch user from CockroachDB.

        Args:
            key: User ID

        Returns:
            User or None
        """
        try:
            user_id = UUID(key)
            stmt = select(User).where(User.id == user_id)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"User fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: User) -> None:
        """Write user to CockroachDB.

        Args:
            key: User ID
            value: User to store
        """
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"User write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete user from CockroachDB.

        Args:
            key: User ID

        Returns:
            True if deleted
        """
        try:
            user_id = UUID(key)
            stmt = select(User).where(User.id == user_id)
            result = await self.db_session.execute(stmt)
            user = result.scalar_one_or_none()

            if user is not None:
                await self.db_session.delete(user)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"User delete failed: {e}")
            return False


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository for API key storage with write-through caching."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize API key repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.WRITE_THROUGH,
            ttl=300,  # 5 minutes
            l1_max_size=1000,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("APIKeyRepository initialized")

    async def get_by_key(self, key: str) -> APIKey | None:
        """Get API key by key string.

        Args:
            key: API key string

        Returns:
            APIKey or None
        """
        stmt = select(APIKey).where(APIKey.key == key)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _fetch_from_storage(self, key: str) -> APIKey | None:
        """Fetch API key from storage."""
        try:
            stmt = select(APIKey).where(APIKey.key == key)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"APIKey fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: APIKey) -> None:
        """Write API key to storage."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"APIKey write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete API key from storage."""
        try:
            stmt = select(APIKey).where(APIKey.key == key)
            result = await self.db_session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if api_key is not None:
                await self.db_session.delete(api_key)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"APIKey delete failed: {e}")
            return False


class SessionRepository(BaseRepository[Session]):
    """Repository for session storage with write-behind caching."""

    def __init__(
        self,
        db_session: AsyncSession,
        redis_client: Any | None = None,
    ):
        """Initialize session repository.

        Args:
            db_session: CockroachDB session
            redis_client: Optional Redis client for L2 cache
        """
        super().__init__(
            storage_backend=db_session,
            cache_strategy=CacheStrategy.WRITE_BEHIND,  # Async for high volume
            ttl=30,  # 30 seconds (ephemeral)
            l1_max_size=2000,
            redis_client=redis_client,
        )
        self.db_session = db_session
        logger.info("SessionRepository initialized")

    async def get_by_session_id(self, session_id: str) -> Session | None:
        """Get session by session ID.

        Args:
            session_id: Session identifier

        Returns:
            Session or None
        """
        stmt = select(Session).where(Session.session_id == session_id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def _fetch_from_storage(self, key: str) -> Session | None:
        """Fetch session from storage."""
        try:
            stmt = select(Session).where(Session.session_id == key)
            result = await self.db_session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Session fetch failed: {e}")
            return None

    async def _write_to_storage(self, key: str, value: Session) -> None:
        """Write session to storage."""
        try:
            self.db_session.add(value)
            await self.db_session.commit()
            await self.db_session.refresh(value)
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Session write failed: {e}")
            raise

    async def _delete_from_storage(self, key: str) -> bool:
        """Delete session from storage."""
        try:
            stmt = select(Session).where(Session.session_id == key)
            result = await self.db_session.execute(stmt)
            session = result.scalar_one_or_none()

            if session is not None:
                await self.db_session.delete(session)
                await self.db_session.commit()
                return True

            return False
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Session delete failed: {e}")
            return False


__all__ = [
    "APIKeyRepository",
    "SessionRepository",
    "UserRepository",
]
