#!/usr/bin/env python3
"""Benchmark Tower Width for Information Bottleneck Optimality.

This script tests whether the 7D tower dimension is optimal according to
Information Bottleneck theory by comparing:
- 7D tower (current, S⁷ intrinsic dimension)
- 14D tower (2× capacity, G₂ dimension)
- 21D tower (H¹⁴ + S⁷ manifold dimension)

Metrics:
- Reconstruction quality (MSE, SSIM-like)
- Rate-distortion curve (bits vs quality)
- Mutual information estimates via MINE
- Codebook utilization
- Training stability

Based on analysis from docs/self_IB_OPTIMALITY_ANALYSIS.md

Usage:
    python scripts/benchmark_tower_width.py [--tower-dims 7,14,21] [--epochs 10]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from kagami_math.semantic_residual_e8 import (
    SemanticResidualE8,
    SemanticResidualE8Config,
)
from kagami.core.world_model.layers.kan_layer import KANLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class BenchmarkConfig:
    """Configuration for tower width benchmark."""

    # Tower dimensions to test
    tower_dims: list[int] = field(default_factory=lambda: [7, 14, 21])

    # Architecture
    bulk_dim: int = 512
    e8_levels: int = 4

    # Training
    batch_size: int = 64
    num_batches: int = 100
    learning_rate: float = 1e-3
    epochs: int = 10

    # Data generation
    data_complexity: str = "medium"  # "low", "medium", "high"
    latent_factors: int = 16  # True intrinsic dimension of data

    # Metrics
    compute_mine: bool = True  # Mutual information estimation
    track_codebook: bool = True

    # Output
    output_dir: str = "benchmark_results"
    save_checkpoints: bool = False


# =============================================================================
# SIMPLE AUTOENCODER FOR BENCHMARK
# =============================================================================


class TowerAutoencoder(nn.Module):
    """Simple autoencoder with configurable tower dimension.

    Architecture:
        Bulk(512) → Tower(D) → E8(8) → Tower(D) → Bulk(512)
    """

    def __init__(
        self,
        bulk_dim: int = 512,
        tower_dim: int = 7,
        e8_levels: int = 4,
        use_kan: bool = True,
    ):
        super().__init__()
        self.bulk_dim = bulk_dim
        self.tower_dim = tower_dim
        self.e8_levels = e8_levels

        # Encoder: Bulk → Tower
        if use_kan and tower_dim >= 4:
            self.bulk_to_tower = KANLayer(
                in_features=bulk_dim,
                out_features=tower_dim,
                num_knots=8,
                degree=3,
            )
        else:
            self.bulk_to_tower = nn.Sequential(
                nn.Linear(bulk_dim, bulk_dim // 2),
                nn.GELU(),
                nn.Linear(bulk_dim // 2, tower_dim),
            )

        # Tower → E8 (8D)
        self.tower_to_e8 = nn.Linear(tower_dim, 8)

        # E8 Residual VQ
        self.e8_vq = SemanticResidualE8(
            SemanticResidualE8Config(
                training_levels=e8_levels,
                inference_levels=e8_levels,
                use_straight_through=True,
            )
        )

        # Decoder: E8 → Tower → Bulk
        self.e8_to_tower = nn.Linear(8, tower_dim)

        if use_kan and tower_dim >= 4:
            self.tower_to_bulk = KANLayer(
                in_features=tower_dim,
                out_features=bulk_dim,
                num_knots=8,
                degree=3,
            )
        else:
            self.tower_to_bulk = nn.Sequential(
                nn.Linear(tower_dim, bulk_dim // 2),
                nn.GELU(),
                nn.Linear(bulk_dim // 2, bulk_dim),
            )

        # Skip connection gate
        self.skip_gate = nn.Parameter(torch.tensor(0.1))

    def forward(self, x: torch.Tensor) -> dict[str, Any]:
        """Forward pass with metrics.

        Returns:
            dict with:
                - reconstructed: Reconstructed input
                - tower_pre: Tower representation before E8
                - e8_quantized: E8 quantized representation
                - e8_indices: Quantization indices
                - vq_loss: VQ commitment loss
                - metrics: E8 metrics dict
        """
        x.shape[0]

        # Encode: Bulk → Tower → E8
        tower_pre = self.bulk_to_tower(x)
        e8_continuous = self.tower_to_e8(tower_pre)

        # E8 Residual VQ
        e8_quantized, indices, metrics = self.e8_vq(e8_continuous)

        # Decode: E8 → Tower → Bulk
        tower_post = self.e8_to_tower(e8_quantized)

        # Skip connection from tower_pre
        tower_combined = tower_post + self.skip_gate * tower_pre

        reconstructed = self.tower_to_bulk(tower_combined)

        return {
            "reconstructed": reconstructed,
            "tower_pre": tower_pre,
            "e8_quantized": e8_quantized,
            "e8_indices": indices,
            "vq_loss": metrics.get("commitment_loss", 0.0),
            "metrics": metrics,
        }

    def get_rate(self) -> float:
        """Get rate in bits per sample."""
        # Each E8 level encodes log2(240) ≈ 7.91 bits
        return self.e8_levels * 7.91


# =============================================================================
# DATA GENERATION
# =============================================================================


def generate_synthetic_data(
    batch_size: int,
    bulk_dim: int,
    latent_factors: int,
    complexity: str = "medium",
) -> torch.Tensor:
    """Generate synthetic data with known intrinsic dimension.

    Args:
        batch_size: Number of samples
        bulk_dim: Output dimension
        latent_factors: True intrinsic dimension
        complexity: "low", "medium", "high" - affects nonlinearity

    Returns:
        Tensor of shape [batch_size, bulk_dim]
    """
    # Generate latent factors
    z = torch.randn(batch_size, latent_factors)

    # Map to bulk dimension with nonlinearity
    W1 = torch.randn(latent_factors, bulk_dim) / latent_factors**0.5
    W2 = torch.randn(latent_factors, bulk_dim) / latent_factors**0.5

    if complexity == "low":
        # Linear mapping (easy)
        x = z @ W1
    elif complexity == "medium":
        # Nonlinear but smooth
        x = torch.tanh(z @ W1) + 0.5 * (z @ W2)
    else:  # high
        # Highly nonlinear
        x = torch.sin(z @ W1) * torch.cos(z @ W2) + torch.tanh(z @ W1)

    # Normalize to unit variance
    x = x / (x.std() + 1e-6)

    return x


# =============================================================================
# MINE ESTIMATOR (Mutual Information)
# =============================================================================


class MINEEstimator(nn.Module):
    """Mutual Information Neural Estimator (MINE).

    Estimates I(X; Z) via variational bound:
        I(X; Z) ≥ E[T(x,z)] - log(E[e^T(x,z')])

    where z' is sampled from marginal p(z).
    """

    def __init__(self, x_dim: int, z_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(x_dim + z_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, x: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Compute T(x, z)."""
        xz = torch.cat([x, z], dim=-1)
        return self.net(xz)

    def estimate_mi(
        self,
        x: torch.Tensor,
        z: torch.Tensor,
        n_samples: int = 1000,
    ) -> float:
        """Estimate mutual information I(X; Z)."""
        self.eval()
        with torch.no_grad():
            # Joint samples
            t_joint = self(x, z)

            # Marginal samples (shuffle z)
            z_marginal = z[torch.randperm(z.shape[0])]
            t_marginal = self(x, z_marginal)

            # MINE lower bound
            mi_estimate = (
                t_joint.mean()
                - torch.logsumexp(t_marginal, dim=0)
                + torch.log(torch.tensor(float(z.shape[0])))
            )

            return mi_estimate.item()


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================


@dataclass
class BenchmarkResult:
    """Results for a single tower dimension."""

    tower_dim: int
    final_loss: float
    reconstruction_mse: float
    rate_bits: float
    distortion: float
    codebook_utilization: float
    mi_x_tower: float | None  # I(X; Tower)
    mi_tower_e8: float | None  # I(Tower; E8)
    training_time: float
    epoch_losses: list[float] = field(default_factory=list)


def run_benchmark(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """Run benchmark for all tower dimensions."""
    results = []

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    for tower_dim in config.tower_dims:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Benchmarking tower_dim = {tower_dim}")
        logger.info(f"{'=' * 60}")

        # Create model
        model = TowerAutoencoder(
            bulk_dim=config.bulk_dim,
            tower_dim=tower_dim,
            e8_levels=config.e8_levels,
        ).to(device)

        param_count = sum(p.numel() for p in model.parameters())
        logger.info(f"Parameters: {param_count:,}")

        # Optimizer
        optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate)

        # MINE estimators (optional)
        mine_x_tower = None
        mine_tower_e8 = None
        if config.compute_mine:
            mine_x_tower = MINEEstimator(config.bulk_dim, tower_dim).to(device)
            mine_tower_e8 = MINEEstimator(tower_dim, 8).to(device)
            mine_optimizer = torch.optim.Adam(
                list(mine_x_tower.parameters()) + list(mine_tower_e8.parameters()),
                lr=1e-3,
            )

        # Training loop
        epoch_losses = []
        start_time = time.time()

        for epoch in range(config.epochs):
            model.train()
            epoch_loss = 0.0

            for batch_idx in range(config.num_batches):
                # Generate data
                x = generate_synthetic_data(
                    config.batch_size,
                    config.bulk_dim,
                    config.latent_factors,
                    config.data_complexity,
                ).to(device)

                # Forward pass
                output = model(x)

                # Loss: reconstruction + VQ commitment
                recon_loss = F.mse_loss(output["reconstructed"], x)
                vq_loss = output["vq_loss"]
                loss = recon_loss + 0.25 * vq_loss

                # Backward pass
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

                # Train MINE (occasionally)
                if config.compute_mine and batch_idx % 10 == 0:
                    with torch.no_grad():
                        output_detach = model(x)

                    # MINE loss for I(X; Tower)
                    t_joint = mine_x_tower(x, output_detach["tower_pre"])
                    z_marginal = output_detach["tower_pre"][torch.randperm(config.batch_size)]
                    t_marginal = mine_x_tower(x, z_marginal)
                    mine_loss_1 = -(t_joint.mean() - torch.logsumexp(t_marginal, dim=0))

                    # MINE loss for I(Tower; E8)
                    t_joint_2 = mine_tower_e8(
                        output_detach["tower_pre"], output_detach["e8_quantized"]
                    )
                    e8_marginal = output_detach["e8_quantized"][torch.randperm(config.batch_size)]
                    t_marginal_2 = mine_tower_e8(output_detach["tower_pre"], e8_marginal)
                    mine_loss_2 = -(t_joint_2.mean() - torch.logsumexp(t_marginal_2, dim=0))

                    mine_optimizer.zero_grad()
                    (mine_loss_1 + mine_loss_2).backward()
                    mine_optimizer.step()

            avg_loss = epoch_loss / config.num_batches
            epoch_losses.append(avg_loss)
            logger.info(f"Epoch {epoch + 1}/{config.epochs}: Loss = {avg_loss:.6f}")

        training_time = time.time() - start_time

        # Final evaluation
        model.eval()
        with torch.no_grad():
            x_eval = generate_synthetic_data(
                config.batch_size * 10,
                config.bulk_dim,
                config.latent_factors,
                config.data_complexity,
            ).to(device)

            output_eval = model(x_eval)
            final_mse = F.mse_loss(output_eval["reconstructed"], x_eval).item()

            # Codebook utilization
            all_indices = output_eval["e8_indices"]
            if isinstance(all_indices, list):
                all_indices = torch.cat([idx.flatten() for idx in all_indices])
            unique_codes = len(torch.unique(all_indices))
            codebook_util = unique_codes / 240  # E8 has 240 codes

            # MINE estimates
            mi_x_tower = None
            mi_tower_e8 = None
            if config.compute_mine:
                mi_x_tower = mine_x_tower.estimate_mi(x_eval, output_eval["tower_pre"])  # type: ignore[union-attr]
                mi_tower_e8 = mine_tower_e8.estimate_mi(  # type: ignore[union-attr]
                    output_eval["tower_pre"], output_eval["e8_quantized"]
                )

        # Compile result
        result = BenchmarkResult(
            tower_dim=tower_dim,
            final_loss=epoch_losses[-1],
            reconstruction_mse=final_mse,
            rate_bits=model.get_rate(),
            distortion=final_mse,  # MSE as distortion
            codebook_utilization=codebook_util,
            mi_x_tower=mi_x_tower,
            mi_tower_e8=mi_tower_e8,
            training_time=training_time,
            epoch_losses=epoch_losses,
        )
        results.append(result)

        logger.info(f"\nResults for tower_dim = {tower_dim}:")
        logger.info(f"  Final MSE: {final_mse:.6f}")
        logger.info(f"  Rate: {model.get_rate():.2f} bits")
        logger.info(f"  Codebook Utilization: {codebook_util:.2%}")
        if mi_x_tower is not None:
            logger.info(f"  I(X; Tower): {mi_x_tower:.4f} nats")
        if mi_tower_e8 is not None:
            logger.info(f"  I(Tower; E8): {mi_tower_e8:.4f} nats")
        logger.info(f"  Training Time: {training_time:.2f}s")

    return results


def save_results(results: list[BenchmarkResult], config: BenchmarkConfig) -> None:
    """Save benchmark results to JSON."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "config": {
            "tower_dims": config.tower_dims,
            "bulk_dim": config.bulk_dim,
            "e8_levels": config.e8_levels,
            "latent_factors": config.latent_factors,
            "data_complexity": config.data_complexity,
            "epochs": config.epochs,
        },
        "results": [
            {
                "tower_dim": r.tower_dim,
                "final_loss": r.final_loss,
                "reconstruction_mse": r.reconstruction_mse,
                "rate_bits": r.rate_bits,
                "distortion": r.distortion,
                "codebook_utilization": r.codebook_utilization,
                "mi_x_tower": r.mi_x_tower,
                "mi_tower_e8": r.mi_tower_e8,
                "training_time": r.training_time,
                "epoch_losses": r.epoch_losses,
            }
            for r in results
        ],
    }

    output_file = output_dir / f"tower_width_benchmark_{int(time.time())}.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    logger.info(f"\nResults saved to: {output_file}")


def print_summary(results: list[BenchmarkResult]) -> None:
    """Print summary comparison table."""
    print("\n" + "=" * 80)
    print("TOWER WIDTH BENCHMARK SUMMARY")
    print("=" * 80)
    print(
        f"{'Tower Dim':<12} {'MSE':<12} {'Rate (bits)':<12} {'Codebook %':<12} "
        f"{'I(X;T)':<12} {'Time (s)':<10}"
    )
    print("-" * 80)

    for r in results:
        mi_str = f"{r.mi_x_tower:.2f}" if r.mi_x_tower else "N/A"
        print(
            f"{r.tower_dim:<12} {r.reconstruction_mse:<12.6f} {r.rate_bits:<12.2f} "
            f"{r.codebook_utilization:<12.2%} {mi_str:<12} {r.training_time:<10.2f}"
        )

    print("=" * 80)

    # Find best by MSE
    best = min(results, key=lambda r: r.reconstruction_mse)
    print(f"\nBest tower dimension by MSE: {best.tower_dim}D (MSE = {best.reconstruction_mse:.6f})")

    # Recommendation
    print("\nRECOMMENDATION:")
    if best.tower_dim == 7:
        print("  ✅ Current 7D tower is optimal for this task complexity.")
    elif best.tower_dim == 14:
        print("  ⚠️ 14D tower shows improvement. Consider G₂ dimension for tower.")
    else:
        print("  ⚠️ 21D tower shows improvement. Consider full manifold dimension.")


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Benchmark tower width for IB optimality")
    parser.add_argument(
        "--tower-dims",
        type=str,
        default="7,14,21",
        help="Comma-separated tower dimensions to test",
    )
    parser.add_argument("--epochs", type=int, default=10, help="Training epochs per config")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument("--num-batches", type=int, default=100, help="Batches per epoch")
    parser.add_argument(
        "--complexity",
        type=str,
        choices=["low", "medium", "high"],
        default="medium",
        help="Data complexity",
    )
    parser.add_argument(
        "--latent-factors",
        type=int,
        default=16,
        help="True intrinsic dimension of data",
    )
    parser.add_argument("--no-mine", action="store_true", help="Skip MINE estimation")
    parser.add_argument(
        "--output-dir", type=str, default="benchmark_results", help="Output directory"
    )

    args = parser.parse_args()

    # Parse tower dims
    tower_dims = [int(d.strip()) for d in args.tower_dims.split(",")]

    config = BenchmarkConfig(
        tower_dims=tower_dims,
        epochs=args.epochs,
        batch_size=args.batch_size,
        num_batches=args.num_batches,
        data_complexity=args.complexity,
        latent_factors=args.latent_factors,
        compute_mine=not args.no_mine,
        output_dir=args.output_dir,
    )

    logger.info("Tower Width Benchmark Configuration:")
    logger.info(f"  Tower dims: {config.tower_dims}")
    logger.info(f"  Bulk dim: {config.bulk_dim}")
    logger.info(f"  E8 levels: {config.e8_levels}")
    logger.info(f"  Data complexity: {config.data_complexity}")
    logger.info(f"  Latent factors: {config.latent_factors}")
    logger.info(f"  Epochs: {config.epochs}")

    # Run benchmark
    results = run_benchmark(config)

    # Save and summarize
    save_results(results, config)
    print_summary(results)


if __name__ == "__main__":
    main()
