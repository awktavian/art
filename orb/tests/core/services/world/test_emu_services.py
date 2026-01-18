from __future__ import annotations

import pytest
from typing import Any

"""Unit tests covering the local Emu3.5 integration surface.

These tests avoid heavyweight GPU/model downloads by stubbing the underlying
inference engine while verifying the K os wiring logic.
"""

from pathlib import Path

from PIL import Image

from kagami.forge.modules.world.world_generation import WorldGenerationModule
from kagami.core.services.world import emu_world_service as emu_module
from kagami.core.services.world import emu_inference as emu_inference_module
from kagami.core.services.world.emu_inference import Emu3InferenceEngine


@pytest.mark.asyncio
async def test_emu_world_service_initializes_with_existing_repo(tmp_path, monkeypatch) -> None:
    """EmuWorldService should initialize when the repo path exists."""

    repo_path = tmp_path / "Emu3.5"
    repo_path.mkdir()
    cache_root = tmp_path / "cache"
    cache_root.mkdir()

    monkeypatch.setenv("EMU_REPO_PATH", str(repo_path))
    monkeypatch.setenv("EMU_WORLD_ENABLED", "1")

    dummy_instances: list[tuple[Path, Path]] = []

    class DummyEngine:
        def __init__(
            self,
            repo: Path,
            cache: Path,
            model_snapshot_path: Path | None = None,
            vq_snapshot_path: Path | None = None,
        ) -> None:
            dummy_instances.append((repo, cache, model_snapshot_path, vq_snapshot_path))  # type: ignore[arg-type]
            self.ready = False

        async def initialize(self) -> None:
            self.ready = True

    model_snapshot = cache_root / "models" / "emu"
    vq_snapshot = cache_root / "models" / "vq"
    model_snapshot.mkdir(parents=True, exist_ok=True)
    vq_snapshot.mkdir(parents=True, exist_ok=True)

    async def fake_download(self) -> tuple[Path, Path]:
        self._download_called = True
        return model_snapshot, vq_snapshot

    monkeypatch.setattr(emu_inference_module, "Emu3InferenceEngine", DummyEngine)
    monkeypatch.setattr(emu_module.EmuWorldService, "_ensure_models_downloaded", fake_download)
    monkeypatch.setattr(emu_module.Config, "get_model_cache_path", lambda: cache_root)

    service = emu_module.EmuWorldService()
    await service.initialize()

    assert service._initialized is True
    assert dummy_instances
    repo_used, cache_used, model_snap, vq_snap = dummy_instances[0]
    assert repo_used == repo_path
    assert cache_used == cache_root / "emu3.5"
    assert model_snap == model_snapshot
    assert vq_snap == vq_snapshot
    assert getattr(service, "_download_called", False) is True


def test_build_prompt_handles_reference_images():
    """Ensure prompt construction toggles IMAGE tokens when ref images exist."""

    engine = Emu3InferenceEngine(Path("."), Path("."))
    sample_image = Image.new("RGB", (8, 8), color="white")

    prompt_with_image, unc_with_image = engine.build_prompt(
        "Describe the sample world",
        mode="visual_narrative",
        reference_image=sample_image,
    )

    assert "<|IMAGE|>" in prompt_with_image
    assert "<|IMAGE|>" in unc_with_image

    prompt_without_image, unc_without_image = engine.build_prompt(
        "Describe the sample world",
        mode="visual_narrative",
    )

    assert "<|IMAGE|>" not in prompt_without_image
    assert "<|IMAGE|>" not in unc_without_image


def test_world_generation_defaults_to_emu(monkeypatch) -> None:
    """WorldGenerationModule should prefer the Emu provider by default."""

    monkeypatch.setenv("WORLD_GEN_PROVIDER", "EMU")
    module = WorldGenerationModule()

    assert module.default_provider == "emu"
    assert "emu" in module.list_providers()


@pytest.mark.asyncio
async def test_generate_world_waits_for_background_completion(monkeypatch, tmp_path) -> None:
    """EmuWorldService should await the managed task when wait=True."""

    service = emu_module.EmuWorldService()
    service._initialized = True
    service._engine = object()  # type: ignore[assignment]
    service.output_root = tmp_path

    async def fake_run_generation(
        self,
        *,
        job_id,
        prompt,
        image_path,
        mode,
        num_steps,
        resolution,
        out_dir,
        correlation_id,
    ):
        self._completed_jobs[job_id] = emu_module.EmuWorldJobResult(
            success=True,
            panorama_path=str(out_dir / "panorama.png"),
            world_output_dir=str(out_dir),
            narrative_data={"mode": mode},
        )

    monkeypatch.setattr(emu_module.EmuWorldService, "_run_generation", fake_run_generation)

    class DummyManager:
        def __init__(self):
            self.created_name = None
            self.coro = None
            self.wait_calls = 0

        async def create_task(self, name, coro, **kwargs):
            self.created_name = name
            self.coro = coro
            return name

        async def wait_for_task(self, name, timeout=None):
            self.wait_calls += 1
            assert name == self.created_name
            return await self.coro

    dummy_manager = DummyManager()
    monkeypatch.setattr(emu_module, "task_manager", dummy_manager)

    job_id = await service.generate_world(
        prompt="Test prompt",
        mode="visual_narrative",
        wait=True,
        num_steps=1,
    )

    assert dummy_manager.wait_calls == 1
    result = await service.get_result(job_id)
    assert result is not None
    assert result.success is True
