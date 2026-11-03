#!/usr/bin/env python3
"""gen-estate-seed-vectors.py — golden vectors for the JS port of the estate stream.

The fixture this writes (tools/estate-seed-vectors.json) is the ONLY thing that
makes js/seed-stream.js a PORT rather than an homage: every value comes from
importing the real `kagami.core.omni.prng.SeededWordStream` out of the LIVE kagami
checkout (default /Users/schizodactyl/projects/kagami, override --repo) and running
it here. kagami is read-only for this lane; nothing in that tree is modified, and
this file records the checkout's HEAD and the sha256 of the module it imported, so
a reader can tell which generation of the law the browser is pinned against.

Float leaves are written TWICE: as `repr()` (Python 3 guarantees the shortest
round-tripping decimal, so JSON.parse lands on the identical IEEE double) and as
the 8-byte big-endian bit pattern in hex, which is what the harness compares --
decimal agreement is a nice property, bit agreement is the claim.

    python3 tools/gen-estate-seed-vectors.py            # writes the fixture
    python3 tools/gen-estate-seed-vectors.py --print    # to stdout, no write

Determinism of the fixture itself: every input is a literal or comes from the
seeded stream, so re-running at the same kagami HEAD and interpreter writes the
same bytes apart from the provenance block (timestamp, git HEAD, python version).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMOS = HERE.parent
OUT = HERE / "estate-seed-vectors.json"
DEFAULT_REPO = Path("/Users/schizodactyl/projects/kagami")

SEED = "e8-omnibus-1102"


def load_stream(repo: Path):
    pkg = repo / "packages"
    if not pkg.is_dir():
        raise SystemExit(f"no kagami packages dir at {pkg} -- pass --repo or run where the checkout lives")
    sys.path.insert(0, str(pkg))
    from kagami.core.omni.prng import SeededWordStream, _canonical_seed_bytes  # noqa: PLC0415
    return SeededWordStream, _canonical_seed_bytes


def head_of(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=20).stdout.strip() or "unknown"
    except Exception as exc:  # noqa: BLE001 - provenance, not correctness
        return f"error:{type(exc).__name__}"


def bits(x: float) -> str:
    import struct
    return struct.pack(">d", x).hex()


def refusal(fn, *a, **kw):
    """Return the exception CLASS name and its message, or None if no raise."""
    try:
        fn(*a, **kw)
    except BaseException as exc:  # noqa: BLE001 - this is the point of the probe
        return {"raises": type(exc).__name__, "message": str(exc)}
    return {"raises": None, "message": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(DEFAULT_REPO), help="live kagami checkout (read-only)")
    ap.add_argument("--print", dest="to_stdout", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    S, csb = load_stream(repo)
    prng_path = repo / "packages/kagami/core/omni/prng.py"

    doc: dict = {
        "schema": "v7-zke8-omnibus/estate-seed-vectors/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "tools/gen-estate-seed-vectors.py",
        "command": " ".join(sys.argv),
        "authority": {
            "module": "kagami.core.omni.prng",
            "imported_from": str(prng_path),
            "module_sha256": hashlib.sha256(prng_path.read_bytes()).hexdigest(),
            "kagami_head": head_of(repo),
            "kagami_readonly": True,
        },
        "interpreter": {
            "python": platform.python_version(),
            "executable": sys.executable,
            "platform": platform.platform(),
        },
    }

    doc["prefix"] = {
        "str:{}".format(SEED): csb(SEED).hex(),
        "str:": csb("").hex(),
        "str:unicode": csb("é🦋").hex(),
        "int:0": csb(0).hex(),
        "int:1": csb(1).hex(),
        "int:255": csb(255).hex(),
        "int:256": csb(256).hex(),
        "int:65536": csb(65536).hex(),
        "bytes:abc": csb(b"abc").hex(),
    }

    s = S(SEED)
    doc["words24"] = [str(s._word()) for _ in range(24)]  # noqa: SLF001

    s = S(SEED)
    widths = [1, 2, 7, 8, 16, 31, 32, 53, 63, 64, 65, 96, 127, 128, 129, 192]
    doc["getrandbits"] = [{"k": k, "value": str(s.getrandbits(k))} for k in widths]

    s = S(SEED)
    doc["random12"] = []
    s = S(SEED)
    for _ in range(12):
        r = s.random()
        doc["random12"].append({"repr": repr(r), "bits": bits(r)})

    s = S(SEED)
    doc["randint"] = []
    for a, b in [(-1, 1), (0, 10), (-5000, 5000), (1, 240), (0, 255), (5, 5), (-1000000, 1000000)]:
        v = s.randint(a, b)
        doc["randint"].append({"a": a, "b": b, "value": v})

    s = S(SEED)
    doc["randrange"] = []
    for spec in [(10,), (2, 10), (0, 100, 7), (1, 2), (0, 1, 3), (-5, 5, 2)]:
        doc["randrange"].append({"args": list(spec), "value": s.randrange(*spec)})

    pop = list("abcdefghijklmnopqrstuvwxyz")
    s = S(SEED)
    doc["choice"] = [s.choice(pop) for _ in range(16)]
    s = S(SEED)
    doc["sample"] = [{"k": k, "value": s.sample(pop, k)} for k in (0, 1, 3, 8, 26)]

    # The carrier-field law of js/seed-stream.js:fieldFromStream, echoed here so
    # the eight lane coefficients are compared cross-language, not just the stream.
    SPATIAL_MAX, TEMPORAL_MAX, TAU = 2.75, 1.6, 6.283185307179586
    s = S(SEED)
    lanes = []
    for _ in range(8):
        fx = -SPATIAL_MAX + s.random() * (2 * SPATIAL_MAX)
        fy = -SPATIAL_MAX + s.random() * (2 * SPATIAL_MAX)
        phi = -0.5 + s.random() * 1.0
        omega = (-TEMPORAL_MAX + s.random() * (2 * TEMPORAL_MAX)) / TAU
        lanes.append({"fx": bits(fx), "fy": bits(fy), "phi": bits(phi), "omega": bits(omega)})
    doc["lanes"] = lanes

    doc["refusals"] = {
        "none_seed": refusal(S, None),
        "bool_seed": refusal(S, True),
        "negative_seed": refusal(S, -1),
        "float_seed": refusal(S, 1.5),
        "negative_k": refusal(S(SEED).getrandbits, -1),
        "randrange_step_zero": refusal(S(SEED).randrange, 0, 10, 0),
        "randint_empty": refusal(S(SEED).randint, 5, 1),
        "choice_empty": refusal(S(SEED).choice, []),
        "sample_too_big": refusal(S(SEED).sample, [1, 2], 3),
        "sample_negative": refusal(S(SEED).sample, [1, 2], -1),
    }

    print(json.dumps(doc, indent=2, sort_keys=True))
    if not args.to_stdout:
        OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print(f"\n# wrote {OUT} ({OUT.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
