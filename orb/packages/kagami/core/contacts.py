"""Contacts — Centralized contact information for Kagami household.

Quick access to phone numbers, emails, and identity info.

Usage:
    from kagami.core.contacts import get_contact, get_owner, CONTACTS

    # Get Tim's info
    tim = get_owner()
    print(tim.phone)  # +16613105469

    # Get any contact
    contact = get_contact("tim")

    # Direct access
    from kagami.core.contacts import TIM
    print(TIM.phone)

Created: January 7, 2026
鏡
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Character assets directory
CHARACTERS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "characters"


@dataclass
class Contact:
    """Contact information for a person."""

    name: str
    identity_id: str
    phone: str | None = None
    email: str | None = None
    role: str = "member"
    permissions: list[str] | None = None

    # Additional metadata
    full_name: str | None = None
    emoji: str | None = None

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> Contact:
        """Create Contact from character metadata.json."""
        return cls(
            name=metadata.get("character_name", "Unknown"),
            identity_id=metadata.get("identity_id", ""),
            phone=metadata.get("phone"),
            email=metadata.get("email"),
            role=metadata.get("role", "member"),
            permissions=metadata.get("permissions"),
            full_name=metadata.get("full_name"),
            emoji=metadata.get("emoji"),
        )

    @property
    def is_owner(self) -> bool:
        """Check if this is the owner."""
        return self.role == "owner"

    @property
    def is_admin(self) -> bool:
        """Check if this contact has admin permissions."""
        return bool(self.permissions and "admin" in self.permissions)


def load_contact(character_name: str) -> Contact | None:
    """Load contact from character metadata.

    Args:
        character_name: Character folder name (tim, bella, etc.)

    Returns:
        Contact or None if not found
    """
    metadata_path = CHARACTERS_DIR / character_name / "metadata.json"

    if not metadata_path.exists():
        logger.debug(f"No metadata for character: {character_name}")
        return None

    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
        return Contact.from_metadata(metadata)
    except Exception as e:
        logger.error(f"Failed to load contact {character_name}: {e}")
        return None


def get_contact(name: str) -> Contact | None:
    """Get contact by name or identity_id.

    Args:
        name: Character name or identity_id

    Returns:
        Contact or None
    """
    # Try direct folder name first
    contact = load_contact(name.lower())
    if contact:
        return contact

    # Search all characters
    if CHARACTERS_DIR.exists():
        for char_dir in CHARACTERS_DIR.iterdir():
            if char_dir.is_dir():
                contact = load_contact(char_dir.name)
                if contact and (
                    contact.name.lower() == name.lower()
                    or contact.identity_id.lower() == name.lower()
                ):
                    return contact

    return None


def get_owner() -> Contact | None:
    """Get the owner contact (Tim).

    Returns:
        Owner Contact or None
    """
    return get_contact("tim")


def get_all_contacts() -> list[Contact]:
    """Get all contacts from character metadata.

    Returns:
        List of Contact objects
    """
    contacts = []

    if CHARACTERS_DIR.exists():
        for char_dir in CHARACTERS_DIR.iterdir():
            if char_dir.is_dir():
                contact = load_contact(char_dir.name)
                if contact:
                    contacts.append(contact)

    return contacts


def get_phone(name: str) -> str | None:
    """Quick lookup for phone number.

    Args:
        name: Contact name

    Returns:
        Phone number or None
    """
    contact = get_contact(name)
    return contact.phone if contact else None


def get_email(name: str) -> str | None:
    """Quick lookup for email.

    Args:
        name: Contact name

    Returns:
        Email or None
    """
    contact = get_contact(name)
    return contact.email if contact else None


# =============================================================================
# QUICK ACCESS CONSTANTS
# =============================================================================

# Load Tim on import for quick access
TIM: Contact | None = None


def _load_tim():
    global TIM
    TIM = get_contact("tim")


try:
    _load_tim()
except Exception:
    pass  # Will be None if not loadable


# Convenience dict
CONTACTS: dict[str, Contact] = {}


def _load_all_contacts():
    global CONTACTS
    for contact in get_all_contacts():
        CONTACTS[contact.identity_id] = contact
        CONTACTS[contact.name.lower()] = contact


try:
    _load_all_contacts()
except Exception:
    pass


__all__ = [
    "CONTACTS",
    "TIM",
    "Contact",
    "get_all_contacts",
    "get_contact",
    "get_email",
    "get_owner",
    "get_phone",
    "load_contact",
]
