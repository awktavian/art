"""Entry point for ForgeMatrix.

Re-exports the orchestrator as the main class.
The canonical singleton is get_forge_matrix() in orchestrator.py.
"""

from __future__ import annotations

from kagami.forge.matrix.orchestrator import ForgeMatrix, get_forge_matrix

__all__ = ["ForgeMatrix", "get_forge_matrix"]
