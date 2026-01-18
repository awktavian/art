import torch
import time
import torch.nn as nn
from kagami.core.world_model.pxo_transformer import PXOTransformer


def benchmark_attention_scaling():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if torch.backends.mps.is_available():
        device = "mps"

    print(f"Benchmarking PXO Attention Scaling on {device}...")

    B = 4
    SeqLen = 2048  # Increased sequence length to stress O(N^2)

    # 1. Standard Transformer (Bulk)
    # Simulating full 2048D attention
    standard_attn = nn.MultiheadAttention(embed_dim=2048, num_heads=8, batch_first=True).to(device)
    x_bulk = torch.randn(B, SeqLen, 2048, device=device)

    # 2. PXO Transformer (Fiber Bundle)
    # Operates on ~384D base but projects to 22D manifold internally
    # We'll benchmark the full block which includes the projection overhead
    pxo = PXOTransformer(
        d_model=384, hyperbolic_dim=14, num_layers=1, use_hyp=True, use_oct=True
    ).to(device)
    x_pxo = torch.randn(B, SeqLen, 384, device=device)

    # Warmup
    print("Warming up...")
    for _ in range(10):
        _ = standard_attn(x_bulk, x_bulk, x_bulk)
        _ = pxo(x_pxo)

    # Measure Standard
    start = time.time()
    iters = 50
    for _ in range(iters):
        _ = standard_attn(x_bulk, x_bulk, x_bulk)
    if device == "cuda":
        torch.cuda.synchronize()
    if device == "mps":
        torch.mps.synchronize()
    dt_standard = (time.time() - start) / iters

    # Measure PXO
    start = time.time()
    for _ in range(iters):
        _ = pxo(x_pxo)
    if device == "cuda":
        torch.cuda.synchronize()
    if device == "mps":
        torch.mps.synchronize()
    dt_pxo = (time.time() - start) / iters

    print(f"\nResults (SeqLen={SeqLen}):")
    print(f"Standard Attention (2048D): {dt_standard * 1000:.2f} ms/step")
    print(f"PXO Fiber Attention (Geometric): {dt_pxo * 1000:.2f} ms/step")
    print(f"Speedup Factor: {dt_standard / dt_pxo:.2f}x")


if __name__ == "__main__":
    benchmark_attention_scaling()
