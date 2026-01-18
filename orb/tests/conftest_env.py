"""Test environment configuration for K os.

This module configures the test environment to use lightweight models
and test-appropriate settings, preventing heavy model loading that
causes test timeouts.

Usage:
    This module is automatically imported by pytest via conftest.py
    to set up the test environment before any tests run.
"""

import os


def configure_test_environment() -> None:
    """Configure environment variables for test execution.

    Sets lightweight models and test-specific configurations to ensure
    fast test execution without loading heavy 32B+ parameter models.
    """
    # Mark test mode
    os.environ["KAGAMI_TEST_MODE"] = "1"
    os.environ["PYTEST_RUNNING"] = "1"

    # Disable torch.compile for tests (MPS backend compilation issues)
    os.environ["TORCH_COMPILE_DISABLE"] = "1"

    # Fix etcd3/protobuf 4.x compatibility (use pure Python parsing)
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

    # Use lightweight models for all LLM operations
    # sshleifer/tiny-gpt2 is 124M params, loads in <1s
    os.environ["KAGAMI_TRANSFORMERS_MODEL_DEFAULT"] = "sshleifer/tiny-gpt2"
    os.environ["KAGAMI_TRANSFORMERS_MODEL_CODER"] = "sshleifer/tiny-gpt2"
    os.environ["KAGAMI_TRANSFORMERS_MODEL_FAST"] = "sshleifer/tiny-gpt2"
    os.environ["KAGAMI_TRANSFORMERS_MODEL_REASONING"] = "sshleifer/tiny-gpt2"
    os.environ["KAGAMI_TRANSFORMERS_MODEL_FLAGSHIP"] = "sshleifer/tiny-gpt2"
    os.environ["KAGAMI_TRANSFORMERS_MODEL_VISION"] = "sshleifer/tiny-gpt2"

    # Disable heavy model logic
    os.environ["KAGAMI_LLM_PREFER_LOCAL"] = "1"

    # Use test echo mode for LLM when appropriate
    # This will be overridden by individual tests that need real models
    os.environ.setdefault(
        "KAGAMI_TEST_ECHO_LLM", "1"
    )  # Use echo mode for speed (transformer imports now fixed)

    # Reduce timeouts for faster test feedback
    os.environ.setdefault("KAGAMI_LLM_TIMEOUT", "10")

    # Skip optional heavy components
    # MUST force-set these for security test bypass to work
    os.environ["KAGAMI_BOOT_MODE"] = "test"
    os.environ["KAGAMI_ENV"] = "test"
    os.environ.setdefault("KAGAMI_API_KEY", "test-api-key-0123456789abcdef0123456789")

    # Ensure offline mode for transformers (use cached models)
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")  # Allow download if needed
    os.environ.setdefault("HF_HUB_OFFLINE", "0")

    # Disable VLLM server for tests
    os.environ["KAGAMI_DISABLE_VLLM"] = "1"

    # Reduce model loading verbosity
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"


# Auto-configure on import
configure_test_environment()
