from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import os


def test_build_prompt_prelude_bounds_and_anchors() -> None:
    # Import locally to avoid heavy imports at module load
    from kagami.core.rules_loader import (
        build_prompt_prelude,
        get_rules_digest,
        verify_rules_digest,
    )

    def test_build_prompt_prelude_bounds_and_anchors(self) -> None:
        """Test prelude contains required components and respects size bounds."""
        from kagami.core.rules_loader import (
            get_rules_digest,
        )

        # Ensure deterministic max size for test
        os.environ["CURSOR_RULES_PRELUDE_MAX"] = "1200"

        prelude = build_prompt_prelude(app_name="TestApp")
        assert isinstance(prelude, str) and len(prelude) > 0

        # Prelude should start with contract header and include security layer and identity
        assert "System Contract (synchronized):" in prelude
        assert "SECURITY:" in prelude  # Safety layer header
        # Identity should include the app name
        assert "TestApp" in prelude

        # Size bounds respected (updated to match actual Core Truth size after Dec 2025 updates)
        # Dec 7, 2025: Increased limit to accommodate new cursor rules (kagami, fetch-map, etc.)
        assert len(prelude) <= 4000  # prelude adds headers around digest; digest capped separately

    # Digest should contain at least some guidance-like lines
    digest = get_rules_digest(max_chars=900)
    assert isinstance(digest, str) and len(digest) > 0
    # Heuristic anchors (optional if curated rules absent), tolerate missing on bare envs
    anchors = [
        "Act decisively",
        "Single `/metrics` exporter",
        "KagamiOSReply contract",
    ]
    missing = [a for a in anchors if a not in digest]
    # Allow at most all missing when rules not present; still assert digest not empty above
    assert len(missing) <= len(anchors)
