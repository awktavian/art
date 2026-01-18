"""Model Export Pipeline for Deployment.

Converts JAX/Flax models to deployment formats:
- ONNX: Cross-platform inference
- CoreML: iOS/macOS deployment
- TFLite: Android/embedded deployment

Usage:
    python -m kagami.core.training.jax.export \
        --checkpoint gs://kagami-models/student-small/final \
        --format onnx \
        --output-dir gs://kagami-models/onnx/small

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExportConfig:
    """Configuration for model export."""

    # Model info
    model_name: str = "organism_rssm"
    version: str = "1.0.0"

    # Input/output shapes
    batch_size: int = 1
    seq_len: int = 1  # Single-step inference
    obs_dim: int = 64
    action_dim: int = 8

    # Output shapes
    deter_dim: int = 256
    stoch_dim: int = 16

    # Export settings
    opset_version: int = 17  # ONNX opset
    optimize: bool = True
    quantize: bool = False  # Enable for mobile


class ONNXExporter:
    """Export JAX model to ONNX format."""

    def __init__(self, config: ExportConfig):
        self.config = config

    def export(
        self,
        model_fn: Any,
        params: dict,
        output_path: str,
    ) -> str:
        """Export model to ONNX.

        Args:
            model_fn: Model apply function
            params: Model parameters
            output_path: Output file path

        Returns:
            Path to exported ONNX file
        """
        try:
            import jax2onnx  # type: ignore
        except ImportError:
            logger.warning("jax2onnx not available, using fallback export")
            return self._export_fallback(model_fn, params, output_path)

        cfg = self.config

        # Define input spec
        dummy_obs = jnp.zeros((cfg.batch_size, cfg.seq_len, cfg.obs_dim))
        dummy_actions = jnp.zeros((cfg.batch_size, cfg.seq_len, cfg.action_dim))
        dummy_h = jnp.zeros((cfg.batch_size, cfg.deter_dim))
        dummy_z = jnp.zeros((cfg.batch_size, cfg.stoch_dim))

        # Export using jax2onnx
        onnx_model = jax2onnx.convert(
            model_fn,
            [dummy_obs, dummy_actions, dummy_h, dummy_z],
            opset=cfg.opset_version,
        )

        # Save
        import onnx

        onnx.save(onnx_model, output_path)
        logger.info(f"Exported ONNX model to {output_path}")

        # Optimize if requested
        if cfg.optimize:
            self._optimize_onnx(output_path)

        # Quantize if requested
        if cfg.quantize:
            self._quantize_onnx(output_path)

        return output_path

    def _export_fallback(
        self,
        model_fn: Any,
        params: dict,
        output_path: str,
    ) -> str:
        """Fallback export using tf2onnx via SavedModel."""
        logger.info("Using TensorFlow SavedModel -> ONNX conversion")

        try:
            import tensorflow as tf
            from jax.experimental import jax2tf
        except ImportError as e:
            logger.error(f"Required packages not available: {e}")
            raise

        cfg = self.config

        # Convert JAX function to TF
        @tf.function(
            input_signature=[
                tf.TensorSpec([cfg.batch_size, cfg.seq_len, cfg.obs_dim], tf.float32),
                tf.TensorSpec([cfg.batch_size, cfg.seq_len, cfg.action_dim], tf.float32),
            ]
        )
        def tf_model(obs, actions):
            # Create JAX random key (deterministic for export)
            key = jax.random.PRNGKey(0)

            # Convert inputs
            obs_jax = jnp.array(obs.numpy())
            actions_jax = jnp.array(actions.numpy())

            # Run model
            outputs = model_fn(
                {"params": params},
                obs=obs_jax,
                actions=actions_jax,
                key=key,
                training=False,
            )

            return {
                "obs_pred": tf.convert_to_tensor(np.array(outputs["obs_pred"])),
                "h": tf.convert_to_tensor(np.array(outputs["h"])),
            }

        # Save as SavedModel
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_model_path = f"{tmpdir}/saved_model"

            # Export concrete function
            concrete_func = tf_model.get_concrete_function()
            tf.saved_model.save(
                tf.Module(),
                saved_model_path,
                signatures={"serving_default": concrete_func},
            )

            # Convert to ONNX
            try:
                import tf2onnx

                tf2onnx.convert.from_saved_model(
                    saved_model_path,
                    output_path=output_path,
                    opset=cfg.opset_version,
                )
            except ImportError:
                # Just save the TF SavedModel
                logger.warning("tf2onnx not available, saving SavedModel instead")
                import shutil

                shutil.copytree(saved_model_path, output_path)

        return output_path

    def _optimize_onnx(self, model_path: str) -> None:
        """Optimize ONNX model."""
        try:
            from onnxruntime.transformers import optimizer

            optimized_model = optimizer.optimize_model(
                model_path,
                model_type="bert",  # Generic transformer
                num_heads=0,
                hidden_size=0,
            )
            optimized_model.save_model_to_file(model_path)
            logger.info("ONNX model optimized")
        except ImportError:
            logger.warning("onnxruntime-tools not available, skipping optimization")

    def _quantize_onnx(self, model_path: str) -> None:
        """Quantize ONNX model to int8."""
        try:
            from onnxruntime.quantization import QuantType, quantize_dynamic

            quantized_path = model_path.replace(".onnx", "_quantized.onnx")
            quantize_dynamic(
                model_path,
                quantized_path,
                weight_type=QuantType.QInt8,
            )
            logger.info(f"Quantized model saved to {quantized_path}")
        except ImportError:
            logger.warning("onnxruntime quantization not available")


class CoreMLExporter:
    """Export JAX model to CoreML format for iOS/macOS."""

    def __init__(self, config: ExportConfig):
        self.config = config

    def export(
        self,
        model_fn: Any,
        params: dict,
        output_path: str,
    ) -> str:
        """Export model to CoreML.

        Args:
            model_fn: Model apply function
            params: Model parameters
            output_path: Output file path (.mlmodel or .mlpackage)

        Returns:
            Path to exported CoreML model
        """
        try:
            import coremltools as ct
        except ImportError:
            logger.error("coremltools not available. Install with: pip install coremltools")
            raise

        cfg = self.config

        # First export to ONNX, then convert to CoreML
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            onnx_path = f.name

        onnx_exporter = ONNXExporter(cfg)
        onnx_exporter.export(model_fn, params, onnx_path)

        # Convert ONNX to CoreML
        try:
            mlmodel = ct.converters.onnx.convert(
                onnx_path,
                minimum_ios_deployment_target="17.0",
            )
        except Exception:
            # Try newer API
            mlmodel = ct.convert(
                onnx_path,
                minimum_deployment_target=ct.target.iOS17,
            )

        # Add metadata
        mlmodel.author = "Kagami"
        mlmodel.short_description = f"OrganismRSSM World Model ({cfg.model_name})"
        mlmodel.version = cfg.version

        # Save
        mlmodel.save(output_path)
        logger.info(f"Exported CoreML model to {output_path}")

        # Cleanup
        os.unlink(onnx_path)

        return output_path


class TFLiteExporter:
    """Export JAX model to TFLite format for Android/embedded."""

    def __init__(self, config: ExportConfig):
        self.config = config

    def export(
        self,
        model_fn: Any,
        params: dict,
        output_path: str,
    ) -> str:
        """Export model to TFLite.

        Args:
            model_fn: Model apply function
            params: Model parameters
            output_path: Output file path (.tflite)

        Returns:
            Path to exported TFLite model
        """
        try:
            import tensorflow as tf
            from jax.experimental import jax2tf
        except ImportError as e:
            logger.error(f"Required packages not available: {e}")
            raise

        cfg = self.config

        # Convert JAX to TF function
        tf_fn = jax2tf.convert(
            lambda obs, actions: model_fn(
                {"params": params},
                obs=obs,
                actions=actions,
                key=jax.random.PRNGKey(0),
                training=False,
            ),
            polymorphic_shapes=[
                f"(b, {cfg.seq_len}, {cfg.obs_dim})",
                f"(b, {cfg.seq_len}, {cfg.action_dim})",
            ],
        )

        # Create concrete function with fixed batch size
        @tf.function(
            input_signature=[
                tf.TensorSpec([1, cfg.seq_len, cfg.obs_dim], tf.float32, name="obs"),
                tf.TensorSpec([1, cfg.seq_len, cfg.action_dim], tf.float32, name="actions"),
            ]
        )
        def model_serving(obs, actions):
            return tf_fn(obs, actions)

        # Convert to TFLite
        converter = tf.lite.TFLiteConverter.from_concrete_functions(
            [model_serving.get_concrete_function()]
        )

        # Optimization settings
        if cfg.quantize:
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            converter.target_spec.supported_types = [tf.float16]

        tflite_model = converter.convert()

        # Save
        with open(output_path, "wb") as f:
            f.write(tflite_model)

        logger.info(f"Exported TFLite model to {output_path}")
        logger.info(f"Model size: {len(tflite_model) / 1024 / 1024:.2f} MB")

        return output_path


class ModelExporter:
    """Unified model export pipeline."""

    def __init__(self, config: ExportConfig | None = None):
        self.config = config or ExportConfig()

    def export(
        self,
        model_fn: Any,
        params: dict,
        format: str,
        output_path: str,
    ) -> str:
        """Export model to specified format.

        Args:
            model_fn: Model apply function
            params: Model parameters
            format: One of 'onnx', 'coreml', 'tflite'
            output_path: Output file path

        Returns:
            Path to exported model
        """
        exporters = {
            "onnx": ONNXExporter,
            "coreml": CoreMLExporter,
            "tflite": TFLiteExporter,
        }

        if format not in exporters:
            raise ValueError(f"Unknown format: {format}. Available: {list(exporters.keys())}")

        exporter = exporters[format](self.config)
        return exporter.export(model_fn, params, output_path)

    def export_all(
        self,
        model_fn: Any,
        params: dict,
        output_dir: str,
        model_name: str | None = None,
    ) -> dict[str, str]:
        """Export model to all formats.

        Returns:
            Dict mapping format to output path
        """
        name = model_name or self.config.model_name
        paths = {}

        formats_and_extensions = [
            ("onnx", ".onnx"),
            ("coreml", ".mlpackage"),
            ("tflite", ".tflite"),
        ]

        os.makedirs(output_dir, exist_ok=True)

        for fmt, ext in formats_and_extensions:
            output_path = os.path.join(output_dir, f"{name}{ext}")
            try:
                paths[fmt] = self.export(model_fn, params, fmt, output_path)
            except Exception as e:
                logger.warning(f"Failed to export {fmt}: {e}")
                paths[fmt] = None

        return paths


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Export OrganismRSSM models")
    parser.add_argument(
        "--checkpoint",
        type=str,
        required=True,
        help="Path to model checkpoint",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["onnx", "coreml", "tflite", "all"],
        default="onnx",
        help="Export format",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="exports/",
        help="Output directory",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="organism_rssm_small",
        help="Model name for output files",
    )
    parser.add_argument(
        "--quantize",
        action="store_true",
        help="Enable quantization for mobile",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Batch size for export",
    )

    args = parser.parse_args()

    config = ExportConfig(
        model_name=args.model_name,
        batch_size=args.batch_size,
        quantize=args.quantize,
    )

    exporter = ModelExporter(config)

    # Load checkpoint (placeholder - implement actual loading)
    logger.info(f"Loading checkpoint from {args.checkpoint}")

    # For demonstration, create dummy model and params
    from kagami.core.training.jax.configs.student_configs import STUDENT_SMALL
    from kagami.core.training.jax.distill import StudentRSSM

    model = StudentRSSM(config=STUDENT_SMALL)
    key = jax.random.PRNGKey(42)

    dummy_obs = jnp.zeros((1, 8, config.obs_dim))
    dummy_actions = jnp.zeros((1, 8, config.action_dim))

    params = model.init(
        {"params": key},
        obs=dummy_obs,
        actions=dummy_actions,
        key=key,
    )["params"]

    # Export
    if args.format == "all":
        paths = exporter.export_all(
            model.apply,
            params,
            args.output_dir,
            args.model_name,
        )
        print("\nExported models:")
        for fmt, path in paths.items():
            if path:
                print(f"  {fmt}: {path}")
    else:
        ext = {"onnx": ".onnx", "coreml": ".mlpackage", "tflite": ".tflite"}[args.format]
        output_path = os.path.join(args.output_dir, f"{args.model_name}{ext}")
        os.makedirs(args.output_dir, exist_ok=True)

        path = exporter.export(model.apply, params, args.format, output_path)
        print(f"\nExported: {path}")


if __name__ == "__main__":
    main()
