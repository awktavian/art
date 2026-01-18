# pyright: reportGeneralTypeIssues=false
"""Consolidated Training Entry Point for Kagami World Model.

CREATED: January 5, 2026
UPDATED: January 5, 2026 - Added Gemini Embedding Grounding

This module provides THE SINGLE entry point for all Kagami training:
- TPU hyperscale training (v5e, v5p, v6e/Trillium)
- Local training (MPS, CUDA, CPU)
- Vertex AI Gemini fine-tuning
- Gemini embedding distillation for language grounding
- Full multimodal support

ALL OTHER TRAINING SCRIPTS ARE DEPRECATED. Use this module.

Features:
- Unified configuration for all backends
- W&B integration (required for production)
- GCS checkpointing with FULL weights (not just metadata)
- Vertex AI Gemini fine-tuning
- Multimodal training (vision + language + action)
- 7-colony parallel training (unique to Kagami)

USAGE:
======
    # CLI
    python -m kagami.core.training.consolidated --config training.yaml

    # Programmatic
    from kagami.core.training.consolidated import train_kagami

    results = await train_kagami(
        config_path="config/training_stable.yaml",
        backend="auto",  # or "tpu", "local", "gemini"
    )

Architecture:
=============
    ┌─────────────────────────────────────────────────────────────────┐
    │                   ConsolidatedTrainer                            │
    │                                                                  │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
    │  │ TPU Backend  │  │Local Backend │  │ Gemini Fine-Tuning   │  │
    │  │ Hyperscale   │  │ MPS/CUDA/CPU │  │ Vertex AI            │  │
    │  └──────────────┘  └──────────────┘  └──────────────────────┘  │
    │                                                                  │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │  Shared Infrastructure                                    │   │
    │  │  - W&B Logger                                            │   │
    │  │  - GCS Checkpointer (full weights)                       │   │
    │  │  - Curriculum Manager                                     │   │
    │  │  - Multimodal Data Pipeline                              │   │
    │  └─────────────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
import yaml

if TYPE_CHECKING:
    from kagami.core.training.gemini_grounding import GeminiGroundingModule

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================
# NOTE: PlateauDetector and KLCollapseMonitor DELETED (Jan 11, 2026)
# These were duplicates of kagami.core.training.validation.TrainingValidator
# which is now the canonical unified validator (see line ~1025)


class TrainingBackend(str, Enum):
    """Training backend options."""

    AUTO = "auto"  # Auto-detect best backend
    TPU = "tpu"  # Google Cloud TPU (hyperscale)
    LOCAL = "local"  # Local GPU/CPU/MPS
    GEMINI = "gemini"  # Vertex AI Gemini fine-tuning


@dataclass
class ConsolidatedConfig:
    """Unified configuration for all training backends.

    This is THE ONLY config class you need. It translates to backend-specific
    configs automatically.
    """

    # === Backend Selection ===
    backend: str | TrainingBackend = TrainingBackend.AUTO

    # === Model ===
    model_preset: str = "balanced"  # Model configuration preset
    bulk_dim: int = 128  # Bulk space dimension
    s7_dim: int = 7  # S7 fiber dimension

    # === Scale ===
    num_devices: int = 1  # TPU chips or GPUs
    global_batch_size: int = 64
    sequence_length: int = 16
    gradient_accumulation_steps: int = 1

    # === Training ===
    total_steps: int = 100_000
    learning_rate: float = 3e-4
    min_lr: float = 1e-5
    warmup_steps: int = 1000
    weight_decay: float = 0.01
    grad_clip: float = 1.0

    # === Curriculum ===
    enable_curriculum: bool = True
    auto_transition: bool = True

    # === Multimodal ===
    enable_vision: bool = True
    enable_language: bool = True
    enable_action: bool = True
    vision_resolution: tuple[int, int] = (128, 128)
    video_frames: int = 16

    # === Language Training ===
    language_warmup_steps: int = 50_000
    language_caption_weight: float = 0.1
    language_grounding_weight: float = 0.1
    language_generation_weight: float = 0.05

    # === Checkpointing ===
    checkpoint_path: str = "gs://kagami-training-schizodactyl-2026/checkpoints"
    checkpoint_every: int = 1000
    max_checkpoints: int = 5
    save_optimizer: bool = True
    save_full_weights: bool = True  # ALWAYS save full weights

    # === Logging ===
    wandb_enabled: bool = True
    wandb_project: str = "kagami-world-model"
    wandb_entity: str = "kagami-ai"
    wandb_tags: list[str] = field(default_factory=list)
    log_every: int = 100
    eval_every: int = 1000

    # === TPU-Specific ===
    preemptible: bool = True  # Use preemptible for cost savings
    tpu_topology: str = "v6e-256"  # TPU topology
    use_colony_parallel: bool = False  # Enable 7-colony parallelism
    use_e8_gradient_reduction: bool = True

    # === Gemini Fine-Tuning ===
    gemini_base_model: str = "gemini-1.5-pro"
    gemini_tuning_epochs: int = 3
    gemini_adapter_size: int = 16

    # === Gemini Embedding Grounding (Jan 5, 2026) ===
    enable_gemini_grounding: bool = True  # Use Gemini embeddings as teacher
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dim: int = 768  # 768, 1536, or 3072
    gemini_grounding_distill_weight: float = 1.0  # MSE distillation weight
    gemini_grounding_contrastive_weight: float = 0.5  # InfoNCE weight

    # === GCP ===
    gcp_project: str = "gen-lang-client-0509316009"
    gcp_region: str = "us-central1"
    gcs_bucket: str = "kagami-training-schizodactyl-2026"

    @classmethod
    def from_yaml(cls, path: str | Path) -> ConsolidatedConfig:
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Flatten nested config
        flat = {}
        for section in [
            "model",
            "training",
            "hardware",
            "data",
            "output",
            "visualization",
            "curriculum",
            "loss",
            "generation",
        ]:
            if section in data:
                for key, value in data[section].items():
                    # Map known keys
                    if key == "batch_size":
                        flat["global_batch_size"] = value
                    elif key == "max_steps":
                        flat["total_steps"] = value
                    elif key == "checkpoint_dir":
                        if not value.startswith("gs://"):
                            flat["checkpoint_path"] = (
                                f"gs://kagami-training-schizodactyl-2026/{value}"
                            )
                        else:
                            flat["checkpoint_path"] = value
                    elif key == "wandb_project":
                        flat["wandb_project"] = value
                    elif hasattr(cls, key):
                        flat[key] = value

        # Top-level wandb config
        if "wandb" in data:
            wb = data["wandb"]
            flat["wandb_enabled"] = wb.get("enabled", True)
            flat["wandb_project"] = wb.get(
                "project", flat.get("wandb_project", "kagami-world-model")
            )
            flat["wandb_entity"] = wb.get("entity", "kagami-ai")
            flat["wandb_tags"] = wb.get("tags", [])

        return cls(**{k: v for k, v in flat.items() if hasattr(cls, k)})

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Enum):
                result[k] = v.value
            elif isinstance(v, tuple):
                result[k] = list(v)
            else:
                result[k] = v
        return result

    @property
    def backend_enum(self) -> TrainingBackend:
        """Get backend as enum."""
        if isinstance(self.backend, TrainingBackend):
            return self.backend
        return TrainingBackend(self.backend)


# =============================================================================
# W&B INTEGRATION
# =============================================================================


class WandBLogger:
    """Weights & Biases logger with full integration.

    Handles:
    - Run initialization
    - Metric logging
    - Artifact management (checkpoints)
    - System metrics
    """

    def __init__(self, config: ConsolidatedConfig):
        """Initialize W&B logger."""
        self.config = config
        self.enabled = config.wandb_enabled
        self._run = None
        self._step = 0

    def initialize(self) -> None:
        """Initialize W&B run."""
        if not self.enabled:
            logger.info("W&B disabled")
            return

        try:
            import wandb

            # Generate run name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = f"kagami_{timestamp}"

            backend_str = (
                self.config.backend.value
                if isinstance(self.config.backend, Enum)
                else str(self.config.backend)
            )
            self._run = wandb.init(
                project=self.config.wandb_project,
                entity=self.config.wandb_entity,
                name=run_name,
                tags=[*self.config.wandb_tags, backend_str, f"devices_{self.config.num_devices}"],
                config=self.config.to_dict(),
                resume="allow",
            )

            logger.info(f"W&B initialized: {self._run.url}")

        except ImportError:
            logger.warning("wandb not installed, disabling logging")
            self.enabled = False
        except Exception as e:
            logger.error(f"W&B initialization failed: {e}")
            self.enabled = False

    def log(self, metrics: dict[str, Any], step: int | None = None) -> None:
        """Log metrics to W&B."""
        if not self.enabled or self._run is None:
            return

        import wandb

        step = step or self._step
        self._step = step

        # Flatten nested dicts
        flat_metrics = {}
        for key, value in metrics.items():
            if isinstance(value, dict):
                for subkey, subval in value.items():
                    flat_metrics[f"{key}/{subkey}"] = subval
            else:
                flat_metrics[key] = value

        wandb.log(flat_metrics, step=step)

    def log_checkpoint(self, checkpoint_path: str, step: int) -> None:
        """Log checkpoint as W&B artifact."""
        if not self.enabled or self._run is None:
            return

        import wandb

        artifact = wandb.Artifact(
            name=f"checkpoint-step-{step}",
            type="model",
            metadata={"step": step},
        )

        if checkpoint_path.startswith("gs://"):
            artifact.add_reference(checkpoint_path)
        else:
            artifact.add_file(checkpoint_path)

        self._run.log_artifact(artifact)

    def finish(self) -> None:
        """Finish W&B run."""
        if self._run is not None:
            import wandb

            wandb.finish()
            self._run = None


# =============================================================================
# GCS CHECKPOINTING (FULL WEIGHTS)
# =============================================================================


class GCSCheckpointer:
    """GCS Checkpointer that saves FULL model weights.

    Unlike the TPU checkpointer that only saved metadata, this saves:
    - Full model state dict
    - Optimizer state dict
    - Scheduler state dict
    - Curriculum state
    - Training metadata
    """

    def __init__(self, config: ConsolidatedConfig):
        """Initialize GCS checkpointer."""
        self.config = config
        self._client = None
        self._bucket = None

    def initialize(self) -> None:
        """Initialize GCS client."""
        try:
            from google.cloud import storage

            self._client = storage.Client(project=self.config.gcp_project)

            # Parse bucket from path
            path = self.config.checkpoint_path
            if path.startswith("gs://"):
                path = path[5:]
            bucket_name = path.split("/")[0]
            self._bucket = self._client.bucket(bucket_name)

            logger.info(f"GCS checkpointer initialized: {bucket_name}")

        except ImportError:
            logger.warning("google-cloud-storage not installed")
        except Exception as e:
            logger.error(f"GCS initialization failed: {e}")

    def save(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer | None,
        scheduler: Any | None,
        step: int,
        loss: float,
        curriculum_state: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Save checkpoint with FULL weights to GCS.

        Args:
            model: Model to checkpoint
            optimizer: Optimizer state
            scheduler: LR scheduler state
            step: Training step
            loss: Current loss
            curriculum_state: Curriculum state dict
            extra: Additional metadata

        Returns:
            GCS path to checkpoint
        """
        import hashlib
        import io

        # Build checkpoint
        checkpoint = {
            "step": step,
            "loss": loss,
            "timestamp": datetime.now(UTC).isoformat(),
            "model_state_dict": model.state_dict(),
            "config": self.config.to_dict(),
        }

        if self.config.save_optimizer and optimizer is not None:
            checkpoint["optimizer_state_dict"] = optimizer.state_dict()

        if scheduler is not None:
            checkpoint["scheduler_state_dict"] = scheduler.state_dict()

        if curriculum_state is not None:
            checkpoint["curriculum_state"] = curriculum_state

        if extra is not None:
            checkpoint["extra"] = extra

        # Count parameters
        num_params = sum(p.numel() for p in model.parameters())
        checkpoint["num_params"] = num_params

        # Serialize
        buffer = io.BytesIO()
        torch.save(checkpoint, buffer)
        data = buffer.getvalue()

        # Compute checksum
        checksum = hashlib.sha256(data).hexdigest()

        # Determine path
        path = self.config.checkpoint_path
        if path.startswith("gs://"):
            path = path[5:]
        parts = path.split("/", 1)
        prefix = parts[1] if len(parts) > 1 else "checkpoints"

        checkpoint_dir = f"{prefix}/step_{step:08d}"

        # Upload to GCS
        if self._bucket is not None:
            # Upload weights
            weights_blob = self._bucket.blob(f"{checkpoint_dir}/checkpoint.pt")
            weights_blob.upload_from_string(data)

            # Upload metadata
            metadata = {
                "step": step,
                "loss": loss,
                "timestamp": checkpoint["timestamp"],
                "num_params": num_params,
                "checksum": checksum,
                "size_bytes": len(data),
            }
            metadata_blob = self._bucket.blob(f"{checkpoint_dir}/metadata.json")
            metadata_blob.upload_from_string(json.dumps(metadata, indent=2))

            gcs_path = f"gs://{self._bucket.name}/{checkpoint_dir}"
            logger.info(
                f"Checkpoint saved: step={step}, size={len(data) / 1024 / 1024:.1f}MB, "
                f"params={num_params:,}, path={gcs_path}"
            )

            return gcs_path
        else:
            # Fallback to local
            local_path = Path(f"checkpoints/step_{step:08d}")
            local_path.mkdir(parents=True, exist_ok=True)

            with open(local_path / "checkpoint.pt", "wb") as f:
                f.write(data)

            with open(local_path / "metadata.json", "w") as f:
                json.dump(
                    {
                        "step": step,
                        "loss": loss,
                        "num_params": num_params,
                        "checksum": checksum,
                    },
                    f,
                    indent=2,
                )

            logger.info(f"Checkpoint saved locally: {local_path}")
            return str(local_path)

    def load(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer | None = None,
        scheduler: Any | None = None,
        path: str | None = None,
        step: int | None = None,
    ) -> dict[str, Any]:
        """Load checkpoint from GCS.

        Args:
            model: Model to load state into
            optimizer: Optimizer to load state into
            scheduler: Scheduler to load state into
            path: Specific checkpoint path (or None for latest)
            step: Specific step to load (or None for latest)

        Returns:
            Checkpoint metadata
        """
        import io

        if self._bucket is None:
            raise RuntimeError("GCS not initialized")

        # Find checkpoint
        if path is None:
            if step is not None:
                checkpoint_path = f"checkpoints/step_{step:08d}/checkpoint.pt"
            else:
                # Find latest
                blobs = list(self._bucket.list_blobs(prefix="checkpoints/step_"))
                checkpoint_dirs = set()
                for blob in blobs:
                    parts = blob.name.split("/")
                    if len(parts) >= 2 and parts[1].startswith("step_"):
                        checkpoint_dirs.add(parts[1])

                if not checkpoint_dirs:
                    raise FileNotFoundError("No checkpoints found")

                latest = sorted(checkpoint_dirs)[-1]
                checkpoint_path = f"checkpoints/{latest}/checkpoint.pt"
        else:
            checkpoint_path = path

        # Download
        blob = self._bucket.blob(checkpoint_path)
        data = blob.download_as_bytes()

        # Load
        buffer = io.BytesIO(data)
        checkpoint = torch.load(buffer, map_location="cpu", weights_only=False)

        # Restore model
        model.load_state_dict(checkpoint["model_state_dict"])

        # Restore optimizer
        if optimizer is not None and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

        # Restore scheduler
        if scheduler is not None and "scheduler_state_dict" in checkpoint:
            scheduler.load_state_dict(checkpoint["scheduler_state_dict"])

        logger.info(
            f"Checkpoint loaded: step={checkpoint.get('step')}, "
            f"loss={checkpoint.get('loss', 'N/A')}"
        )

        return checkpoint


# =============================================================================
# VERTEX AI GEMINI FINE-TUNING
# =============================================================================


class GeminiTuner:
    """Vertex AI Gemini Fine-Tuning integration.

    Provides:
    - Supervised fine-tuning of Gemini models
    - Multimodal training support
    - Integration with Kagami's world model outputs
    """

    def __init__(self, config: ConsolidatedConfig):
        """Initialize Gemini tuner."""
        self.config = config
        self._client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Vertex AI client."""
        try:
            from google.cloud import aiplatform

            aiplatform.init(
                project=self.config.gcp_project,
                location=self.config.gcp_region,
            )

            self._initialized = True
            logger.info(
                f"Gemini tuner initialized: project={self.config.gcp_project}, "
                f"region={self.config.gcp_region}"
            )

        except ImportError:
            logger.warning("google-cloud-aiplatform not installed")
        except Exception as e:
            logger.error(f"Gemini tuner initialization failed: {e}")

    async def create_tuning_job(
        self,
        training_data_uri: str,
        validation_data_uri: str | None = None,
        tuned_model_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a Gemini fine-tuning job.

        Args:
            training_data_uri: GCS path to training JSONL
            validation_data_uri: GCS path to validation JSONL
            tuned_model_name: Name for the tuned model

        Returns:
            Job information dict
        """
        if not self._initialized:
            await self.initialize()

        from google.cloud import aiplatform

        # Create tuning job
        tuned_model_name = (
            tuned_model_name or f"kagami-gemini-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        sft_tuning_job = aiplatform.SupervisedTuningJob(
            source_model=self.config.gemini_base_model,
            train_dataset=training_data_uri,
            validation_dataset=validation_data_uri,
            tuned_model_display_name=tuned_model_name,
            epochs=self.config.gemini_tuning_epochs,
            adapter_size=self.config.gemini_adapter_size,
        )

        # Submit job
        sft_tuning_job.run()

        logger.info(f"Gemini tuning job created: {sft_tuning_job.resource_name}")

        return {
            "job_name": sft_tuning_job.resource_name,
            "tuned_model_name": tuned_model_name,
            "base_model": self.config.gemini_base_model,
            "status": "running",
        }

    async def prepare_training_data(
        self,
        world_model_outputs: list[dict[str, Any]],
        output_uri: str,
    ) -> str:
        """Prepare training data for Gemini from world model outputs.

        Converts world model predictions to Gemini training format.

        Args:
            world_model_outputs: List of world model prediction dicts
            output_uri: GCS path to write JSONL

        Returns:
            GCS path to prepared data
        """
        import json

        from google.cloud import storage

        # Convert to Gemini format
        training_examples = []
        for output in world_model_outputs:
            # Format depends on task type
            if "caption" in output:
                # Image captioning
                example = {
                    "text_input": output.get("prompt", "Describe this image."),
                    "output": output["caption"],
                }
                if "image_uri" in output:
                    example["image_uri"] = output["image_uri"]
            elif "action" in output:
                # Action prediction
                example = {
                    "text_input": f"State: {output.get('state', '')}. What action should be taken?",
                    "output": output["action"],
                }
            else:
                # General Q&A
                example = {
                    "text_input": output.get("input", ""),
                    "output": output.get("output", ""),
                }

            training_examples.append(example)

        # Write JSONL
        jsonl_data = "\n".join(json.dumps(ex) for ex in training_examples)

        # Upload to GCS
        client = storage.Client(project=self.config.gcp_project)

        if output_uri.startswith("gs://"):
            uri = output_uri[5:]
        else:
            uri = output_uri

        bucket_name, blob_path = uri.split("/", 1)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(jsonl_data)

        gcs_uri = f"gs://{bucket_name}/{blob_path}"
        logger.info(f"Prepared {len(training_examples)} examples: {gcs_uri}")

        return gcs_uri


# =============================================================================
# CONSOLIDATED TRAINER
# =============================================================================


class ConsolidatedTrainer:
    """THE unified trainer for all Kagami training.

    This replaces:
    - scripts/training/train_kagami.py
    - packages/kagami/core/training/unified_trainer.py
    - packages/kagami/core/training/joint_rssm_efe_trainer.py
    - packages/kagami/core/training/tpu/trainer.py
    - And all other training code
    """

    def __init__(
        self,
        model: nn.Module | None = None,
        config: ConsolidatedConfig | None = None,
    ):
        """Initialize consolidated trainer.

        Args:
            model: World model (created automatically if None)
            config: Training configuration
        """
        self.config = config or ConsolidatedConfig()
        self.model = model

        # Components
        self._wandb = WandBLogger(self.config)
        self._checkpointer = GCSCheckpointer(self.config)
        self._gemini_tuner = (
            GeminiTuner(self.config) if self.config.backend == TrainingBackend.GEMINI else None
        )

        # Gemini Grounding Module (Jan 5, 2026)
        self._gemini_grounding: GeminiGroundingModule | None = None
        if self.config.enable_gemini_grounding:
            try:
                from kagami.core.training.gemini_grounding import (
                    GeminiGroundingConfig,
                )

                grounding_config = GeminiGroundingConfig(
                    embedding_model=self.config.gemini_embedding_model,
                    embedding_dim=self.config.gemini_embedding_dim,
                    distillation_weight=self.config.gemini_grounding_distill_weight,
                    alignment_weight=self.config.gemini_grounding_contrastive_weight,
                )
                # Will be fully initialized in setup() when we know WM dim
                self._grounding_config = grounding_config
                logger.info("Gemini grounding enabled")
            except ImportError as e:
                logger.warning(f"Gemini grounding not available: {e}")

        # State
        self._backend_trainer: Any = None
        self._optimizer: torch.optim.Optimizer | None = None
        self._scheduler: Any = None
        self._curriculum: Any = None
        self._step = 0
        self._initialized = False

        # MANDATORY Validator (Jan 8, 2026 - Consolidated from lessons learned)
        from kagami.core.training.validation import TrainingValidator

        self._validator = TrainingValidator(
            kl_collapse_threshold=1e-4,
            kl_warning_threshold=0.1,
            kl_consecutive_limit=100,
            plateau_window=1000,
            plateau_velocity_threshold=1e-6,
            lr_reduction_factor=0.5,
            min_lr=self.config.min_lr,
            cooldown_steps=2000,
            gradient_explosion_threshold=100.0,
            divergence_threshold=10.0,
        )

    def _detect_backend(self) -> TrainingBackend:
        """Auto-detect best training backend."""
        backend = self.config.backend_enum
        if backend != TrainingBackend.AUTO:
            return backend

        # Check TPU
        tpu_vars = ["TPU_NAME", "TPU_WORKER_HOSTNAMES", "CLOUD_TPU_TASK_ID"]
        if any(os.environ.get(var) for var in tpu_vars):
            return TrainingBackend.TPU

        # Check for XLA
        try:
            import torch_xla.core.xla_model as xm

            if "xla" in str(xm.xla_device()).lower():
                return TrainingBackend.TPU
        except ImportError:
            pass

        return TrainingBackend.LOCAL

    def _create_model(self) -> nn.Module:
        """Create the REAL world model (OrganismRSSM).

        This is the actual production world model trained on TPU v6e (Jan 6, 2026).
        OrganismRSSM is the 7-colony RSSM with E8 lattice quantization.

        NOT creating:
        - KagamiWorldModel (wrapper, not trained directly)
        - UnifiedWorldModel (higher-level abstraction)

        Returns:
            OrganismRSSM - the production world model
        """
        from kagami.core.config.unified_config import RSSMConfig
        from kagami.core.world_model.rssm_core import OrganismRSSM

        # Create RSSM config with proper settings
        rssm_config = RSSMConfig(
            colony_dim=self.config.bulk_dim,  # 128
            num_colonies=7,
            stochastic_dim=14,  # H14
            latent_classes=240,  # E8 lattice (240 roots)
            kl_free_nats=3.0,  # KL collapse prevention (Jan 6, 2026)
            kl_collapse_threshold=1e-4,
            unimix=0.01,  # 1% uniform mixing
        )

        model = OrganismRSSM(rssm_config)
        logger.info(
            f"Created OrganismRSSM: bulk_dim={self.config.bulk_dim}, "
            f"7 colonies, 240-class E8 latent, kl_free_nats={rssm_config.kl_free_nats}"
        )
        return model

    def _create_optimizer(self) -> torch.optim.Optimizer:
        """Create optimizer."""
        if self.model is None:
            raise RuntimeError("Model not initialized")

        return torch.optim.AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
            betas=(0.9, 0.95),
        )

    def _create_scheduler(self) -> Any:
        """Create learning rate scheduler."""
        from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts

        return CosineAnnealingWarmRestarts(
            self._optimizer,
            T_0=self.config.warmup_steps,
            T_mult=2,
            eta_min=self.config.min_lr,
        )

    async def setup(self) -> None:
        """Initialize all training components."""
        if self._initialized:
            return

        logger.info("Setting up consolidated trainer...")

        # Create model if needed
        if self.model is None:
            self.model = self._create_model()

        # Initialize Gemini grounding module (Jan 5, 2026)
        # UPDATED (Jan 5, 2026): Use actual model state dimension
        if self.config.enable_gemini_grounding and hasattr(self, "_grounding_config"):
            try:
                from kagami.core.training.gemini_grounding import GeminiGroundingModule

                # Get world model state dimension from actual model
                # State = deterministic (h) + stochastic (z), organism-level
                if hasattr(self.model, "deter_dim") and hasattr(self.model, "stoch_dim"):
                    wm_dim = self.model.deter_dim + self.model.stoch_dim
                else:
                    # Fallback to config-based computation
                    # colony_dim (h) + stochastic_dim (z) = 128 + 14 = 142
                    wm_dim = self.config.bulk_dim + 14

                self._gemini_grounding = GeminiGroundingModule(
                    wm_dim=wm_dim,
                    config=self._grounding_config,
                    device="cpu",  # Will be moved to appropriate device later
                )
                logger.info(f"Gemini grounding initialized: wm_dim={wm_dim}")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini grounding: {e}")
                self._gemini_grounding = None

        # Detect backend
        backend = self._detect_backend()
        logger.info(f"Using backend: {backend.value}")

        # Initialize W&B
        self._wandb.initialize()

        # Initialize GCS checkpointer
        self._checkpointer.initialize()

        # Initialize backend-specific trainer
        if backend == TrainingBackend.TPU:
            # Use JAX training module for TPU (replaces old tpu/ module)
            from kagami.core.training.jax import TrainingConfig
            from kagami.core.training.jax import train as jax_train

            # Store config for TPU training
            self._tpu_config = TrainingConfig(
                total_steps=self.config.total_steps,
                batch_size=self.config.global_batch_size,
                learning_rate=self.config.learning_rate,
                warmup_steps=self.config.warmup_steps,
                checkpoint_interval=self.config.checkpoint_every,
                log_interval=self.config.log_every,
            )
            self._jax_train = jax_train
            logger.info("TPU backend configured with JAX training module")

        elif backend == TrainingBackend.GEMINI:
            if self._gemini_tuner is None:
                self._gemini_tuner = GeminiTuner(self.config)
            await self._gemini_tuner.initialize()

        else:
            # Local training
            self._optimizer = self._create_optimizer()
            self._scheduler = self._create_scheduler()

            # Create curriculum
            if self.config.enable_curriculum:
                from kagami.core.training.unified_curriculum import UnifiedCurriculumScheduler

                self._curriculum = UnifiedCurriculumScheduler()

        self._initialized = True
        logger.info("Consolidated trainer setup complete")

    async def train(
        self,
        dataloader: Any | None = None,
        total_steps: int | None = None,
        resume_from: str | int | None = None,
    ) -> dict[str, Any]:
        """Run training.

        Args:
            dataloader: Data loader (required for local training)
            total_steps: Override total steps from config
            resume_from: Step number or checkpoint path to resume from

        Returns:
            Training results
        """
        if not self._initialized:
            await self.setup()

        total_steps = total_steps or self.config.total_steps
        backend = self._detect_backend()

        # Load checkpoint if resuming
        if resume_from is not None:
            if isinstance(resume_from, int):
                self._checkpointer.load(
                    self.model, self._optimizer, self._scheduler, step=resume_from
                )
            else:
                self._checkpointer.load(
                    self.model, self._optimizer, self._scheduler, path=resume_from
                )

        logger.info(f"Starting training: backend={backend.value}, steps={total_steps}")

        if backend == TrainingBackend.TPU:
            # TPU training via orchestrator
            progress = self._backend_trainer.train(total_steps=total_steps)

            results = {
                "step": progress.step,
                "loss": progress.current_loss,
                "best_loss": progress.best_loss,
                "samples_seen": progress.samples_seen,
                "tokens_per_second": progress.tokens_per_second,
                "backend": "tpu",
            }

        elif backend == TrainingBackend.GEMINI:
            # Gemini fine-tuning
            if dataloader is None:
                raise ValueError("dataloader required for Gemini fine-tuning")

            # Collect outputs for Gemini training
            outputs = []
            for batch in dataloader:
                # Generate predictions from world model
                with torch.no_grad():
                    pred = self.model(batch)
                    outputs.append(
                        {
                            "input": batch.get("text", ""),
                            "output": pred.get("action", ""),
                        }
                    )

            # Prepare and upload training data
            data_uri = await self._gemini_tuner.prepare_training_data(
                outputs,
                f"gs://{self.config.gcs_bucket}/gemini_training/data_{datetime.now().strftime('%Y%m%d%H%M%S')}.jsonl",
            )

            # Create tuning job
            job = await self._gemini_tuner.create_tuning_job(data_uri)

            results = {
                "backend": "gemini",
                "job": job,
            }

        else:
            # Local training - requires real data
            if dataloader is None:
                raise ValueError(
                    "Local training requires a dataloader. "
                    "Use --backend tpu for TPU training with GCS data pipeline, "
                    "or provide a dataloader with real training data."
                )

            results = await self._train_local(dataloader, total_steps)

        # Final W&B log
        self._wandb.log(results, step=self._step)
        self._wandb.finish()

        return results

    async def _train_local(
        self,
        dataloader: Any,
        total_steps: int,
    ) -> dict[str, Any]:
        """Local training loop with plateau detection and KL monitoring (Jan 6, 2026)."""
        device = self._get_device()
        self.model.to(device)
        self.model.train()

        best_loss = float("inf")
        total_loss = 0.0
        num_lr_reductions = 0
        loss_val = 0.0  # Initialize for safety

        step = 0
        epoch = 0

        while step < total_steps:
            epoch += 1

            for batch in dataloader:
                if step >= total_steps:
                    break

                step += 1
                self._step = step

                # Move batch to device
                batch = self._to_device(batch, device)

                # Forward pass
                self._optimizer.zero_grad()

                # Unpack batch for OrganismRSSM
                if isinstance(batch, dict):
                    e8_code = batch.get("e8_code")
                    s7_phase = batch.get("s7_phase")
                    actions = batch.get("actions")
                    targets = batch.get("targets")

                    # Ensure proper dimensions [B, T, D]
                    # If tensors are 2D [B, D], expand to [B, 1, D]
                    if e8_code is not None and e8_code.dim() == 2:
                        e8_code = e8_code.unsqueeze(1)
                    if s7_phase is not None and s7_phase.dim() == 2:
                        s7_phase = s7_phase.unsqueeze(1)
                    if actions is not None and actions.dim() == 2:
                        actions = actions.unsqueeze(1)

                    outputs = self.model(
                        e8_code=e8_code,
                        s7_phase=s7_phase,
                        actions=actions,
                        sample=self.training if hasattr(self, "training") else True,
                    )

                    # Compute loss from OrganismRSSM outputs
                    # The model returns:
                    #   - kl_balanced: balanced KL divergence (training signal)
                    #   - s7_coherence_loss: S7 hierarchy consistency loss
                    #   - organism_actions: predicted actions for reconstruction
                    loss = torch.tensor(0.0, device=device, requires_grad=True)

                    # Primary loss: KL divergence for variational training
                    kl_balanced = outputs.get("kl_balanced")
                    if kl_balanced is not None and isinstance(kl_balanced, torch.Tensor):
                        if kl_balanced.requires_grad:
                            loss = kl_balanced
                        else:
                            # Detached scalar - need to create differentiable loss
                            pass

                    # Add S7 coherence loss if available
                    s7_loss = outputs.get("s7_coherence_loss")
                    if (
                        s7_loss is not None
                        and isinstance(s7_loss, torch.Tensor)
                        and s7_loss.requires_grad
                    ):
                        loss = loss + 0.1 * s7_loss

                    # Add action prediction reconstruction loss if targets available
                    if targets is not None:
                        organism_actions = outputs.get("organism_actions")
                        if organism_actions is not None:
                            # Actions shape: [B, T, A], targets: [B, T, A]
                            recon_loss = F.mse_loss(organism_actions, targets)
                            loss = loss + recon_loss

                    # Fallback to explicit loss keys if provided
                    if not loss.requires_grad:
                        if "loss" in outputs and outputs["loss"].requires_grad:
                            loss = outputs["loss"]
                        elif "total_loss" in outputs and outputs["total_loss"].requires_grad:
                            loss = outputs["total_loss"]
                        else:
                            # Create dummy loss for gradient flow testing
                            logger.warning(
                                f"No differentiable loss found at step {step}, using dummy loss"
                            )
                            # Sum all model parameters to create a differentiable dummy loss
                            loss = (
                                sum(p.sum() for p in self.model.parameters() if p.requires_grad)
                                * 0.0
                            )
                else:
                    outputs = self.model(batch)
                    loss = outputs.get(
                        "loss", outputs.get("total_loss", torch.tensor(0.0, device=device))
                    )

                # === LANGUAGE GROUNDING (Jan 5, 2026) ===
                # Compute Gemini embedding alignment loss if enabled and text data available
                if (
                    self._gemini_grounding is not None
                    and isinstance(batch, dict)
                    and batch.get("texts") is not None
                ):
                    try:
                        # Extract world model state (organism-level)
                        # h: [B, 7, H] → h_organism: [B, H]
                        # z: [B, 7, Z] → z_organism: [B, Z]
                        h_seq = outputs.get("h")  # [B, T, 7, H] or [B, 7, H]
                        z_seq = outputs.get("z")  # [B, T, 7, Z] or [B, 7, Z]

                        if h_seq is not None and z_seq is not None:
                            # Get last timestep if sequential
                            if h_seq.dim() == 4:
                                h = h_seq[:, -1]  # [B, 7, H]
                                z = z_seq[:, -1]  # [B, 7, Z]
                            else:
                                h = h_seq  # [B, 7, H]
                                z = z_seq  # [B, 7, Z]

                            # Aggregate over colonies (mean pooling)
                            h_organism = h.mean(dim=1)  # [B, H]
                            z_organism = z.mean(dim=1)  # [B, Z]

                            # Concatenate to get full state
                            wm_state = torch.cat([h_organism, z_organism], dim=-1)  # [B, H+Z]

                            # Compute grounding loss
                            texts = batch["texts"]
                            grounding_losses = self._gemini_grounding(wm_state, texts=texts)

                            # Add to total loss (weighted by language_grounding_weight)
                            grounding_total = grounding_losses.get("total_loss", torch.tensor(0.0))
                            loss = loss + self.config.language_grounding_weight * grounding_total

                            # Track for logging
                            outputs["grounding_loss"] = grounding_total
                            outputs["grounding_mse"] = grounding_losses.get(
                                "mse_loss", torch.tensor(0.0)
                            )
                            outputs["grounding_contrastive"] = grounding_losses.get(
                                "contrastive_loss", torch.tensor(0.0)
                            )
                    except Exception as e:
                        if step % 100 == 0:
                            logger.warning(f"Language grounding failed at step {step}: {e}")

                # === KL MONITORING (Jan 6, 2026) ===
                kl_value = outputs.get("kl_balanced", outputs.get("kl", torch.tensor(0.0)))
                if isinstance(kl_value, torch.Tensor):
                    kl_value = kl_value.mean().item()
                self._kl_monitor.update(kl_value, step)

                # Backward pass
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.grad_clip)

                # Optimizer step
                self._optimizer.step()
                self._scheduler.step()

                # Track loss
                loss_val = loss.item()
                total_loss += loss_val
                if loss_val < best_loss:
                    best_loss = loss_val

                # === PLATEAU DETECTION (Jan 6, 2026) ===
                current_lr = self._scheduler.get_last_lr()[0]
                plateau_status = self._plateau_detector.update(loss_val, step, current_lr)

                if plateau_status["should_reduce_lr"]:
                    # Reduce LR in optimizer
                    new_lr = plateau_status["new_lr"]
                    for param_group in self._optimizer.param_groups:
                        param_group["lr"] = new_lr
                    num_lr_reductions += 1

                # Curriculum update
                if self._curriculum is not None:
                    # Pass loss as dict for curriculum with extra metrics
                    curriculum_result = self._curriculum.step(
                        {
                            "total": loss_val,
                            "kl": kl_value,
                            "reconstruction": outputs.get("recon_loss", loss_val),
                        },
                        step,
                    )

                    # Log curriculum transitions
                    if curriculum_result.get("should_transition"):
                        logger.info(
                            f"CURRICULUM TRANSITION at step {step}: "
                            f"{curriculum_result.get('transition_from')} → "
                            f"{curriculum_result.get('transition_to')} "
                            f"(reason: {curriculum_result.get('transition_reason')})"
                        )

                # Logging
                if step % self.config.log_every == 0:
                    avg_loss = total_loss / step
                    lr = self._optimizer.param_groups[0]["lr"]

                    metrics = {
                        "Loss/train": loss_val,
                        "Loss/avg": avg_loss,
                        "Loss/best": best_loss,
                        "Training/learning_rate": lr,
                        "Training/epoch": epoch,
                        # New metrics (Jan 6, 2026)
                        "Monitor/kl": kl_value,
                        "Monitor/plateau_detected": int(plateau_status["plateau_detected"]),
                        "Monitor/loss_velocity": plateau_status["loss_velocity"],
                        "Monitor/lr_reductions": num_lr_reductions,
                    }

                    # Language grounding metrics (Jan 5, 2026)
                    if "grounding_loss" in outputs:
                        grounding_loss = outputs["grounding_loss"]
                        if isinstance(grounding_loss, torch.Tensor):
                            grounding_loss = grounding_loss.item()
                        metrics["Loss/grounding"] = grounding_loss
                    if "grounding_mse" in outputs:
                        grounding_mse = outputs["grounding_mse"]
                        if isinstance(grounding_mse, torch.Tensor):
                            grounding_mse = grounding_mse.item()
                        metrics["Loss/grounding_mse"] = grounding_mse
                    if "grounding_contrastive" in outputs:
                        grounding_contrastive = outputs["grounding_contrastive"]
                        if isinstance(grounding_contrastive, torch.Tensor):
                            grounding_contrastive = grounding_contrastive.item()
                        metrics["Loss/grounding_contrastive"] = grounding_contrastive

                    if self._curriculum is not None:
                        metrics["Curriculum/phase"] = str(self._curriculum.current_phase)
                        metrics["Curriculum/phase_step"] = self._curriculum.state.phase_step

                    self._wandb.log(metrics, step=step)

                    logger.info(
                        f"Step {step}/{total_steps}: loss={loss_val:.4f}, "
                        f"kl={kl_value:.4f}, avg={avg_loss:.4f}, "
                        f"best={best_loss:.4f}, lr={lr:.2e}"
                    )

                # Checkpointing
                if step % self.config.checkpoint_every == 0:
                    curriculum_state = None
                    if self._curriculum is not None:
                        curriculum_state = self._curriculum.get_state()

                    ckpt_path = self._checkpointer.save(
                        self.model,
                        self._optimizer,
                        self._scheduler,
                        step=step,
                        loss=loss_val,
                        curriculum_state=curriculum_state,
                        extra={
                            "kl": kl_value,
                            "lr_reductions": num_lr_reductions,
                            "plateau_detected": plateau_status["plateau_detected"],
                        },
                    )

                    self._wandb.log_checkpoint(ckpt_path, step)

        return {
            "step": step,
            "loss": loss_val,
            "best_loss": best_loss,
            "avg_loss": total_loss / step if step > 0 else float("inf"),
            "epochs": epoch,
            "backend": "local",
            "lr_reductions": num_lr_reductions,
            "final_kl": kl_value,
        }

    def _get_device(self) -> torch.device:
        """Get best available device."""
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _to_device(self, batch: Any, device: torch.device) -> Any:
        """Move batch to device."""
        if isinstance(batch, torch.Tensor):
            return batch.to(device)
        elif isinstance(batch, dict):
            return {k: self._to_device(v, device) for k, v in batch.items()}
        elif isinstance(batch, (list, tuple)):
            return type(batch)(self._to_device(v, device) for v in batch)
        return batch


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


async def train_kagami(
    config_path: str | Path | None = None,
    config: ConsolidatedConfig | None = None,
    model: nn.Module | None = None,
    dataloader: Any | None = None,
    backend: str = "auto",
    **kwargs: Any,
) -> dict[str, Any]:
    """Main training entry point.

    Args:
        config_path: Path to YAML config file
        config: ConsolidatedConfig object (overrides config_path)
        model: Model to train (created from config if None)
        dataloader: Data loader (required for local/gemini backends)
        backend: Training backend override
        **kwargs: Additional config overrides

    Returns:
        Training results dict
    """
    # Load config
    if config is None:
        if config_path is not None:
            config = ConsolidatedConfig.from_yaml(config_path)
        else:
            config = ConsolidatedConfig()

    # Apply overrides
    if backend != "auto":
        config.backend = TrainingBackend(backend)

    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # Create and run trainer
    trainer = ConsolidatedTrainer(model=model, config=config)
    results = await trainer.train(dataloader=dataloader)

    return results


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Kagami World Model Training (Consolidated)")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/training_stable.yaml",
        help="Path to training config YAML",
    )
    parser.add_argument(
        "--backend",
        "-b",
        type=str,
        default="auto",
        choices=["auto", "tpu", "local", "gemini"],
        help="Training backend",
    )
    parser.add_argument(
        "--steps",
        "-s",
        type=int,
        default=None,
        help="Total training steps (overrides config)",
    )
    parser.add_argument(
        "--resume",
        "-r",
        type=str,
        default=None,
        help="Resume from checkpoint (step number or path)",
    )
    parser.add_argument(
        "--wandb-project",
        type=str,
        default=None,
        help="W&B project name",
    )
    parser.add_argument(
        "--no-wandb",
        action="store_true",
        help="Disable W&B logging",
    )

    args = parser.parse_args()

    # Build config overrides
    kwargs = {}
    if args.steps is not None:
        kwargs["total_steps"] = args.steps
    if args.wandb_project is not None:
        kwargs["wandb_project"] = args.wandb_project
    if args.no_wandb:
        kwargs["wandb_enabled"] = False

    # Run training
    results = asyncio.run(
        train_kagami(
            config_path=args.config,
            backend=args.backend,
            **kwargs,
        )
    )

    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print("=" * 60)
    for key, value in results.items():
        print(f"  {key}: {value}")
    print("=" * 60)


if __name__ == "__main__":
    main()
