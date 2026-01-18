"""Secure user management for K os authentication.

This module provides user storage and authentication using secure password hashing
with Argon2 and database persistence.
"""

# GAIA imports commented out - always use fallback for now
import hashlib as _hashlib
import logging
import os
import secrets
import secrets as _secrets
import string
import string as _string
import uuid

from kagami.core.database.connection import (
    check_connection,
    get_db,
    init_db,
    init_db_sync,
)
from kagami.core.database.models import User as DBUser
from sqlalchemy.exc import SQLAlchemyError


class CryptoConfig:
    """Fallback placeholder type to align conditional signatures."""

    salt: str | None = None


def generate_secure_token(length: int = 32) -> str:
    alphabet = _string.ascii_letters + _string.digits
    return "".join(_secrets.choice(alphabet) for _ in range(max(1, int(length))))


def _weak_hash_password(password: str | bytes, config: CryptoConfig | None = None) -> str:
    """WEAK hash for testing only. Use kagami.api.security.hash_password in production.

    SECURITY: This function is BLOCKED in production environments.
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()

    # SECURITY: Block weak hashing in production - no exceptions
    if environment == "production":
        raise RuntimeError(
            "SECURITY VIOLATION: Weak password hashing is BLOCKED in production. "
            "Install passlib and bcrypt: pip install passlib bcrypt"
        )

    allow_weak = (os.getenv("KAGAMI_ALLOW_WEAK_HASH") or "0").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not allow_weak:
        raise RuntimeError(
            "Strong password hashing unavailable; set KAGAMI_ALLOW_WEAK_HASH=1 for tests only"
        )
    try:
        logging.getLogger(__name__).warning(
            "⚠️ SECURITY: Using weak SHA-256 password hashing (tests/dev only). "
            "Do NOT enable KAGAMI_ALLOW_WEAK_HASH in production."
        )
    except Exception:
        pass
    p = password if isinstance(password, bytes | bytearray) else str(password).encode("utf-8")
    return _hashlib.sha256(p).hexdigest()


def hash_password(password: str | bytes, config: CryptoConfig | None = None) -> str:
    """Hash password - uses strong bcrypt if available, weak SHA-256 for tests."""
    try:
        from kagami_api.security import hash_password as secure_hash

        # Ignore config param - bcrypt doesn't need it
        p = password if isinstance(password, str) else password.decode("utf-8")
        return secure_hash(p)
    except ImportError:
        return _weak_hash_password(password, config)


def verify_password(password: str | bytes, hashed: str, config: CryptoConfig | None = None) -> bool:
    """Verify password against hash - supports both bcrypt and weak SHA-256.

    SECURITY: Uses constant-time comparison to prevent timing attacks.
    """
    import hmac

    try:
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        p = password if isinstance(password, str) else password.decode("utf-8")
        return bool(pwd_context.verify(p, hashed))
    except ImportError:
        # Fallback to weak comparison for test environments
        # SECURITY: Use constant-time comparison even for weak hashes
        weak_hash = _weak_hash_password(password, config)
        return hmac.compare_digest(weak_hash, hashed)
    except Exception:
        return False


logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password.

    Args:
        length: Password length (default: 16)

    Returns:
        Secure random password string
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Remove confusing characters
    alphabet = alphabet.replace("'", "").replace('"', "").replace("\\", "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


class UserStore:
    """Secure user storage and management with database persistence."""

    def __init__(self) -> None:
        self._use_database: bool = False
        self.users: dict[str, dict] = {}
        self._ensure_database_setup()
        self._initialize_default_users()

    def _ensure_database_setup(self) -> None:
        """Ensure database is set up and accessible."""
        environment = os.getenv("ENVIRONMENT", "development")

        try:
            # Explicit development safeguard: if DATABASE_URL is missing/empty,
            # prefer in-memory store to keep unit tests deterministic.
            db_url = os.getenv("DATABASE_URL", "").strip()
            if not db_url:
                if environment == "production":
                    logger.critical("DATABASE_URL must be set in production mode")
                    raise RuntimeError(
                        "Database connection required in production. Please set DATABASE_URL."
                    )

                logger.warning(
                    "No DATABASE_URL configured; using in-memory user store (development mode)"
                )
                self._use_database = False
                return

            if not check_connection():
                if environment == "production":
                    logger.critical("Database connection failed in production mode")
                    raise RuntimeError(
                        "Database connection required in production. "
                        "Please ensure DATABASE_URL is correctly configured and the database is accessible."
                    )

                logger.warning(
                    "Database connection failed, falling back to in-memory storage (development mode)"
                )
                self._use_database = False
                return

            # Initialize database tables
            # Prefer synchronous init to avoid event loop issues in unit tests
            try:
                # If an event loop exists and is running, use sync init to avoid nested loop errors
                import asyncio as _asyncio

                try:
                    _asyncio.get_running_loop()
                    # Running loop exists - use sync init to avoid nested loop errors
                    init_db_sync()
                except RuntimeError:
                    # No running loop - safe to create one
                    loop = _asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(init_db())
                    finally:
                        loop.close()
            except Exception:
                # Final fallback to sync init
                init_db_sync()

            self._use_database = True
            logger.info("Database connection established")

        except RuntimeError:
            # Re-raise runtime errors (production failures) from None
            raise
        except Exception as e:
            if environment == "production":
                logger.critical(f"Database setup failed in production: {e}")
                raise RuntimeError(f"Database setup required in production. Error: {e}") from None

            logger.warning(
                f"Database setup failed, using in-memory storage (development mode): {e}"
            )
            self._use_database = False

    def _initialize_default_users(self) -> None:
        """Initialize default users from environment variables or secure defaults."""
        environment = os.getenv("ENVIRONMENT", "development")

        # Check if users already exist
        if self._use_database:
            try:
                for session in get_db():
                    existing_users = session.query(DBUser).count()
                    if existing_users > 0:
                        logger.info(f"Found {existing_users} existing users in database")
                        return
                    break
            except Exception as e:
                logger.error(f"Failed to check existing users: {e}")
                return
        elif hasattr(self, "users") and self.users:
            return

        # Check for environment-configured users first
        admin_password = os.getenv("KAGAMI_ADMIN_PASSWORD")
        user_password = os.getenv("KAGAMI_USER_PASSWORD")
        guest_password = os.getenv("KAGAMI_GUEST_PASSWORD")

        # Use secure generated passwords if not provided
        if not admin_password:
            # In production, admin password must be explicitly set
            if environment == "production" and not False:
                logger.critical("KAGAMI_ADMIN_PASSWORD must be set in production")
                raise RuntimeError("Admin password required in production")
            admin_password = generate_secure_token()
            logger.warning(
                f"No KAGAMI_ADMIN_PASSWORD set. Generated secure password: {admin_password}"
            )
            logger.warning("Please set KAGAMI_ADMIN_PASSWORD environment variable for production")

        if not user_password:
            # In production, user password must be explicitly set
            if environment == "production" and not False:
                logger.critical("KAGAMI_USER_PASSWORD must be set in production")
                raise RuntimeError("User password required in production")
            user_password = generate_secure_token()
            logger.warning(
                f"No KAGAMI_USER_PASSWORD set. Generated secure password: {user_password}"
            )
            logger.warning("Please set KAGAMI_USER_PASSWORD environment variable for production")

        if not guest_password:
            # In production, guest password must be explicitly set
            if environment == "production" and not False:
                logger.critical("KAGAMI_GUEST_PASSWORD must be set in production")
                raise RuntimeError("Guest password required in production")
            guest_password = generate_secure_token()
            logger.warning(
                f"No KAGAMI_GUEST_PASSWORD set. Generated secure password: {guest_password}"
            )
            logger.warning("Please set KAGAMI_GUEST_PASSWORD environment variable for production")

        # Create users
        try:
            if self._use_database:
                self._create_db_users(str(admin_password), str(user_password), str(guest_password))
            else:
                self._create_memory_users(
                    str(admin_password), str(user_password), str(guest_password)
                )

            logger.info("Successfully initialized user store with secure password hashing")

        except Exception as e:
            logger.error(f"Failed to initialize secure user store: {e}")
            # Fall back to demo mode with warnings
            self._initialize_demo_users()

    def _create_db_users(
        self, admin_password: str, user_password: str, guest_password: str
    ) -> None:
        """Create users in database."""
        try:
            for session in get_db():
                users = [
                    DBUser(
                        username="admin",
                        email="admin@kagami.local",
                        tenant_id=str(uuid.uuid4()),
                        hashed_password=hash_password(admin_password),
                        roles=["admin", "user"],
                        is_superuser=True,
                    ),
                    DBUser(
                        username="user",
                        email="user@kagami.local",
                        tenant_id=str(uuid.uuid4()),
                        hashed_password=hash_password(user_password),
                        roles=["user"],
                    ),
                    DBUser(
                        username="guest",
                        email="guest@kagami.local",
                        tenant_id=str(uuid.uuid4()),
                        hashed_password=hash_password(guest_password),
                        roles=["guest"],
                    ),
                ]

                for user in users:
                    session.add(user)
                session.commit()
                logger.info("Created default users in database")
                break

        except SQLAlchemyError as e:
            logger.error(f"Failed to create database users: {e}")
            raise

    def _create_memory_users(
        self, admin_password: str, user_password: str, guest_password: str
    ) -> None:
        """Create users in memory storage."""
        # Deterministic tenant ids for local/dev
        admin_tid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:admin"))
        user_tid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:user"))
        guest_tid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:guest"))
        self.users = {
            "admin": {
                "username": "admin",
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:admin")),
                "hashed_password": hash_password(admin_password),
                "roles": ["admin", "user"],
                "is_active": True,
                "email": "admin@kagami.local",
                "tenant_id": admin_tid,
            },
            "user": {
                "username": "user",
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:user")),
                "hashed_password": hash_password(user_password),
                "roles": ["user"],
                "is_active": True,
                "email": "user@kagami.local",
                "tenant_id": user_tid,
            },
            "guest": {
                "username": "guest",
                "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:guest")),
                "hashed_password": hash_password(guest_password),
                "roles": ["guest"],
                "is_active": True,
                "email": "guest@kagami.local",
                "tenant_id": guest_tid,
            },
        }

    def _initialize_demo_users(self) -> None:
        """Initialize demo users with clear warnings (development only)."""
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            logger.critical("DEMO USERS NOT ALLOWED IN PRODUCTION")
            raise RuntimeError("Demo users cannot be used in production")

        logger.critical("USING INSECURE DEMO USERS - NOT FOR PRODUCTION")
        logger.critical("Set KAGAMI_ADMIN_PASSWORD, KAGAMI_USER_PASSWORD, KAGAMI_GUEST_PASSWORD")

        try:
            # Generate secure passwords for demo users
            admin_password = generate_secure_password()
            user_password = generate_secure_password()
            guest_password = generate_secure_password()

            # Log passwords to console ONLY in demo mode
            logger.warning("=" * 60)
            logger.warning("DEMO MODE - Generated secure passwords:")
            logger.warning(f"Admin: {admin_password}")
            logger.warning(f"User: {user_password}")
            logger.warning(f"Guest: {guest_password}")
            logger.warning("Save these passwords - they will not be shown again!")
            logger.warning("=" * 60)

            if self._use_database:
                for session in get_db():
                    demo_users = [
                        DBUser(
                            username="admin",
                            email="admin@kagami.local",
                            tenant_id=str(uuid.uuid4()),
                            hashed_password=hash_password(admin_password),
                            roles=["admin", "user"],
                            is_superuser=True,
                        ),
                        DBUser(
                            username="user",
                            email="user@kagami.local",
                            tenant_id=str(uuid.uuid4()),
                            hashed_password=hash_password(user_password),
                            roles=["user"],
                        ),
                        DBUser(
                            username="guest",
                            email="guest@kagami.local",
                            tenant_id=str(uuid.uuid4()),
                            hashed_password=hash_password(guest_password),
                            roles=["guest"],
                        ),
                    ]

                    for user in demo_users:
                        session.add(user)
                    session.commit()
            else:
                self.users = {
                    "admin": {
                        "username": "admin",
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:admin")),
                        "hashed_password": hash_password(admin_password),
                        "roles": ["admin", "user"],
                        "is_active": True,
                        "email": "admin@kagami.local",
                        "tenant_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:admin")),
                    },
                    "user": {
                        "username": "user",
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:user")),
                        "hashed_password": hash_password(user_password),
                        "roles": ["user"],
                        "is_active": True,
                        "email": "user@kagami.local",
                        "tenant_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:user")),
                    },
                    "guest": {
                        "username": "guest",
                        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:user:guest")),
                        "hashed_password": hash_password(guest_password),
                        "roles": ["guest"],
                        "is_active": True,
                        "email": "guest@kagami.local",
                        "tenant_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "kagami:tenant:guest")),
                    },
                }
            logger.warning("Demo users initialized with secure passwords")

        except Exception as e:
            logger.critical(f"Failed to initialize even demo users: {e}")
            if not self._use_database:
                self.users = {}

    def authenticate_user(self, username: str, password: str) -> dict | None:
        """Authenticate a user with username and password.

        Args:
            username: Username to authenticate
            password: Plain text password

        Returns:
            User dict if authentication successful, None otherwise
        """
        if not username or not password:
            return None

        try:
            if self._use_database:
                for session in get_db():
                    user = (
                        session.query(DBUser)
                        .filter(DBUser.username == username, DBUser.is_active.is_(True))
                        .first()
                    )
                    if not user:
                        return None
                    if verify_password(password, str(user.hashed_password)):
                        return {
                            "id": str(user.id),
                            "username": user.username,
                            "email": user.email,
                            "roles": user.roles or [],
                            "is_active": user.is_active,
                            "is_superuser": user.is_superuser,
                            "tenant_id": user.tenant_id,
                            "stripe_customer_id": user.stripe_customer_id,
                            "created_at": (
                                user.created_at.isoformat() if user.created_at else None
                            ),
                        }
                    break
                return None
            else:
                user_dict = self.users.get(username)
                if not user_dict or not user_dict.get("is_active", True):
                    return None

                if verify_password(password, user_dict["hashed_password"]):
                    # Always return a copy with stable ids
                    out = dict(user_dict)
                    out.setdefault(
                        "id", str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:user:{username}"))
                    )
                    out.setdefault(
                        "tenant_id",
                        str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:tenant:{username}")),
                    )
                    return out

        except Exception as e:
            logger.error(f"Password verification failed for user {username}: {e}")

        return None

    def get_user(self, username: str) -> dict | None:
        """Get user by username.

        Args:
            username: Username to retrieve

        Returns:
            User dict if found, None otherwise
        """
        try:
            if self._use_database:
                for session in get_db():
                    user = session.query(DBUser).filter(DBUser.username == username).first()
                    if user:
                        return {
                            "id": str(user.id),
                            "username": user.username,
                            "email": user.email,
                            "tenant_id": user.tenant_id,
                            "roles": user.roles or [],
                            "is_active": user.is_active,
                            "is_superuser": user.is_superuser,
                            "stripe_customer_id": user.stripe_customer_id,
                            "created_at": (
                                user.created_at.isoformat() if user.created_at else None
                            ),
                        }
                    break
            else:
                u = self.users.get(username)
                if not u:
                    return None
                out = dict(u)
                out.setdefault("id", str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:user:{username}")))
                out.setdefault(
                    "tenant_id",
                    str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:tenant:{username}")),
                )
                return out
        except Exception as e:
            logger.error(f"Failed to get user {username}: {e}")

        return None

    def user_exists(self, username: str) -> bool:
        """Check if user exists.

        Args:
            username: Username to check

        Returns:
            True if user exists, False otherwise
        """
        try:
            if self._use_database:
                for session in get_db():
                    exists = (
                        session.query(DBUser).filter(DBUser.username == username).first()
                        is not None
                    )
                    return exists
                return False
            else:
                return username in self.users
        except Exception as e:
            logger.error(f"Failed to check if user exists {username}: {e}")
            return False

    def add_user(
        self, username: str, password: str, roles: list[str], email: str | None = None
    ) -> bool:
        """Add a new user to the store.

        Args:
            username: Username for new user
            password: Plain text password
            roles: List of roles for the user
            email: Email address for the user

        Returns:
            True if user added successfully, False otherwise
        """
        if self.user_exists(username):
            logger.warning(f"Attempt to add existing user: {username}")
            return False

        try:
            password_hash = hash_password(password)

            if self._use_database:
                for session in get_db():
                    user = DBUser(
                        username=username,
                        email=email or f"{username}@kagami.local",
                        tenant_id=str(uuid.uuid4()),
                        hashed_password=password_hash,
                        roles=roles,
                    )
                    session.add(user)
                    session.commit()
                    break
            else:
                self.users[username] = {
                    "username": username,
                    "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:user:{username}")),
                    "email": email or f"{username}@kagami.local",
                    "hashed_password": password_hash,
                    "roles": roles,
                    "is_active": True,
                    "tenant_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"kagami:tenant:{username}")),
                }

            logger.info(f"Added new user: {username}")
            return True

        except Exception as e:
            logger.error(f"Failed to add user {username}: {e}")
            return False

    def update_password(self, username: str, new_password: str) -> bool:
        """Update user password.

        Args:
            username: Username to update
            new_password: New plain text password

        Returns:
            True if password updated successfully, False otherwise
        """
        try:
            password_hash = hash_password(new_password)

            if self._use_database:
                for session in get_db():
                    user = session.query(DBUser).filter(DBUser.username == username).first()
                    if not user:
                        return False
                    # Assign to mapped attribute via setattr to satisfy typing
                    user.hashed_password = password_hash  # type: ignore[assignment]  # SQLAlchemy Column assignment
                    session.commit()
                    break
            else:
                user_dict = self.users.get(username)
                if not user_dict:
                    return False
                user_dict["hashed_password"] = password_hash

            logger.info(f"Updated password for user: {username}")
            return True

        except Exception as e:
            logger.error(f"Failed to update password for user {username}: {e}")
            return False

    def deactivate_user(self, username: str) -> bool:
        """Deactivate a user account.

        Args:
            username: Username to deactivate

        Returns:
            True if user deactivated successfully, False otherwise
        """
        try:
            if self._use_database:
                for session in get_db():
                    user = session.query(DBUser).filter(DBUser.username == username).first()
                    if not user:
                        return False
                    user.is_active = False  # type: ignore[assignment]  # SQLAlchemy Column assignment
                    session.commit()
                    break
            else:
                user_dict = self.users.get(username)
                if not user_dict:
                    return False
                user_dict["is_active"] = False

            logger.info(f"Deactivated user: {username}")
            return True

        except Exception as e:
            logger.error(f"Failed to deactivate user {username}: {e}")
            return False

    def list_users(self) -> list[str]:
        """List all usernames in the store.

        Returns:
            List of usernames
        """
        try:
            if self._use_database:
                for session in get_db():
                    users = session.query(DBUser.username).all()
                    return [user.username for user in users]
                return []
            else:
                return list(self.users.keys())
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []


# Global user store instance
_user_store: UserStore | None = None


def get_user_store() -> UserStore:
    """Get the global user store instance.

    Returns:
        The global UserStore instance
    """
    global _user_store

    if _user_store is None:
        _user_store = UserStore()

    return _user_store


def reset_user_store_for_testing() -> None:
    """Reset user store singleton for testing.

    This function is ONLY for use in test fixtures to ensure proper
    isolation between parallel test workers.

    CRITICAL: Clears state but KEEPS singleton instance to prevent
    multiple instances within a single test.

    SECURITY: Never call this in production code!

    Example:
        @pytest.fixture(autouse=True)
        def reset_auth_state():
            from kagami_api.user_store import reset_user_store_for_testing
            reset_user_store_for_testing()
            yield
            reset_user_store_for_testing()
    """
    global _user_store

    # Get or create singleton (don't destroy it)
    if _user_store is None:
        _user_store = UserStore()

    # Clear internal caches/state if they exist
    if hasattr(_user_store, "_users"):
        _user_store._users.clear()
    if hasattr(_user_store, "_cache"):
        _user_store._cache.clear()

    # DO NOT set _user_store = None here!
    # Keeping the instance ensures test code using get_user_store()
    # gets the SAME instance throughout the test
