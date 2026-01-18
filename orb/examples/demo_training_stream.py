#!/usr/bin/env python3
"""Demo script for the Training Stream.

Simulates a training run and emits metrics to the Learning gallery.
Run this while viewing /gallery/learning.html to see real-time updates.

Usage:
    python scripts/demo/demo_training_stream.py

Prerequisites:
    - Redis must be running
    - API server must be running (make run-api)
    - Open http://localhost:8889/learning.html in browser

Created: November 30, 2025
"""

import argparse
import math
import random
import time


def simulate_training(
    num_steps: int = 500,
    delay: float = 0.1,
    verbose: bool = True,
) -> None:
    """Simulate a training run with realistic metrics.

    Args:
        num_steps: Number of training steps to simulate
        delay: Delay between steps (seconds)
        verbose: Print progress to console
    """
    from kagami_api.services.training_stream import (
        emit_training_metrics,
        mark_training_active,
        mark_training_complete,
    )

    print("=" * 60)
    print("TRAINING STREAM DEMO")
    print("=" * 60)
    print(f"Simulating {num_steps} training steps")
    print("Open http://localhost:8889/learning.html to watch")
    print("=" * 60)
    print()

    # Start training session
    run_id = mark_training_active("demo_run")
    print(f"Started training session: {run_id}")
    print()

    try:
        for step in range(num_steps):
            # Progress through training (0 to 1)
            progress = step / num_steps

            # Simulate decreasing loss
            base_loss = 2.0 * math.exp(-3.0 * progress) + 0.05
            noise = random.gauss(0, 0.05)
            total_loss = max(0.01, base_loss + noise)

            # Component losses
            distill_loss = total_loss * random.uniform(0.3, 0.5)
            contrastive_loss = total_loss * random.uniform(0.2, 0.3)
            vq_loss = total_loss * random.uniform(0.1, 0.2)
            ema_loss = total_loss * random.uniform(0.05, 0.15)

            # Gradients (log-scale)
            grad_base = 1e-4 * (1 + 2 * (1 - progress))
            p1 = grad_base * 0.01 * random.uniform(0.5, 2.0)
            p50 = grad_base * random.uniform(0.5, 2.0)
            p99 = grad_base * 100 * random.uniform(0.5, 2.0)

            # Strange loop coherence (increases with training)
            loop_strength = min(0.95, progress * 1.2 + random.gauss(0, 0.05))
            closure_loss = max(0.01, (1 - loop_strength) * 0.5 + random.gauss(0, 0.02))

            # VQ codebook activity (more codes used as training progresses)
            num_active = int(50 + progress * 450 * random.uniform(0.8, 1.2))
            active_indices = random.sample(range(512), min(num_active, 512))

            # Emit metrics
            emit_training_metrics(
                step=step,
                epoch=step // 100,
                losses={
                    "total": total_loss,
                    "distill": distill_loss,
                    "contrastive": contrastive_loss,
                    "vq": vq_loss,
                    "ema": ema_loss,
                    "loop_closure": closure_loss,
                },
                gradients={
                    "p1": p1,
                    "p50": p50,
                    "p99": p99,
                },
                loop={
                    "strength": loop_strength,
                    "closure": closure_loss,
                },
                system={
                    "lr": 1e-4 * (1 - progress * 0.9),
                    "memory": 4.5 + random.gauss(0, 0.1),
                    "samples_per_sec": 120 + random.gauss(0, 10),
                    "device": "cuda:0",
                },
                codebook={
                    "active_indices": active_indices,
                },
                force=True,
            )

            # Progress logging
            if verbose and step % 50 == 0:
                print(
                    f"Step {step:4d} | "
                    f"loss={total_loss:.4f} | "
                    f"loop={loop_strength:.1%} | "
                    f"codes={len(active_indices)}"
                )

            time.sleep(delay)

    except KeyboardInterrupt:
        print("\nInterrupted by user")

    finally:
        mark_training_complete(
            {
                "final_loss": total_loss,
                "final_loop_strength": loop_strength,
            }
        )
        print()
        print("=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Demo the Training Stream")
    parser.add_argument(
        "--steps",
        type=int,
        default=500,
        help="Number of training steps to simulate",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between steps (seconds)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    simulate_training(
        num_steps=args.steps,
        delay=args.delay,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
