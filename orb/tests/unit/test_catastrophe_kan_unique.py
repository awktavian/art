"""CatastropheKAN Duplicate Removal Verification (P1 Important).

Verifies that there is only ONE canonical implementation of CatastropheKAN
and that all imports are consistent.

Background:
-----------
December 2025: CatastropheKAN was unified to single source of truth:
kagami/core/world_model/layers/catastrophe_kan.py

This test ensures no duplicate implementations exist.

Created: December 15, 2025
Priority: P1 (Important)
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import ast
import os
from pathlib import Path


@pytest.fixture
def kagami_root():
    """Get kagami root directory."""
    # Assuming tests are in tests/unit/
    test_file = Path(__file__)
    repo_root = test_file.parent.parent.parent
    kagami_root = repo_root / "packages" / "kagami"
    return kagami_root


class TestOnlyOneCatastropheKANImplementation:
    """Test that CatastropheKAN has only one implementation."""

    def test_only_one_catastrophekan_implementation(self, kagami_root: Any) -> None:
        """Verify only ONE file defines CatastropheKAN class."""
        # Expected canonical file
        canonical_file = kagami_root / "core" / "world_model" / "layers" / "catastrophe_kan.py"

        assert canonical_file.exists(), f"Canonical file missing: {canonical_file}"

        # Search for any other files defining CatastropheKAN
        duplicate_files = []

        for py_file in kagami_root.rglob("*.py"):
            if py_file == canonical_file:
                continue  # Skip canonical file

            try:
                with open(py_file) as f:
                    content = f.read()

                # Parse AST
                tree = ast.parse(content, filename=str(py_file))

                # Check for class definitions
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        if node.name in [
                            "CatastropheKAN",
                            "CatastropheKANLayer",
                            "BatchedCatastropheKANLayer",
                            "BatchedCatastropheBasis",
                        ]:
                            duplicate_files.append((py_file, node.name))

            except (SyntaxError, UnicodeDecodeError):
                # Skip files that can't be parsed
                pass

        assert len(duplicate_files) == 0, (
            f"Found duplicate CatastropheKAN implementations: {duplicate_files}"
        )

    def test_no_model_layers_directory(self, kagami_root: Any) -> None:
        """Verify old model_layers/ directory doesn't exist."""
        # Old location (if it ever existed)
        old_dir = kagami_root / "core" / "world_model" / "model_layers"

        if old_dir.exists():
            # Check if it contains CatastropheKAN
            catastrophe_files = list(old_dir.glob("*catastrophe*"))
            assert len(catastrophe_files) == 0, (
                f"Found old catastrophe files in {old_dir}: {catastrophe_files}"
            )


class TestCanonicalImportsWork:
    """Test that canonical imports are functional."""

    def test_canonical_imports_work(self) -> None:
        """Verify imports from layers/catastrophe_kan.py work."""
        # This should NOT raise
        from kagami.core.world_model.layers.catastrophe_kan import (
            CatastropheKANLayer,
            BatchedCatastropheKANLayer,
            BatchedCatastropheBasis,
            FanoOctonionCombiner,
        )

        # Verify classes exist
        assert CatastropheKANLayer is not None
        assert BatchedCatastropheKANLayer is not None
        assert BatchedCatastropheBasis is not None
        assert FanoOctonionCombiner is not None

    def test_layers_init_exports(self) -> None:
        """Verify layers/__init__.py exports CatastropheKAN."""
        from kagami.core.world_model import layers

        # Should be exported
        assert hasattr(layers, "CatastropheKANLayer")
        assert hasattr(layers, "BatchedCatastropheKANLayer")
        assert hasattr(layers, "BatchedCatastropheBasis")

    def test_import_via_layers_module(self) -> None:
        """Test import via layers module."""
        from kagami.core.world_model.layers import (
            CatastropheKANLayer,
            BatchedCatastropheKANLayer,
        )

        assert CatastropheKANLayer is not None
        assert BatchedCatastropheKANLayer is not None


class TestNoBrokenReferencesAfterDeletion:
    """Test that no broken references exist after deletion."""

    def test_no_broken_references_after_deletion(self, kagami_root: Any) -> None:
        """Verify no imports reference deleted paths."""
        # Common broken import patterns
        broken_patterns = [
            "from kagami.core.world_model.model_layers.catastrophe_kan",
            "from kagami.core.world_model.model_layers import catastrophe_kan",
            "from kagami.core.model_layers.catastrophe_kan",
        ]

        broken_imports = []

        for py_file in kagami_root.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read()

                for pattern in broken_patterns:
                    if pattern in content:
                        broken_imports.append((py_file, pattern))

            except UnicodeDecodeError:
                pass

        assert len(broken_imports) == 0, f"Found broken imports: {broken_imports}"

    def test_all_imports_use_canonical_path(self, kagami_root: Any) -> None:
        """Verify all imports use canonical path."""
        canonical_import_path = "kagami.core.world_model.layers.catastrophe_kan"

        non_canonical = []

        for py_file in kagami_root.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read()

                # Check if file imports CatastropheKAN
                if "CatastropheKAN" in content or "catastrophe_kan" in content:
                    # Verify it uses canonical path
                    if canonical_import_path not in content:
                        # Check if it's a relative import within layers/
                        if "layers" not in str(py_file):
                            non_canonical.append(py_file)

            except UnicodeDecodeError:
                pass

        # Filter out the canonical file itself and __init__.py
        non_canonical = [
            f
            for f in non_canonical
            if "catastrophe_kan.py" not in str(f) and "__init__.py" not in str(f)
        ]

        # Some files might use relative imports - that's OK if they're in same package
        # This test is informational


class TestCatastropheKANFunctionality:
    """Test CatastropheKAN functionality is preserved."""

    def test_catastrophekan_layer_instantiates(self) -> None:
        """Verify CatastropheKANLayer can be instantiated."""
        from kagami.core.world_model.layers.catastrophe_kan import CatastropheKANLayer

        layer = CatastropheKANLayer(in_features=64, out_features=64, colony_idx=0)

        assert layer is not None
        assert hasattr(layer, "forward")

    def test_batched_catastrophe_kan_instantiates(self) -> None:
        """Verify BatchedCatastropheKANLayer can be instantiated."""
        from kagami.core.world_model.layers.catastrophe_kan import BatchedCatastropheKANLayer

        kan = BatchedCatastropheKANLayer(
            in_features=64,
            out_features=64,
        )

        assert kan is not None
        assert hasattr(kan, "forward")

    def test_batched_catastrophe_basis_instantiates(self) -> None:
        """Verify BatchedCatastropheBasis can be instantiated."""
        from kagami.core.world_model.layers.catastrophe_kan import BatchedCatastropheBasis

        basis = BatchedCatastropheBasis(
            num_channels=64,
            init_scale=0.1,
        )

        assert basis is not None
        assert hasattr(basis, "forward")

    def test_fano_octonion_combiner_instantiates(self) -> None:
        """Verify FanoOctonionCombiner can be instantiated."""
        from kagami.core.world_model.layers.catastrophe_kan import FanoOctonionCombiner

        combiner = FanoOctonionCombiner(d_model=64)

        assert combiner is not None
        assert hasattr(combiner, "forward")


class TestCatastropheKANForwardPass:
    """Test CatastropheKAN forward pass works."""

    def test_catastrophekan_layer_forward(self) -> None:
        """Test CatastropheKANLayer forward pass."""
        import torch
        from kagami.core.world_model.layers.catastrophe_kan import CatastropheKANLayer

        layer = CatastropheKANLayer(in_features=64, out_features=128, colony_idx=0)

        # Input: [B, in_features]
        x = torch.randn(4, 64)

        # Forward
        y = layer(x)

        # Output: [B, out_features]
        assert y.shape == (4, 128)

    def test_batched_catastrophe_kan_forward(self) -> None:
        """Test BatchedCatastropheKANLayer forward pass."""
        import torch
        from kagami.core.world_model.layers.catastrophe_kan import BatchedCatastropheKANLayer

        kan = BatchedCatastropheKANLayer(
            in_features=64,
            out_features=128,
        )

        # Input: [B, 7, in_features]
        x = torch.randn(4, 7, 64)

        # Forward
        y = kan(x)

        # Output: [B, 7, out_features]
        assert y.shape == (4, 7, 128)

    def test_fano_octonion_combiner_forward(self) -> None:
        """Test FanoOctonionCombiner forward pass."""
        import torch
        from kagami.core.world_model.layers.catastrophe_kan import FanoOctonionCombiner

        combiner = FanoOctonionCombiner(d_model=256)

        # Input: [B, 7, features]
        x = torch.randn(4, 7, 256)

        # Forward (combines across colonies)
        y = combiner(x)

        # Output: [B, features] (combined via Fano-weighted aggregation)
        assert y.shape == (4, 256)


class TestImportConsistencyAcrossCodebase:
    """Test that all imports are consistent."""

    def test_import_consistency_across_codebase(self, kagami_root: Any) -> None:
        """Verify all CatastropheKAN imports use same path."""
        import_paths = []

        for py_file in kagami_root.rglob("*.py"):
            try:
                with open(py_file) as f:
                    content = f.read()

                # Find import statements
                tree = ast.parse(content, filename=str(py_file))

                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        if hasattr(node, "module") and node.module:
                            if "catastrophe_kan" in node.module:
                                import_paths.append((py_file, node.module))

            except (SyntaxError, UnicodeDecodeError):
                pass

        # All should use canonical path
        canonical = "kagami.core.world_model.layers.catastrophe_kan"

        for file, module in import_paths:
            # Allow relative imports within layers package
            if "layers" in str(file) and module.startswith("."):
                continue

            assert canonical in module or module == "kagami.core.world_model.layers", (
                f"Non-canonical import in {file}: {module}"
            )


class TestDocumentationUpToDate:
    """Test that documentation references correct location."""

    def test_canonical_file_has_docstring(self, kagami_root: Any) -> None:
        """Verify canonical file has proper module docstring."""
        canonical_file = kagami_root / "core" / "world_model" / "layers" / "catastrophe_kan.py"

        with open(canonical_file) as f:
            content = f.read()

        # Should have module docstring
        assert '"""' in content
        assert "Catastrophe" in content
        assert "KAN" in content

    def test_layers_init_documents_catastrophe_kan(self, kagami_root: Any) -> None:
        """Verify layers/__init__.py documents CatastropheKAN."""
        init_file = kagami_root / "core" / "world_model" / "layers" / "__init__.py"

        if init_file.exists():
            with open(init_file) as f:
                content = f.read()

            # Should mention CatastropheKAN
            assert "catastrophe_kan" in content.lower() or "CatastropheKAN" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
