"""Shared security utilities to prevent circular dependencies.

Contains password hashing/verification and constants shared between
security.py and routes/auth.py.
"""

import logging

import bcrypt
from kagami.core.config import get_int_config

logger = logging.getLogger(__name__)

# Configuration constants - read from environment
ACCESS_TOKEN_EXPIRE_MINUTES = get_int_config("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
REFRESH_TOKEN_EXPIRE_DAYS = get_int_config("REFRESH_TOKEN_EXPIRE_DAYS", 7)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password
        hashed_password: The bcrypt hashed password

    Returns:
        True if password matches, False otherwise
    """
    try:
        result: bool = bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
        return result
    except Exception as e:
        logger.warning(f"Password verification failed: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hashed password
    """
    salt = bcrypt.gensalt()
    hashed: str = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    return hashed
