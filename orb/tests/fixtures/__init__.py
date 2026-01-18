"""Shared test fixtures and utilities for Kagami test suite.

This module provides common fixtures and utilities used across multiple test modules.
All test fixtures should be defined here or in module-specific conftest.py files.

Standard Fixtures:
    - Database fixtures (SQLite in-memory, PostgreSQL)
    - Redis fixtures (real and mocked)
    - Model fixtures (mocked transformers models)
    - Agent fixtures (colony agents for testing)
    - Safety fixtures (CBF testing utilities)

Usage:
    Import fixtures directly from this module or use pytest's automatic
    fixture discovery from conftest.py files.
"""

from __future__ import annotations

__all__ = [
    # Fixtures are automatically discovered by pytest
    # This module exists primarily for organization
]
