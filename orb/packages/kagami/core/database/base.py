"""Database base configuration for K os."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Unified SQLAlchemy Base for all K os models."""


__all__ = ["Base"]
