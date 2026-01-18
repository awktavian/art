"""UnifiedWorldModel Demo - Automatic World Model + RSSM Integration.

This script demonstrates how to use the UnifiedWorldModel for end-to-end
training with automatic S7 extraction and RSSM dynamics.

Usage:
    python examples/unified_world_model_demo.py
"""

import torch
from kagami.core.world_model import (
    create_unified_world_model,
)


def main():
    print("=" * 70)
    print("UnifiedWorldModel Demo")
    print("=" * 70)

    # Create model with factory function
    print("\n1. Creating UnifiedWorldModel...")
    model = create_unified_world_model(
        bulk_dim=128,  # Compact for demo
        device="cpu",
    )
    print(f"   ✅ Model initialized with {sum(p.numel() for p in model.parameters()):,} parameters")

    # Create sample observations
    print("\n2. Creating sample observations...")
    batch_size = 4
    seq_len = 8
    obs_dim = 128

    observations = torch.randn(batch_size, seq_len, obs_dim)
    print(f"   Observations shape: {observations.shape}")

    # Forward pass (inference mode)
    print("\n3. Running forward pass (inference)...")
    model.eval()
    with torch.no_grad():
        state = model.forward(observations, training=False)

    print("   ✅ Forward pass complete")
    print(f"   - Organism action shape: {state.organism_action.shape}")
    print(f"   - S7 phase shape: {state.core_state.s7_phase.shape}")  # type: ignore[union-attr]
    print(f"   - E8 code shape: {state.core_state.e8_code.shape}")  # type: ignore[union-attr]
    print(f"   - RSSM deterministic state shape: {state.h_next.shape}")
    print(f"   - RSSM stochastic state shape: {state.z_next.shape}")

    # Training step
    print("\n4. Running training step...")
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # Create training targets
    target_obs = torch.randn(batch_size, seq_len, obs_dim)
    targets = {"observations": target_obs}

    # Forward + loss + backward
    optimizer.zero_grad()
    state = model.forward(observations, training=True)
    loss, loss_dict = model.compute_loss(state, targets)
    loss.backward()
    optimizer.step()

    print("   ✅ Training step complete")
    print(f"   - Total loss: {loss_dict['total']:.4f}")
    print(
        f"   - Loss components: {', '.join(f'{k}: {v:.4f}' for k, v in loss_dict.items() if k != 'total')}"
    )

    # Checkpoint save/load
    print("\n5. Testing checkpoint save/load...")
    checkpoint = model.get_state_dict_unified()
    print(f"   Checkpoint saved with {len(checkpoint)} keys")

    # Create new model and load
    model2 = create_unified_world_model(bulk_dim=128, device="cpu")
    model2.load_state_dict_unified(checkpoint)
    print("   ✅ Checkpoint loaded successfully")

    # State management
    print("\n6. Testing state management...")
    model.reset_rssm_state(batch_size=batch_size)
    print("   ✅ RSSM state reset")

    # Multi-step rollout
    print("\n7. Running multi-step rollout...")
    model.eval()
    with torch.no_grad():
        for t in range(3):
            obs_t = torch.randn(batch_size, obs_dim)
            state = model.forward(obs_t, training=False)
            print(
                f"   Step {t + 1}: action = {state.organism_action[0, :3].tolist()}"
            )  # First 3 dims of first sample

    print("\n" + "=" * 70)
    print("Demo complete! UnifiedWorldModel is ready for use.")
    print("=" * 70)


if __name__ == "__main__":
    main()
