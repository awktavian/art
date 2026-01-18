"""MPS-optimized wrapper for UniRig model integration."""

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

import torch

from kagami.core.utils.external_repos import check_unirig

logger = logging.getLogger(__name__)

# Check repo availability early
_repo_status = check_unirig()
if _repo_status.available:
    # Add UniRig paths to Python path if local repo exists
    unirig_repo_path = (
        Path(__file__).parent.parent.parent.parent.parent / "external" / "unirig_repo"
    )
    if unirig_repo_path.exists():
        sys.path.insert(0, str(unirig_repo_path))
else:
    # UniRig is an optional external dependency - use debug level to avoid startup noise
    # Users who need rigging will see the error when they try to use the feature
    logger.debug(
        f"UniRig not fully available: {_repo_status.error_message}. "
        f"Character rigging features may be limited. {_repo_status.setup_command}"
    )


class MPSUniRigWrapper:
    """Wrapper for UniRig with MPS optimizations."""

    def __init__(self, device: torch.device | None = None) -> None:
        """Initialize the UniRig wrapper.

        Args:
            device: PyTorch device to use. Defaults to MPS if available.
        """
        self.device = device or torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model_path = Path.home() / ".cache" / "huggingface" / "models--VAST-AI--UniRig"
        self.api_url = os.environ.get("UNIRIG_API_URL", "https://api.unirig.ai/v3")
        self.api_key = os.environ.get("UNIRIG_API_KEY", "")
        self.pipeline = None
        self.initialized = False
        self._performance_stats = {
            "total_generations": 0,
            "average_time_ms": 0.0,
            "device": str(self.device),
        }

    async def load_models(self) -> Any:
        """Load UniRig models asynchronously and return True on success."""
        if self.initialized:
            return

        # Warn if repo not fully available (but don't fail - API mode might work)
        if not _repo_status.available:
            logger.warning(
                f"UniRig repository check: {_repo_status.error_message}. "
                f"Will attempt to use API mode if configured."
            )

        try:
            logger.info("Loading UniRig models...")

            # Check if using API mode
            if self.api_key:
                logger.info("Using UniRig API mode")
                self.mode = "api"
                # Initialize API client
                import httpx

                self.api_client = httpx.AsyncClient(
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
            else:
                # Require local model; auto-download if missing
                if not self.model_path.exists():
                    try:
                        logger.info(
                            "UniRig local weights not found. Attempting auto-download from Hugging Face (VAST-AI/UniRig)..."
                        )
                        self.model_path.mkdir(parents=True, exist_ok=True)
                        try:
                            from huggingface_hub import hf_hub_download
                        except Exception as _dl_err:
                            raise RuntimeError(
                                f"huggingface_hub required to auto-download UniRig: {_dl_err}"
                            ) from None
                        ckpt_path = hf_hub_download(
                            repo_id="VAST-AI/UniRig", filename="unirig_1.pt"
                        )
                        import shutil as _shutil

                        _shutil.copy2(ckpt_path, str(self.model_path / "unirig_1.pt"))
                        logger.info("✅ UniRig weights downloaded to %s", str(self.model_path))
                    except Exception as _e:
                        raise RuntimeError(
                            f"UniRig auto-download failed: {_e}. Set UNIRIG_API_KEY for API mode or place weights at {self.model_path}."
                        ) from None

                logger.info(f"Loading UniRig from {self.model_path}")
                self.mode = "local"

                # Load the local model
                from unirig import UniRigModel

                # Optional precision control
                precision = os.environ.get("UNIRIG_PRECISION", "auto").lower()
                if self.device.type in ("cuda", "mps") and precision in (
                    "fp16",
                    "half",
                    "auto",
                ):
                    pass
                self.model = UniRigModel.from_pretrained(self.model_path, device=self.device)
                logger.info("UniRig model loaded successfully")

            self.initialized = True
            logger.info(f"UniRig initialized in {self.mode} mode")
            return True

        except Exception as e:
            logger.error(f"Failed to load UniRig models: {e}")
            raise

    async def generate_rig(
        self, mesh_path: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate rig for a mesh.

        Args:
            mesh_path: Path to the input mesh
            options: Optional generation options

        Returns:
            Dictionary with rigging results
        """
        if not self.initialized:
            await self.load_models()

        try:
            start_time = (
                torch.cuda.Event(enable_timing=True) if self.device.type == "cuda" else None
            )
            end_time = torch.cuda.Event(enable_timing=True) if self.device.type == "cuda" else None

            if start_time:
                start_time.record()

            logger.info(f"Generating rig for mesh: {mesh_path}")

            if self.mode == "api":
                import time

                start_ms = time.time() * 1000.0
                result = await self._generate_rig_api(mesh_path, options)
                try:
                    from kagami_observability.metrics import (
                        UNIRIG_RIG_LATENCY_MS,
                        UNIRIG_RIGS,
                    )

                    UNIRIG_RIGS.labels("api").inc()
                    UNIRIG_RIG_LATENCY_MS.observe(max(0.0, (time.time() * 1000.0) - start_ms))
                except Exception:
                    pass
            elif self.mode == "local":
                import time

                start_ms = time.time() * 1000.0
                result = await self._generate_rig_local(mesh_path, options)
                try:
                    from kagami_observability.metrics import (
                        UNIRIG_RIG_LATENCY_MS,
                        UNIRIG_RIGS,
                    )

                    UNIRIG_RIGS.labels("local").inc()
                    UNIRIG_RIG_LATENCY_MS.observe(max(0.0, (time.time() * 1000.0) - start_ms))
                except Exception:
                    pass
            else:
                raise RuntimeError(f"Invalid mode: {self.mode}") from None

            if start_time and end_time:
                end_time.record()
                torch.cuda.synchronize()
                elapsed_time = start_time.elapsed_time(end_time)
                self._update_performance_stats(elapsed_time)

            return result

        except Exception as e:
            logger.error(f"Rig generation failed: {e}")
            return {"success": False, "error": str(e), "mode": self.mode}

    def get_memory_usage(self) -> dict[str, Any]:
        """Best-effort memory stats for observability."""
        try:
            import psutil
        except Exception:
            psutil: Any = None  # type: ignore[no-redef]
        mem = psutil.virtual_memory()._asdict() if psutil else {}
        return {
            "device": str(self.device),
            "mode": getattr(self, "mode", "unknown"),
            "rss_bytes": mem.get("used"),
        }

    async def rig_mesh(self, mesh: Any, cls: str | None = None) -> dict[str, Any]:
        """Compatibility shim used by RiggingModule.

        Saves the provided mesh to a temporary OBJ file, calls generate_rig,
        and returns a dict[str, Any] containing the rigged mesh, skeleton and weights.
        """
        try:
            import tempfile

            import trimesh as _trimesh  # local import to avoid hard dep at import time

            with tempfile.TemporaryDirectory() as td:
                obj_path = str(Path(td) / "input.obj")
                # Export mesh
                try:
                    mesh.export(obj_path)
                except Exception:
                    # Construct trimesh and export
                    m = _trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces)
                    m.export(obj_path)

                # Options can include class token
                opts: dict[str, Any] = {}
                if cls is not None:
                    opts["class_token"] = cls

                res = await self.generate_rig(obj_path, opts)
                if not res or not res.get("success"):
                    raise RuntimeError(res.get("error", "rig generation failed")) from None

                rigged_mesh_path = res.get("rig_path")
                try:
                    rigged_mesh = _trimesh.load(rigged_mesh_path) if rigged_mesh_path else mesh
                except Exception:
                    rigged_mesh = mesh

                return {
                    "mesh": rigged_mesh,
                    "skeleton": res.get("skeleton"),
                    "weights": res.get("weights"),
                }
        except Exception as e:
            logger.error(f"rig_mesh failed: {e}")
            raise

    async def _generate_rig_api(
        self, mesh_path: str, options: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Generate rig using UniRig API."""
        # Read mesh file
        with open(mesh_path, "rb") as f:
            mesh_data = f.read()

        # Prepare API request
        files = {"mesh": (Path(mesh_path).name, mesh_data, "application/octet-stream")}
        data = options or {}

        # Make API call
        response = await self.api_client.post(f"{self.api_url}/generate", files=files, data=data)
        response.raise_for_status()

        result_any = response.json()
        result: dict[str, Any] = result_any if isinstance(result_any, dict) else {"raw": result_any}
        result["mode"] = "api"
        return result

    async def _generate_rig_local(
        self, mesh_path: str, options: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Generate rig using local UniRig model."""
        # Load mesh
        import trimesh

        mesh = trimesh.load(mesh_path)

        # Convert to tensor
        vertices = torch.tensor(mesh.vertices, dtype=torch.float32, device=self.device)  # type: ignore  # Dynamic attr
        faces = torch.tensor(mesh.faces, dtype=torch.long, device=self.device)  # type: ignore  # Dynamic attr

        # Run inference
        with torch.no_grad():
            use_autocast = os.environ.get("UNIRIG_PRECISION", "auto").lower() in (
                "fp16",
                "half",
                "auto",
            ) and self.device.type in ("cuda", "mps")
            if use_autocast and self.device.type == "cuda":
                with torch.cuda.amp.autocast():
                    result = self.model.generate_rig(
                        vertices=vertices, faces=faces, **(options or {})
                    )
            else:
                result = self.model.generate_rig(vertices=vertices, faces=faces, **(options or {}))

        # Save rigged mesh
        rigged_path = mesh_path.replace(".obj", "_rigged.obj")
        result.save(rigged_path)

        return {
            "success": True,
            "rig_path": rigged_path,
            "skeleton": result.skeleton.to_dict(),
            "weights": (
                result.weights.detach().cpu().numpy().tolist()
                if hasattr(result.weights, "detach")
                else result.weights.cpu().numpy().tolist()
            ),
            "mode": "local",
        }

    def _update_performance_stats(self, elapsed_time: float) -> None:
        """Update performance statistics."""
        total_generations = self._performance_stats.get("total_generations", 0)
        if isinstance(total_generations, (int, float)):
            self._performance_stats["total_generations"] = int(total_generations) + 1
            total = int(total_generations) + 1
        else:
            self._performance_stats["total_generations"] = 1
            total = 1

        avg_time = self._performance_stats.get("average_time_ms", 0.0)
        if isinstance(avg_time, (int, float)):
            avg = float(avg_time)
        else:
            avg = 0.0

        self._performance_stats["average_time_ms"] = (avg * (total - 1) + elapsed_time) / total

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self._performance_stats.copy()

    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, "pipeline") and self.pipeline is not None:
            del self.pipeline  # type: ignore  # Defensive/fallback code
            # Use unified cache clearing (handles CUDA/MPS)
            from kagami.core.utils.device import empty_cache

            empty_cache(self.device)
        # Close API client if used
        try:
            api_client = getattr(self, "api_client", None)
            if api_client is not None and hasattr(api_client, "aclose"):
                # Ensure the client is closed asynchronously
                import anyio

                anyio.run(api_client.aclose)
        except Exception:
            pass


def create_mps_unirig(device: torch.device | None = None) -> MPSUniRigWrapper:
    """Create (or reuse) an MPS-optimized UniRig wrapper.

    Args:
        device: PyTorch device to use. Defaults to MPS if available.

    Returns:
        MPSUniRigWrapper instance
    """
    # Cache wrappers per device so repeated Forge module instantiations
    # do not reload the UniRig client/model.
    global _UNIRIG_WRAPPER_CACHE
    global _UNIRIG_WRAPPER_CACHE_LOCK

    # Coerce strings into torch.device for defensive compatibility.
    coerced: torch.device | None
    if isinstance(device, str):
        try:  # type: ignore[unreachable]
            coerced = torch.device(device)
        except Exception:
            coerced = None
    else:
        coerced = device

    # Determine effective device key (wrapper chooses default if None).
    effective = coerced or torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    key = str(effective)

    with _UNIRIG_WRAPPER_CACHE_LOCK:
        existing = _UNIRIG_WRAPPER_CACHE.get(key)
        if existing is not None:
            return existing
        wrapper = MPSUniRigWrapper(device=effective)
        _UNIRIG_WRAPPER_CACHE[key] = wrapper
        return wrapper


# Cache storage (module-level)
_UNIRIG_WRAPPER_CACHE: dict[str, MPSUniRigWrapper] = {}
_UNIRIG_WRAPPER_CACHE_LOCK = threading.Lock()
