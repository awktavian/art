# SPDX-License-Identifier: MIT
"""Reproducibility utilities for benchmark runs.

Ensures benchmarks can be reproduced exactly by tracking:
- Random seeds
- Package versions
- Hardware configuration
- Environment variables
"""

from __future__ import annotations

import hashlib
import os
import platform
import random
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ReproducibilityInfo:
    """Complete reproducibility information for a benchmark run."""

    # Seeds
    random_seed: int = 42
    numpy_seed: int | None = None
    torch_seed: int | None = None

    # Environment
    python_version: str = ""
    platform_info: str = ""
    hostname: str = ""

    # Package versions
    package_versions: dict[str, str] = field(default_factory=dict)

    # Hardware
    cpu_info: str = ""
    gpu_info: str = ""
    memory_gb: float = 0.0

    # Timestamp
    timestamp: str = ""

    # Workspace
    workspace_hash: str = ""
    git_commit: str = ""
    git_branch: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "random_seed": self.random_seed,
            "numpy_seed": self.numpy_seed,
            "torch_seed": self.torch_seed,
            "python_version": self.python_version,
            "platform_info": self.platform_info,
            "hostname": self.hostname,
            "package_versions": self.package_versions,
            "cpu_info": self.cpu_info,
            "gpu_info": self.gpu_info,
            "memory_gb": self.memory_gb,
            "timestamp": self.timestamp,
            "workspace_hash": self.workspace_hash,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
        }


def set_global_seed(seed: int = 42) -> None:
    """Set global random seeds for reproducibility.

    Sets seeds for:
    - Python's random module
    - NumPy (if available)
    - PyTorch (if available)

    Args:
        seed: The random seed to use.
    """
    # Python random
    random.seed(seed)

    # NumPy
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    # PyTorch
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
            # Ensure deterministic algorithms
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        if torch.backends.mps.is_available():
            # MPS doesn't have direct seed control, but we set the general seed
            pass
    except ImportError:
        pass


def get_package_versions() -> dict[str, str]:
    """Get versions of key packages."""
    packages = [
        "torch",
        "numpy",
        "scipy",
        "httpx",
        "fastapi",
        "pydantic",
        "z3-solver",
        "transformers",
    ]

    versions = {}
    for pkg in packages:
        try:
            if pkg == "z3-solver":
                import z3

                versions[pkg] = z3.get_version_string()
            else:
                import importlib.metadata

                versions[pkg] = importlib.metadata.version(pkg)
        except Exception:
            pass

    return versions


def get_hardware_info() -> dict[str, Any]:
    """Get hardware configuration."""
    import psutil

    info = {
        "cpu": platform.processor() or "unknown",
        "cpu_count": psutil.cpu_count(logical=True),
        "memory_gb": psutil.virtual_memory().total / (1024**3),
        "gpu": "none",
    }

    # GPU info
    try:
        import torch

        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            info["gpu_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        elif torch.backends.mps.is_available():
            info["gpu"] = "Apple MPS"
    except ImportError:
        pass

    return info


def get_git_info() -> dict[str, str]:
    """Get git repository information."""
    import subprocess

    info = {"commit": "", "branch": ""}

    try:
        # Get commit hash
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["commit"] = result.stdout.strip()[:12]

        # Get branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            info["branch"] = result.stdout.strip()
    except Exception:
        pass

    return info


def get_workspace_hash() -> str:
    """Generate hash of current workspace for tracking."""
    workspace = os.getcwd()
    return hashlib.sha256(workspace.encode()).hexdigest()[:12]


def get_reproducibility_info(seed: int = 42) -> dict[str, Any]:
    """Get complete reproducibility information.

    Args:
        seed: The random seed being used.

    Returns:
        Dictionary with all reproducibility info.
    """
    hw_info = get_hardware_info()
    git_info = get_git_info()

    info = ReproducibilityInfo(
        random_seed=seed,
        python_version=sys.version.split()[0],
        platform_info=f"{platform.system()} {platform.release()}",
        hostname=platform.node(),
        package_versions=get_package_versions(),
        cpu_info=hw_info.get("cpu", "unknown"),
        gpu_info=hw_info.get("gpu", "none"),
        memory_gb=hw_info.get("memory_gb", 0.0),
        timestamp=datetime.utcnow().isoformat() + "Z",
        workspace_hash=get_workspace_hash(),
        git_commit=git_info.get("commit", ""),
        git_branch=git_info.get("branch", ""),
    )

    # Set numpy/torch seeds if available
    try:
        import numpy  # noqa: F401 - availability check

        info.numpy_seed = seed
    except ImportError:
        pass

    try:
        import torch  # noqa: F401 - availability check

        info.torch_seed = seed
    except ImportError:
        pass

    return info.to_dict()


@dataclass
class ReproducibilityContext:
    """Context manager for reproducible benchmark execution.

    Usage:
        with ReproducibilityContext(seed=42) as ctx:
            # Run benchmark
            result = run_benchmark()
            result.reproducibility_info = ctx.info
    """

    seed: int = 42
    info: dict[str, Any] = field(default_factory=dict)
    # Saved RNG state for restoration on exit (best-effort; optional deps)
    _py_random_state: object | None = field(default=None, init=False, repr=False)
    _numpy_random_state: object | None = field(default=None, init=False, repr=False)
    _torch_cpu_state: object | None = field(default=None, init=False, repr=False)
    _torch_cuda_state: object | None = field(default=None, init=False, repr=False)
    _torch_cudnn_deterministic: bool | None = field(default=None, init=False, repr=False)
    _torch_cudnn_benchmark: bool | None = field(default=None, init=False, repr=False)

    def __enter__(self) -> ReproducibilityContext:
        """Enter context and set seeds."""
        # Capture current RNG state so benchmarks don't globally pollute callers.
        self._py_random_state = random.getstate()
        try:
            import numpy as np

            self._numpy_random_state = np.random.get_state()
        except ImportError:
            self._numpy_random_state = None

        try:
            import torch

            self._torch_cpu_state = torch.random.get_rng_state()
            if torch.cuda.is_available():
                self._torch_cuda_state = torch.cuda.get_rng_state_all()
            # Preserve deterministic flags if available
            try:
                self._torch_cudnn_deterministic = bool(torch.backends.cudnn.deterministic)
                self._torch_cudnn_benchmark = bool(torch.backends.cudnn.benchmark)
            except Exception:
                self._torch_cudnn_deterministic = None
                self._torch_cudnn_benchmark = None
        except ImportError:
            self._torch_cpu_state = None
            self._torch_cuda_state = None
            self._torch_cudnn_deterministic = None
            self._torch_cudnn_benchmark = None

        set_global_seed(self.seed)
        self.info = get_reproducibility_info(self.seed)
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: object,
    ) -> None:
        """Exit context."""
        # Restore RNG state (best-effort).
        if self._py_random_state is not None:
            try:
                random.setstate(self._py_random_state)  # type: ignore[arg-type]
            except Exception:
                pass

        if self._numpy_random_state is not None:
            try:
                import numpy as np

                np.random.set_state(self._numpy_random_state)  # type: ignore[arg-type]
            except Exception:
                pass

        if self._torch_cpu_state is not None:
            try:
                import torch

                torch.random.set_rng_state(self._torch_cpu_state)  # type: ignore[arg-type]
                if self._torch_cuda_state is not None and torch.cuda.is_available():
                    try:
                        torch.cuda.set_rng_state_all(self._torch_cuda_state)  # type: ignore[arg-type]
                    except Exception:
                        pass
                if self._torch_cudnn_deterministic is not None:
                    try:
                        torch.backends.cudnn.deterministic = self._torch_cudnn_deterministic
                    except Exception:
                        pass
                if self._torch_cudnn_benchmark is not None:
                    try:
                        torch.backends.cudnn.benchmark = self._torch_cudnn_benchmark
                    except Exception:
                        pass
            except Exception:
                pass

        return None


@contextmanager
def reproducible_benchmark(seed: int = 42) -> Generator[dict[str, Any], None, None]:
    """Context manager for reproducible benchmark runs.

    Usage:
        with reproducible_benchmark(seed=42) as repro_info:
            result = run_my_benchmark()
            result["reproducibility"] = repro_info
    """
    set_global_seed(seed)
    info = get_reproducibility_info(seed)
    yield info
