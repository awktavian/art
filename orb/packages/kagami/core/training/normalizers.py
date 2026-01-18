"""Data Sample Normalizers for Curriculum Training.

The Kagami curriculum includes:
- Genesis puzzles: `jepa` (dynamics), `generation` (control), `render` (video)
- QM9: Molecular geometry for SE(3) equivariance (RESTORED Dec 20, 2025)
- TreeOfLife: Hierarchical trees for H¹⁴ hyperbolic embeddings (RESTORED Dec 20, 2025)

Each normalizer preserves geometric structure for geometry-aware losses.
"""

from __future__ import annotations

from typing import Any, Protocol


def _copy_text_fields(sample: dict[str, Any], normalized: dict[str, Any]) -> None:
    """Copy text/caption fields to normalized dict[str, Any].

    Args:
        sample: Source sample
        normalized: Target normalized dict[str, Any] (modified in-place)
    """
    if isinstance(sample.get("text"), str):
        normalized["text"] = sample["text"]
    if isinstance(sample.get("caption"), str) and "text" not in normalized:
        normalized["text"] = sample["caption"]


def _copy_fields(sample: dict[str, Any], normalized: dict[str, Any], fields: list[str]) -> None:
    """Copy specified fields from sample to normalized dict[str, Any].

    Args:
        sample: Source sample
        normalized: Target normalized dict[str, Any] (modified in-place)
        fields: List of field names to copy if present
    """
    for field in fields:
        if field in sample:
            normalized[field] = sample[field]


class SampleNormalizer(Protocol):
    """Protocol for sample normalizers."""

    def normalize(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize sample to common training format.

        Args:
            sample: Raw sample from dataset
            source: Dataset source name

        Returns:
            Normalized sample with common fields
        """
        ...


class GenesisNormalizer:
    """Normalizer for Genesis physics simulation data.

    PRESERVE DYNAMICS - pass through temporal structure, state transitions.
    """

    # Temporal structure fields
    DYNAMICS_FIELDS = ["state_t", "state_t_plus_1", "action_t", "fingerprint", "metadata"]

    def normalize(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize Genesis physics sample."""
        normalized: dict[str, Any] = {}

        # Pass through temporal structure DIRECTLY
        _copy_fields(sample, normalized, self.DYNAMICS_FIELDS)
        # Preserve language supervision (Genesis provides dynamic `caption`)
        _copy_text_fields(sample, normalized)

        return normalized


class RenderNormalizer:
    """Normalizer for Genesis render stream (physics + RGB frames).

    Used for video prediction training: state → predict → decode → render → compare.
    """

    # State + frame fields
    RENDER_FIELDS = [
        "state_t",
        "state_t_plus_1",
        "action_t",
        "frames_t",  # [T, 3, H, W] RGB frames
        "frames_t_plus_1",
        "fingerprint",
        "metadata",
    ]

    def normalize(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize render sample with physics state and RGB frames."""
        normalized: dict[str, Any] = {}

        # Pass through state + frames
        _copy_fields(sample, normalized, self.RENDER_FIELDS)
        # Preserve language supervision (render stream also carries captions)
        _copy_text_fields(sample, normalized)

        return normalized


class QM9Normalizer:
    """Normalizer for QM9 molecular geometry data.

    PRESERVE GEOMETRIC STRUCTURE - pass through 3D coords, atom types, quaternions.
    The model needs raw geometric data for geometry-aware losses.

    RESTORED: December 20, 2025
    """

    # Geometric fields to preserve
    GEOMETRIC_FIELDS = ["positions", "atom_types", "charges", "quaternions", "num_atoms"]

    # Property targets for regression
    PROPERTY_FIELDS = ["energy_U0", "energy_gap", "dipole", "polarizability"]

    # Text and metadata
    TEXT_FIELDS = ["text", "smiles", "fingerprint"]

    # Routing flags
    FLAG_FIELDS = ["is_geometric", "is_molecular"]

    def normalize(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize QM9 molecular geometry sample."""
        normalized: dict[str, Any] = {}

        # Pass through geometric structure DIRECTLY
        _copy_fields(sample, normalized, self.GEOMETRIC_FIELDS)

        # Property targets for regression
        _copy_fields(sample, normalized, self.PROPERTY_FIELDS)

        # Text and metadata
        _copy_fields(sample, normalized, self.TEXT_FIELDS)

        # Flags for model routing
        _copy_fields(sample, normalized, self.FLAG_FIELDS)

        return normalized


class TreeOfLifeNormalizer:
    """Normalizer for TreeOfLife hierarchical tree data.

    PRESERVE HIERARCHY - pass through graph structure, node depths, adjacency.

    RESTORED: December 20, 2025
    """

    # Graph structure fields
    HIERARCHY_FIELDS = [
        "node_depths",
        "depth_targets",
        "adjacency",
        "edges",
        "num_nodes",
        "max_depth",
    ]

    # Text and metadata
    TEXT_FIELDS = ["text", "fingerprint", "tree_id"]

    # Routing flags
    FLAG_FIELDS = ["is_hierarchical", "is_tree"]

    def normalize(self, sample: dict[str, Any], source: str) -> dict[str, Any]:
        """Normalize TreeOfLife hierarchy sample."""
        normalized: dict[str, Any] = {}

        # Pass through graph structure DIRECTLY
        _copy_fields(sample, normalized, self.HIERARCHY_FIELDS)

        # Text and metadata
        _copy_fields(sample, normalized, self.TEXT_FIELDS)

        # Flags for model routing
        _copy_fields(sample, normalized, self.FLAG_FIELDS)

        return normalized


# Registry mapping source names to normalizers
NORMALIZERS: dict[str, SampleNormalizer] = {
    "jepa": GenesisNormalizer(),
    "generation": GenesisNormalizer(),
    "render": RenderNormalizer(),
    "qm9": QM9Normalizer(),
    "treeoflife": TreeOfLifeNormalizer(),
    "tree_of_life": TreeOfLifeNormalizer(),  # Alias
}


def get_normalizer(source: str) -> SampleNormalizer:
    """Get normalizer for given source.

    Args:
        source: Dataset source name

    Returns:
        Normalizer instance for that source
    """
    key = (source or "").strip().lower()
    if key in NORMALIZERS:
        return NORMALIZERS[key]
    raise KeyError(f"Unknown normalizer source: {source!r}. Known: {sorted(NORMALIZERS.keys())}")
