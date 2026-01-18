"""Test configuration for HAL tests.

Created: December 15, 2025
"""

import os
import sys
from pathlib import Path

import pytest

# Ensure satellite packages are importable for HAL tests
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HAL_PATH = _REPO_ROOT / "satellites" / "hal"
_SMARTHOME_PATH = _REPO_ROOT / "satellites" / "smarthome"

for path in [_HAL_PATH, _SMARTHOME_PATH]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture(autouse=True)
def reset_virtual_hal_config() -> None:
    """Reset virtual HAL config between tests to prevent state leakage.

    This is critical for tests that modify environment variables
    affecting virtual HAL configuration (e.g., KAGAMI_VIRTUAL_MIC_PATTERN).

    Without this, the global config singleton persists across tests,
    causing hangs and flaky behavior in the full test suite.
    """
    # Store original env vars
    virtual_env_vars = [
        "KAGAMI_VIRTUAL_MIC_PATTERN",
        "KAGAMI_VIRTUAL_RECORD_MODE",
        "KAGAMI_VIRTUAL_OUTPUT_DIR",
        "KAGAMI_VIRTUAL_DETERMINISTIC",
        "KAGAMI_VIRTUAL_SEED",
        "KAGAMI_VIRTUAL_CAMERA_WIDTH",
        "KAGAMI_VIRTUAL_CAMERA_HEIGHT",
    ]
    original_values = {var: os.environ.get(var) for var in virtual_env_vars}

    # Run test
    yield

    # Cleanup: Reset config and restore environment
    try:
        from kagami_hal.adapters.virtual.config import reset_virtual_config

        reset_virtual_config()
    except ImportError:
        pass  # Virtual HAL not available

    # Restore original environment variables
    for var, value in original_values.items():
        if value is None:
            os.environ.pop(var, None)
        else:
            os.environ[var] = value
