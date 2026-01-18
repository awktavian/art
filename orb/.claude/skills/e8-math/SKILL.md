# E8 Math Skill

Mathematical foundations for the hierarchy. E8 lattice, octonions, Fano plane.

## E8 Lattice

240 roots, 8D optimal sphere packing. Used for quantization.

```python
from kagami_math.e8_lattice_quantizer import nearest_e8

quantized = nearest_e8(x)  # Nearest lattice point
```

## Octonions

8D normed division algebra. Non-associative but alternative.

```python
from kagami_math.octonions import OctonionManifold, octonion_mul

product = octonion_mul(v1, v2)
```

## Fano Plane

7 lines, 7 points. Defines octonion multiplication.

```python
from kagami_math.fano_plane import FANO_LINES, get_fano_line_for_pair

# FANO_LINES = [(1,2,3), (1,4,5), (1,7,6), (2,4,6), (2,5,7), (3,4,7), (3,6,5)]
line = get_fano_line_for_pair(1, 2)  # Returns (1, 2, 3)
```

## Key Files

| File | Purpose |
|------|---------|
| `kagami_math/e8_lattice_quantizer.py` | E8 quantization |
| `kagami_math/octonions/` | Octonion operations |
| `kagami_math/fano_plane.py` | Fano plane structure |
