"""Tests for agent security module.

Verifies:
- Input validation
- XSS prevention
- Rate limiting
- Connection tracking
- Security audit

Colony: Crystal (e7) — Verification
Created: January 7, 2026
鏡
"""

import asyncio
import pytest

from kagami.core.agents.security import (
    ConnectionTracker,
    InputValidationError,
    RateLimiter,
    check_rate_limit,
    check_websocket_connection,
    get_security_config,
    mask_credential,
    register_websocket_connection,
    run_security_audit,
    safe_yaml_load,
    sanitize_css_value,
    sanitize_for_html_attribute,
    sanitize_html_content,
    sanitize_javascript_string,
    unregister_websocket_connection,
    validate_action_params,
    validate_action_type,
    validate_agent_id,
    validate_agent_path,
    validate_entity_name,
    validate_obs_config,
    validate_properties,
    validate_query,
)


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestAgentIdValidation:
    """Test agent ID validation."""

    def test_valid_agent_id(self):
        """Test valid agent IDs."""
        assert validate_agent_id("my-agent") == "my-agent"
        assert validate_agent_id("agent_123") == "agent_123"
        assert validate_agent_id("Agent-001") == "Agent-001"

    def test_empty_agent_id(self):
        """Test empty agent ID rejected."""
        with pytest.raises(InputValidationError, match="cannot be empty"):
            validate_agent_id("")

    def test_too_long_agent_id(self):
        """Test agent ID length limit."""
        with pytest.raises(InputValidationError, match="too long"):
            validate_agent_id("a" * 100)

    def test_invalid_characters(self):
        """Test invalid characters rejected."""
        with pytest.raises(InputValidationError, match="invalid characters"):
            validate_agent_id("agent<script>")

        with pytest.raises(InputValidationError, match="invalid characters"):
            validate_agent_id("agent/../../etc")


class TestQueryValidation:
    """Test query validation."""

    def test_valid_query(self):
        """Test valid queries."""
        assert validate_query("What is the weather?") == "What is the weather?"
        assert validate_query("  spaces  ") == "spaces"

    def test_empty_query(self):
        """Test empty query rejected."""
        with pytest.raises(InputValidationError, match="cannot be empty"):
            validate_query("")

    def test_too_long_query(self):
        """Test query length limit."""
        config = get_security_config()
        with pytest.raises(InputValidationError, match="too long"):
            validate_query("a" * (config.max_query_length + 1))

    def test_blocked_patterns(self):
        """Test blocked patterns rejected."""
        blocked_queries = [
            "<script>alert('xss')</script>",
            "javascript:void(0)",
            "onclick=alert(1)",
            "../../../etc/passwd",
            "eval(bad_code)",
        ]

        for query in blocked_queries:
            with pytest.raises(InputValidationError, match="blocked content"):
                validate_query(query)


class TestActionValidation:
    """Test action validation."""

    def test_valid_action_type(self):
        """Test valid action types."""
        assert validate_action_type("obs_command") == "obs_command"
        assert validate_action_type("smarthome") == "smarthome"
        assert validate_action_type("composio") == "composio"

    def test_invalid_action_type(self):
        """Test invalid action type rejected."""
        with pytest.raises(InputValidationError, match="not allowed"):
            validate_action_type("exec_shell")

        with pytest.raises(InputValidationError, match="not allowed"):
            validate_action_type("unknown")

    def test_valid_params(self):
        """Test valid parameters."""
        params = {"scene": "Main", "value": 50}
        assert validate_action_params(params) == params

    def test_params_with_blocked_content(self):
        """Test parameters with blocked content rejected."""
        with pytest.raises(InputValidationError, match="blocked content"):
            validate_action_params({"url": "javascript:alert(1)"})

    def test_too_many_params(self):
        """Test parameter count limit."""
        config = get_security_config()
        many_params = {f"key{i}": i for i in range(config.max_action_params + 10)}
        with pytest.raises(InputValidationError, match="Too many parameters"):
            validate_action_params(many_params)


# =============================================================================
# XSS Prevention Tests
# =============================================================================


class TestXssPrevention:
    """Test XSS prevention functions."""

    def test_sanitize_html_content(self):
        """Test HTML content sanitization."""
        result = sanitize_html_content("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "alert" not in result or "&" in result

    def test_sanitize_html_attribute(self):
        """Test HTML attribute sanitization."""
        result = sanitize_for_html_attribute('"><img src=x onerror=alert(1)>')
        assert '"' not in result
        assert ">" not in result
        assert "<" not in result

    def test_sanitize_css_value(self):
        """Test CSS value sanitization."""
        dangerous_css = [
            "expression(alert(1))",
            "url(javascript:alert(1))",
            "-moz-binding:url(evil.xml)",
        ]

        for css in dangerous_css:
            result = sanitize_css_value(css)
            assert "expression" not in result.lower()
            assert "javascript" not in result.lower()

    def test_sanitize_javascript_string(self):
        """Test JavaScript string escaping."""
        result = sanitize_javascript_string('"; alert("xss"); var x = "')
        # Should be JSON-escaped
        assert "\\" in result or "&" in result


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Test rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(self):
        """Test rate limiter allows burst."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=5)

        # Should allow burst
        for _ in range(5):
            assert await limiter.is_allowed("test_key")

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess(self):
        """Test rate limiter blocks excess."""
        limiter = RateLimiter(requests_per_minute=60, burst_size=3)

        # Use up burst
        for _ in range(3):
            await limiter.is_allowed("test_key")

        # Should be blocked
        assert not await limiter.is_allowed("test_key")

    @pytest.mark.asyncio
    async def test_rate_limiter_replenishes(self):
        """Test rate limiter replenishes over time."""
        limiter = RateLimiter(requests_per_minute=6000, burst_size=1)

        # Use up burst
        assert await limiter.is_allowed("test_key")
        assert not await limiter.is_allowed("test_key")

        # Wait for replenishment (100 req/sec = 10ms per request)
        await asyncio.sleep(0.02)

        # Should have tokens again
        assert await limiter.is_allowed("test_key")

    @pytest.mark.asyncio
    async def test_global_rate_limit(self):
        """Test global rate limit function."""
        # First call should work
        result = await check_rate_limit("test_global_key")
        assert result is True


# =============================================================================
# Connection Tracking Tests
# =============================================================================


class TestConnectionTracking:
    """Test WebSocket connection tracking."""

    @pytest.mark.asyncio
    async def test_connection_allowed(self):
        """Test connection allowed when under limit."""
        tracker = ConnectionTracker()
        allowed, reason = await tracker.can_connect("agent1", "192.168.1.1")
        assert allowed is True
        assert reason == ""

    @pytest.mark.asyncio
    async def test_connection_tracking(self):
        """Test connection registration."""
        tracker = ConnectionTracker()

        await tracker.add_connection("agent1", "192.168.1.1")
        await tracker.add_connection("agent1", "192.168.1.2")

        # Should still be under limit
        allowed, _ = await tracker.can_connect("agent1", "192.168.1.3")
        assert allowed is True

        await tracker.remove_connection("agent1", "192.168.1.1")

    @pytest.mark.asyncio
    async def test_global_connection_functions(self):
        """Test global connection functions."""
        allowed, reason = await check_websocket_connection("test_agent", "127.0.0.1")
        assert allowed is True

        await register_websocket_connection("test_agent", "127.0.0.1")
        await unregister_websocket_connection("test_agent", "127.0.0.1")


# =============================================================================
# Credential Handling Tests
# =============================================================================


class TestCredentialHandling:
    """Test credential handling."""

    def test_mask_credential(self):
        """Test credential masking."""
        # 18 chars - 4 visible = 14 stars + 4 visible
        result = mask_credential("sk-1234567890abcdef")
        assert result.endswith("cdef")
        assert "*" in result

        # Short string shows last 4 chars
        result_short = mask_credential("short")
        assert result_short.endswith("hort")
        assert "*" in result_short

        # Empty string
        assert mask_credential("") == "***"

    def test_obs_config_validation(self):
        """Test OBS config validation."""
        valid_config = {
            "websocket": "ws://localhost:4455/",
            "password": "secret123",
        }
        result = validate_obs_config(valid_config)
        assert result["websocket"] == valid_config["websocket"]

    def test_obs_config_invalid_url(self):
        """Test OBS config with invalid URL."""
        invalid_config = {
            "websocket": "not-a-url",
        }
        with pytest.raises(InputValidationError, match="Invalid OBS WebSocket URL"):
            validate_obs_config(invalid_config)


# =============================================================================
# Path Safety Tests
# =============================================================================


class TestPathSafety:
    """Test path traversal prevention."""

    def test_validate_safe_path(self):
        """Test safe path validation."""
        import tempfile

        base = tempfile.gettempdir()
        result = validate_agent_path("test.md", base)
        assert base in result

    def test_validate_traversal_blocked(self):
        """Test path traversal blocked."""
        import tempfile

        base = tempfile.gettempdir()
        with pytest.raises(InputValidationError, match="traversal"):
            validate_agent_path("../../etc/passwd", base)


# =============================================================================
# YAML Safety Tests
# =============================================================================


class TestYamlSafety:
    """Test YAML loading safety."""

    def test_safe_yaml_load(self):
        """Test safe YAML loading."""
        yaml_content = """
name: test
value: 123
"""
        result = safe_yaml_load(yaml_content)
        assert result["name"] == "test"
        assert result["value"] == 123

    def test_yaml_invalid_type(self):
        """Test YAML must be dictionary."""
        with pytest.raises(InputValidationError, match="must be a dictionary"):
            safe_yaml_load("- item1\n- item2")

    def test_yaml_invalid_syntax(self):
        """Test invalid YAML rejected."""
        with pytest.raises(InputValidationError, match="Invalid YAML"):
            safe_yaml_load("invalid: yaml: content:")


# =============================================================================
# Security Audit Tests
# =============================================================================


class TestSecurityAudit:
    """Test security audit."""

    def test_run_security_audit(self):
        """Test security audit runs."""
        result = run_security_audit()

        assert isinstance(result.passed, bool)
        assert isinstance(result.checks, list)
        assert len(result.checks) > 0
        assert result.timestamp > 0

    def test_audit_checks_environment(self):
        """Test audit checks environment."""
        result = run_security_audit()

        check_names = [c["name"] for c in result.checks]
        assert "environment" in check_names
        assert "rate_limit" in check_names
        assert "input_validation" in check_names


# =============================================================================
# Knowledge Graph Validation Tests
# =============================================================================


class TestKnowledgeGraphValidation:
    """Test knowledge graph validation."""

    def test_validate_entity_name(self):
        """Test entity name validation."""
        assert validate_entity_name("user_123") == "user_123"
        assert validate_entity_name("  trimmed  ") == "trimmed"

        # HTML should be escaped
        result = validate_entity_name("<script>bad</script>")
        assert "<" not in result
        assert ">" not in result

    def test_validate_entity_name_empty(self):
        """Test empty entity name rejected."""
        with pytest.raises(InputValidationError, match="cannot be empty"):
            validate_entity_name("")

    def test_validate_entity_name_too_long(self):
        """Test entity name length limit."""
        config = get_security_config()
        with pytest.raises(InputValidationError, match="too long"):
            validate_entity_name("a" * (config.max_entity_name_length + 1))

    def test_validate_properties(self):
        """Test properties validation."""
        props = {"key": "value", "nested": {"a": 1}}
        result = validate_properties(props)
        assert result == props

    def test_validate_properties_too_large(self):
        """Test properties size limit."""
        # Create large properties
        large_props = {"key": "x" * 100000}
        with pytest.raises(InputValidationError, match="too large"):
            validate_properties(large_props)
