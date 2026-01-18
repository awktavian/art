#!/usr/bin/env python3
"""Kagami Training CLI — Apollo-Grade Training Infrastructure.

THE single entry point for all training operations.

Usage:
    # Data Generation
    kagami-train data generate --config training.yaml --output gs://bucket/path

    # TPU Training
    kagami-train tpu start --config training.yaml
    kagami-train tpu status
    kagami-train tpu logs
    kagami-train tpu stop

    # Distillation
    kagami-train distill --teacher gs://models/teacher --student small

    # Export
    kagami-train export --checkpoint gs://checkpoints/step_100000 --format onnx

    # Monitoring (opens dashboard)
    kagami-train monitor

    # Full Pipeline (data → train → distill → export)
    kagami-train pipeline --config training.yaml

Design Principles:
    1. Single entry point — no scattered scripts
    2. Declarative config — all settings in YAML
    3. Repeatable — same config = same results
    4. Observable — integrated monitoring
    5. Centralized — all state in GCS

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kagami-train")


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class TrainingConfig:
    """Unified training configuration."""

    # GCS Paths
    data_bucket: str = "gs://kagami-training-data"
    checkpoint_bucket: str = "gs://kagami-checkpoints"
    model_bucket: str = "gs://kagami-models"

    # TPU
    tpu_name: str = "kagami-tpu"
    tpu_zone: str = "us-central2-b"
    tpu_type: str = "v6e-4"
    gcp_project: str = "kagami-prod"

    # Training
    total_steps: int = 500000
    batch_size: int = 256
    seq_len: int = 32
    learning_rate: float = 1e-4

    # Data Generation
    data_shards: int = 1000
    samples_per_shard: int = 1000

    # Distillation
    teacher_checkpoint: str = "gs://kagami-models/teacher/final"
    student_sizes: list = field(default_factory=lambda: ["small", "base", "large"])

    # Export
    export_formats: list = field(default_factory=lambda: ["onnx", "coreml", "tflite"])

    # Monitoring
    wandb_project: str = "kagami-training"
    wandb_entity: str = "kagami-ai"
    telemetry_port: int = 8765

    @classmethod
    def from_yaml(cls, path: str) -> TrainingConfig:
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Flatten nested config
        flat = {}
        for section in ["gcs", "tpu", "training", "data", "distillation", "export", "monitoring"]:
            if section in data:
                for k, v in data[section].items():
                    flat[k] = v

        # Handle top-level keys
        for k, v in data.items():
            if not isinstance(v, dict):
                flat[k] = v

        return cls(**{k: v for k, v in flat.items() if hasattr(cls, k)})


# =============================================================================
# DATA GENERATION
# =============================================================================


class DataGenerator:
    """Generate training data shards to GCS."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    async def generate(self, dataset: str = "all") -> dict[str, int]:
        """Generate training data.

        Args:
            dataset: One of 'genesis', 'qm9', 'tree', 'language', 'all'

        Returns:
            Dict mapping dataset name to shard count
        """
        logger.info(f"Generating training data: {dataset}")

        results = {}
        datasets = [dataset] if dataset != "all" else ["genesis", "qm9", "tree", "language"]

        for ds in datasets:
            logger.info(f"Generating {ds} dataset...")
            shards = await self._generate_dataset(ds)
            results[ds] = shards
            logger.info(f"✓ {ds}: {shards} shards")

        return results

    async def _generate_dataset(self, dataset: str) -> int:
        """Generate a specific dataset."""
        from kagami.core.training.datasets import (
            GenesisGeneratorConfig,
            GenesisPuzzleGenerator,
            LanguageCuratorConfig,
            LanguageDataCurator,
            QM9Preprocessor,
            QM9PreprocessorConfig,
            TreeOfLifeConfig,
            TreeOfLifePreprocessor,
        )

        cfg = self.config
        output_dir = f"{cfg.data_bucket}/{dataset}/v1"

        if dataset == "genesis":
            gen_config = GenesisGeneratorConfig(
                output_dir=output_dir,
                num_shards=cfg.data_shards,
                trajectories_per_shard=cfg.samples_per_shard,
            )
            generator = GenesisPuzzleGenerator(gen_config)
            paths = generator.generate()
            return len(paths)

        elif dataset == "qm9":
            qm9_config = QM9PreprocessorConfig(
                output_dir=output_dir,
                num_shards=min(100, cfg.data_shards),  # QM9 is smaller
            )
            preprocessor = QM9Preprocessor(qm9_config)
            paths = preprocessor.preprocess()
            return len(paths)

        elif dataset == "tree":
            tree_config = TreeOfLifeConfig(
                output_dir=output_dir,
                num_shards=min(200, cfg.data_shards),
            )
            preprocessor = TreeOfLifePreprocessor(tree_config)
            paths = preprocessor.preprocess()
            return len(paths)

        elif dataset == "language":
            lang_config = LanguageCuratorConfig(
                output_dir=output_dir,
                num_shards=cfg.data_shards,
            )
            curator = LanguageDataCurator(lang_config)
            paths = curator.curate()
            return len(paths)

        else:
            raise ValueError(f"Unknown dataset: {dataset}")


# =============================================================================
# TPU ORCHESTRATOR
# =============================================================================


class TPUOrchestrator:
    """Manage TPU VMs for training."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    def _run_gcloud(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a gcloud command."""
        cmd = ["gcloud", *args]
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)

    def exists(self) -> bool:
        """Check if TPU exists."""
        result = self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "describe",
                self.config.tpu_name,
                f"--zone={self.config.tpu_zone}",
                f"--project={self.config.gcp_project}",
            ],
            check=False,
        )
        return result.returncode == 0

    def status(self) -> dict[str, Any]:
        """Get TPU status."""
        if not self.exists():
            return {"status": "NOT_FOUND", "name": self.config.tpu_name}

        result = self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "describe",
                self.config.tpu_name,
                f"--zone={self.config.tpu_zone}",
                f"--project={self.config.gcp_project}",
                "--format=json",
            ],
        )
        return json.loads(result.stdout)

    def create(self) -> bool:
        """Create TPU VM."""
        if self.exists():
            logger.info(f"TPU {self.config.tpu_name} already exists")
            return True

        logger.info(f"Creating TPU {self.config.tpu_name}...")
        result = self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "create",
                self.config.tpu_name,
                f"--zone={self.config.tpu_zone}",
                f"--accelerator-type={self.config.tpu_type}",
                "--version=v2-alpha-tpuv6e",
                f"--project={self.config.gcp_project}",
            ],
            check=False,
        )
        return result.returncode == 0

    def delete(self) -> bool:
        """Delete TPU VM."""
        if not self.exists():
            logger.info(f"TPU {self.config.tpu_name} does not exist")
            return True

        logger.info(f"Deleting TPU {self.config.tpu_name}...")
        result = self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "delete",
                self.config.tpu_name,
                f"--zone={self.config.tpu_zone}",
                f"--project={self.config.gcp_project}",
                "--quiet",
            ],
            check=False,
        )
        return result.returncode == 0

    def ssh(self, command: str) -> str:
        """Execute command on TPU via SSH."""
        result = self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "ssh",
                self.config.tpu_name,
                f"--zone={self.config.tpu_zone}",
                f"--project={self.config.gcp_project}",
                f"--command={command}",
            ],
        )
        return result.stdout

    def install_deps(self) -> None:
        """Install training dependencies on TPU."""
        logger.info("Installing dependencies on TPU...")
        self.ssh(
            "pip install -q jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html && "
            "pip install -q flax optax tqdm tensorflow"
        )

    def copy_code(self, local_path: str) -> None:
        """Copy training code to TPU."""
        logger.info(f"Copying {local_path} to TPU...")
        self._run_gcloud(
            [
                "compute",
                "tpus",
                "tpu-vm",
                "scp",
                local_path,
                f"{self.config.tpu_name}:~/train.py",
                f"--zone={self.config.tpu_zone}",
                f"--project={self.config.gcp_project}",
            ],
        )

    def start_training(self) -> None:
        """Start training on TPU."""
        from datetime import datetime

        cfg = self.config
        # SECURITY: Use Python datetime instead of shell command to avoid injection
        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        checkpoint_dir = f"{cfg.checkpoint_bucket}/organism-rssm/{run_id}"

        cmd = f"""
        export JAX_PLATFORMS=tpu
        export TF_CPP_MIN_LOG_LEVEL=2
        nohup python3 train.py \
            --data-dir {cfg.data_bucket}/genesis/v1 \
            --steps {cfg.total_steps} \
            --batch-size {cfg.batch_size} \
            --seq-len {cfg.seq_len} \
            --lr {cfg.learning_rate} \
            --checkpoint-dir {checkpoint_dir} \
            > ~/training.log 2>&1 &
        echo "Training started with PID $!"
        """

        logger.info(f"Starting training: {cfg.total_steps} steps")
        output = self.ssh(cmd)
        logger.info(output)

    def get_logs(self, lines: int = 100) -> str:
        """Get recent training logs."""
        return self.ssh(f"tail -n {lines} ~/training.log 2>/dev/null || echo 'No logs yet'")


# =============================================================================
# DISTILLATION
# =============================================================================


class DistillationRunner:
    """Run knowledge distillation from teacher to student models."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    async def distill(self, student_size: str) -> str:
        """Distill teacher to student model.

        Args:
            student_size: One of 'small', 'base', 'large'

        Returns:
            Path to distilled model checkpoint
        """
        logger.info(f"Distilling to {student_size} student...")

        from kagami.core.training.jax.configs.student_configs import get_student_config
        from kagami.core.training.jax.distill import DistillationPipeline

        cfg = self.config
        student_config = get_student_config(student_size)

        pipeline = DistillationPipeline(
            teacher_checkpoint=cfg.teacher_checkpoint,
            student_config=student_config,
        )

        output_dir = f"{cfg.model_bucket}/student-{student_size}"
        checkpoint = pipeline.distill(
            data_dir=f"{cfg.data_bucket}/genesis/v1",
            output_dir=output_dir,
        )

        logger.info(f"✓ Distilled {student_size} model: {checkpoint}")
        return checkpoint


# =============================================================================
# EXPORT
# =============================================================================


class ModelExporter:
    """Export models to deployment formats."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    async def export(self, checkpoint: str, format: str) -> str:
        """Export model to deployment format.

        Args:
            checkpoint: Path to model checkpoint
            format: One of 'onnx', 'coreml', 'tflite'

        Returns:
            Path to exported model
        """
        logger.info(f"Exporting {checkpoint} to {format}...")

        from kagami.core.training.jax.export import ExportConfig
        from kagami.core.training.jax.export import ModelExporter as JaxExporter

        cfg = self.config
        export_config = ExportConfig()

        JaxExporter(export_config)

        # Determine output path
        model_name = checkpoint.split("/")[-1]
        output_path = f"{cfg.model_bucket}/{format}/{model_name}"

        # Would need actual model loading here
        # For now, just log the intent
        logger.info(f"Would export to: {output_path}")
        return output_path


# =============================================================================
# MONITORING
# =============================================================================


class TrainingMonitor:
    """Launch training monitoring dashboard."""

    def __init__(self, config: TrainingConfig):
        self.config = config

    def start(self) -> None:
        """Start monitoring dashboard."""

        logger.info(f"Starting monitoring dashboard on port {self.config.telemetry_port}...")
        logger.info(f"Open http://localhost:{self.config.telemetry_port}")

        # Import and run the live telemetry server
        import asyncio
        import subprocess

        try:
            # Use the existing telemetry module
            from kagami.core.training.jax.telemetry import run_telemetry_server

            asyncio.run(run_telemetry_server(self.config.telemetry_port))
        except ImportError:
            # SECURITY: Use subprocess.run instead of os.system to avoid shell injection
            logger.info("Using standalone telemetry server...")
            subprocess.run(
                [
                    "python",
                    "scripts/training/live_telemetry.py",
                    "--port",
                    str(self.config.telemetry_port),
                ],
                check=False,
            )


# =============================================================================
# PIPELINE ORCHESTRATOR
# =============================================================================


class PipelineOrchestrator:
    """Run the full training pipeline."""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.data_generator = DataGenerator(config)
        self.tpu = TPUOrchestrator(config)
        self.distiller = DistillationRunner(config)
        self.exporter = ModelExporter(config)

    async def run(self, stages: list[str] | None = None) -> dict[str, Any]:
        """Run training pipeline.

        Args:
            stages: List of stages to run, or None for all.
                   Options: 'data', 'train', 'distill', 'export'

        Returns:
            Dict with results from each stage
        """
        stages = stages or ["data", "train", "distill", "export"]
        results = {}

        logger.info("=" * 60)
        logger.info("KAGAMI TRAINING PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Stages: {stages}")
        logger.info(f"TPU: {self.config.tpu_name} ({self.config.tpu_type})")
        logger.info("=" * 60)

        # Stage 1: Data Generation
        if "data" in stages:
            logger.info("\n📊 STAGE 1: Data Generation")
            results["data"] = await self.data_generator.generate("all")

        # Stage 2: TPU Training
        if "train" in stages:
            logger.info("\n🚀 STAGE 2: TPU Training")

            # Create TPU if needed
            if not self.tpu.exists():
                self.tpu.create()

            # Install deps and copy code
            self.tpu.install_deps()
            self.tpu.copy_code("packages/kagami/core/training/jax/train.py")

            # Start training
            self.tpu.start_training()
            results["train"] = {"status": "started", "tpu": self.config.tpu_name}

        # Stage 3: Distillation
        if "distill" in stages:
            logger.info("\n🎓 STAGE 3: Knowledge Distillation")
            results["distill"] = {}
            for size in self.config.student_sizes:
                checkpoint = await self.distiller.distill(size)
                results["distill"][size] = checkpoint

        # Stage 4: Export
        if "export" in stages:
            logger.info("\n📦 STAGE 4: Model Export")
            results["export"] = {}
            for format in self.config.export_formats:
                for size in self.config.student_sizes:
                    checkpoint = f"{self.config.model_bucket}/student-{size}/final"
                    output = await self.exporter.export(checkpoint, format)
                    results["export"][f"{size}_{format}"] = output

        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)

        return results


# =============================================================================
# CLI
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="kagami-train",
        description="Kagami Training CLI — Apollo-Grade Training Infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Generate all training data
    kagami-train data generate --config training.yaml

    # Start TPU training
    kagami-train tpu start --config training.yaml

    # Check TPU status
    kagami-train tpu status

    # Run full pipeline
    kagami-train pipeline --config training.yaml

    # Export model to ONNX
    kagami-train export --checkpoint gs://models/final --format onnx
        """,
    )

    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config/training_v6e_production.yaml",
        help="Path to training configuration YAML",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Data commands
    data_parser = subparsers.add_parser("data", help="Data generation commands")
    data_sub = data_parser.add_subparsers(dest="data_cmd")

    gen_parser = data_sub.add_parser("generate", help="Generate training data")
    gen_parser.add_argument(
        "--dataset",
        choices=["all", "genesis", "qm9", "tree", "language"],
        default="all",
        help="Dataset to generate",
    )
    gen_parser.add_argument("--output", type=str, help="Override output path")

    # TPU commands
    tpu_parser = subparsers.add_parser("tpu", help="TPU management commands")
    tpu_sub = tpu_parser.add_subparsers(dest="tpu_cmd")

    tpu_sub.add_parser("status", help="Get TPU status")
    tpu_sub.add_parser("create", help="Create TPU VM")
    tpu_sub.add_parser("delete", help="Delete TPU VM")
    tpu_sub.add_parser("start", help="Start training on TPU")
    tpu_sub.add_parser("stop", help="Stop training on TPU")

    logs_parser = tpu_sub.add_parser("logs", help="Get training logs")
    logs_parser.add_argument("--lines", "-n", type=int, default=100, help="Number of lines")

    # Distillation commands
    distill_parser = subparsers.add_parser("distill", help="Knowledge distillation")
    distill_parser.add_argument(
        "--teacher",
        type=str,
        help="Teacher checkpoint path",
    )
    distill_parser.add_argument(
        "--student",
        choices=["small", "base", "large", "all"],
        default="all",
        help="Student model size",
    )

    # Export commands
    export_parser = subparsers.add_parser("export", help="Export model to deployment format")
    export_parser.add_argument("--checkpoint", type=str, required=True, help="Checkpoint path")
    export_parser.add_argument(
        "--format",
        choices=["onnx", "coreml", "tflite", "all"],
        default="all",
        help="Export format",
    )

    # Monitor command
    subparsers.add_parser("monitor", help="Start monitoring dashboard")

    # Benchmark command (INTEGRATED profiling)
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run TPU throughput benchmark (integrated profiling)"
    )
    benchmark_parser.add_argument(
        "--steps", type=int, default=1000, help="Number of benchmark steps"
    )
    benchmark_parser.add_argument(
        "--batch-size", type=int, default=512, help="Batch size for benchmark"
    )
    benchmark_parser.add_argument(
        "--seq-len", type=int, default=64, help="Sequence length for benchmark"
    )
    benchmark_parser.add_argument(
        "--warmup", type=int, default=100, help="Warmup steps before measurement"
    )
    benchmark_parser.add_argument(
        "--output", type=str, default="/tmp/kagami_benchmark", help="Output directory for reports"
    )

    # Profile command (analyze existing training)
    profile_parser = subparsers.add_parser("profile", help="Profile existing training run")
    profile_parser.add_argument("--data-dir", type=str, required=True, help="Path to training data")
    profile_parser.add_argument("--steps", type=int, default=500, help="Steps to profile")
    profile_parser.add_argument(
        "--output", type=str, default="/tmp/kagami_profiles", help="Output directory"
    )

    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Run full training pipeline")
    pipeline_parser.add_argument(
        "--stages",
        nargs="+",
        choices=["data", "train", "distill", "export"],
        help="Stages to run (default: all)",
    )

    return parser


async def main_async(args: argparse.Namespace) -> int:
    """Async main entry point."""
    # Load config
    config = (
        TrainingConfig.from_yaml(args.config) if os.path.exists(args.config) else TrainingConfig()
    )

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.command == "data":
        if args.data_cmd == "generate":
            generator = DataGenerator(config)
            results = await generator.generate(args.dataset)
            print(json.dumps(results, indent=2))

    elif args.command == "tpu":
        tpu = TPUOrchestrator(config)

        if args.tpu_cmd == "status":
            status = tpu.status()
            print(json.dumps(status, indent=2))

        elif args.tpu_cmd == "create":
            success = tpu.create()
            return 0 if success else 1

        elif args.tpu_cmd == "delete":
            success = tpu.delete()
            return 0 if success else 1

        elif args.tpu_cmd == "start":
            if not tpu.exists():
                tpu.create()
            tpu.install_deps()
            tpu.copy_code("packages/kagami/core/training/jax/train.py")
            tpu.start_training()

        elif args.tpu_cmd == "logs":
            logs = tpu.get_logs(args.lines)
            print(logs)

    elif args.command == "distill":
        distiller = DistillationRunner(config)
        if args.student == "all":
            for size in config.student_sizes:
                await distiller.distill(size)
        else:
            await distiller.distill(args.student)

    elif args.command == "export":
        exporter = ModelExporter(config)
        formats = config.export_formats if args.format == "all" else [args.format]
        for fmt in formats:
            await exporter.export(args.checkpoint, fmt)

    elif args.command == "monitor":
        monitor = TrainingMonitor(config)
        monitor.start()

    elif args.command == "benchmark":
        # Run integrated TPU benchmark
        from kagami.core.training.jax.profiler import run_benchmark

        logger.info("Running TPU benchmark (integrated profiling)...")
        report = run_benchmark(
            steps=args.steps,
            batch_size=args.batch_size,
            seq_len=args.seq_len,
            warmup_steps=args.warmup,
            output_dir=args.output,
        )
        print("\n" + report.summary())
        print(f"\nDetailed report saved to: {args.output}/benchmark_report.json")

    elif args.command == "profile":
        # Profile an existing training run with real data
        from kagami.core.training.jax.train import train

        logger.info(f"Profiling training with data from {args.data_dir}...")
        result = train(
            data_dir=args.data_dir,
            total_steps=args.steps,
            batch_size=512,
            seq_len=64,
            checkpoint_dir=args.output,
        )
        print(json.dumps(result, indent=2))

    elif args.command == "pipeline":
        pipeline = PipelineOrchestrator(config)
        results = await pipeline.run(args.stages)
        print(json.dumps(results, indent=2, default=str))

    else:
        parser = create_parser()
        parser.print_help()

    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted")
        return 130
    except Exception as e:
        logger.error(f"Error: {e}")
        if os.environ.get("DEBUG"):
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())
