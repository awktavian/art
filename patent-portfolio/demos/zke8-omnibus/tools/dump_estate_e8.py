#!/usr/bin/env python3
"""Dump the estate's OWN E8 outputs as JSON so a node script can check the
browser port against them. Read-only: imports kagami_math + the codec, writes
one JSON file. No builds, no writes into any repository.

Usage: python3 dump_estate_e8.py OUT.json
"""
import json
import sys

import numpy as np
import torch

from kagami_math.dimensions import generate_e8_roots
from kagami_math.e8_lattice_quantizer import nearest_e8
from kagami_math.e8_lattice_protocol import E8LatticeResidualConfig, ResidualE8LatticeVQ
from kagami.core.digest.e8_period_codec import E8PeriodCodec

SEED = 20261102
N = 512

def main(out_path: str) -> int:
    roots = generate_e8_roots().to(torch.float64)
    codec = E8PeriodCodec()

    rng = np.random.default_rng(SEED)
    # Integral, even-sum vectors: the ActivityBin class the codec is lossless on.
    ints = rng.integers(-64, 64, size=(N // 2, 8)).astype(np.int64)
    # Force even coordinate sum (D8 membership) on half of them.
    ints[:, 7] = ints[:, 7] - (ints.sum(axis=1) % 2)
    # Integral, odd-sum vectors.
    odd = rng.integers(-64, 64, size=(N // 4, 8)).astype(np.int64)
    odd[:, 7] = odd[:, 7] - (odd.sum(axis=1) % 2) + 1
    # Non-integral small vectors (the reference leg).
    reals = rng.uniform(-1.9, 1.9, size=(N // 4, 8)).astype(np.float64)

    vecs = np.concatenate([ints, odd, reals], axis=0)

    root_index = []
    for v in vecs:
        root_index.append(int(codec.root_index([float(c) for c in v])))

    x = torch.tensor(vecs, dtype=torch.float32)
    q = nearest_e8(x).to(torch.float64).numpy()

    vq = ResidualE8LatticeVQ(E8LatticeResidualConfig())
    with torch.no_grad():
        out = vq(x)
    # forward returns dict[str, Tensor] — "quantized" [..., 8], "indices" [..., L, 8]
    # (e8_lattice_protocol.py:243-264, :332-345).
    recon_t = out["quantized"]
    indices = out["indices"]  # [N, L, 8] half-step integer codes
    levels = int(indices.shape[1])

    # The protocol's adaptive stop is BATCH-WIDE (`torch.all(...)`,
    # e8_lattice_protocol.py:310-315), so the emitted L is a property of the
    # batch, not of a vector. The port stops per-vector. To compare like for
    # like, re-run the first 32 vectors each as a batch of one and record the
    # per-vector level count the estate produces under that framing.
    per_vec_levels = []
    per_vec_codes = []
    per_vec_recon = []
    for i in range(min(32, vecs.shape[0])):
        with torch.no_grad():
            single = vq(x[i : i + 1])
        per_vec_levels.append(int(single["indices"].shape[1]))
        per_vec_codes.append([[int(c) for c in row] for row in single["indices"][0].tolist()])
        per_vec_recon.append([float(c) for c in single["quantized"][0].to(torch.float64).tolist()])

    body = {
        "roots": [[float(c) for c in row] for row in roots.numpy().tolist()],
        "vectors": [[float(c) for c in row] for row in vecs.tolist()],
        "root_index": root_index,
        "nearest_e8": [[float(c) for c in row] for row in q.tolist()],
        "ladder": {
            "level_scales": [float(s) for s in vq.level_scales.tolist()],
            "level_scales_used": [
                float(s) for s in vq.level_scales.clamp(min=1e-6).to(torch.float64).tolist()
            ],
            "levels": levels,
            "recon": [[float(c) for c in row] for row in recon_t.to(torch.float64).numpy().tolist()],
            "codes": [[[int(c) for c in row] for row in per_vec] for per_vec in indices.tolist()],
            "per_vector_levels": per_vec_levels,
            "per_vector_codes": per_vec_codes,
            "per_vector_recon": per_vec_recon,
        },
        "config": {
            "max_levels": int(E8LatticeResidualConfig().max_levels),
            "min_levels": int(E8LatticeResidualConfig().min_levels),
            "initial_scale": float(E8LatticeResidualConfig().initial_scale),
            "decay": float(E8LatticeResidualConfig().decay),
            "residual_threshold": float(E8LatticeResidualConfig().residual_threshold),
        },
    }
    with open(out_path, "w") as fh:
        json.dump(body, fh)
    print(f"wrote {out_path}: {len(vecs)} vectors, ladder levels={levels}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
