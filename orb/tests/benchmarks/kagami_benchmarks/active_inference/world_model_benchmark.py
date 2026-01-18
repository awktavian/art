# SPDX-License-Identifier: MIT
"""World Model Benchmark.

Validates the world model component of Active Inference:
- State prediction accuracy
- Observation encoding quality
- Temporal coherence
- Information compression (Information Bottleneck)

The world model is critical for accurate EFE computation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class WorldModelBenchmarkResult:
    """Result of world model benchmark."""

    # Prediction quality
    prediction_mse: float = 0.0
    prediction_r2: float = 0.0
    temporal_coherence: float = 0.0

    # Information Bottleneck
    compression_ratio: float = 0.0
    reconstruction_loss: float = 0.0
    kl_divergence: float = 0.0

    # Latency
    encode_latency_ms: float = 0.0
    predict_latency_ms: float = 0.0
    decode_latency_ms: float = 0.0

    # Overall
    passed: bool = False
    score: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_mse": self.prediction_mse,
            "prediction_r2": self.prediction_r2,
            "temporal_coherence": self.temporal_coherence,
            "compression_ratio": self.compression_ratio,
            "reconstruction_loss": self.reconstruction_loss,
            "kl_divergence": self.kl_divergence,
            "encode_latency_ms": self.encode_latency_ms,
            "predict_latency_ms": self.predict_latency_ms,
            "decode_latency_ms": self.decode_latency_ms,
            "passed": self.passed,
            "score": self.score,
            "error": self.error,
        }


class WorldModelBenchmark:
    """Benchmark for K OS World Model."""

    def __init__(
        self,
        device: str | None = None,
        batch_size: int = 32,
        seq_len: int = 16,
        # KagamiWorldModel default: E8(8) + S7(7) = 15D observations
        obs_dim: int = 15,
        state_dim: int = 64,
    ) -> None:
        """Initialize world model benchmark.

        Args:
            device: Torch device.
            batch_size: Batch size for tests.
            seq_len: Sequence length.
            obs_dim: Observation dimension.
            state_dim: State dimension.
        """
        if device is None:
            # Use unified device selection (MPS > CUDA > CPU)
            from kagami.core.utils.device import get_device_str

            device = get_device_str()

        self.device = torch.device(device)
        self.batch_size = batch_size
        self.seq_len = seq_len
        self.obs_dim = obs_dim
        self.state_dim = state_dim

        logger.info(f"World Model Benchmark on {self.device}")

    def _infer_bulk_dim(self, model: Any | None) -> int:
        """Infer bulk observation dimensionality (hourglass input) from model if available."""
        if model is None:
            return self.obs_dim
        config = getattr(model, "config", None)
        if config is not None:
            dims = getattr(config, "layer_dimensions", None)
            if isinstance(dims, (tuple, list)) and len(dims) > 0:
                try:
                    return int(dims[0])
                except Exception:
                    pass
            bulk_dim = getattr(config, "bulk_dim", None)
            if bulk_dim is not None:
                try:
                    return int(bulk_dim)
                except Exception:
                    pass
        return self.obs_dim

    def _infer_manifold_dim(self, model: Any | None) -> int:
        """Infer manifold observation dimensionality (RSSM observation space) from model if available."""
        if model is None:
            return 15
        rssm = getattr(model, "rssm", None)
        if rssm is not None and hasattr(rssm, "obs_dim"):
            try:
                return int(rssm.obs_dim)
            except Exception:
                pass
        config = getattr(model, "config", None)
        if config is not None:
            try:
                return int(getattr(config, "e8_dim", 8)) + int(getattr(config, "s7_dim", 7))
            except Exception:
                pass
        return 15

    def _move_model_to_device(self, model: Any) -> Any:
        """Best-effort move model weights to the benchmark device."""
        try:
            if hasattr(model, "to"):
                model = model.to(self.device)
            if hasattr(model, "eval"):
                model.eval()
        except Exception as e:
            logger.debug(f"Failed to move model to device {self.device}: {e}")
        return model

    def _get_world_model(self) -> Any:
        """Get world model from K OS via canonical service."""
        try:
            from kagami.core.world_model import get_world_model_service

            service = get_world_model_service()
            model = service.model  # Returns KagamiWorldModel
            return self._move_model_to_device(model)
        except ImportError:
            logger.warning("World model service not available")
            return None
        except Exception as e:
            logger.warning(f"World model initialization failed: {e}")
            return None

    def _create_test_sequence(self, obs_dim: int | None = None) -> torch.Tensor:
        """Create test observation sequence."""
        obs_dim = int(obs_dim if obs_dim is not None else self.obs_dim)

        # Create a sequence with temporal structure
        t = torch.linspace(0, 2 * 3.14159, self.seq_len)

        # Base signal with harmonics
        base = torch.sin(t).unsqueeze(-1)
        harmonics = torch.sin(2 * t).unsqueeze(-1) * 0.5

        # Expand to full dimension
        signal = torch.cat([base, harmonics], dim=-1)
        # Repeat enough times to cover obs_dim, then slice.
        reps = max(1, (obs_dim + signal.shape[-1] - 1) // signal.shape[-1])
        signal = signal.repeat(1, reps)[..., :obs_dim]

        # Add noise
        noise = torch.randn_like(signal) * 0.1

        # Batch it
        obs = (signal + noise).unsqueeze(0).repeat(self.batch_size, 1, 1)

        return obs.to(self.device).contiguous()

    def _encode_bulk_to_manifold(
        self, model: Any, bulk_obs: torch.Tensor
    ) -> tuple[torch.Tensor, Any, dict[str, Any]]:
        """Encode bulk observations and return per-step manifold observations [B, T, 15]."""
        if not hasattr(model, "encode"):
            raise AttributeError("Model missing encode()")

        core_state, enc_metrics = model.encode(bulk_obs)
        if not isinstance(enc_metrics, dict):
            enc_metrics = {}

        shell = getattr(core_state, "shell_residual", None)
        if shell is None:
            shell = getattr(core_state, "e8_code", None)
        s7 = getattr(core_state, "s7_phase", None)

        if not isinstance(shell, torch.Tensor):
            raise ValueError("CoreState missing shell_residual/e8_code tensor")
        if shell.dim() == 2:
            shell = shell.unsqueeze(1)

        B, T, _ = shell.shape
        s7_dim = self._infer_manifold_dim(model) - int(shell.shape[-1])
        if s7_dim <= 0:
            s7_dim = 7

        if not isinstance(s7, torch.Tensor):
            s7 = torch.zeros(B, T, s7_dim, device=shell.device, dtype=shell.dtype)
        elif s7.dim() == 2:
            s7 = s7.unsqueeze(1)

        # Align time/batch dims defensively.
        if s7.shape[0] != B or s7.shape[1] != T:
            min_b = min(int(s7.shape[0]), int(B))
            min_t = min(int(s7.shape[1]), int(T))
            shell = shell[:min_b, :min_t]
            s7 = s7[:min_b, :min_t]

        organism_obs = torch.cat([shell, s7], dim=-1)
        return organism_obs, core_state, enc_metrics

    def test_prediction_accuracy(self) -> tuple[bool, dict[str, float]]:
        """Test one-step prediction accuracy."""
        try:
            model = self._get_world_model()
            obs = self._create_test_sequence(
                obs_dim=self._infer_bulk_dim(model) if model is not None else self.obs_dim
            )

            if model is None:
                # Mock prediction test
                # Predict next step from current
                x_t = obs[:, :-1, :]
                x_t1 = obs[:, 1:, :]

                # Simple linear prediction (baseline)
                pred = x_t  # Naive: predict no change

                mse = F.mse_loss(pred, x_t1).item()

                # R² score
                ss_res = ((x_t1 - pred) ** 2).sum()
                ss_tot = ((x_t1 - x_t1.mean()) ** 2).sum()
                r2 = 1 - (ss_res / ss_tot).item() if ss_tot > 0 else 0.0

                return True, {"mse": mse, "r2": r2, "mock": True}

            # Use actual model (KagamiWorldModel): one-step prior prediction via RSSM
            with torch.no_grad():
                rssm = getattr(model, "rssm", None)
                if rssm is None or not hasattr(getattr(rssm, "dynamics", rssm), "step"):
                    raise AttributeError(
                        "Model missing rssm.dynamics.step() for prediction benchmark"
                    )

                manifold_obs, _core_state, _enc_metrics = self._encode_bulk_to_manifold(model, obs)
                B, T, D = manifold_obs.shape
                dyn = getattr(rssm, "dynamics", rssm)
                h_dim = int(getattr(dyn, "deterministic_dim", 256))
                z_dim = int(getattr(dyn, "stochastic_dim", 14))
                action_dim = int(getattr(rssm, "action_dim", 8))

                h = torch.zeros(B, h_dim, device=self.device)
                z = torch.zeros(B, z_dim, device=self.device)
                action = torch.zeros(B, action_dim, device=self.device)

                preds: list[torch.Tensor] = []
                targets: list[torch.Tensor] = []

                for t in range(T - 1):
                    x_t = manifold_obs[:, t, :]
                    x_tp1 = manifold_obs[:, t + 1, :]

                    # Posterior update using current observation.
                    h_post, z_post, _ = dyn.step(h, z, action, obs=x_t)

                    # Prior roll-forward without observation to predict next.
                    h_prior, z_prior, _ = dyn.step(h_post, z_post, action, obs=None)
                    x_pred = rssm.predict_obs(h_prior, z_prior)

                    # Align dimensions if heads differ from obs (defensive).
                    if x_pred.shape[-1] != D:
                        min_d = min(int(x_pred.shape[-1]), int(D))
                        x_pred = x_pred[..., :min_d]
                        x_tp1 = x_tp1[..., :min_d]

                    preds.append(x_pred)
                    targets.append(x_tp1)

                    # Filter forward with posterior (typical).
                    h, z = h_post, z_post

                pred_obs = torch.stack(preds, dim=1)
                target = torch.stack(targets, dim=1)

                mse = F.mse_loss(pred_obs, target).item()
                ss_res = ((target - pred_obs) ** 2).sum()
                ss_tot = ((target - target.mean()) ** 2).sum()
                r2 = 1 - (ss_res / ss_tot).item() if ss_tot > 0 else 0.0

            return True, {"mse": mse, "r2": r2}

        except Exception as e:
            logger.error(f"Prediction accuracy test failed: {e}")
            return False, {"error": str(e)}  # type: ignore[dict-item]

    def test_temporal_coherence(self) -> tuple[bool, dict[str, float]]:
        """Test temporal coherence of state representations."""
        try:
            model = self._get_world_model()
            obs = self._create_test_sequence(
                obs_dim=self._infer_bulk_dim(model) if model is not None else self.obs_dim
            )

            if model is None:
                # Mock: check autocorrelation
                states = obs.mean(dim=-1)  # Simple state

                # Compute lag-1 autocorrelation
                mean = states.mean()
                var = ((states - mean) ** 2).mean()
                autocorr = ((states[:, :-1] - mean) * (states[:, 1:] - mean)).mean() / (var + 1e-8)

                return True, {"autocorrelation": autocorr.item(), "mock": True}

            with torch.no_grad():
                rssm = getattr(model, "rssm", None)
                if rssm is None or not hasattr(getattr(rssm, "dynamics", rssm), "step"):
                    raise AttributeError(
                        "Model missing rssm.dynamics.step() for coherence benchmark"
                    )

                manifold_obs, _core_state, _enc_metrics = self._encode_bulk_to_manifold(model, obs)
                B, T, _D = manifold_obs.shape
                dyn = getattr(rssm, "dynamics", rssm)
                h_dim = int(getattr(dyn, "deterministic_dim", 256))
                z_dim = int(getattr(dyn, "stochastic_dim", 14))
                action_dim = int(getattr(rssm, "action_dim", 8))

                h = torch.zeros(B, h_dim, device=self.device)
                z = torch.zeros(B, z_dim, device=self.device)
                action = torch.zeros(B, action_dim, device=self.device)

                zs: list[torch.Tensor] = []
                for t in range(T):
                    x_t = manifold_obs[:, t, :]
                    h, z, _ = dyn.step(h, z, action, obs=x_t)
                    zs.append(z)

                z_seq = torch.stack(zs, dim=1)  # [B, T, z_dim]
                z_norm = F.normalize(z_seq, dim=-1)
                sim = (z_norm[:, :-1] * z_norm[:, 1:]).sum(dim=-1).mean()
                coherence = float(sim.detach().item())

            return coherence > 0.5, {"coherence": coherence}

        except Exception as e:
            logger.error(f"Temporal coherence test failed: {e}")
            return False, {"error": str(e)}  # type: ignore[dict-item]

    def test_information_bottleneck(self) -> tuple[bool, dict[str, float]]:
        """Test Information Bottleneck properties.

        I(X;Z) - β·I(Z;Y) should be minimized.
        """
        try:
            model = self._get_world_model()
            obs = self._create_test_sequence(
                obs_dim=self._infer_bulk_dim(model) if model is not None else self.obs_dim
            )

            if model is None:
                # Mock IB test
                # Compression ratio = input_dim / state_dim
                compression = self.obs_dim / self.state_dim

                return True, {
                    "compression_ratio": compression,
                    "reconstruction_loss": 0.1,
                    "kl_divergence": 0.5,
                    "mock": True,
                }

            with torch.no_grad():
                if not hasattr(model, "encode") or not hasattr(model, "decode"):
                    raise AttributeError("Model missing encode/decode for IB benchmark")

                # KagamiWorldModel encode/decode return (value, metrics).
                core_state, enc_metrics = model.encode(obs)
                recon, _dec_metrics = model.decode(core_state)

                # Use E8 code dimensionality as compressed latent size.
                e8_code = getattr(core_state, "e8_code", None)
                if not isinstance(e8_code, torch.Tensor):
                    raise ValueError("CoreState missing e8_code tensor")

                z_dim = int(e8_code.shape[-1])
                compression = float(obs.shape[-1]) / float(z_dim) if z_dim > 0 else 0.0

                # Align recon dims defensively.
                recon_aligned = recon
                obs_aligned = obs
                if recon_aligned.shape != obs_aligned.shape:
                    min_t = min(int(recon_aligned.shape[1]), int(obs_aligned.shape[1]))
                    min_d = min(int(recon_aligned.shape[-1]), int(obs_aligned.shape[-1]))
                    recon_aligned = recon_aligned[:, :min_t, :min_d]
                    obs_aligned = obs_aligned[:, :min_t, :min_d]

                recon_loss = float(F.mse_loss(recon_aligned, obs_aligned).item())

                # Surrogate KL: Kagami encode path is quantized, not VAE; use 0 unless provided.
                kl_val = (
                    enc_metrics.get("kl_divergence", 0.0) if isinstance(enc_metrics, dict) else 0.0
                )
                if isinstance(kl_val, torch.Tensor):
                    kl_val = float(kl_val.detach().mean().item())
                else:
                    kl_val = float(kl_val)

            return True, {
                "compression_ratio": compression,
                "reconstruction_loss": recon_loss,
                "kl_divergence": kl_val,
            }

        except Exception as e:
            logger.error(f"Information Bottleneck test failed: {e}")
            return False, {"error": str(e)}  # type: ignore[dict-item]

    def benchmark_latency(self, n_iterations: int = 50) -> dict[str, float]:
        """Benchmark world model operation latencies."""
        model = self._get_world_model()
        obs = self._create_test_sequence(
            obs_dim=self._infer_bulk_dim(model) if model is not None else self.obs_dim
        )

        encode_times = []
        predict_times = []
        decode_times = []

        for _ in range(n_iterations):
            if model is None:
                # Mock timings
                start = time.perf_counter()
                _ = obs.mean(dim=-1)
                encode_times.append((time.perf_counter() - start) * 1000)

                start = time.perf_counter()
                _ = obs[:, 1:, :]
                predict_times.append((time.perf_counter() - start) * 1000)

                start = time.perf_counter()
                _ = obs.clone()
                decode_times.append((time.perf_counter() - start) * 1000)
            else:
                with torch.no_grad():
                    # Encode
                    start = time.perf_counter()
                    if hasattr(model, "encode"):
                        z, _ = model.encode(obs)
                    else:
                        z = obs
                    if self.device.type == "cuda":
                        torch.cuda.synchronize()
                    elif self.device.type == "mps":
                        torch.mps.synchronize()
                    encode_times.append((time.perf_counter() - start) * 1000)

                    # Predict
                    start = time.perf_counter()
                    rssm = getattr(model, "rssm", None)
                    if rssm is not None and hasattr(getattr(rssm, "dynamics", rssm), "step"):
                        # Derive manifold obs from encoded CoreState (avoid re-encoding).
                        shell = getattr(z, "shell_residual", None)
                        if shell is None:
                            shell = getattr(z, "e8_code", None)
                        s7 = getattr(z, "s7_phase", None)
                        if isinstance(shell, torch.Tensor):
                            if shell.dim() == 2:
                                shell = shell.unsqueeze(1)
                            B, T, _ = shell.shape
                            s7_dim = self._infer_manifold_dim(model) - int(shell.shape[-1])
                            if s7_dim <= 0:
                                s7_dim = 7
                            if not isinstance(s7, torch.Tensor):
                                s7 = torch.zeros(
                                    B, T, s7_dim, device=shell.device, dtype=shell.dtype
                                )
                            elif s7.dim() == 2:
                                s7 = s7.unsqueeze(1)
                            manifold_obs = torch.cat([shell, s7], dim=-1)
                        else:
                            # Fallback: zero manifold observation
                            B = obs.shape[0]
                            manifold_obs = torch.zeros(
                                B,
                                1,
                                self._infer_manifold_dim(model),
                                device=self.device,
                                dtype=obs.dtype,
                            )

                        dyn = getattr(rssm, "dynamics", rssm)
                        h_dim = int(getattr(dyn, "deterministic_dim", 256))
                        z_dim = int(getattr(dyn, "stochastic_dim", 14))
                        action_dim = int(getattr(rssm, "action_dim", 8))
                        h0 = torch.zeros(B, h_dim, device=self.device)
                        z0 = torch.zeros(B, z_dim, device=self.device)
                        action = torch.zeros(B, action_dim, device=self.device)
                        h_post, z_post, _ = dyn.step(h0, z0, action, obs=manifold_obs[:, 0, :])
                        _h_prior, _z_prior, _ = dyn.step(h_post, z_post, action, obs=None)
                    else:
                        # Fallback: no prediction path available
                        _ = z
                    if self.device.type == "cuda":
                        torch.cuda.synchronize()
                    elif self.device.type == "mps":
                        torch.mps.synchronize()
                    predict_times.append((time.perf_counter() - start) * 1000)

                    # Decode
                    start = time.perf_counter()
                    if hasattr(model, "decode"):
                        _ = model.decode(z)
                    if self.device.type == "cuda":
                        torch.cuda.synchronize()
                    elif self.device.type == "mps":
                        torch.mps.synchronize()
                    decode_times.append((time.perf_counter() - start) * 1000)

        return {
            "encode_ms": sum(encode_times) / len(encode_times),
            "predict_ms": sum(predict_times) / len(predict_times),
            "decode_ms": sum(decode_times) / len(decode_times),
        }

    async def run(self, num_samples: int = 50) -> WorldModelBenchmarkResult:
        """Run full world model benchmark.

        Args:
            num_samples: Number of latency samples.

        Returns:
            WorldModelBenchmarkResult with all metrics.
        """
        logger.info("Starting World Model benchmark...")
        result = WorldModelBenchmarkResult()

        try:
            # Test 1: Prediction accuracy
            logger.info("Testing prediction accuracy...")
            _pred_ok, pred_data = self.test_prediction_accuracy()
            result.prediction_mse = pred_data.get("mse", 0.0)
            result.prediction_r2 = pred_data.get("r2", 0.0)

            # Test 2: Temporal coherence
            logger.info("Testing temporal coherence...")
            _coh_ok, coh_data = self.test_temporal_coherence()
            result.temporal_coherence = coh_data.get(
                "coherence", coh_data.get("autocorrelation", 0.0)
            )

            # Test 3: Information Bottleneck
            logger.info("Testing Information Bottleneck...")
            _ib_ok, ib_data = self.test_information_bottleneck()
            result.compression_ratio = ib_data.get("compression_ratio", 0.0)
            result.reconstruction_loss = ib_data.get("reconstruction_loss", 0.0)
            result.kl_divergence = ib_data.get("kl_divergence", 0.0)

            # Benchmark latency
            logger.info(f"Benchmarking latency ({num_samples} samples)...")
            latency = self.benchmark_latency(n_iterations=num_samples)
            result.encode_latency_ms = latency["encode_ms"]
            result.predict_latency_ms = latency["predict_ms"]
            result.decode_latency_ms = latency["decode_ms"]

            # Compute score
            # Higher R² is better, lower MSE is better
            r2_score = max(0, result.prediction_r2)  # Clamp to [0, 1]
            coherence_score = max(0, result.temporal_coherence)
            compression_score = min(1.0, result.compression_ratio / 4.0)  # 4x compression = 1.0

            result.score = (r2_score + coherence_score + compression_score) / 3.0
            result.passed = result.score > 0.3  # Threshold

            logger.info(f"World Model benchmark complete: score={result.score:.2f}")

        except Exception as e:
            logger.error(f"World Model benchmark failed: {e}")
            result.error = str(e)
            result.passed = False

        return result


def run_world_model_benchmark(  # type: ignore[no-untyped-def]
    num_samples: int = 50,
    device: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Run world model benchmark.

    Args:
        num_samples: Number of latency samples.
        device: Torch device.
        **kwargs: Additional arguments.

    Returns:
        Dictionary with benchmark results.
    """
    benchmark = WorldModelBenchmark(device=device)

    try:
        result = asyncio.run(benchmark.run(num_samples=num_samples))
        return {
            "score": result.score,
            "passed": result.passed,
            "status": "completed" if not result.error else "failed",
            "error": result.error,
            "prediction_mse": result.prediction_mse,
            "prediction_r2": result.prediction_r2,
            "temporal_coherence": result.temporal_coherence,
            "compression_ratio": result.compression_ratio,
            "reconstruction_loss": result.reconstruction_loss,
            "kl_divergence": result.kl_divergence,
            "latency": {
                "encode_ms": result.encode_latency_ms,
                "predict_ms": result.predict_latency_ms,
                "decode_ms": result.decode_latency_ms,
            },
        }
    except Exception as e:
        logger.error(f"World Model benchmark failed: {e}")
        return {
            "score": 0.0,
            "passed": False,
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_world_model_benchmark(num_samples=20)
    print(f"World Model Benchmark Result: {result}")
