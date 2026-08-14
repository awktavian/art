# Vendored files

Cross-repo copies. Canonical source wins every conflict; edit upstream, re-copy here.

| File | Vendored from | Source commit | Date | Sync policy |
|---|---|---|---|---|
| `scripts/download_images.py` | `tim/wardrobe/scripts/download_images.py` (same repo) | `art@5cecde8` | 2026-04-01 (copied in `art@007d128`, 2026-04-07) | manual re-copy |

Files are kept byte-identical with the canonical copies so exact-dup detection
(`sha256` equality) remains a valid sync check. If a v2-specific change is
ever needed, fork the file out of this manifest.
