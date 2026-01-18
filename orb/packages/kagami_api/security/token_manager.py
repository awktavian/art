"""JWT Token Manager - Consolidated token management with blacklisting.

Extracted from kagami_api.auth for clean module separation.
Provides enhanced JWT token management with Redis-backed blacklisting.
"""

import logging
from typing import TYPE_CHECKING, Any

from jose import jwt
from kagami.core.caching.redis import RedisClientFactory
from kagami.core.config import get_config, get_int_config

if TYPE_CHECKING:
    from redis import Redis

logger = logging.getLogger(__name__)


class TokenManager:
    """Enhanced JWT token manager with blacklisting and security features.

    Features:
    - JWT token creation (access + refresh)
    - Token verification and validation
    - Redis-backed token blacklisting
    - User-level token revocation
    - Automatic expired token cleanup
    """

    def __init__(self) -> None:
        import os

        self.secret_key: str | None = get_config("JWT_SECRET")
        self.algorithm = "HS256"
        self.access_token_expire_minutes: int = get_int_config("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
        self.refresh_token_expire_days: int = get_int_config("REFRESH_TOKEN_EXPIRE_DAYS", 30)

        # Initialize Redis for token blacklisting
        self.redis_client: Redis[str] | None = None
        self.blacklisted_tokens: set[str] = set()  # Fallback in-memory storage
        self._initialize_redis()

        # Debug: log instance ID in test mode
        if os.getenv("KAGAMI_TEST_MODE") == "1":
            logger.debug(f"TokenManager instance created: id={id(self)}")

    def _initialize_redis(self) -> None:
        """Initialize Redis connection for distributed token blacklisting.

        Skips Redis in test mode (KAGAMI_TEST_DISABLE_REDIS=1) to prevent
        test pollution and ensure proper isolation.
        """
        import os

        # Skip Redis in test mode for proper test isolation
        if os.getenv("KAGAMI_TEST_DISABLE_REDIS") == "1":
            logger.info("Redis disabled in test mode, using in-memory token blacklist")
            self.redis_client = None
            return

        try:
            redis = RedisClientFactory.get_client(
                purpose="default", async_mode=False, decode_responses=True
            )
            # Test connection
            redis.ping()
            self.redis_client = redis
            logger.info("Redis connection established for token blacklisting")
        except Exception as e:
            logger.warning(f"Redis connection failed, using in-memory token blacklist: {e}")
            self.redis_client = None

    def create_access_token(self, data: dict[str, Any], expires_delta: Any | None = None) -> str:
        """Create a new access token."""
        from datetime import datetime, timedelta

        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return str(encoded_jwt)

    def create_refresh_token(
        self, data: dict[str, Any], expires_delta: Any | None = None, family_id: str | None = None
    ) -> str:
        """Create a new refresh token with optional token family ID.

        Args:
            data: Token payload data
            expires_delta: Custom expiration timedelta
            family_id: Token family ID for rotation tracking (generated if not provided)

        Returns:
            Encoded JWT refresh token
        """
        import uuid
        from datetime import datetime, timedelta

        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)

        # Generate or use provided token family ID for rotation tracking
        if family_id is None:
            family_id = str(uuid.uuid4())

        to_encode.update(
            {
                "exp": expire,
                "iat": datetime.utcnow(),
                "type": "refresh",
                "family_id": family_id,  # Track token family for reuse detection
            }
        )
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return str(encoded_jwt)

    def verify_token(self, token: str) -> dict[str, Any] | None:
        """Verify and decode a token."""
        from jose import JWTError

        try:
            if self.is_token_blacklisted(token):
                logger.warning("Attempt to use blacklisted token")
                return None
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            token_type = payload.get("type")
            if token_type not in ["access", "refresh"]:
                logger.warning(f"Invalid token type: {token_type}")
                return None
            return dict(payload)
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None

    def blacklist_token(self, token: str) -> bool:
        """Add token to blacklist."""
        import os
        from datetime import datetime

        try:
            norm = str(token).strip()
            try:
                payload = jwt.get_unverified_claims(norm)
            except Exception:
                payload = jwt.decode(
                    norm,
                    self.secret_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False, "verify_signature": False},
                )
            exp_timestamp = payload.get("exp")
            if not exp_timestamp:
                logger.error("Token missing expiration timestamp")
                return False
            exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
            ttl = int((exp_datetime - datetime.utcnow()).total_seconds())
            if ttl <= 0:
                return True  # Already expired
            redis = self.redis_client
            if redis is not None:
                redis.setex(f"blacklist:{norm}", ttl, "1")
                logger.info("Token blacklisted in Redis")
            else:
                self.blacklisted_tokens.add(norm)
                if os.getenv("KAGAMI_TEST_MODE") == "1":
                    logger.info(
                        f"Token blacklisted in memory (instance={id(self)}, blacklist_size={len(self.blacklisted_tokens)})"
                    )
                else:
                    logger.info("Token blacklisted in memory")
            return True
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
            return False

    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted."""
        from datetime import datetime

        try:
            norm = str(token).strip()
            redis = self.redis_client
            if redis is not None:
                result = redis.get(f"blacklist:{norm}")
                return result is not None
            else:
                if norm in self.blacklisted_tokens:
                    try:
                        payload = jwt.decode(
                            norm,
                            self.secret_key,
                            algorithms=[self.algorithm],
                            options={"verify_exp": False},
                        )
                        exp_ts = payload.get("exp")
                        if exp_ts and datetime.utcnow().timestamp() > exp_ts:
                            self.blacklisted_tokens.discard(norm)
                            return False
                    except Exception:
                        pass
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to check token blacklist: {e}")
            return True  # Fail closed

    def is_token_family_revoked(self, family_id: str) -> bool:
        """Check if an entire token family has been revoked (reuse detected).

        Args:
            family_id: Token family ID to check

        Returns:
            True if family is revoked, False otherwise
        """
        try:
            redis = self.redis_client
            if redis is not None:
                result = redis.get(f"family_revoked:{family_id}")
                return result is not None
            else:
                # Fallback to in-memory (not ideal for distributed systems)
                return hasattr(self, "_revoked_families") and family_id in self._revoked_families
        except Exception as e:
            logger.error(f"Failed to check family revocation: {e}")
            return False

    def revoke_token_family(self, family_id: str) -> bool:
        """Revoke entire token family (triggered by reuse detection).

        Args:
            family_id: Token family ID to revoke

        Returns:
            True if successful, False otherwise
        """
        try:
            redis = self.redis_client
            if redis is not None:
                # Revoke family for 30 days (longer than max refresh token lifetime)
                redis.setex(f"family_revoked:{family_id}", 60 * 60 * 24 * 30, "1")
                logger.warning(f"Revoked token family due to reuse detection: {family_id}")
                return True
            else:
                # Fallback to in-memory
                if not hasattr(self, "_revoked_families"):
                    self._revoked_families: set[str] = set()
                self._revoked_families.add(family_id)
                logger.warning(f"Revoked token family (in-memory): {family_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to revoke token family: {e}")
            return False

    def refresh_access_token(
        self, refresh_token: str, client_info: dict[str, Any] | None = None
    ) -> dict[str, str] | None:
        """Generate new access token from refresh token with rotation.

        Implements token refresh rotation:
        1. Verify the refresh token
        2. Check for token reuse (family-based detection)
        3. Blacklist the old refresh token
        4. Generate new access + refresh tokens (same family)
        5. Log the refresh event for audit

        Args:
            refresh_token: The refresh token to use
            client_info: Optional client information for audit logging

        Returns:
            Dict with new access_token, refresh_token, and token_type
            None if refresh failed (invalid/expired/reused token)
        """
        from jose import JWTError

        try:
            payload = jwt.decode(
                str(refresh_token).strip(), self.secret_key, algorithms=[self.algorithm]
            )
        except JWTError as e:
            logger.warning(f"JWT verification failed during refresh: {e}")
            return None

        if not payload or payload.get("type") != "refresh":
            logger.warning("Attempted to refresh with non-refresh token")
            return None

        # Extract family_id for reuse detection
        family_id = payload.get("family_id")
        user_id = payload.get("sub", "unknown")

        # SECURITY: Check if token family has been revoked (reuse detection)
        if family_id and self.is_token_family_revoked(family_id):
            logger.error(
                f"SECURITY ALERT: Attempted reuse of revoked token family: {family_id} (user: {user_id})"
            )
            # Log security event
            try:
                from kagami_api.audit_logger import AuditEventType, get_audit_logger

                get_audit_logger().log_authentication(
                    AuditEventType.TOKEN_REFRESH,
                    user_id=user_id,
                    request=None,
                    outcome="failure",
                    details={
                        "reason": "token_reuse_detected",
                        "family_id": family_id,
                        "security_alert": True,
                    },
                )
            except Exception:
                pass
            return None

        # SECURITY: Check if token is already blacklisted (attempted reuse)
        if self.is_token_blacklisted(refresh_token):
            logger.error(f"SECURITY ALERT: Attempted reuse of blacklisted token (user: {user_id})")
            # Revoke entire token family to prevent further reuse
            if family_id:
                self.revoke_token_family(family_id)
            # Log security event
            try:
                from kagami_api.audit_logger import AuditEventType, get_audit_logger

                get_audit_logger().log_authentication(
                    AuditEventType.TOKEN_REFRESH,
                    user_id=user_id,
                    request=None,
                    outcome="failure",
                    details={
                        "reason": "token_reuse_attempt",
                        "family_id": family_id,
                        "security_alert": True,
                        "action_taken": "family_revoked" if family_id else "none",
                    },
                )
            except Exception:
                pass
            return None

        # Extract user data (exclude JWT metadata)
        user_data = {
            k: v for k, v in payload.items() if k not in ["exp", "iat", "type", "family_id"]
        }

        # Generate new access token
        new_access_token = self.create_access_token(user_data)

        # Check rotation config (MANDATORY in production)
        import os

        env = (os.getenv("ENVIRONMENT") or "development").lower()

        rotate_refresh_config: str | None = get_config("ROTATE_REFRESH_TOKENS")
        if rotate_refresh_config is None:
            # Default: enable rotation in production/staging, disable in development
            rotate_refresh = env in ("production", "prod", "staging")
        else:
            rotate_refresh = rotate_refresh_config.lower() == "true"

        # SECURITY: Token rotation is MANDATORY in production - no bypass allowed
        if env == "production" and not rotate_refresh:
            logger.error(
                "SECURITY VIOLATION: Token rotation cannot be disabled in production. "
                "Remove ROTATE_REFRESH_TOKENS=false from configuration."
            )
            rotate_refresh = True  # Force enable in production

        if rotate_refresh:
            # ROTATION: Blacklist old refresh token
            blacklist_success = self.blacklist_token(refresh_token)

            # ROTATION: Generate new refresh token (preserve family_id)
            new_refresh_token = self.create_refresh_token(user_data, family_id=family_id)

            # Log successful refresh with rotation
            logger.info(
                f"Token refreshed with rotation for user {user_id} (family: {family_id or 'none'})"
            )

            # Audit log the refresh event
            try:
                from kagami_api.audit_logger import AuditEventType, get_audit_logger

                get_audit_logger().log_authentication(
                    AuditEventType.TOKEN_REFRESH,
                    user_id=user_id,
                    request=None,
                    outcome="success",
                    details={
                        "rotated": True,
                        "family_id": family_id,
                        "old_token_blacklisted": blacklist_success,
                        "client_info": client_info or {},
                    },
                )
            except Exception as e:
                logger.debug(f"Audit logging failed: {e}")

            return {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "token_type": "bearer",
            }
        else:
            # Legacy mode: no rotation (not recommended)
            logger.info(f"Token refreshed WITHOUT rotation for user {user_id}")

            # Audit log the refresh event
            try:
                from kagami_api.audit_logger import AuditEventType, get_audit_logger

                get_audit_logger().log_authentication(
                    AuditEventType.TOKEN_REFRESH,
                    user_id=user_id,
                    request=None,
                    outcome="success",
                    details={
                        "rotated": False,
                        "family_id": family_id,
                        "client_info": client_info or {},
                    },
                )
            except Exception as e:
                logger.debug(f"Audit logging failed: {e}")

            return {"access_token": new_access_token, "token_type": "bearer"}

    def revoke_all_user_tokens(self, user_id: str) -> bool:
        """Revoke all tokens for a specific user."""
        from datetime import datetime

        try:
            redis = self.redis_client
            if redis is not None:
                redis.setex(
                    f"user_revoked:{user_id}",
                    60 * 60 * 24 * 30,  # 30 days
                    str(datetime.utcnow().timestamp()),
                )
                logger.info(f"Revoked all tokens for user: {user_id}")
                return True
            else:
                logger.warning("Cannot revoke user tokens without Redis")
                return False
        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return False

    def is_user_revoked(self, user_id: str, token_issued_at: Any) -> bool:
        """Check if user tokens were revoked after token issuance."""
        from datetime import datetime

        try:
            redis = self.redis_client
            if redis is None:
                return False
            revoke_timestamp = redis.get(f"user_revoked:{user_id}")
            if not revoke_timestamp:
                return False
            revoke_time = datetime.fromtimestamp(float(revoke_timestamp))
            if isinstance(token_issued_at, datetime):
                issued_at_dt = token_issued_at
            elif isinstance(token_issued_at, int | float):
                issued_at_dt = datetime.fromtimestamp(float(token_issued_at))
            elif isinstance(token_issued_at, str):
                try:
                    issued_at_dt = datetime.fromtimestamp(float(token_issued_at))
                except Exception:
                    return False
            else:
                return False
            return issued_at_dt < revoke_time
        except Exception as e:
            logger.error(f"Failed to check user revocation: {e}")
            return False

    def get_token_info(self, token: str) -> dict[str, Any] | None:
        """Get detailed information about a token."""
        from datetime import datetime

        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            exp_timestamp = payload.get("exp")
            iat_timestamp = payload.get("iat")
            return {
                "valid": not self.is_token_blacklisted(token),
                "expired": (
                    datetime.utcnow().timestamp() > exp_timestamp if exp_timestamp else True
                ),
                "issued_at": (
                    datetime.fromtimestamp(iat_timestamp).isoformat() if iat_timestamp else None
                ),
                "expires_at": (
                    datetime.fromtimestamp(exp_timestamp).isoformat() if exp_timestamp else None
                ),
                "token_type": payload.get("type"),
                "subject": payload.get("sub"),
                "blacklisted": self.is_token_blacklisted(token),
            }
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return None

    def cleanup_expired_blacklist(self) -> int:
        """Clean up expired tokens from in-memory blacklist."""
        from datetime import datetime

        if self.redis_client is not None:
            return 0  # Redis handles TTL automatically
        cleaned = 0
        tokens_to_remove = []
        for token in self.blacklisted_tokens:
            try:
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=[self.algorithm],
                    options={"verify_exp": False},
                )
                exp_timestamp = payload.get("exp")
                if exp_timestamp and datetime.utcnow().timestamp() > exp_timestamp:
                    tokens_to_remove.append(token)
            except Exception:
                tokens_to_remove.append(token)
        for token in tokens_to_remove:
            self.blacklisted_tokens.discard(token)
            cleaned += 1
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} expired tokens from blacklist")
        return cleaned


# Singleton instance
_token_manager: TokenManager | None = None


def get_token_manager() -> TokenManager:
    """Get singleton token manager instance."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


def reset_token_manager_for_testing() -> None:
    """Reset token manager singleton for testing.

    This function is ONLY for use in test fixtures to ensure proper
    isolation between parallel test workers.

    CRITICAL: Clears state but KEEPS singleton instance to prevent
    multiple instances within a single test.

    SECURITY: Never call this in production code!

    Example:
        @pytest.fixture(autouse=True)
        def reset_auth_state():
            from kagami_api.security.token_manager import reset_token_manager_for_testing
            reset_token_manager_for_testing()
            yield
            reset_token_manager_for_testing()
    """
    global _token_manager

    # Get or create singleton (don't destroy it)
    if _token_manager is None:
        _token_manager = TokenManager()

    # Clear Redis blacklist keys
    redis = _token_manager.redis_client
    if redis is not None:
        try:
            # Flush all blacklist keys in test Redis DB
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match="blacklist:*", count=100)
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break
            # Also clear user revocation keys
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match="user_revoked:*", count=100)
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break
            # Clear token family revocation keys
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match="family_revoked:*", count=100)
                if keys:
                    redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            # If Redis fails, continue (fallback to in-memory)
            logger.warning(f"Failed to clear Redis in test reset: {e}")

    # Clear in-memory state (CRITICAL: don't destroy instance)
    if hasattr(_token_manager, "blacklisted_tokens"):
        _token_manager.blacklisted_tokens.clear()
    if hasattr(_token_manager, "_revoked_families"):
        _token_manager._revoked_families.clear()

    # DO NOT set _token_manager = None here!
    # Keeping the instance ensures test code using get_token_manager()
    # gets the SAME instance throughout the test


__all__ = ["TokenManager", "get_token_manager", "reset_token_manager_for_testing"]
