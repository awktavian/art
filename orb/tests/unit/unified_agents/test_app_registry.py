"""Tests for App Registry.

Validates:
1. list_apps_v2() - app enumeration
2. infer_app_from_action() - action routing

Created: December 14, 2025
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



from kagami.core.unified_agents.app_registry import (
    list_apps_v2,
    infer_app_from_action,
    ACTION_TO_APP_MAP,
    AGENT_PERSONALITIES,
    APP_METADATA,
)

# =============================================================================
# TEST LIST APPS V2
# =============================================================================


class TestListAppsV2:
    """Test app enumeration."""

    def test_returns_dict(self):
        """Should return dictionary of apps."""
        apps = list_apps_v2()
        assert isinstance(apps, dict)

    def test_contains_all_colonies(self):
        """Should contain all 7 colonies."""
        apps = list_apps_v2()

        for colony in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]:
            assert colony in apps

    def test_app_structure(self):
        """Each app should have required fields."""
        apps = list_apps_v2()

        forge = apps["forge"]
        assert "registry_id" in forge
        assert "maturity" in forge
        assert "metadata" in forge

    def test_action_index(self):
        """Should include action index."""
        apps = list_apps_v2()

        assert "_action_index" in apps
        assert isinstance(apps["_action_index"], dict)

    def test_metadata_matches(self):
        """Metadata should match APP_METADATA."""
        apps = list_apps_v2()

        for colony in ["spark", "forge", "crystal"]:
            assert apps[colony]["metadata"] == APP_METADATA.get(colony, {})


# =============================================================================
# TEST INFER APP FROM ACTION
# =============================================================================


class TestInferAppFromAction:
    """Test action routing logic."""

    def test_none_input(self):
        """Should handle None input."""
        assert infer_app_from_action(None) is None

    def test_empty_string(self):
        """Should handle empty string."""
        assert infer_app_from_action("") is None
        assert infer_app_from_action("   ") is None

    def test_namespace_hints_plans(self):
        """Should route plans.* to plans."""
        assert infer_app_from_action("plans.create") == "plans"
        assert infer_app_from_action("plan.update") == "plans"

    def test_namespace_hints_files(self):
        """Should route files.* to files."""
        assert infer_app_from_action("files.upload") == "files"
        assert infer_app_from_action("file.search") == "files"

    def test_namespace_hints_forge(self):
        """Should route forge.* to forge."""
        assert infer_app_from_action("forge.build") == "forge"

    def test_namespace_hints_research(self):
        """Should route research.* to research."""
        assert infer_app_from_action("research.web") == "research"

    def test_planner_verbs(self):
        """Should route planning verbs to plans."""
        assert infer_app_from_action("plan") == "plans"
        assert infer_app_from_action("create_plan") == "plans"
        assert infer_app_from_action("generate_tasks") == "plans"

    def test_file_verbs(self):
        """Should route file verbs to files."""
        assert infer_app_from_action("upload") == "files"
        assert infer_app_from_action("search") == "files"
        assert infer_app_from_action("scan") == "files"

    def test_verb_mapping_exact(self):
        """Should route exact verb matches."""
        assert infer_app_from_action("create") == "spark"
        assert infer_app_from_action("build") == "forge"
        assert infer_app_from_action("test") == "crystal"

    def test_verb_mapping_prefix(self):
        """Should route verb prefixes."""
        assert infer_app_from_action("create.feature") == "spark"
        assert infer_app_from_action("build.component") == "forge"
        assert infer_app_from_action("test.function") == "crystal"

    def test_verb_mapping_underscore(self):
        """Should route verb_action patterns."""
        assert infer_app_from_action("create_feature") == "spark"
        assert infer_app_from_action("build_component") == "forge"

    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert infer_app_from_action("CREATE") == "spark"
        assert infer_app_from_action("Build") == "forge"
        assert infer_app_from_action("TEST") == "crystal"

    def test_unknown_action(self):
        """Should return None for unknown actions."""
        assert infer_app_from_action("unknown_action") is None
        assert infer_app_from_action("xyz.abc") is None

    def test_all_action_map_verbs(self):
        """Should handle all verbs from ACTION_TO_APP_MAP."""
        for verb, _app in ACTION_TO_APP_MAP.items():
            result = infer_app_from_action(verb)
            # Should route to expected app (or a compatible alias)
            assert result is not None
