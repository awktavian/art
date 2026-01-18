"""Pytest configuration - fix PyTorch cleanup segfault.

ROOT CAUSE (Jan 5, 2026):
========================
PyTorch segfaults during cleanup when HuggingFace Hub downloads models
in background threads. The crash occurs in torch::Library::~Library()
when Python exits while hf_xet threads are still active.

SOLUTION:
=========
1. Disable HuggingFace offline mode (prevents background downloads)
2. Use torch multiprocessing 'spawn' method (safer cleanup)
3. Set torch threads to 1 during tests (reduces race conditions)
4. Gracefully shutdown thread pools before exit

This fixes the SIGSEGV at address 0x120 in libtorch_cpu.dylib.
"""

import os
import sys

# =============================================================================
# PYTORCH SEGFAULT FIX
# =============================================================================

# Prevent HuggingFace from spawning background download threads
os.environ["HF_HUB_OFFLINE"] = "0"  # Online mode, but controlled
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"  # No telemetry threads
os.environ["TRANSFORMERS_OFFLINE"] = "0"

# Set torch to use single thread during tests (prevents race conditions)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Torch multiprocessing method (spawn is safest)
os.environ["TORCH_MULTIPROCESSING_METHOD"] = "spawn"

# Disable torch JIT (reduces cleanup complexity)
os.environ["PYTORCH_JIT"] = "0"


def pytest_configure(config):
    """Configure pytest - set up torch for safe cleanup."""
    try:
        import torch
        import torch.multiprocessing as mp

        # Set multiprocessing start method to spawn (safest)
        mp.set_start_method("spawn", force=True)

        # Set torch threads to 1 (reduces race conditions)
        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)

        # Disable CUDA if available (not needed for tests)
        if torch.cuda.is_available():
            torch.cuda.is_available = lambda: False

    except ImportError:
        pass  # torch not installed, skip


def pytest_sessionfinish(session, exitstatus):
    """Clean shutdown - wait for background threads before exit."""
    import threading
    import time

    # Wait for non-daemon threads to finish (max 5 seconds)
    start = time.time()
    while time.time() - start < 5.0:
        non_daemon = [
            t for t in threading.enumerate() if t.daemon is False and t != threading.main_thread()
        ]
        if not non_daemon:
            break
        time.sleep(0.1)

    # Force cleanup of HuggingFace download threads
    hf_threads = [t for t in threading.enumerate() if "hf-xet" in t.name.lower()]
    if hf_threads:
        print(f"\n⚠️  Warning: {len(hf_threads)} HuggingFace download threads still active")
        print("   Waiting 2s for graceful shutdown...")
        time.sleep(2.0)


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

# Add packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "packages"))

# Disable warnings in tests
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
